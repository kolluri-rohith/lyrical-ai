"""Test setup: an isolated SQLite database and storage directory per test session."""

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="lyricalai-tests-"))

# Must be set before the application modules are imported.
os.environ.update(
    {
        "ENVIRONMENT": "test",
        "DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
        "STORAGE_PATH": str(_TMP / "storage"),
        "MODEL_CACHE_DIR": "",
        "MAX_FILE_SIZE_MB": "1",
        "MAX_DURATION_MINUTES": "1",
        "MIN_FREE_DISK_MB": "1",
        "DEVICE": "cpu",
        "PRELOAD_MODELS": "false",
        "ENABLE_SEPARATION_FALLBACK": "true",
        "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256",
        "CORS_ORIGINS": "http://localhost:5173",
    }
)

from fastapi.testclient import TestClient  # noqa: E402

from app.database.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import TranscriptionJob, User  # noqa: E402
from app.services.job_queue import job_queue  # noqa: E402
from app.utils import storage  # noqa: E402

CLIENT_A = {"X-Client-Id": "client-aaaaaaaa-0001"}
CLIENT_B = {"X-Client-Id": "client-bbbbbbbb-0002"}

requires_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    shutil.rmtree(_TMP, ignore_errors=True)


@pytest.fixture(autouse=True)
def clean_state(client, monkeypatch):
    """Empty tables before each test and keep uploads from reaching the real worker."""
    with SessionLocal() as db:
        for job in db.query(TranscriptionJob).all():
            db.delete(job)
        for user in db.query(User).all():
            db.delete(user)
        db.commit()
    for name in storage.SUBDIRECTORIES:
        for path in storage.storage_dir(name).iterdir():
            storage.remove_file(path)
    submitted: list[str] = []
    monkeypatch.setattr(job_queue, "submit", submitted.append)
    yield submitted


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture(scope="session")
def media_dir() -> Path:
    directory = _TMP / "media"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _ffmpeg(*arguments: str) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *arguments],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="session")
def tone_wav(media_dir) -> Path:
    """Three seconds of a 440 Hz tone."""
    path = media_dir / "tone.wav"
    _ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:duration=3", str(path))
    return path


@pytest.fixture(scope="session")
def silent_wav(media_dir) -> Path:
    path = media_dir / "silent.wav"
    _ffmpeg("-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "2", str(path))
    return path


@pytest.fixture(scope="session")
def video_mp4(media_dir) -> Path:
    """A short video with a tone as its audio track."""
    path = media_dir / "clip.mp4"
    _ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=3:size=160x120:rate=10",
        "-f", "lavfi", "-i", "sine=frequency=330:duration=3",
        "-c:v", "mpeg4", "-c:a", "aac", "-shortest", str(path),
    )
    return path


@pytest.fixture(scope="session")
def video_without_audio(media_dir) -> Path:
    path = media_dir / "mute.mp4"
    _ffmpeg(
        "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=10",
        "-c:v", "mpeg4", "-an", str(path),
    )
    return path


def upload(client, content: bytes, filename: str, content_type: str, **kwargs):
    """POST a file to the transcription endpoint."""
    headers = kwargs.pop("headers", CLIENT_A)
    data = {"language": kwargs.pop("language", "auto")}
    return client.post(
        "/api/transcriptions",
        files={"file": (filename, content, content_type)},
        data=data,
        headers=headers,
    )


def new_job_id() -> str:
    return str(uuid.uuid4())
