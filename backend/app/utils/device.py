"""Resolve DEVICE=auto|cpu|cuda to the device the models actually run on."""

from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("device")


@lru_cache
def resolve_device() -> str:
    requested = get_settings().device
    if requested == "cpu":
        return "cpu"

    import torch

    if torch.cuda.is_available():
        return "cuda"
    if requested == "cuda":
        logger.warning("DEVICE=cuda was requested but CUDA is not available; using CPU")
    return "cpu"
