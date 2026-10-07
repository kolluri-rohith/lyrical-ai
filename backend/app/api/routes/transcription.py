"""Create a transcription job, follow its progress, fetch and export the lyrics."""

import shutil
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.api import serializers
from app.api.deps import CurrentCaller, DbSession, OwnedJob, load_job
from app.core.config import get_settings
from app.core.exceptions import (
    AppError,
    ConflictError,
    FileTooLargeError,
    InsufficientStorageError,
    NotFoundError,
)
from app.core.logging import get_logger
from app.models import JobStatus, TranscriptionJob
from app.schemas.base import ErrorResponse
from app.schemas.transcription import JobCreatedResponse, JobDetailResponse, JobStatusResponse
from app.services import lyrics_service
from app.services.job_queue import job_queue
from app.services.language_service import AUTO_LANGUAGE, resolve_request
from app.utils import storage
from app.utils.files import classify_upload, download_basename, file_extension, sanitize_filename

logger = get_logger("api.transcription")
router = APIRouter(prefix="/transcriptions", tags=["Transcriptions"])

COPY_CHUNK_BYTES = 1024 * 1024
MEDIA_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".mkv": "video/x-matroska",
}


def _store_upload(file: UploadFile, stored_filename: str) -> int:
    """Copy the upload into storage, enforcing the size limit. Returns bytes written."""
    limit = get_settings().max_file_size_bytes
    destination = storage.upload_path(stored_filename)
    written = 0
    try:
        with destination.open("wb") as target:
            while chunk := file.file.read(COPY_CHUNK_BYTES):
                written += len(chunk)
                if written > limit:
                    raise FileTooLargeError(
                        f"The file is too large. The maximum size is "
                        f"{get_settings().max_file_size_mb} MB."
                    )
                target.write(chunk)
    except BaseException:
        storage.remove_file(destination)
        raise
    if written == 0:
        storage.remove_file(destination)
        raise AppError("The uploaded file is empty.", code="EMPTY_FILE")
    return written


@router.post(
    "",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload audio/video and start a transcription",
    description=(
        "Accepts an audio (MP3, WAV, M4A, AAC, FLAC) or video (MP4, MOV, MKV) file and "
        "returns immediately with a job id in the `QUEUED` state. Processing happens in "
        "the background; poll `/api/transcriptions/{jobId}/status`."
    ),
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        507: {"model": ErrorResponse},
    },
)
def create_transcription(
    db: DbSession,
    caller: CurrentCaller,
    file: Annotated[UploadFile, File(description="Audio or video file")],
    language: Annotated[
        str,
        Form(
            description=(
                "`auto`, or a language code or name (`en`, `hi`, `te`, `Hindi`, ...). "
                "Anything other than `auto` is transcribed strictly in that language."
            )
        ),
    ] = AUTO_LANGUAGE,
) -> JobCreatedResponse:
    settings = get_settings()
    language = resolve_request(language)
    if language is None:
        raise AppError("Unsupported language selection.", code="UNSUPPORTED_LANGUAGE")

    original_filename = sanitize_filename(file.filename)
    file_type, extension = classify_upload(original_filename, file.content_type)

    if storage.free_disk_mb() < settings.min_free_disk_mb:
        logger.error("Upload rejected: less than %d MB of free disk", settings.min_free_disk_mb)
        raise InsufficientStorageError(
            "The server is low on storage right now. Please try again later."
        )

    job_id = str(uuid.uuid4())
    stored_filename = f"{job_id}{extension}"
    file_size = _store_upload(file, stored_filename)

    job = TranscriptionJob(
        id=job_id,
        user_id=caller.user.id if caller.user else None,
        client_id=None if caller.user else caller.client_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_type=file_type,
        file_size=file_size,
        requested_language=language,
        status=JobStatus.QUEUED.value,
    )
    try:
        db.add(job)
        db.commit()
    except Exception:
        storage.remove_file(storage.upload_path(stored_filename))
        raise

    job_queue.submit(job.id)
    logger.info(
        "job=%s stage=QUEUED type=%s size=%d language=%s",
        job.id, file_type, file_size, language,
    )
    return JobCreatedResponse(job_id=job.id, status=JobStatus.QUEUED, created_at=job.created_at)


@router.get(
    "/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Current processing stage of a job",
    responses={404: {"model": ErrorResponse}},
)
def get_status(job: OwnedJob, db: DbSession) -> JobStatusResponse:
    return serializers.to_status(db, job)


@router.get(
    "/{job_id}",
    response_model=JobDetailResponse,
    summary="Job details and, once completed, the timestamped lyrics",
    responses={404: {"model": ErrorResponse}},
)
def get_transcription(job: OwnedJob) -> JobDetailResponse:
    return serializers.to_detail(job)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job, its lyrics and its files",
    responses={404: {"model": ErrorResponse}},
)
def delete_transcription(job: OwnedJob, db: DbSession) -> Response:
    job_id, stored_filename = job.id, job.stored_filename
    db.delete(job)
    db.commit()
    # If the worker is mid-job it notices the missing row and cleans up after itself.
    storage.remove_file(storage.upload_path(stored_filename))
    logger.info("job=%s deleted", job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _completed_lines(job: TranscriptionJob) -> list[lyrics_service.LyricSegment]:
    if job.status != JobStatus.COMPLETED.value:
        raise ConflictError("The lyrics are not ready yet.", code="NOT_READY")
    return [
        lyrics_service.LyricSegment(segment.start_time, segment.end_time, segment.text)
        for segment in job.segments
    ]


def _attachment(content: str, media_type: str, job: TranscriptionJob, extension: str) -> Response:
    filename = f"{download_basename(job.original_filename)}.{extension}"
    return Response(
        content=content.encode("utf-8"),
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{job_id}/download/txt",
    summary="Download the lyrics as plain text",
    response_class=Response,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def download_txt(
    job: OwnedJob,
    timestamps: Annotated[bool, Query(description="Prefix each line with [mm:ss]")] = False,
) -> Response:
    content = lyrics_service.to_txt(_completed_lines(job), timestamps=timestamps)
    return _attachment(content, "text/plain", job, "txt")


@router.get(
    "/{job_id}/download/srt",
    summary="Download the lyrics as SubRip subtitles",
    response_class=Response,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def download_srt(job: OwnedJob) -> Response:
    return _attachment(lyrics_service.to_srt(_completed_lines(job)), "application/x-subrip", job, "srt")


@router.get(
    "/{job_id}/download/vtt",
    summary="Download the lyrics as WebVTT subtitles",
    response_class=Response,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def download_vtt(job: OwnedJob) -> Response:
    return _attachment(lyrics_service.to_vtt(_completed_lines(job)), "text/vtt", job, "vtt")


@router.get(
    "/{job_id}/media",
    summary="Stream the original upload for playback",
    description=(
        "Supports HTTP range requests. Media elements cannot send headers, so this "
        "endpoint is keyed by the unguessable job id alone."
    ),
    response_class=FileResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_media(job_id: str, db: DbSession) -> FileResponse:
    job = load_job(db, job_id)
    path = storage.upload_path(job.stored_filename)
    if not path.is_file():
        raise NotFoundError("The media for this transcription is no longer available.")
    media_type = MEDIA_TYPES.get(file_extension(job.stored_filename), "application/octet-stream")
    return FileResponse(path, media_type=media_type, content_disposition_type="inline")
