"""Pipeline tests with real FFmpeg. The cloud API, Demucs and Whisper are replaced by
stubs here; the local models are exercised for real in test_models_integration.py."""

import shutil
import subprocess

import pytest

from app.core.config import get_settings
from app.models import JobStatus, TranscriptionJob
from app.services import audio_service, transcription_service, video_service
from app.services.cloud_transcription_service import (
    CloudTranscript,
    cloud_transcription_service,
)
from app.services.vocal_separation_service import vocal_separation_service
from app.services.whisper_service import RawSegment, whisper_service
from app.utils import storage
from app.utils.ffmpeg import probe
from tests.conftest import CLIENT_A, requires_ffmpeg, upload

pytestmark = requires_ffmpeg

SEGMENTS = [
    RawSegment(0.0, 1.2, " पहली पंक्ति "),
    RawSegment(1.2, 1.5, "[Music]"),
    RawSegment(1.5, 2.8, "दूसरी पंक्ति"),
]


@pytest.fixture
def stub_cloud(monkeypatch):
    """Stand-in for the cloud API; records the audio and language it was sent."""
    calls: list[dict] = []

    def transcribe(audio_path, language=None):
        calls.append({"language": language, "info": probe(audio_path), "name": audio_path.name})
        return CloudTranscript(segments=list(SEGMENTS), language="hindi")

    monkeypatch.setattr(cloud_transcription_service, "transcribe", transcribe)
    return calls


@pytest.fixture
def stub_models(monkeypatch):
    """Local backend with stand-ins for the two models."""
    calls: dict = {"separated": [], "detected": 0, "transcribed": []}

    def separate(audio_path, output_path):
        calls["separated"].append(probe(audio_path))
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
        return list(SEGMENTS)

    monkeypatch.setattr(get_settings(), "transcription_backend", "local")
    monkeypatch.setattr(vocal_separation_service, "separate_vocals", separate)
    monkeypatch.setattr(whisper_service, "load_audio", lambda path: [0.0] * 16000)
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


def _first_sound_at(path) -> float:
    """Seconds of silence at the start of an audio file."""
    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "silencedetect=n=-40dB:d=0.1",
         "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr
    return float(log.split("silence_end: ")[1].split()[0])


def test_probe_reads_duration_and_streams(tone_wav, video_mp4, video_without_audio):
    audio = probe(tone_wav)
    assert audio.has_audio and not audio.has_video
    assert audio.duration == pytest.approx(3.0, abs=0.2)
    assert audio.audio_streams[0].sample_rate == 44100

    video = probe(video_mp4)
    assert video.has_audio and video.has_video
    assert video.audio_streams[0].codec == "aac"
    assert not probe(video_without_audio).has_audio


# --- Cloud backend (the default) ---------------------------------------------


def test_audio_job_is_sent_to_the_cloud_and_stores_lyrics(client, db, tone_wav, stub_cloud, stages):
    job_id = _run(client, tone_wav, "audio/wav")

    assert stages == ["VALIDATING", "PREPROCESSING", "TRANSCRIBING", "POST_PROCESSING"]
    detail = _detail(client, job_id)
    assert detail["status"] == "COMPLETED"
    assert detail["detectedLanguage"] == "hi"  # mapped from the API's "hindi"
    assert detail["duration"] == pytest.approx(3.0, abs=0.2)
    assert detail["warning"] is None
    assert detail["modelName"] == "whisper-1"
    assert detail["device"] == "cloud"
    assert [segment["text"] for segment in detail["segments"]] == ["पहली पंक्ति", "दूसरी पंक्ति"]
    assert detail["segments"][1]["start"] == 1.5
    assert detail["processingTime"] > 0

    # The API received lossless mono 16 kHz audio and, for Auto Detect, no language.
    sent = stub_cloud[0]
    assert sent["language"] is None
    assert sent["name"].endswith(".api.flac")
    assert sent["info"].audio_streams[0].codec == "flac"
    assert sent["info"].audio_streams[0].sample_rate == 16000
    assert sent["info"].audio_streams[0].channels == 1
    assert sent["info"].duration == pytest.approx(3.0, abs=0.2)

    job = db.get(TranscriptionJob, job_id)
    assert job.transcription_progress == 100
    assert _no_intermediates_left(job_id)
    assert detail["mediaAvailable"] is True  # the upload is kept for playback


def test_video_job_goes_through_the_same_encode_as_audio(client, video_mp4, stub_cloud, stages):
    job_id = _run(client, video_mp4, "video/mp4")
    assert stages == [
        "VALIDATING", "EXTRACTING_AUDIO", "PREPROCESSING", "TRANSCRIBING", "POST_PROCESSING",
    ]
    assert _detail(client, job_id)["status"] == "COMPLETED"
    sent = stub_cloud[0]["info"].audio_streams[0]
    assert (sent.codec, sent.sample_rate, sent.channels) == ("flac", 16000, 1)
    assert _no_intermediates_left(job_id)


def test_video_audio_keeps_its_position_on_the_video_timeline(video_late_audio, tmp_path):
    # The audio track starts 2 s into the video and the beep is 0.5 s into the track.
    encoded = audio_service.encode_for_api(video_late_audio, tmp_path / "late.flac")
    assert _first_sound_at(encoded) == pytest.approx(2.5, abs=0.15)
    assert probe(encoded).duration == pytest.approx(6.0, abs=0.2)


def test_video_track_selection(video_two_tracks, video_mp4):
    info = probe(video_two_tracks)
    assert [stream.language for stream in info.audio_streams] == ["eng", "hin"]

    # Auto Detect follows the container's default track, not simply the first one.
    assert video_service.select_audio_stream(info).position == 1
    # A chosen language picks the track tagged with it.
    assert video_service.select_audio_stream(info, "en").position == 0
    assert video_service.select_audio_stream(info, "hi").position == 1
    # No track in that language: fall back to the default.
    assert video_service.select_audio_stream(info, "te").position == 1
    assert video_service.select_audio_stream(probe(video_mp4), "te").position == 0


def test_explicit_language_is_passed_strictly(client, tone_wav, stub_cloud):
    job_id = _run(client, tone_wav, "audio/wav", language="te")
    assert stub_cloud[0]["language"] == "te"
    # The job reports the requested language even though the stub answers "hindi".
    assert _detail(client, job_id)["detectedLanguage"] == "te"


def test_language_may_be_sent_by_name(client, tone_wav, stub_cloud):
    job_id = _run(client, tone_wav, "audio/wav", language="Hindi")
    assert stub_cloud[0]["language"] == "hi"
    assert _detail(client, job_id)["detectedLanguage"] == "hi"


def test_auto_detect_of_an_unsupported_language_is_flagged(client, tone_wav, monkeypatch):
    monkeypatch.setattr(
        cloud_transcription_service, "transcribe",
        lambda audio_path, language=None: CloudTranscript(list(SEGMENTS), "azerbaijani"),
    )
    detail = _detail(client, _run(client, tone_wav, "audio/wav"))
    assert detail["status"] == "COMPLETED"
    assert detail["detectedLanguage"] is None
    assert "not one LyricalAI supports" in detail["warning"]


def test_oversized_flac_is_compressed_before_upload(client, noise_mp3, stub_cloud, monkeypatch):
    # 50 s of noise: about 1.6 MB as FLAC, about 0.4 MB as 64 kbps MP3.
    monkeypatch.setattr(get_settings(), "openai_max_upload_mb", 1)
    job_id = _run(client, noise_mp3, "audio/mpeg")
    assert _detail(client, job_id)["status"] == "COMPLETED"
    assert stub_cloud[0]["name"].endswith(".api.mp3")
    assert stub_cloud[0]["info"].duration == pytest.approx(50.0, abs=0.5)
    assert _no_intermediates_left(job_id)


def test_audio_too_big_for_the_api_is_not_sent(client, tone_wav, stub_cloud, monkeypatch):
    monkeypatch.setattr(get_settings(), "openai_max_upload_mb", 0)
    job_id = _run(client, tone_wav, "audio/wav")
    _assert_failed(client, job_id, "too long for the transcription service")
    assert stub_cloud == []


# --- Local backend ------------------------------------------------------------


def test_local_backend_runs_every_stage(client, tone_wav, stub_models, stages):
    job_id = _run(client, tone_wav, "audio/wav")
    assert stages == [
        "VALIDATING", "PREPROCESSING", "SEPARATING_VOCALS",
        "DETECTING_LANGUAGE", "TRANSCRIBING", "POST_PROCESSING",
    ]
    detail = _detail(client, job_id)
    assert detail["status"] == "COMPLETED"
    assert detail["detectedLanguage"] == "hi"
    assert detail["modelName"] == "whisper-small"
    # Demucs received normalised stereo 44.1 kHz audio.
    assert stub_models["separated"][0].duration == pytest.approx(3.0, abs=0.2)
    assert stub_models["separated"][0].audio_streams[0].sample_rate == 44100
    assert _no_intermediates_left(job_id)


def test_local_backend_explicit_language_skips_detection(client, tone_wav, stub_models):
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


# --- Failures -------------------------------------------------------------------


def _assert_failed(client, job_id, expected_fragment):
    detail = _detail(client, job_id)
    assert detail["status"] == JobStatus.FAILED.value
    assert expected_fragment in detail["errorMessage"]
    assert detail["mediaAvailable"] is False  # failed uploads are discarded
    assert _no_intermediates_left(job_id)


def test_corrupt_media_fails_cleanly(client, media_dir, stub_cloud):
    corrupt = media_dir / "corrupt.mp3"
    corrupt.write_bytes(b"this is definitely not audio" * 50)
    job_id = _run(client, corrupt, "audio/mpeg")
    _assert_failed(client, job_id, "corrupt or is not a valid")


def test_video_without_audio_fails_cleanly(client, video_without_audio, stub_cloud):
    job_id = _run(client, video_without_audio, "video/mp4")
    _assert_failed(client, job_id, "no audio track")


def test_silent_audio_fails_cleanly(client, silent_wav, stub_cloud):
    job_id = _run(client, silent_wav, "audio/wav")
    _assert_failed(client, job_id, "silent")
    assert stub_cloud == []  # nothing is sent to the paid API


def test_file_longer_than_the_limit_fails(client, tone_wav, stub_cloud, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_duration_minutes", 0)
    job_id = _run(client, tone_wav, "audio/wav")
    _assert_failed(client, job_id, "too long")


def test_nothing_transcribed_is_reported(client, tone_wav, monkeypatch):
    monkeypatch.setattr(
        cloud_transcription_service, "transcribe",
        lambda *args, **kwargs: CloudTranscript(segments=[], language="english"),
    )
    job_id = _run(client, tone_wav, "audio/wav")
    _assert_failed(client, job_id, "No lyrics could be detected")


def test_unexpected_errors_are_not_leaked(client, tone_wav, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("connection reset at C:\\secret\\path line 42")

    monkeypatch.setattr(cloud_transcription_service, "transcribe", broken)
    job_id = _run(client, tone_wav, "audio/wav")
    detail = _detail(client, job_id)
    assert detail["status"] == "FAILED"
    assert "secret" not in detail["errorMessage"]
    assert "connection" not in detail["errorMessage"]


def test_job_deleted_mid_flight_is_cleaned_up(client, tone_wav, monkeypatch):
    response = upload(client, tone_wav.read_bytes(), tone_wav.name, "audio/wav")
    job_id = response.json()["jobId"]

    def delete_then_transcribe(audio_path, language=None):
        client.delete(f"/api/transcriptions/{job_id}", headers=CLIENT_A)
        return CloudTranscript(segments=list(SEGMENTS), language="english")

    monkeypatch.setattr(cloud_transcription_service, "transcribe", delete_then_transcribe)
    transcription_service.process_job(job_id)  # must not raise

    assert client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_A).status_code == 404
    assert _no_intermediates_left(job_id)
    assert list(storage.storage_dir("uploads").glob(f"{job_id}.*")) == []
