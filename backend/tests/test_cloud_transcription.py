"""The cloud transcription client, with the HTTP call replaced by a recorder."""

import httpx
import pytest

from app.core.config import get_settings
from app.core.exceptions import PipelineError
from app.services import cloud_transcription_service as module
from app.services.cloud_transcription_service import cloud_transcription_service

VERBOSE_JSON = {
    "task": "transcribe",
    "language": "telugu",
    "duration": 4.0,
    "text": "మొదటి పంక్తి రెండవ పంక్తి",
    "segments": [
        {"id": 0, "start": 0.0, "end": 2.1, "text": " మొదటి పంక్తి"},
        {"id": 1, "start": 2.1, "end": 4.0, "text": " రెండవ పంక్తి"},
    ],
}


@pytest.fixture
def audio(tmp_path):
    path = tmp_path / "song.api.flac"
    path.write_bytes(b"fLaC" + b"\x00" * 64)
    return path


@pytest.fixture
def api(monkeypatch):
    """Replaces httpx.post; answers with the queued responses and records each request."""
    recorded: list[dict] = []
    answers: list = []

    def post(url, *, headers, data, files, timeout):
        name, handle = files["file"]
        recorded.append(
            {"url": url, "headers": headers, "data": dict(data), "file": name,
             "bytes": len(handle.read())}
        )
        answer = answers.pop(0) if answers else httpx.Response(200, json=VERBOSE_JSON)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(module.httpx, "post", post)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    return recorded, answers


def test_request_carries_the_strict_language(audio, api):
    recorded, _ = api
    result = cloud_transcription_service.transcribe(audio, "te")

    request = recorded[0]
    assert request["url"] == "https://transcription.invalid/v1/audio/transcriptions"
    assert request["headers"] == {"Authorization": "Bearer test-api-key"}
    assert request["data"] == {
        "model": "whisper-1",
        "response_format": "verbose_json",
        "timestamp_granularities[]": "segment",
        "temperature": "0",
        "language": "te",
    }
    assert request["file"] == "song.api.flac" and request["bytes"] == 68

    assert result.language == "telugu"
    assert [(s.start, s.end, s.text) for s in result.segments] == [
        (0.0, 2.1, " మొదటి పంక్తి"),
        (2.1, 4.0, " రెండవ పంక్తి"),
    ]


def test_auto_detect_sends_no_language(audio, api):
    recorded, _ = api
    cloud_transcription_service.transcribe(audio, None)
    assert "language" not in recorded[0]["data"]


def test_temporary_failures_are_retried(audio, api):
    recorded, answers = api
    answers.extend([httpx.ConnectError("boom"), httpx.Response(503, text="overloaded")])
    assert len(cloud_transcription_service.transcribe(audio, "hi").segments) == 2
    assert len(recorded) == 3


def test_persistent_failure_reports_the_service_as_busy(audio, api):
    recorded, answers = api
    answers.extend([httpx.Response(429, text="rate limited")] * 3)
    with pytest.raises(PipelineError, match="busy right now"):
        cloud_transcription_service.transcribe(audio, "hi")
    assert len(recorded) == 3


def test_bad_key_is_not_retried_and_not_leaked(audio, api):
    recorded, answers = api
    answers.append(httpx.Response(401, text="Incorrect API key provided: test-api-key"))
    with pytest.raises(PipelineError) as raised:
        cloud_transcription_service.transcribe(audio, "hi")
    assert len(recorded) == 1
    assert "not configured" in raised.value.user_message
    assert "test-api-key" not in raised.value.user_message


def test_missing_key_fails_before_any_request(audio, api, monkeypatch):
    recorded, _ = api
    monkeypatch.setattr(get_settings(), "openai_api_key", "")
    with pytest.raises(PipelineError, match="not configured"):
        cloud_transcription_service.transcribe(audio, "hi")
    assert recorded == []
