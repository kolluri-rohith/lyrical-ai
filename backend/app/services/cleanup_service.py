"""Periodic cleanup of old media and stray intermediate files.

Lyrics stay in the database; only the bulky files are removed. Once an upload
is gone the job simply reports `mediaAvailable: false`.
"""

import asyncio
import time
from datetime import timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionLocal
from app.models import TERMINAL_STATUSES, TranscriptionJob
from app.utils import storage
from app.utils.time import utcnow

logger = get_logger("cleanup")

# Intermediate files are deleted by the pipeline; anything this old was orphaned by a crash.
ORPHAN_MAX_AGE_SECONDS = 6 * 3600
INTERMEDIATE_DIRECTORIES = ("audio", "vocals", "temp")


def cleanup_old_files() -> int:
    """Delete expired uploads and orphaned intermediates. Returns files removed."""
    settings = get_settings()
    removed = 0

    cutoff = utcnow() - timedelta(hours=settings.file_retention_hours)
    with SessionLocal() as db:
        expired = db.scalars(
            select(TranscriptionJob.stored_filename).where(
                TranscriptionJob.status.in_(TERMINAL_STATUSES),
                TranscriptionJob.completed_at < cutoff,
            )
        ).all()
        known_uploads = set(db.scalars(select(TranscriptionJob.stored_filename)).all())

    for stored_filename in expired:
        path = storage.upload_path(stored_filename)
        if path.is_file():
            storage.remove_file(path)
            removed += 1

    orphan_cutoff = time.time() - ORPHAN_MAX_AGE_SECONDS
    for name in INTERMEDIATE_DIRECTORIES:
        for path in storage.storage_dir(name).iterdir():
            if path.is_file() and path.name != ".gitkeep" and path.stat().st_mtime < orphan_cutoff:
                storage.remove_file(path)
                removed += 1
    # Uploads whose job row no longer exists (e.g. deleted while the file was locked).
    for path in storage.storage_dir("uploads").iterdir():
        if (
            path.is_file()
            and path.name != ".gitkeep"
            and path.name not in known_uploads
            and path.stat().st_mtime < orphan_cutoff
        ):
            storage.remove_file(path)
            removed += 1

    if removed:
        logger.info("Cleanup removed %d file(s)", removed)
    return removed


async def cleanup_loop() -> None:
    interval = get_settings().cleanup_interval_minutes * 60
    while True:
        try:
            await asyncio.to_thread(cleanup_old_files)
        except Exception:
            logger.exception("Cleanup run failed")
        await asyncio.sleep(interval)
