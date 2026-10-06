"""Thin wrappers around the ffmpeg / ffprobe binaries."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import PipelineError
from app.core.logging import get_logger

logger = get_logger("ffmpeg")

PROBE_TIMEOUT_SECONDS = 60
STDERR_LOG_CHARS = 600


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    has_audio: bool
    has_video: bool


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _run(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        logger.error("%s binary not found on PATH", command[0])
        raise PipelineError("The media processing tool is not available on the server.") from exc
    except subprocess.TimeoutExpired as exc:
        logger.error("%s timed out after %ss", command[0], timeout)
        raise PipelineError(
            "Processing this file took too long. Please try a shorter file."
        ) from exc


def probe(path: Path) -> MediaInfo:
    """Inspect a media file. Raises PipelineError when it cannot be decoded."""
    result = _run(
        [
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            str(path),
        ],
        timeout=PROBE_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        logger.warning("ffprobe rejected file: %s", result.stderr[-STDERR_LOG_CHARS:])
        raise PipelineError("The file is corrupt or is not a valid audio/video file.")

    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise PipelineError("The file is corrupt or is not a valid audio/video file.") from exc

    streams = data.get("streams", [])
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    # Cover art in MP3/M4A files shows up as a video stream flagged attached_pic.
    video_streams = [
        s
        for s in streams
        if s.get("codec_type") == "video"
        and not s.get("disposition", {}).get("attached_pic")
    ]

    duration = _to_float(data.get("format", {}).get("duration"))
    if duration <= 0 and audio_streams:
        duration = _to_float(audio_streams[0].get("duration"))

    return MediaInfo(
        duration=duration,
        has_audio=bool(audio_streams),
        has_video=bool(video_streams),
    )


def run_ffmpeg(arguments: list[str], *, failure_message: str) -> str:
    """Run ffmpeg with the given arguments and return its stderr log."""
    result = _run(
        ["ffmpeg", "-hide_banner", "-nostdin", "-y", *arguments],
        timeout=get_settings().ffmpeg_timeout_seconds,
    )
    if result.returncode != 0:
        logger.error("ffmpeg failed: %s", result.stderr[-STDERR_LOG_CHARS:])
        if "No space left on device" in result.stderr:
            raise PipelineError("The server ran out of disk space. Please try again later.")
        raise PipelineError(failure_message)
    return result.stderr


def _to_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
