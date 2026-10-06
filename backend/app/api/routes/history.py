from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api import serializers
from app.api.deps import CurrentCaller, DbSession
from app.models import TranscriptionJob
from app.schemas.transcription import JobListResponse

router = APIRouter(prefix="/transcriptions", tags=["History"])


@router.get(
    "",
    response_model=JobListResponse,
    summary="Previous transcriptions of the caller, newest first",
    description=(
        "Logged-in users see the jobs on their account; anonymous callers see the jobs "
        "created with their `X-Client-Id`."
    ),
)
def list_transcriptions(
    db: DbSession,
    caller: CurrentCaller,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobListResponse:
    if caller.user is not None:
        owner_filter = TranscriptionJob.user_id == caller.user.id
    elif caller.client_id is not None:
        owner_filter = (TranscriptionJob.user_id.is_(None)) & (
            TranscriptionJob.client_id == caller.client_id
        )
    else:
        return JobListResponse(items=[], total=0)

    total = db.scalar(select(func.count()).select_from(TranscriptionJob).where(owner_filter)) or 0
    jobs = db.scalars(
        select(TranscriptionJob)
        .where(owner_filter)
        .options(selectinload(TranscriptionJob.result))
        .order_by(TranscriptionJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return JobListResponse(items=[serializers.to_summary(job) for job in jobs], total=total)
