"""The transcription pipeline: runs one job from uploaded file to stored lyrics.

    validate -> (video: extract audio) -> preprocess -> separate vocals
             -> detect language -> transcribe -> post-process -> save

Every stage change is written to the database, so the status endpoint always
reports what the worker is really doing.
"""

import errno
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import PipelineError
from app.core.logging import get_logger
from app.database.session import SessionLocal
from app.models import (
    JobStatus,
    TranscriptionJob,
    TranscriptionResult,
    TranscriptionSegment,
)
from app.services import audio_service, lyrics_service, video_service
from app.services.language_service import AUTO_LANGUAGE
from app.services.vocal_separation_service import vocal_separation_service
from app.services.whisper_service import whisper_service
from app.utils import storage
from app.utils.ffmpeg import probe
from app.utils.time import utcnow

logger = get_logger("pipeline")

GENERIC_FAILURE_MESSAGE = (
    "Something went wrong while processing this file. Please try again."
)
SEPARATION_FALLBACK_WARNING = (
    "Vocal separation was not available for this file, so the lyrics were transcribed "
    "from the full mix. Accuracy may be lower than usual."
)
# Write transcription progress to the database at most every N percent.
PROGRESS_STEP_PERCENT = 2


class JobCancelled(Exception):
    """The job was deleted while it was being processed."""


def _update_job(job_id: str, **fields) -> None:
    with SessionLocal() as db:
        job = db.get(TranscriptionJob, job_id)
        if job is None:
            raise JobCancelled(job_id)
        for name, value in fields.items():
            setattr(job, name, value)
        db.commit()


def _set_stage(job_id: str, status: JobStatus, **fields) -> None:
    logger.info("job=%s stage=%s", job_id, status.value)
    _update_job(job_id, status=status.value, **fields)


def _make_progress_reporter(job_id: str):
    last_reported = -PROGRESS_STEP_PERCENT

    def report(fraction: float) -> None:
        nonlocal last_reported
        percent = int(fraction * 100)
        if percent - last_reported >= PROGRESS_STEP_PERCENT:
            last_reported = percent
            _update_job(job_id, transcription_progress=percent)

    return report


def _separate_vocals(job_id: str, mix_path: Path) -> tuple[Path, str | None]:
    """Return (audio to transcribe, warning). Falls back to the mix if Demucs fails."""
    try:
        vocals = vocal_separation_service.separate_vocals(mix_path, storage.vocals_path(job_id))
        return vocals, None
    except Exception as exc:
        logger.exception("job=%s vocal separation failed", job_id)
        if not get_settings().enable_separation_fallback:
            raise PipelineError(
                "Vocal separation failed for this file. Please try again."
            ) from exc
        return mix_path, SEPARATION_FALLBACK_WARNING


def _run_pipeline(job_id: str, started: float) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        job = db.get(TranscriptionJob, job_id)
        if job is None:
            raise JobCancelled(job_id)
        upload = storage.upload_path(job.stored_filename)
        requested_language = job.requested_language
        declared_type = job.file_type

    # --- Validate -----------------------------------------------------------
    _set_stage(job_id, JobStatus.VALIDATING, started_at=utcnow())
    if not upload.is_file():
        raise PipelineError("The uploaded file is no longer available. Please upload it again.")
    info = probe(upload)
    if not info.has_audio:
        if declared_type == "video":
            raise PipelineError("This video has no audio track, so there is nothing to transcribe.")
        raise PipelineError("No audio could be found in this file.")
    if info.duration <= 0:
        raise PipelineError("The file is corrupt or is not a valid audio/video file.")
    if info.duration > settings.max_duration_seconds:
        raise PipelineError(
            f"This file is too long. The maximum length is {settings.max_duration_minutes} minutes."
        )
    _update_job(job_id, duration=round(info.duration, 3))

    # --- Extract audio (video only) ----------------------------------------
    source = upload
    if declared_type == "video":
        _set_stage(job_id, JobStatus.EXTRACTING_AUDIO)
        source = video_service.extract_audio(upload, storage.temp_path(job_id, ".extracted.wav"))

    # --- Preprocess ---------------------------------------------------------
    _set_stage(job_id, JobStatus.PREPROCESSING)
    audio_service.ensure_not_silent(source)
    mix_path = audio_service.normalize_for_separation(source, storage.audio_path(job_id))

    # --- Separate vocals ----------------------------------------------------
    _set_stage(job_id, JobStatus.SEPARATING_VOCALS)
    voice_path, warning = _separate_vocals(job_id, mix_path)
    if warning:
        _update_job(job_id, warning=warning)
    whisper_input = audio_service.convert_for_whisper(
        voice_path, storage.temp_path(job_id, ".whisper.wav")
    )

    # --- Detect language ----------------------------------------------------
    _set_stage(job_id, JobStatus.DETECTING_LANGUAGE)
    audio = whisper_service.load_audio(whisper_input)
    if requested_language == AUTO_LANGUAGE:
        language, probability = whisper_service.detect_language(audio)
        logger.info("job=%s detected language=%s (p=%.2f)", job_id, language, probability)
    else:
        language = requested_language
    _update_job(job_id, detected_language=language)

    # --- Transcribe ---------------------------------------------------------
    _set_stage(job_id, JobStatus.TRANSCRIBING, transcription_progress=0)
    raw_segments = whisper_service.transcribe(
        audio, language, on_progress=_make_progress_reporter(job_id)
    )

    # --- Post-process -------------------------------------------------------
    _set_stage(job_id, JobStatus.POST_PROCESSING, transcription_progress=100)
    lines = lyrics_service.post_process(raw_segments)
    if not lines:
        raise PipelineError(
            "No lyrics could be detected in this file. It may be instrumental or too noisy."
        )

    # --- Save ---------------------------------------------------------------
    processing_time = round(time.perf_counter() - started, 2)
    with SessionLocal() as db:
        job = db.get(TranscriptionJob, job_id)
        if job is None:
            raise JobCancelled(job_id)
        job.segments = [
            TranscriptionSegment(
                sequence_number=index, start_time=line.start, end_time=line.end, text=line.text
            )
            for index, line in enumerate(lines)
        ]
        job.result = TranscriptionResult(
            full_text=lyrics_service.build_full_text(lines),
            model_name=whisper_service.model_name,
            device=whisper_service.device,
            processing_time=processing_time,
        )
        job.status = JobStatus.COMPLETED.value
        job.completed_at = utcnow()
        db.commit()

    logger.info(
        "job=%s stage=COMPLETED model=%s device=%s duration=%.1fs processing_time=%.1fs lines=%d",
        job_id, whisper_service.model_name, whisper_service.device,
        info.duration, processing_time, len(lines),
    )


def _mark_failed(job_id: str, message: str) -> None:
    try:
        _update_job(
            job_id,
            status=JobStatus.FAILED.value,
            error_message=message,
            completed_at=utcnow(),
        )
    except JobCancelled:
        pass
    except Exception:
        logger.exception("job=%s could not be marked as failed", job_id)


def _discard_upload(job_id: str) -> None:
    """A failed or deleted job has no use for its upload any more."""
    for path in storage.storage_dir("uploads").glob(f"{job_id}.*"):
        storage.remove_file(path)


def process_job(job_id: str) -> None:
    """Entry point for the background worker. Never raises."""
    started = time.perf_counter()
    logger.info("job=%s started", job_id)
    try:
        _run_pipeline(job_id, started)
    except JobCancelled:
        logger.info("job=%s was deleted during processing", job_id)
        _discard_upload(job_id)
    except PipelineError as exc:
        logger.warning("job=%s stage=FAILED reason=%s", job_id, exc.user_message)
        _mark_failed(job_id, exc.user_message)
        _discard_upload(job_id)
    except Exception as exc:
        logger.exception("job=%s stage=FAILED unexpected error", job_id)
        if isinstance(exc, MemoryError):
            message = "The server ran out of memory on this file. Please try a shorter file."
        elif isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
            message = "The server ran out of disk space. Please try again later."
        else:
            message = GENERIC_FAILURE_MESSAGE
        _mark_failed(job_id, message)
        _discard_upload(job_id)
    finally:
        for path in storage.intermediate_paths(job_id):
            storage.remove_file(path)
