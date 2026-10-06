import pytest

from app.core.exceptions import UnsupportedFileError
from app.utils import storage
from app.utils.files import classify_upload, download_basename, sanitize_filename


@pytest.mark.parametrize(
    ("filename", "content_type", "expected"),
    [
        ("song.mp3", "audio/mpeg", ("audio", ".mp3")),
        ("SONG.MP3", "audio/mpeg", ("audio", ".mp3")),
        ("take.wav", "audio/x-wav", ("audio", ".wav")),
        ("voice.m4a", "audio/mp4", ("audio", ".m4a")),
        ("voice.aac", "audio/aac", ("audio", ".aac")),
        ("master.flac", "audio/flac", ("audio", ".flac")),
        ("clip.mp4", "video/mp4", ("video", ".mp4")),
        ("clip.mov", "video/quicktime", ("video", ".mov")),
        ("clip.mkv", "video/x-matroska", ("video", ".mkv")),
        # Browsers that cannot tell send a generic type; the extension decides.
        ("song.mp3", "application/octet-stream", ("audio", ".mp3")),
        ("song.mp3", None, ("audio", ".mp3")),
    ],
)
def test_supported_uploads_are_classified(filename, content_type, expected):
    assert classify_upload(filename, content_type) == expected


@pytest.mark.parametrize("filename", ["notes.txt", "malware.exe", "archive.zip", "noextension"])
def test_unsupported_extensions_are_rejected(filename):
    with pytest.raises(UnsupportedFileError):
        classify_upload(filename, "application/octet-stream")


def test_mime_type_must_match_extension():
    with pytest.raises(UnsupportedFileError):
        classify_upload("song.mp3", "text/html")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.mp3", "passwd.mp3"),
        ("C:\\Users\\me\\Music\\track.mp3", "track.mp3"),
        ("my:song?.mp3", "my_song_.mp3"),
        ("పాట.mp3", "పాట.mp3"),
        ("", "upload"),
        (None, "upload"),
    ],
)
def test_filenames_are_sanitized(raw, expected):
    assert sanitize_filename(raw) == expected


def test_long_filenames_keep_their_extension():
    name = sanitize_filename("a" * 400 + ".mp3")
    assert len(name) <= 200
    assert name.endswith(".mp3")


def test_download_name_is_ascii_safe():
    assert download_basename("My Song (final).mp3") == "My_Song_final"
    assert download_basename("పాట.mp3") == "lyrics"


@pytest.mark.parametrize("filename", ["../secret.wav", "..\\secret.wav", "nested/file.wav"])
def test_storage_paths_cannot_escape(client, filename):
    with pytest.raises(ValueError):
        storage.upload_path(filename)
