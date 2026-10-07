from app.models import JobStatus, TranscriptionJob, TranscriptionResult, TranscriptionSegment
from app.utils import storage
from tests.conftest import CLIENT_A, CLIENT_B, new_job_id, upload

FAKE_MP3 = b"ID3" + b"\x00" * 2048


def _complete(db, job_id: str) -> None:
    """Give a job the rows the pipeline would have written."""
    job = db.get(TranscriptionJob, job_id)
    job.status = JobStatus.COMPLETED.value
    job.detected_language = "te"
    job.duration = 30.0
    job.segments = [
        TranscriptionSegment(sequence_number=0, start_time=12.3, end_time=17.2, text="మొదటి పంక్తి"),
        TranscriptionSegment(sequence_number=1, start_time=17.2, end_time=23.0, text="రెండవ పంక్తి"),
    ]
    job.result = TranscriptionResult(
        full_text="మొదటి పంక్తి\nరెండవ పంక్తి",
        model_name="whisper-small",
        device="cpu",
        processing_time=4.2,
    )
    db.commit()


def test_health(client):
    body = client.get("/api/health").json()
    assert body["database"] == "ok"
    assert body["status"] == "ok"
    assert body["device"] == "cloud"
    assert body["whisperModel"] == "whisper-1"
    assert body["modelsLoaded"] == {"whisper": False, "demucs": False}


def test_public_config(client):
    body = client.get("/api/config").json()
    assert body["maxFileSizeMb"] == 1
    assert [language["code"] for language in body["languages"]] == ["en", "hi", "te"]
    assert ".mp3" in body["audioExtensions"]
    assert ".mp4" in body["videoExtensions"]


def test_openapi_docs_are_served(client):
    assert client.get("/api/docs").status_code == 200
    assert client.get("/api/redoc").status_code == 200
    assert "/api/transcriptions" in client.get("/api/openapi.json").json()["paths"]


def test_upload_returns_queued_job_immediately(client, clean_state):
    response = upload(client, FAKE_MP3, "song.mp3", "audio/mpeg", language="hi")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "QUEUED"
    assert clean_state == [body["jobId"]]  # handed to the background worker

    status = client.get(f"/api/transcriptions/{body['jobId']}/status", headers=CLIENT_A).json()
    assert status["status"] == "QUEUED"
    assert status["fileType"] == "audio"
    assert status["queuePosition"] == 0
    assert status["transcriptionProgress"] is None
    assert storage.upload_path(f"{body['jobId']}.mp3").is_file()


def test_upload_rejects_unsupported_extension(client):
    response = upload(client, b"hello", "notes.txt", "text/plain")
    assert response.status_code == 415
    assert response.json()["code"] == "UNSUPPORTED_FILE"


def test_upload_rejects_mismatched_mime_type(client):
    response = upload(client, FAKE_MP3, "song.mp3", "text/html")
    assert response.status_code == 415


def test_upload_rejects_empty_file(client):
    response = upload(client, b"", "song.mp3", "audio/mpeg")
    assert response.status_code == 400
    assert response.json()["code"] == "EMPTY_FILE"


def test_upload_accepts_a_language_name(client, db):
    response = upload(client, FAKE_MP3, "song.mp3", "audio/mpeg", language=" Telugu ")
    assert response.status_code == 202
    assert db.get(TranscriptionJob, response.json()["jobId"]).requested_language == "te"


def test_upload_rejects_unknown_language(client):
    response = upload(client, FAKE_MP3, "song.mp3", "audio/mpeg", language="fr")
    assert response.status_code == 400
    assert response.json()["code"] == "UNSUPPORTED_LANGUAGE"


def test_upload_rejects_oversized_file(client):
    # The limit is 1 MB in tests; this also exceeds the Content-Length pre-check.
    response = upload(client, b"\x00" * (3 * 1024 * 1024), "song.mp3", "audio/mpeg")
    assert response.status_code == 413
    assert response.json()["code"] == "FILE_TOO_LARGE"
    assert list(storage.storage_dir("uploads").glob("*.mp3")) == []


def test_upload_just_over_the_limit_is_rejected_and_removed(client):
    response = upload(client, b"\x00" * (1024 * 1024 + 10), "song.mp3", "audio/mpeg")
    assert response.status_code == 413
    assert list(storage.storage_dir("uploads").glob("*.mp3")) == []


def test_missing_file_is_a_clean_validation_error(client):
    response = client.post("/api/transcriptions", data={"language": "auto"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body["detail"], str)


def test_unknown_job_is_404(client):
    for job_id in (new_job_id(), "not-a-uuid", "..%2F..%2Fetc"):
        response = client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_A)
        assert response.status_code == 404
        assert set(response.json()) == {"detail", "code"}


def test_jobs_are_private_to_the_client_that_created_them(client):
    job_id = upload(client, FAKE_MP3, "mine.mp3", "audio/mpeg").json()["jobId"]

    assert client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_A).status_code == 200
    assert client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_B).status_code == 404
    assert client.get(f"/api/transcriptions/{job_id}").status_code == 404
    assert client.delete(f"/api/transcriptions/{job_id}", headers=CLIENT_B).status_code == 404

    assert client.get("/api/transcriptions", headers=CLIENT_A).json()["total"] == 1
    assert client.get("/api/transcriptions", headers=CLIENT_B).json()["total"] == 0
    assert client.get("/api/transcriptions").json() == {"items": [], "total": 0}


def test_result_and_history_for_completed_job(client, db):
    job_id = upload(client, FAKE_MP3, "పాట.mp3", "audio/mpeg").json()["jobId"]
    _complete(db, job_id)

    detail = client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_A).json()
    assert detail["status"] == "COMPLETED"
    assert detail["originalFilename"] == "పాట.mp3"
    assert detail["detectedLanguage"] == "te"
    assert detail["languageName"] == "Telugu"
    assert detail["modelName"] == "whisper-small"
    assert detail["mediaAvailable"] is True
    assert detail["segments"][0] == {"index": 0, "start": 12.3, "end": 17.2, "text": "మొదటి పంక్తి"}
    assert detail["fullText"].splitlines() == ["మొదటి పంక్తి", "రెండవ పంక్తి"]

    history = client.get("/api/transcriptions", headers=CLIENT_A).json()
    assert history["total"] == 1
    assert history["items"][0]["preview"] == "మొదటి పంక్తి / రెండవ పంక్తి"


def test_history_is_paginated_newest_first(client):
    ids = [upload(client, FAKE_MP3, f"{n}.mp3", "audio/mpeg").json()["jobId"] for n in range(3)]
    page = client.get("/api/transcriptions?limit=2&offset=0", headers=CLIENT_A).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    rest = client.get("/api/transcriptions?limit=2&offset=2", headers=CLIENT_A).json()
    assert {item["jobId"] for item in page["items"] + rest["items"]} == set(ids)
    assert client.get("/api/transcriptions?limit=0", headers=CLIENT_A).status_code == 422


def test_downloads_require_a_completed_job(client):
    job_id = upload(client, FAKE_MP3, "song.mp3", "audio/mpeg").json()["jobId"]
    response = client.get(f"/api/transcriptions/{job_id}/download/srt", headers=CLIENT_A)
    assert response.status_code == 409
    assert response.json()["code"] == "NOT_READY"


def test_txt_srt_and_vtt_downloads(client, db):
    job_id = upload(client, FAKE_MP3, "My Song.mp3", "audio/mpeg").json()["jobId"]
    _complete(db, job_id)
    base = f"/api/transcriptions/{job_id}/download"

    txt = client.get(f"{base}/txt", headers=CLIENT_A)
    assert txt.status_code == 200
    assert txt.headers["content-disposition"] == 'attachment; filename="My_Song.txt"'
    assert txt.text == "మొదటి పంక్తి\nరెండవ పంక్తి\n"

    stamped = client.get(f"{base}/txt?timestamps=true", headers=CLIENT_A)
    assert stamped.text.startswith("[00:12] మొదటి పంక్తి")

    srt = client.get(f"{base}/srt", headers=CLIENT_A)
    assert srt.headers["content-disposition"] == 'attachment; filename="My_Song.srt"'
    assert srt.text.startswith("1\n00:00:12,300 --> 00:00:17,200\nమొదటి పంక్తి\n")

    vtt = client.get(f"{base}/vtt", headers=CLIENT_A)
    assert vtt.text.startswith("WEBVTT")

    assert client.get(f"{base}/srt", headers=CLIENT_B).status_code == 404


def test_media_streaming_supports_range_requests(client):
    job_id = upload(client, FAKE_MP3, "song.mp3", "audio/mpeg").json()["jobId"]

    full = client.get(f"/api/transcriptions/{job_id}/media")
    assert full.status_code == 200
    assert full.headers["content-type"] == "audio/mpeg"
    assert full.content == FAKE_MP3

    partial = client.get(f"/api/transcriptions/{job_id}/media", headers={"Range": "bytes=0-2"})
    assert partial.status_code == 206
    assert partial.content == b"ID3"


def test_delete_removes_job_and_files(client):
    job_id = upload(client, FAKE_MP3, "song.mp3", "audio/mpeg").json()["jobId"]
    assert client.delete(f"/api/transcriptions/{job_id}", headers=CLIENT_A).status_code == 204
    assert client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_A).status_code == 404
    assert client.get(f"/api/transcriptions/{job_id}/media").status_code == 404
    assert not storage.upload_path(f"{job_id}.mp3").exists()


def test_queue_position_counts_jobs_ahead(client):
    first = upload(client, FAKE_MP3, "1.mp3", "audio/mpeg").json()["jobId"]
    second = upload(client, FAKE_MP3, "2.mp3", "audio/mpeg").json()["jobId"]
    assert client.get(f"/api/transcriptions/{first}/status", headers=CLIENT_A).json()["queuePosition"] == 0
    assert client.get(f"/api/transcriptions/{second}/status", headers=CLIENT_A).json()["queuePosition"] == 1


def test_cors_allows_the_configured_origin_only(client):
    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in denied.headers
