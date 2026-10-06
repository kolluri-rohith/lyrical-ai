from datetime import datetime

from pydantic import Field

from app.models import JobStatus
from app.schemas.base import CamelModel


class JobCreatedResponse(CamelModel):
    job_id: str
    status: JobStatus
    created_at: datetime


class JobStatusResponse(CamelModel):
    job_id: str
    status: JobStatus
    file_type: str = Field(description='"audio" or "video"')
    transcription_progress: int | None = Field(
        default=None, description="0-100, real decoder progress while TRANSCRIBING"
    )
    queue_position: int | None = Field(
        default=None, description="Jobs that will run before this one while QUEUED"
    )
    detected_language: str | None = None
    warning: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SegmentResponse(CamelModel):
    index: int
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    text: str


class JobBase(CamelModel):
    job_id: str
    original_filename: str
    file_type: str
    file_size: int
    requested_language: str
    detected_language: str | None = None
    status: JobStatus
    duration: float | None = Field(default=None, description="Media duration in seconds")
    created_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None


class JobSummaryResponse(JobBase):
    preview: str | None = Field(default=None, description="First characters of the lyrics")


class JobListResponse(CamelModel):
    items: list[JobSummaryResponse]
    total: int


class JobDetailResponse(JobBase):
    language_name: str | None = None
    warning: str | None = None
    media_available: bool = False
    full_text: str | None = None
    model_name: str | None = None
    device: str | None = None
    processing_time: float | None = Field(default=None, description="Seconds spent processing")
    segments: list[SegmentResponse] = []
