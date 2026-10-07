"""The transcription pipeline: runs one job from uploaded file to stored lyrics.

    validate -> (video: pick the audio track) -> preprocess -> transcribe
             -> post-process -> save

Transcription runs on one of two backends (TRANSCRIPTION_BACKEND):

    cloud : the audio is sent to an OpenAI-compatible Whisper API; no model is loaded
    local : separate vocals (Demucs) -> detect language -> transcribe (Whisper)

Every stage change is written to the database, so the status endpoint always
reports what the worker is really doing.
"""

import errno
import time
from dataclasses import dataclass
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
from app.services.cloud_transcription_service import cloud_transcription_service
from app.services.language_service import AUTO_LANGUAGE, resolve_language
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
UNSUPPORTED_LANGUAGE_WARNING = (
    "The language detected in this file is not one LyricalAI supports, so the lyrics "
    "may be wrong. Choose the song's language yourself and try again."
)
TOO_LARGE_FOR_API_MESSAGE = (
    "This file is too long for the transcription service. Please try a shorter file."
)
# Write transcription progress to the database at most every N percent.
PROGRESS_STEP_PERCENT = 2


class JobCancelled(Exception):
    """The job was deleted while it was being processed."""


@dataclass(frozen=True)
class _Transcript:
    segments: list
    model_name: str
    device: str | None


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


def _encode_for_api(job_id: str, upload: Path, stream: int) -> Path:
    """Audio file to send to the API: lossless FLAC, or MP3 if that is over the limit."""
    limit = get_settings().openai_max_upload_bytes
    flac = audio_service.encode_for_api(
        upload, storage.temp_path(job_id, ".api.flac"), stream=stream
    )
    if flac.stat().st_size <= limit:
        return flac
    logger.info("job=%s FLAC is over the API upload limit; compressing to MP3", job_id)
    mp3 = audio_service.compress_for_api(flac, storage.temp_path(job_id, ".api.mp3"))
    storage.remove_file(flac)
    if mp3.stat().st_size > limit:
        raise PipelineError(TOO_LARGE_FOR_API_MESSAGE)
    return mp3


def _transcribe_in_cloud(
    job_id: str, upload: Path, stream: int, language: str | None
) -> _Transcript:
    """Send the audio to the cloud API. `language` is None only for Auto Detect."""
    api_audio = _encode_for_api(job_id, upload, stream)

    # An explicit choice is final: it is passed to the API as its `language`
    # parameter, which switches the API's own language detection off for this job.
    _set_stage(job_id, JobStatus.TRANSCRIBING, detected_language=language)
    result = cloud_transcription_service.transcribe(api_audio, language)

    if language is None:
        detected = resolve_language(result.language)
        logger.info("job=%s detected language=%s (%s)", job_id, detected, result.language)
        if detected is None:
            _update_job(job_id, warning=UNSUPPORTED_LANGUAGE_WARNING)
        else:
            _update_job(job_id, detected_language=detected)

    return _Transcript(
        segments=result.segments,
        model_name=cloud_transcription_service.model_name,
        device=cloud_transcription_service.device,
    )


def _transcribe_locally(
    job_id: str, upload: Path, stream: int, language: str | None
) -> _Transcript:
    """Demucs + Whisper in this process. `language` is None only for Auto Detect."""
    mix_path = audio_service.normalize_for_separation(
        upload, storage.audio_path(job_id), stream=stream
    )

    _set_stage(job_id, JobStatus.SEPARATING_VOCALS)
    voice_path, warning = _separate_vocals(job_id, mix_path)
    if warning:
        _update_job(job_id, warning=warning)
    whisper_input = audio_service.convert_for_whisper(
        voice_path, storage.temp_path(job_id, ".whisper.wav")
    )

    _set_stage(job_id, JobStatus.DETECTING_LANGUAGE)
    audio = whisper_service.load_audio(whisper_input)
    if language is None:
        language, probability = whisper_service.detect_language(audio)
        logger.info("job=%s detected language=%s (p=%.2f)", job_id, language, probability)
    _update_job(job_id, detected_language=language)

    _set_stage(job_id, JobStatus.TRANSCRIBING, transcription_progress=0)
    segments = whisper_service.transcribe(
        audio, language, on_progress=_make_progress_reporter(job_id)
    )
    return _Transcript(
        segments=segments,
        model_name=whisper_service.model_name,
        device=whisper_service.device,
    )


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

    # --- Pick the audio track (video only) ---------------------------------
    explicit_language = None if requested_language == AUTO_LANGUAGE else requested_language
    stream = 0
    if declared_type == "video":
        _set_stage(job_id, JobStatus.EXTRACTING_AUDIO)
        track = video_service.select_audio_stream(info, explicit_language)
        stream = track.position
        logger.info(
            "job=%s audio track %d of %d: codec=%s rate=%d channels=%d language=%s",
            job_id, track.position + 1, len(info.audio_streams),
            track.codec, track.sample_rate, track.channels, track.language,
        )

    # --- Preprocess ---------------------------------------------------------
    _set_stage(job_id, JobStatus.PREPROCESSING)
    audio_service.ensure_not_silent(upload, stream=stream)

    # --- Transcribe ---------------------------------------------------------
    if settings.uses_local_models:
        transcript = _transcribe_locally(job_id, upload, stream, explicit_language)
    else:
        transcript = _transcribe_in_cloud(job_id, upload, stream, explicit_language)
    raw_segments = transcript.segments

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
            model_name=transcript.model_name,
            device=transcript.device,
            processing_time=processing_time,
        )
        job.status = JobStatus.COMPLETED.value
        job.completed_at = utcnow()
        db.commit()

    logger.info(
        "job=%s stage=COMPLETED model=%s device=%s duration=%.1fs processing_time=%.1fs lines=%d",
        job_id, transcript.model_name, transcript.device,
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
