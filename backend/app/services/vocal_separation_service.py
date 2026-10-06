"""Vocal isolation with Demucs. The model is loaded once and reused for every job."""

import threading
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.utils.device import resolve_device

logger = get_logger("demucs")

VOCALS_STEM = "vocals"


class VocalSeparationService:
    def __init__(self) -> None:
        self._model = None
        self._device: str | None = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def load(self) -> None:
        """Load the Demucs model (downloads the weights on first use)."""
        with self._lock:
            if self._model is not None:
                return
            from demucs.pretrained import get_model

            name = get_settings().demucs_model
            device = resolve_device()
            started = time.perf_counter()
            model = get_model(name)
            model.eval()
            model.to(device)
            self._model = model
            self._device = device
            logger.info(
                "Demucs model '%s' loaded on %s in %.1fs",
                name, device, time.perf_counter() - started,
            )

    def separate_vocals(self, audio_path: Path, output_path: Path) -> Path:
        """Split `audio_path` into stems and write only the vocal stem to `output_path`.

        The instrumental stems only ever exist in memory and are dropped here.
        """
        import soundfile
        import torch
        from demucs.apply import apply_model

        self.load()
        model = self._model

        samples, sample_rate = soundfile.read(str(audio_path), dtype="float32", always_2d=True)
        if sample_rate != model.samplerate or samples.shape[1] != model.audio_channels:
            raise ValueError("Audio must be preprocessed to the Demucs sample rate and channels")

        mix = torch.from_numpy(samples.T.copy())  # (channels, frames)
        reference = mix.mean(dim=0)
        mean, std = reference.mean(), reference.std() + 1e-8
        mix = (mix - mean) / std

        with torch.no_grad():
            stems = apply_model(
                model,
                mix[None],
                device=self._device,
                shifts=1,
                split=True,
                overlap=0.25,
                progress=False,
            )[0]

        vocals = stems[model.sources.index(VOCALS_STEM)] * std + mean
        soundfile.write(
            str(output_path),
            vocals.clamp(-1.0, 1.0).cpu().numpy().T,
            sample_rate,
            subtype="PCM_16",
        )
        del stems, vocals, mix
        if self._device == "cuda":
            torch.cuda.empty_cache()
        return output_path


vocal_separation_service = VocalSeparationService()
