"""Whisper transcription through an OpenAI-compatible API.

The audio file is streamed from disk to the API, so the backend holds neither a model
nor the audio in memory.
"""

import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.core.exceptions import PipelineError
from app.core.logging import get_logger
from app.services.whisper_service import RawSegment

logger = get_logger("cloud")

MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2.0
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
CONNECT_TIMEOUT_SECONDS = 15
ERROR_BODY_LOG_CHARS = 600

NOT_CONFIGURED_MESSAGE = "The transcription service is not configured on the server."
UNAVAILABLE_MESSAGE = "The transcription service is busy right now. Please try again in a moment."
REJECTED_MESSAGE = "The transcription service could not process this file."


@dataclass(frozen=True)
class CloudTranscript:
    segments: list[RawSegment]
    language: str | None  # as reported by the API, usually an English name ("hindi")


class CloudTranscriptionService:
    device = "cloud"

    @property
    def is_configured(self) -> bool:
        return bool(get_settings().openai_api_key.strip())

    @property
    def model_name(self) -> str:
        return get_settings().openai_transcription_model

    def transcribe(self, audio_path: Path, language: str | None = None) -> CloudTranscript:
        """Transcribe `audio_path`, returning timestamped segments.

        With `language` (an ISO 639-1 code) the API decodes strictly in that language
        and does no detection of its own. Only `language=None` lets it auto-detect.
        """
        settings = get_settings()
        if not self.is_configured:
            logger.error("OPENAI_API_KEY is not set; cannot transcribe")
            raise PipelineError(NOT_CONFIGURED_MESSAGE)

        fields = {
            "model": settings.openai_transcription_model,
            "response_format": "verbose_json",
            "timestamp_granularities[]": "segment",
            "temperature": "0",
        }
        if language:
            fields["language"] = language

        payload = self._post(audio_path, fields)
        segments = [
            RawSegment(
                start=float(segment.get("start") or 0.0),
                end=float(segment.get("end") or 0.0),
                text=str(segment.get("text") or ""),
            )
            for segment in payload.get("segments") or []
        ]
        return CloudTranscript(segments=segments, language=payload.get("language"))

    def _post(self, audio_path: Path, fields: dict[str, str]) -> dict:
        settings = get_settings()
        url = f"{settings.openai_base_url.rstrip('/')}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {settings.openai_api_key.strip()}"}
        timeout = httpx.Timeout(settings.openai_timeout_seconds, connect=CONNECT_TIMEOUT_SECONDS)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                with audio_path.open("rb") as audio:
                    response = httpx.post(
                        url,
                        headers=headers,
                        data=fields,
                        files={"file": (audio_path.name, audio)},
                        timeout=timeout,
                    )
            except httpx.HTTPError as exc:
                logger.warning("Transcription API attempt %d failed: %r", attempt, exc)
                response = None

            if response is not None and response.status_code == 200:
                try:
                    return response.json()
                except ValueError as exc:
                    logger.error("Transcription API returned a non-JSON body")
                    raise PipelineError(REJECTED_MESSAGE) from exc

            if response is not None and response.status_code not in RETRYABLE_STATUS_CODES:
                logger.error(
                    "Transcription API rejected the request: %d %s",
                    response.status_code, response.text[:ERROR_BODY_LOG_CHARS],
                )
                if response.status_code in (401, 403):
                    raise PipelineError(NOT_CONFIGURED_MESSAGE)
                raise PipelineError(REJECTED_MESSAGE)

            if response is not None:
                logger.warning(
                    "Transcription API attempt %d returned %d", attempt, response.status_code
                )
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)

        raise PipelineError(UNAVAILABLE_MESSAGE)


cloud_transcription_service = CloudTranscriptionService()
