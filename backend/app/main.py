"""LyricalAI API: FastAPI application factory and lifecycle."""

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import api_router
from app.core.config import APP_NAME, APP_VERSION, get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.core.middleware import UploadSizeLimitMiddleware
from app.database.migrations import run_migrations
from app.services.cleanup_service import cleanup_loop
from app.services.job_queue import job_queue, preload_if_configured
from app.utils.ffmpeg import ffmpeg_available
from app.utils.storage import ensure_storage_dirs

logger = get_logger("app")

DESCRIPTION = """
Multilingual automatic lyric transcription.

Upload a song or a music video and LyricalAI extracts the audio (FFmpeg), isolates
the vocals (Demucs) and transcribes them into timestamped lyrics (Whisper) in
English, Hindi or Telugu.

Errors are always returned as `{"detail": "...", "code": "..."}`.
"""


def _configure_model_cache() -> None:
    """Point the model libraries at MODEL_CACHE_DIR so weights are downloaded once."""
    cache_dir = get_settings().model_cache_dir
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TORCH_HOME", str(cache_dir / "torch"))
    os.environ.setdefault("HF_HOME", str(cache_dir / "huggingface"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    _configure_model_cache()
    ensure_storage_dirs()

    if settings.jwt_secret_is_placeholder:
        logger.warning("JWT_SECRET_KEY is still a placeholder; set a long random value in .env")
    if not ffmpeg_available():
        logger.error("FFmpeg/ffprobe not found on PATH; uploads cannot be processed")

    await asyncio.to_thread(run_migrations)
    job_queue.start()
    await asyncio.to_thread(job_queue.recover)
    preload_if_configured()
    cleanup_task = asyncio.create_task(cleanup_loop())

    logger.info(
        "%s %s started (whisper=%s, device=%s, max upload=%d MB)",
        APP_NAME, APP_VERSION, settings.whisper_model, settings.device, settings.max_file_size_mb,
    )
    try:
        yield
    finally:
        cleanup_task.cancel()
        job_queue.stop()


def _error(status_code: int, detail: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail, "code": code})


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.detail, exc.code)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        field = ".".join(str(part) for part in first.get("loc", ())[1:])
        message = str(first.get("msg", "Invalid request")).removeprefix("Value error, ")
        detail = f"{field}: {message}" if field else message
        return _error(422, detail, "VALIDATION_ERROR")

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _error(exc.status_code, detail, f"HTTP_{exc.status_code}")

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Full details go to the log only; the client never sees a stack trace.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _error(500, "Something went wrong on our side. Please try again.", "INTERNAL_ERROR")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=f"{APP_NAME} API",
        version=APP_VERSION,
        description=DESCRIPTION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        UploadSizeLimitMiddleware,
        max_file_bytes=settings.max_file_size_bytes,
        max_file_mb=settings.max_file_size_mb,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Client-Id"],
        expose_headers=["Content-Disposition"],
    )

    _register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/docs", include_in_schema=False)
    def docs_redirect() -> RedirectResponse:
        return RedirectResponse("/api/docs")

    @app.get("/redoc", include_in_schema=False)
    def redoc_redirect() -> RedirectResponse:
        return RedirectResponse("/api/redoc")

    return app


app = create_app()
