"""Pipeline tests with real FFmpeg. Demucs and Whisper are replaced by stubs here;
they are exercised for real in test_models_integration.py."""

import shutil

import pytest

from app.models import JobStatus, TranscriptionJob
from app.services import transcription_service
from app.services.vocal_separation_service import vocal_separation_service
from app.services.whisper_service import RawSegment, whisper_service
from app.utils import storage
from app.utils.ffmpeg import probe
from tests.conftest import CLIENT_A, requires_ffmpeg, upload

pytestmark = requires_ffmpeg


@pytest.fixture
def stub_models(monkeypatch):
    """Stand-ins for the two models; records what the pipeline asked of them."""
    calls: dict = {"separated": [], "detected": 0, "transcribed": []}

    def separate(audio_path, output_path):
        info = probe(audio_path)
        calls["separated"].append(info)
        shutil.copyfile(audio_path, output_path)
        return output_path

    def detect(audio):
        calls["detected"] += 1
        return "hi", 0.93

    def transcribe(audio, language, on_progress=None):
        calls["transcribed"].append({"language": language, "samples": len(audio)})
        if on_progress:
            on_progress(0.5)
            on_progress(1.0)
        return [
            RawSegment(0.0, 1.2, " पहली पंक्ति "),
            RawSegment(1.2, 1.5, "[Music]"),
            RawSegment(1.5, 2.8, "दूसरी पंक्ति"),
        ]

    monkeypatch.setattr(vocal_separation_service, "separate_vocals", separate)
    monkeypatch.setattr(whisper_service, "detect_language", detect)
    monkeypatch.setattr(whisper_service, "transcribe", transcribe)
    return calls


@pytest.fixture
def stages(monkeypatch):
    seen: list[str] = []
    original = transcription_service._set_stage

    def recording(job_id, status, **fields):
        seen.append(status.value)
        original(job_id, status, **fields)

    monkeypatch.setattr(transcription_service, "_set_stage", recording)
    return seen


def _run(client, path, content_type, language="auto") -> str:
    response = upload(client, path.read_bytes(), path.name, content_type, language=language)
    assert response.status_code == 202, response.text
    job_id = response.json()["jobId"]
    transcription_service.process_job(job_id)
    return job_id


def _detail(client, job_id) -> dict:
    return client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_A).json()


def _no_intermediates_left(job_id) -> bool:
    return not any(path.exists() for path in storage.intermediate_paths(job_id))


def test_probe_reads_duration_and_streams(tone_wav, video_mp4, video_without_audio):
    audio = probe(tone_wav)
    assert audio.has_audio and not audio.has_video
    assert audio.duration == pytest.approx(3.0, abs=0.2)

    video = probe(video_mp4)
    assert video.has_audio and video.has_video
    assert not probe(video_without_audio).has_audio


def test_audio_job_runs_every_stage_and_stores_lyrics(client, db, tone_wav, stub_models, stages):
    job_id = _run(client, tone_wav, "audio/wav")

    assert stages == [
        "VALIDATING", "PREPROCESSING", "SEPARATING_VOCALS",
        "DETECTING_LANGUAGE", "TRANSCRIBING", "POST_PROCESSING",
    ]
    detail = _detail(client, job_id)
    assert detail["status"] == "COMPLETED"
    assert detail["detectedLanguage"] == "hi"
    assert detail["duration"] == pytest.approx(3.0, abs=0.2)
    assert detail["warning"] is None
    assert [segment["text"] for segment in detail["segments"]] == ["पहली पंक्ति", "दूसरी पंक्ति"]
    assert detail["segments"][1]["start"] == 1.5
    assert detail["processingTime"] > 0

    # Demucs received normalised stereo 44.1 kHz audio; Whisper received 16 kHz samples.
    assert stub_models["separated"][0].duration == pytest.approx(3.0, abs=0.2)
    assert stub_models["transcribed"][0]["samples"] == pytest.approx(3 * 16000, rel=0.1)

    job = db.get(TranscriptionJob, job_id)
    assert job.transcription_progress == 100
    assert _no_intermediates_left(job_id)
    assert detail["mediaAvailable"] is True  # the upload is kept for playback


def test_video_job_extracts_audio_first(client, video_mp4, stub_models, stages):
    job_id = _run(client, video_mp4, "video/mp4")
    assert stages[:3] == ["VALIDATING", "EXTRACTING_AUDIO", "PREPROCESSING"]
    assert _detail(client, job_id)["status"] == "COMPLETED"
    assert _no_intermediates_left(job_id)


def test_explicit_language_skips_detection(client, tone_wav, stub_models):
    job_id = _run(client, tone_wav, "audio/wav", language="te")
    assert stub_models["detected"] == 0
    assert stub_models["transcribed"][0]["language"] == "te"
    assert _detail(client, job_id)["detectedLanguage"] == "te"


def test_separation_failure_falls_back_to_the_full_mix(client, tone_wav, stub_models, monkeypatch):
    def broken(audio_path, output_path):
        raise RuntimeError("demucs exploded at /internal/path")

    monkeypatch.setattr(vocal_separation_service, "separate_vocals", broken)
    job_id = _run(client, tone_wav, "audio/wav")
    detail = _detail(client, job_id)
    assert detail["status"] == "COMPLETED"
    assert "Accuracy may be lower" in detail["warning"]
    assert "/internal/path" not in detail["warning"]


def _assert_failed(client, job_id, expected_fragment):
    detail = _detail(client, job_id)
    assert detail["status"] == JobStatus.FAILED.value
    assert expected_fragment in detail["errorMessage"]
    assert detail["mediaAvailable"] is False  # failed uploads are discarded
    assert _no_intermediates_left(job_id)


def test_corrupt_media_fails_cleanly(client, media_dir, stub_models):
    corrupt = media_dir / "corrupt.mp3"
    corrupt.write_bytes(b"this is definitely not audio" * 50)
    job_id = _run(client, corrupt, "audio/mpeg")
    _assert_failed(client, job_id, "corrupt or is not a valid")


def test_video_without_audio_fails_cleanly(client, video_without_audio, stub_models):
    job_id = _run(client, video_without_audio, "video/mp4")
    _assert_failed(client, job_id, "no audio track")


def test_silent_audio_fails_cleanly(client, silent_wav, stub_models):
    job_id = _run(client, silent_wav, "audio/wav")
    _assert_failed(client, job_id, "silent")


def test_file_longer_than_the_limit_fails(client, tone_wav, stub_models, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_duration_minutes", 0)
    job_id = _run(client, tone_wav, "audio/wav")
    _assert_failed(client, job_id, "too long")


def test_nothing_transcribed_is_reported(client, tone_wav, stub_models, monkeypatch):
    monkeypatch.setattr(whisper_service, "transcribe", lambda *args, **kwargs: [])
    job_id = _run(client, tone_wav, "audio/wav")
    _assert_failed(client, job_id, "No lyrics could be detected")


def test_unexpected_errors_are_not_leaked(client, tone_wav, stub_models, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("CUDA error at C:\\secret\\path line 42")

    monkeypatch.setattr(whisper_service, "transcribe", broken)
    job_id = _run(client, tone_wav, "audio/wav")
    detail = _detail(client, job_id)
    assert detail["status"] == "FAILED"
    assert "secret" not in detail["errorMessage"]
    assert "CUDA" not in detail["errorMessage"]


def test_job_deleted_mid_flight_is_cleaned_up(client, tone_wav, stub_models, monkeypatch):
    response = upload(client, tone_wav.read_bytes(), tone_wav.name, "audio/wav")
    job_id = response.json()["jobId"]

    def delete_then_detect(audio):
        client.delete(f"/api/transcriptions/{job_id}", headers=CLIENT_A)
        return "en", 0.9

    monkeypatch.setattr(whisper_service, "detect_language", delete_then_detect)
    transcription_service.process_job(job_id)  # must not raise

    assert client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_A).status_code == 404
    assert _no_intermediates_left(job_id)
    assert list(storage.storage_dir("uploads").glob(f"{job_id}.*")) == []
