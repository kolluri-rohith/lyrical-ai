"""Audio preprocessing with FFmpeg: silence check, normalisation and resampling."""

import re
from pathlib import Path

from app.core.exceptions import PipelineError
from app.utils.ffmpeg import run_ffmpeg

SEPARATION_SAMPLE_RATE = 44100  # what Demucs expects
WHISPER_SAMPLE_RATE = 16000  # what Whisper expects
SILENCE_THRESHOLD_DB = -60.0
# EBU R128 loudness normalisation so quiet uploads are not under-transcribed.
LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"

_MAX_VOLUME_PATTERN = re.compile(r"max_volume:\s*(-?(?:\d+(?:\.\d+)?|inf))\s*dB")


def measure_max_volume_db(source: Path) -> float | None:
    """Peak level of the first audio stream in dBFS, or None if it cannot be measured."""
    log = run_ffmpeg(
        ["-i", str(source), "-map", "0:a:0", "-vn", "-af", "volumedetect", "-f", "null", "-"],
        failure_message="The audio in this file could not be decoded.",
    )
    match = _MAX_VOLUME_PATTERN.search(log)
    if not match:
        return None
    return float(match.group(1))


def ensure_not_silent(source: Path) -> None:
    max_volume = measure_max_volume_db(source)
    if max_volume is not None and max_volume <= SILENCE_THRESHOLD_DB:
        raise PipelineError("The audio in this file is silent, so there is nothing to transcribe.")


def normalize_for_separation(source: Path, output_path: Path) -> Path:
    """Decode anything FFmpeg understands to loudness-normalised stereo 44.1 kHz WAV."""
    run_ffmpeg(
        [
            "-i", str(source),
            "-vn",
            "-map", "0:a:0",
            "-af", LOUDNORM_FILTER,
            "-ac", "2",
            "-ar", str(SEPARATION_SAMPLE_RATE),
            "-c:a", "pcm_s16le",
            str(output_path),
        ],
        failure_message="The audio in this file could not be processed.",
    )
    return output_path


def convert_for_whisper(source: Path, output_path: Path) -> Path:
    """Downmix to mono 16 kHz WAV, the input format Whisper works on."""
    run_ffmpeg(
        [
            "-i", str(source),
            "-vn",
            "-ac", "1",
            "-ar", str(WHISPER_SAMPLE_RATE),
            "-c:a", "pcm_s16le",
            str(output_path),
        ],
        failure_message="The audio could not be prepared for transcription.",
    )
    return output_path
