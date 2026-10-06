from app.schemas.base import CamelModel


class ModelsLoaded(CamelModel):
    whisper: bool
    demucs: bool


class HealthResponse(CamelModel):
    status: str
    version: str
    database: str
    ffmpeg: bool
    device: str
    whisper_model: str
    models_loaded: ModelsLoaded


class LanguageResponse(CamelModel):
    code: str
    name: str
    native_name: str


class ConfigResponse(CamelModel):
    max_file_size_mb: int
    max_duration_minutes: int
    languages: list[LanguageResponse]
    audio_extensions: list[str]
    video_extensions: list[str]
