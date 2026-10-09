"""Thin wrappers around the ffmpeg / ffprobe binaries."""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import PipelineError
from app.core.logging import get_logger

logger = get_logger("ffmpeg")

PROBE_TIMEOUT_SECONDS = 60
STDERR_LOG_CHARS = 600


@dataclass(frozen=True)
class AudioStream:
    position: int  # index among the audio streams, as used by `-map 0:a:N`
    codec: str
    sample_rate: int
    channels: int
    language: str | None  # container language tag, e.g. "hin"
    is_default: bool


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    has_audio: bool
    has_video: bool
    audio_streams: tuple[AudioStream, ...] = ()


_resolved: dict[str, str] = {}


def _windows_path_dirs() -> list[str]:
    """PATH as currently saved in the registry.

    A terminal opened before FFmpeg was installed (e.g. with winget) keeps the old PATH,
    so the process cannot see the new binaries even though they are installed.
    """
    import winreg

    keys = [
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ]
    dirs: list[str] = []
    for hive, subkey in keys:
        try:
            with winreg.OpenKey(hive, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        dirs.extend(os.path.expandvars(part) for part in str(value).split(";") if part)
    return dirs


def _windows_candidates(name: str) -> list[str]:
    candidates = [shutil.which(name, path=directory) for directory in _windows_path_dirs()]
    # winget installs Gyan.FFmpeg under %LOCALAPPDATA%\Microsoft\WinGet\Packages.
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        packages = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        candidates.extend(str(p) for p in sorted(packages.glob(f"*FFmpeg*/*/bin/{name}.exe")))
    return [c for c in candidates if c]


def binary(name: str) -> str | None:
    """Full path of `ffmpeg` / `ffprobe`, or None when it cannot be found."""
    if name in _resolved:
        return _resolved[name]

    configured = getattr(get_settings(), f"{name}_path")
    if configured:
        found = shutil.which(configured)
        if found is None:
            logger.error("%s_PATH=%s does not point to an executable", name.upper(), configured)
    else:
        found = shutil.which(name)
        if found is None and sys.platform == "win32":
            found = next(iter(_windows_candidates(name)), None)
            if found:
                logger.warning("%s is not on PATH; using %s", name, found)

    if found:
        _resolved[name] = found
    return found


def ffmpeg_available() -> bool:
    return binary("ffmpeg") is not None and binary("ffprobe") is not None


def _run(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    executable = binary(command[0])
    if executable is None:
        logger.error("%s binary not found on PATH", command[0])
        raise PipelineError("The media processing tool is not available on the server.")
    try:
        return subprocess.run(
            [executable, *command[1:]],
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
        audio_streams=tuple(
            AudioStream(
                position=position,
                codec=str(stream.get("codec_name") or "unknown"),
                sample_rate=int(_to_float(stream.get("sample_rate"))),
                channels=int(_to_float(stream.get("channels"))),
                language=(stream.get("tags") or {}).get("language"),
                is_default=bool(stream.get("disposition", {}).get("default")),
            )
            for position, stream in enumerate(audio_streams)
        ),
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
