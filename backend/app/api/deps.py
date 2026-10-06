"""Request dependencies: who is calling, and which jobs they may see.

Authentication is optional. A caller is identified by a JWT (registered user)
or, failing that, by the anonymous `X-Client-Id` their browser generated.
"""

import re
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, UnauthorizedError
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models import TranscriptionJob, User

_CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_JOB_ID_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

_bearer = HTTPBearer(auto_error=False, description="Optional JWT from /api/auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_optional_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User | None:
    if credentials is None:
        return None
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        # A token was sent but is invalid/expired: say so, so the client can drop it.
        raise UnauthorizedError("Your session has expired. Please log in again.")
    return user


def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise UnauthorizedError("Please log in to continue.")
    return user


@dataclass(frozen=True)
class Caller:
    user: User | None
    client_id: str | None

    def owns(self, job: TranscriptionJob) -> bool:
        if job.user_id is not None:
            return self.user is not None and self.user.id == job.user_id
        if job.client_id is not None:
            return self.client_id == job.client_id
        # Uploaded with no identity at all (e.g. curl): the unguessable job id is the key.
        return True


def get_caller(
    user: Annotated[User | None, Depends(get_optional_user)],
    x_client_id: Annotated[
        str | None,
        Header(description="Anonymous browser id used to scope history without an account"),
    ] = None,
) -> Caller:
    client_id = x_client_id if x_client_id and _CLIENT_ID_PATTERN.match(x_client_id) else None
    return Caller(user=user, client_id=client_id)


CurrentCaller = Annotated[Caller, Depends(get_caller)]


def load_job(db: Session, job_id: str) -> TranscriptionJob:
    job = db.get(TranscriptionJob, job_id) if _JOB_ID_PATTERN.match(job_id) else None
    if job is None:
        raise NotFoundError("Transcription not found.")
    return job


def get_owned_job(job_id: str, db: DbSession, caller: CurrentCaller) -> TranscriptionJob:
    job = load_job(db, job_id)
    if not caller.owns(job):
        # 404 rather than 403 so job ids cannot be probed.
        raise NotFoundError("Transcription not found.")
    return job


OwnedJob = Annotated[TranscriptionJob, Depends(get_owned_job)]
