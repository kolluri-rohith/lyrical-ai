"""Map ORM objects to API response schemas."""

from sqlalchemy.orm import Session

from app.models import TranscriptionJob
from app.schemas.transcription import (
    JobDetailResponse,
    JobStatusResponse,
    JobSummaryResponse,
    SegmentResponse,
)
from app.services.job_queue import queue_position
from app.services.language_service import language_name
from app.utils import storage
from app.utils.time import as_utc

PREVIEW_CHARS = 140


def _utc(value):
    return as_utc(value) if value is not None else None


def _base_fields(job: TranscriptionJob) -> dict:
    return {
        "job_id": job.id,
        "original_filename": job.original_filename,
        "file_type": job.file_type,
        "file_size": job.file_size,
        "requested_language": job.requested_language,
        "detected_language": job.detected_language,
        "status": job.status,
        "duration": job.duration,
        "created_at": _utc(job.created_at),
        "completed_at": _utc(job.completed_at),
        "error_message": job.error_message,
    }


def to_status(db: Session, job: TranscriptionJob) -> JobStatusResponse:
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        file_type=job.file_type,
        transcription_progress=job.transcription_progress,
        queue_position=queue_position(db, job),
        detected_language=job.detected_language,
        warning=job.warning,
        error_message=job.error_message,
        created_at=_utc(job.created_at),
        started_at=_utc(job.started_at),
        completed_at=_utc(job.completed_at),
    )


def to_summary(job: TranscriptionJob) -> JobSummaryResponse:
    preview = None
    if job.result is not None:
        text = " / ".join(job.result.full_text.splitlines())
        preview = text if len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS].rstrip() + "…"
    return JobSummaryResponse(**_base_fields(job), preview=preview)


def to_detail(job: TranscriptionJob) -> JobDetailResponse:
    result = job.result
    return JobDetailResponse(
        **_base_fields(job),
        language_name=language_name(job.detected_language),
        warning=job.warning,
        media_available=storage.upload_path(job.stored_filename).is_file(),
        full_text=result.full_text if result else None,
        model_name=result.model_name if result else None,
        device=result.device if result else None,
        processing_time=result.processing_time if result else None,
        segments=[
            SegmentResponse(
                index=segment.sequence_number,
                start=segment.start_time,
                end=segment.end_time,
                text=segment.text,
            )
            for segment in job.segments
        ],
    )
