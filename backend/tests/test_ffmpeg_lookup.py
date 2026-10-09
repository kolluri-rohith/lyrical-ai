import pytest

from app.core.config import get_settings
from app.core.exceptions import PipelineError
from app.utils import ffmpeg


@pytest.fixture(autouse=True)
def _fresh_lookup(monkeypatch):
    monkeypatch.setattr(ffmpeg, "_resolved", {})
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_missing_binary_reports_unavailable(monkeypatch):
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda *args, **kwargs: None)
    monkeypatch.setattr(ffmpeg, "_windows_candidates", lambda name: [])

    assert ffmpeg.ffmpeg_available() is False
    with pytest.raises(PipelineError, match="media processing tool is not available"):
        ffmpeg.probe(ffmpeg.Path("song.mp3"))


def test_binary_found_outside_path_is_used(monkeypatch):
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda *args, **kwargs: None)
    monkeypatch.setattr(ffmpeg.sys, "platform", "win32")
    monkeypatch.setattr(ffmpeg, "_windows_candidates", lambda name: [rf"C:\ffmpeg\bin\{name}.exe"])

    assert ffmpeg.binary("ffprobe") == r"C:\ffmpeg\bin\ffprobe.exe"
    assert ffmpeg.ffmpeg_available() is True


def test_configured_path_wins(monkeypatch):
    monkeypatch.setenv("FFMPEG_PATH", "/opt/ffmpeg/bin/ffmpeg")
    monkeypatch.setattr(
        ffmpeg.shutil, "which", lambda cmd, **kwargs: cmd if cmd.startswith("/opt/") else None
    )

    assert ffmpeg.binary("ffmpeg") == "/opt/ffmpeg/bin/ffmpeg"
