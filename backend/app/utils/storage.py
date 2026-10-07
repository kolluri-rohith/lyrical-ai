"""Storage layout helpers. Every path is derived from STORAGE_PATH and a job id."""

import shutil
from pathlib import Path

from app.core.config import get_settings

SUBDIRECTORIES = ("uploads", "audio", "vocals", "results", "temp")


def storage_root() -> Path:
    return get_settings().storage_path.resolve()


def storage_dir(name: str) -> Path:
    if name not in SUBDIRECTORIES:
        raise ValueError(f"Unknown storage directory: {name}")
    return storage_root() / name


def ensure_storage_dirs() -> None:
    for name in SUBDIRECTORIES:
        storage_dir(name).mkdir(parents=True, exist_ok=True)


def safe_join(directory: Path, filename: str) -> Path:
    """Join and refuse anything that would escape `directory`."""
    base = directory.resolve()
    candidate = (base / filename).resolve()
    if base != candidate.parent:
        raise ValueError("Path escapes the storage directory")
    return candidate


def upload_path(stored_filename: str) -> Path:
    return safe_join(storage_dir("uploads"), stored_filename)


def audio_path(job_id: str) -> Path:
    return safe_join(storage_dir("audio"), f"{job_id}.wav")


def vocals_path(job_id: str) -> Path:
    return safe_join(storage_dir("vocals"), f"{job_id}.wav")


def temp_path(job_id: str, suffix: str) -> Path:
    return safe_join(storage_dir("temp"), f"{job_id}{suffix}")


def remove_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def intermediate_paths(job_id: str) -> list[Path]:
    return [
        audio_path(job_id),
        vocals_path(job_id),
        temp_path(job_id, ".api.flac"),
        temp_path(job_id, ".api.mp3"),
        temp_path(job_id, ".whisper.wav"),
    ]


def free_disk_mb() -> float:
    return shutil.disk_usage(storage_root()).free / (1024 * 1024)
