from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession
from app.core.config import APP_VERSION, get_settings
from app.core.logging import get_logger
from app.schemas.system import ConfigResponse, HealthResponse, LanguageResponse, ModelsLoaded
from app.services.language_service import SUPPORTED_LANGUAGES
from app.services.vocal_separation_service import vocal_separation_service
from app.services.whisper_service import whisper_service
from app.utils.device import resolve_device
from app.utils.ffmpeg import ffmpeg_available
from app.utils.files import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS

logger = get_logger("health")
router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description="Reports database connectivity, FFmpeg availability and model state.",
)
def health(db: DbSession) -> HealthResponse:
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        logger.exception("Database health check failed")
        database = "error"

    ffmpeg = ffmpeg_available()
    return HealthResponse(
        status="ok" if database == "ok" and ffmpeg else "degraded",
        version=APP_VERSION,
        database=database,
        ffmpeg=ffmpeg,
        device=whisper_service.device or resolve_device(),
        whisper_model=get_settings().whisper_model,
        models_loaded=ModelsLoaded(
            whisper=whisper_service.is_loaded, demucs=vocal_separation_service.is_loaded
        ),
    )


@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="Public upload limits and supported languages",
)
def public_config() -> ConfigResponse:
    settings = get_settings()
    return ConfigResponse(
        max_file_size_mb=settings.max_file_size_mb,
        max_duration_minutes=settings.max_duration_minutes,
        languages=[
            LanguageResponse(code=lang.code, name=lang.name, native_name=lang.native_name)
            for lang in SUPPORTED_LANGUAGES.values()
        ],
        audio_extensions=sorted(AUDIO_EXTENSIONS),
        video_extensions=sorted(VIDEO_EXTENSIONS),
    )
