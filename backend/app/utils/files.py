"""Upload validation: extension, MIME type and filename hygiene."""

import re
import unicodedata
from pathlib import PurePosixPath, PureWindowsPath

from app.core.exceptions import UnsupportedFileError

AUDIO_EXTENSIONS: dict[str, set[str]] = {
    ".mp3": {"audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mpeg-3"},
    ".wav": {"audio/wav", "audio/x-wav", "audio/wave", "audio/vnd.wave"},
    ".m4a": {"audio/mp4", "audio/x-m4a", "audio/m4a", "audio/aac", "video/mp4"},
    ".aac": {"audio/aac", "audio/x-aac", "audio/aacp", "audio/vnd.dlna.adts"},
    ".flac": {"audio/flac", "audio/x-flac"},
}
VIDEO_EXTENSIONS: dict[str, set[str]] = {
    ".mp4": {"video/mp4", "application/mp4"},
    ".mov": {"video/quicktime"},
    ".mkv": {"video/x-matroska", "video/matroska", "application/x-matroska"},
}
# Browsers send these when they cannot tell; the extension and ffprobe decide then.
GENERIC_MIME_TYPES = {"", "application/octet-stream", "binary/octet-stream"}

MAX_FILENAME_LENGTH = 200


def file_extension(filename: str) -> str:
    return PurePosixPath(filename).suffix.lower()


def classify_upload(filename: str, content_type: str | None) -> tuple[str, str]:
    """Return (file_type, extension) or raise UnsupportedFileError."""
    extension = file_extension(filename)
    if extension in AUDIO_EXTENSIONS:
        file_type, allowed = "audio", AUDIO_EXTENSIONS[extension]
    elif extension in VIDEO_EXTENSIONS:
        file_type, allowed = "video", VIDEO_EXTENSIONS[extension]
    else:
        supported = ", ".join(sorted(e.lstrip(".").upper() for e in ALL_EXTENSIONS))
        raise UnsupportedFileError(f"Unsupported file type. Supported formats: {supported}.")

    mime = (content_type or "").split(";")[0].strip().lower()
    if mime not in GENERIC_MIME_TYPES and mime not in allowed:
        raise UnsupportedFileError(
            "The file's content type does not match its extension. "
            "Please upload a valid audio or video file."
        )
    return file_type, extension


ALL_EXTENSIONS = sorted({*AUDIO_EXTENSIONS, *VIDEO_EXTENSIONS})


def sanitize_filename(filename: str | None) -> str:
    """Reduce a client-supplied filename to a safe display name (never used as a path)."""
    raw = filename or ""
    # Drop any directory part, whichever OS the client used.
    name = PureWindowsPath(raw).name
    name = PurePosixPath(name).name
    name = unicodedata.normalize("NFC", name)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip(" .")
    if len(name) > MAX_FILENAME_LENGTH:
        extension = file_extension(name)
        name = name[: MAX_FILENAME_LENGTH - len(extension)] + extension
    return name or "upload"


def download_basename(original_filename: str) -> str:
    """ASCII-safe base name for Content-Disposition."""
    stem = PurePosixPath(original_filename).stem
    ascii_stem = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii")
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", ascii_stem).strip("._-")
    return ascii_stem[:80] or "lyrics"
