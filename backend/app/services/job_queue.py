"""In-process job worker.

One worker thread runs jobs one at a time, so only one FFmpeg process runs at once
and, with the local backend, a single copy of each model is shared.
"""

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.session import SessionLocal
from app.models import TERMINAL_STATUSES, JobStatus, TranscriptionJob
from app.services.transcription_service import process_job
from app.services.vocal_separation_service import vocal_separation_service
from app.services.whisper_service import whisper_service
from app.utils import storage
from app.utils.time import utcnow

logger = get_logger("queue")

INTERRUPTED_MESSAGE = (
    "Processing was interrupted because the server restarted. Please upload the file again."
)


class JobQueue:
    def __init__(self) -> None:
        self._executor: ThreadPoolExecutor | None = None

    def start(self) -> None:
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lyricalai-job")

    def stop(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None

    def submit(self, job_id: str) -> None:
        self.start()
        self._executor.submit(process_job, job_id)

    def preload_models(self) -> None:
        """Warm the models on the worker thread so the first job does not pay for it."""
        self.start()
        self._executor.submit(_load_models)

    def recover(self) -> None:
        """After a restart: fail jobs that were mid-flight, re-queue the ones still waiting."""
        with SessionLocal() as db:
            unfinished = db.scalars(
                select(TranscriptionJob)
                .where(TranscriptionJob.status.notin_(TERMINAL_STATUSES))
                .order_by(TranscriptionJob.created_at)
            ).all()
            requeue: list[str] = []
            for job in unfinished:
                waiting = job.status == JobStatus.QUEUED.value
                if waiting and storage.upload_path(job.stored_filename).is_file():
                    requeue.append(job.id)
                    continue
                job.status = JobStatus.FAILED.value
                job.error_message = INTERRUPTED_MESSAGE
                job.completed_at = utcnow()
                storage.remove_file(storage.upload_path(job.stored_filename))
            db.commit()

        for job_id in requeue:
            self.submit(job_id)
        if unfinished:
            logger.info(
                "Recovered %d unfinished job(s): %d re-queued, %d marked failed",
                len(unfinished), len(requeue), len(unfinished) - len(requeue),
            )


def _load_models() -> None:
    try:
        whisper_service.load()
        if get_settings().separates_vocals:
            vocal_separation_service.load()
    except Exception:
        logger.exception("Model preloading failed; models will be loaded on first use")


def queue_position(db, job: TranscriptionJob) -> int | None:
    """Number of jobs that will run before this one, or None once it has started."""
    if job.status != JobStatus.QUEUED.value:
        return None
    waiting_ahead = db.scalar(
        select(func.count())
        .select_from(TranscriptionJob)
        .where(
            TranscriptionJob.status == JobStatus.QUEUED.value,
            TranscriptionJob.created_at < job.created_at,
        )
    )
    running = db.scalar(
        select(func.count())
        .select_from(TranscriptionJob)
        .where(TranscriptionJob.status.notin_((JobStatus.QUEUED.value, *TERMINAL_STATUSES)))
    )
    return int(waiting_ahead or 0) + int(running or 0)


job_queue = JobQueue()


def preload_if_configured() -> None:
    settings = get_settings()
    # The cloud backend has no models to load.
    if settings.uses_local_models and settings.preload_models:
        job_queue.preload_models()
