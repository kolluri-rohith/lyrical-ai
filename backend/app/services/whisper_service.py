"""Local Whisper transcription (faster-whisper / CTranslate2). The model is loaded once.

Only used with TRANSCRIPTION_BACKEND=local. Nothing heavy is imported until then, so
this module is safe to import without requirements-local.txt installed.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.audio_service import WHISPER_SAMPLE_RATE
from app.services.language_service import pick_supported_language
from app.utils.device import resolve_device

logger = get_logger("whisper")

# How many 30 s windows of (voiced) audio to look at when detecting the language.
LANGUAGE_DETECTION_SEGMENTS = 4
VAD_PARAMETERS = {"min_silence_duration_ms": 700, "speech_pad_ms": 400}

ProgressCallback = Callable[[float], None]


@dataclass(frozen=True)
class RawSegment:
    start: float
    end: float
    text: str


class WhisperService:
    def __init__(self) -> None:
        self._model = None
        self._device: str | None = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def device(self) -> str | None:
        return self._device

    @property
    def model_name(self) -> str:
        return f"whisper-{get_settings().whisper_model}"

    def load(self) -> None:
        """Load the Whisper model (downloads the weights on first use)."""
        with self._lock:
            if self._model is not None:
                return
            device = resolve_device()
            started = time.perf_counter()
            try:
                self._model = self._create_model(device)
            except Exception:
                if device != "cuda":
                    raise
                # CTranslate2 needs the CUDA/cuDNN runtime libraries; fall back if absent.
                logger.exception("Could not load Whisper on CUDA; falling back to CPU")
                device = "cpu"
                self._model = self._create_model(device)
            self._device = device
            logger.info(
                "Whisper model '%s' loaded on %s in %.1fs",
                get_settings().whisper_model, device, time.perf_counter() - started,
            )

    @staticmethod
    def _create_model(device: str):
        from faster_whisper import WhisperModel

        settings = get_settings()
        compute_type = settings.whisper_compute_type
        if compute_type == "auto":
            compute_type = "float16" if device == "cuda" else "int8"
        cache_dir = settings.model_cache_dir
        return WhisperModel(
            settings.whisper_model,
            device=device,
            compute_type=compute_type,
            download_root=str(cache_dir / "whisper") if cache_dir else None,
        )

    @staticmethod
    def load_audio(path: Path) -> np.ndarray:
        from faster_whisper import decode_audio

        return decode_audio(str(path), sampling_rate=WHISPER_SAMPLE_RATE)

    def detect_language(self, audio: np.ndarray) -> tuple[str, float]:
        """Most likely supported language of `audio` and its probability."""
        self.load()
        try:
            language, probability, all_probabilities = self._model.detect_language(
                audio,
                vad_filter=True,
                language_detection_segments=LANGUAGE_DETECTION_SEGMENTS,
            )
        except Exception:
            # VAD can leave nothing to analyse on very sparse vocals.
            logger.warning("Language detection with VAD failed; retrying on the raw audio")
            language, probability, all_probabilities = self._model.detect_language(
                audio, language_detection_segments=LANGUAGE_DETECTION_SEGMENTS
            )

        supported = pick_supported_language(all_probabilities or [(language, probability)])
        if supported is None:
            return language, probability
        return supported

    def transcribe(
        self,
        audio: np.ndarray,
        language: str,
        on_progress: ProgressCallback | None = None,
    ) -> list[RawSegment]:
        """Transcribe `audio` in `language`, returning timestamped segments."""
        self.load()
        settings = get_settings()
        segments, info = self._model.transcribe(
            audio,
            language=language,
            task="transcribe",
            beam_size=settings.whisper_beam_size,
            vad_filter=settings.whisper_vad_filter,
            vad_parameters=VAD_PARAMETERS if settings.whisper_vad_filter else None,
            # Songs repeat a lot; feeding previous text back in makes Whisper loop.
            condition_on_previous_text=False,
        )

        total = float(info.duration or 0.0)
        collected: list[RawSegment] = []
        # `segments` is a generator: decoding happens as it is consumed.
        for segment in segments:
            collected.append(RawSegment(start=segment.start, end=segment.end, text=segment.text))
            if on_progress and total > 0:
                on_progress(min(segment.end / total, 1.0))
        return collected


whisper_service = WhisperService()
