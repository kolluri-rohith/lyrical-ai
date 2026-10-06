"""End-to-end test with the REAL Demucs and Whisper models.

Slow, and it downloads the model weights on first run, so it is opt-in:

    LYRICALAI_TEST_AUDIO=path/to/song.mp3 LYRICALAI_TEST_LANGUAGE=en pytest -m integration

Optionally set LYRICALAI_TEST_EXPECT to a word that must appear in the lyrics.
"""

import os
import shutil
from pathlib import Path

import pytest

from app.database.session import SessionLocal
from app.models import TranscriptionJob
from app.services import transcription_service
from app.utils import storage
from app.utils.files import classify_upload
from tests.conftest import CLIENT_A, new_job_id, requires_ffmpeg

SAMPLE = os.environ.get("LYRICALAI_TEST_AUDIO")

pytestmark = [
    pytest.mark.integration,
    requires_ffmpeg,
    pytest.mark.skipif(not SAMPLE, reason="set LYRICALAI_TEST_AUDIO to run the real models"),
]


def test_real_pipeline_produces_timestamped_lyrics(client, monkeypatch):
    from app.core.config import get_settings

    sample = Path(SAMPLE)
    settings = get_settings()
    monkeypatch.setattr(settings, "max_duration_minutes", 15)
    monkeypatch.setattr(settings, "enable_separation_fallback", False)  # Demucs must really work

    language = os.environ.get("LYRICALAI_TEST_LANGUAGE", "auto")
    file_type, extension = classify_upload(sample.name, None)

    # Created directly (not through the upload API) so the 1 MB test upload limit
    # does not apply to a real song.
    job_id = new_job_id()
    shutil.copyfile(sample, storage.upload_path(f"{job_id}{extension}"))
    with SessionLocal() as db:
        db.add(
            TranscriptionJob(
                id=job_id,
                client_id=CLIENT_A["X-Client-Id"],
                original_filename=sample.name,
                stored_filename=f"{job_id}{extension}",
                file_type=file_type,
                file_size=sample.stat().st_size,
                requested_language=language,
            )
        )
        db.commit()

    transcription_service.process_job(job_id)

    detail = client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_A).json()
    assert detail["status"] == "COMPLETED", detail["errorMessage"]
    assert detail["warning"] is None
    assert detail["segments"], "expected at least one lyric line"
    assert all(segment["end"] >= segment["start"] for segment in detail["segments"])
    if language != "auto":
        assert detail["detectedLanguage"] == language

    expected = os.environ.get("LYRICALAI_TEST_EXPECT")
    if expected:
        assert expected.lower() in detail["fullText"].lower()

    srt = client.get(f"/api/transcriptions/{job_id}/download/srt", headers=CLIENT_A).text
    assert "-->" in srt
