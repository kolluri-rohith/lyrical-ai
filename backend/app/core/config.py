"""Application configuration, read once from environment variables / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

APP_NAME = "LyricalAI"
APP_VERSION = "1.0.0"

INSECURE_SECRET_PLACEHOLDERS = {"", "change_me", "change_me_to_a_long_random_string"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"

    # --- Database -----------------------------------------------------------
    # DATABASE_URL wins when set; otherwise the URL is built from POSTGRES_*.
    database_url: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "lyricalai"
    postgres_user: str = "lyricalai"
    postgres_password: str = "change_me"

    # --- Uploads / storage --------------------------------------------------
    storage_path: Path = Path("./storage")
    max_file_size_mb: int = 50
    max_duration_minutes: int = 15
    file_retention_hours: int = 72
    cleanup_interval_minutes: int = 60
    min_free_disk_mb: int = 500

    # --- Transcription ------------------------------------------------------
    # "cloud" sends the audio to an OpenAI-compatible API and loads no model, so the
    # backend fits in a small instance. "local" runs Demucs + Whisper in-process and
    # needs requirements-local.txt and several GB of RAM.
    transcription_backend: Literal["cloud", "local"] = "cloud"
    openai_api_key: str = ""
    # Any OpenAI-compatible endpoint works, e.g. https://api.groq.com/openai/v1
    openai_base_url: str = "https://api.openai.com/v1"
    # Must support response_format=verbose_json (segment timestamps), e.g. whisper-1.
    openai_transcription_model: str = "whisper-1"
    openai_timeout_seconds: int = 600
    openai_max_upload_mb: int = 25

    # --- Local AI models (TRANSCRIPTION_BACKEND=local only) -----------------
    whisper_model: Literal["tiny", "base", "small", "medium"] = "small"
    whisper_compute_type: str = "auto"
    whisper_beam_size: int = 5
    whisper_vad_filter: bool = True
    demucs_model: str = "htdemucs"
    device: Literal["auto", "cpu", "cuda"] = "auto"
    model_cache_dir: Path | None = None
    preload_models: bool = False
    enable_separation_fallback: bool = True
    ffmpeg_timeout_seconds: int = 600

    # --- API / security -----------------------------------------------------
    cors_origins: str = "http://localhost:5173"
    jwt_secret_key: str = "change_me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    @field_validator("database_url", mode="before")
    @classmethod
    def _strip_database_url(cls, value: str | None) -> str:
        return (value or "").strip()

    @field_validator("model_cache_dir", mode="before")
    @classmethod
    def _empty_cache_dir_is_unset(cls, value: str | Path | None) -> str | Path | None:
        # An empty MODEL_CACHE_DIR means "use the libraries' default cache".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @property
    def sqlalchemy_url(self) -> URL | str:
        if self.database_url:
            # Heroku-style scheme is not understood by SQLAlchemy 2.
            return self.database_url.replace("postgres://", "postgresql://", 1)
        return URL.create(
            "postgresql+psycopg2",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def uses_local_models(self) -> bool:
        return self.transcription_backend == "local"

    @property
    def openai_max_upload_bytes(self) -> int:
        return self.openai_max_upload_mb * 1024 * 1024

    @property
    def max_duration_seconds(self) -> int:
        return self.max_duration_minutes * 60

    @property
    def jwt_secret_is_placeholder(self) -> bool:
        return self.jwt_secret_key in INSECURE_SECRET_PLACEHOLDERS


@lru_cache
def get_settings() -> Settings:
    return Settings()
