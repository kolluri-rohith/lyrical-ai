"""Audio preprocessing with FFmpeg: silence check, normalisation and resampling.

Every function reads the original upload (audio file or video container) directly and
takes the audio track to use as `stream`, its index for FFmpeg's `-map 0:a:N`.
"""

import re
from pathlib import Path

from app.core.exceptions import PipelineError
from app.utils.ffmpeg import run_ffmpeg

SEPARATION_SAMPLE_RATE = 44100  # what Demucs expects
WHISPER_SAMPLE_RATE = 16000  # what Whisper expects
SILENCE_THRESHOLD_DB = -60.0
# Keeps the audio on the container's timeline. In a video the audio track often starts
# later than the picture or has gaps; without this FFmpeg drops that offset and every
# lyric timestamp is early by that much when played against the original file.
TIMELINE_FILTER = "aresample=async=1:first_pts=0"
# EBU R128 loudness normalisation so quiet uploads are not under-transcribed.
LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"
# Used only when the lossless encode is over the transcription API's upload limit.
API_FALLBACK_BITRATE = "64k"

_MAX_VOLUME_PATTERN = re.compile(r"max_volume:\s*(-?(?:\d+(?:\.\d+)?|inf))\s*dB")


def _audio_input(source: Path, stream: int) -> list[str]:
    return ["-i", str(source), "-vn", "-sn", "-dn", "-map", f"0:a:{stream}"]


def measure_max_volume_db(source: Path, *, stream: int = 0) -> float | None:
    """Peak level of one audio stream in dBFS, or None if it cannot be measured."""
    log = run_ffmpeg(
        [*_audio_input(source, stream), "-af", "volumedetect", "-f", "null", "-"],
        failure_message="The audio in this file could not be decoded.",
    )
    match = _MAX_VOLUME_PATTERN.search(log)
    if not match:
        return None
    return float(match.group(1))


def ensure_not_silent(source: Path, *, stream: int = 0) -> None:
    max_volume = measure_max_volume_db(source, stream=stream)
    if max_volume is not None and max_volume <= SILENCE_THRESHOLD_DB:
        raise PipelineError("The audio in this file is silent, so there is nothing to transcribe.")


def encode_for_api(source: Path, output_path: Path, *, stream: int = 0) -> Path:
    """Decode one audio stream to loudness-normalised mono 16 kHz FLAC for the cloud API.

    16 kHz mono is what Whisper resamples to internally, and FLAC is lossless, so the
    API receives everything the model can use in the smallest lossless form.
    """
    run_ffmpeg(
        [
            *_audio_input(source, stream),
            "-af", f"{TIMELINE_FILTER},{LOUDNORM_FILTER}",
            "-ac", "1",
            "-ar", str(WHISPER_SAMPLE_RATE),
            "-c:a", "flac",
            str(output_path),
        ],
        failure_message="The audio in this file could not be processed.",
    )
    return output_path


def compress_for_api(source: Path, output_path: Path) -> Path:
    """Re-encode already prepared audio as MP3 when the FLAC is too big to upload."""
    run_ffmpeg(
        [
            "-i", str(source),
            "-c:a", "libmp3lame",
            "-b:a", API_FALLBACK_BITRATE,
            str(output_path),
        ],
        failure_message="The audio could not be prepared for transcription.",
    )
    return output_path


def normalize_for_separation(source: Path, output_path: Path, *, stream: int = 0) -> Path:
    """Decode anything FFmpeg understands to loudness-normalised stereo 44.1 kHz WAV."""
    run_ffmpeg(
        [
            *_audio_input(source, stream),
            "-af", f"{TIMELINE_FILTER},{LOUDNORM_FILTER}",
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
