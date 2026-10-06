from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from tests.conftest import CLIENT_A, upload

FAKE_MP3 = b"ID3" + b"\x00" * 512
ACCOUNT = {"name": "Asha", "email": "Asha@Example.com", "password": "correct horse"}


def _register(client, **overrides):
    return client.post("/api/auth/register", json={**ACCOUNT, **overrides})


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_password_hashing_round_trip():
    hashed = hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert verify_password("s3cret-password", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("anything", "not-a-bcrypt-hash")


def test_register_returns_token_and_never_the_password(client, db):
    response = _register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["tokenType"] == "bearer"
    assert body["user"]["email"] == "asha@example.com"
    assert "password" not in str(body).lower()

    stored = db.query(User).one()
    assert stored.password_hash != ACCOUNT["password"]
    assert stored.password_hash.startswith("$2")


def test_register_validates_input(client):
    assert _register(client, password="short").status_code == 422
    assert _register(client, email="not-an-email").status_code == 422
    assert _register(client, name="   ").status_code == 422


def test_duplicate_email_is_rejected(client):
    assert _register(client).status_code == 201
    duplicate = _register(client, email="asha@example.com")
    assert duplicate.status_code == 409


def test_login_and_me(client):
    _register(client)
    wrong = client.post(
        "/api/auth/login", json={"email": ACCOUNT["email"], "password": "wrong password"}
    )
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "INVALID_CREDENTIALS"

    unknown = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever1"}
    )
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]

    login = client.post(
        "/api/auth/login", json={"email": ACCOUNT["email"], "password": ACCOUNT["password"]}
    )
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers=_bearer(login.json()["accessToken"]))
    assert me.json()["name"] == "Asha"


def test_me_requires_a_valid_token(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=_bearer("garbage")).status_code == 401
    # A well-formed token for a user that does not exist.
    assert client.get("/api/auth/me", headers=_bearer(create_access_token(999))).status_code == 401


def test_users_only_see_and_delete_their_own_jobs(client):
    asha = _register(client).json()["accessToken"]
    ravi = _register(client, name="Ravi", email="ravi@example.com").json()["accessToken"]

    job_id = upload(
        client, FAKE_MP3, "song.mp3", "audio/mpeg", headers={**CLIENT_A, **_bearer(asha)}
    ).json()["jobId"]

    assert client.get("/api/transcriptions", headers=_bearer(asha)).json()["total"] == 1
    assert client.get("/api/transcriptions", headers=_bearer(ravi)).json()["total"] == 0
    # The anonymous client id alone no longer grants access to an account's job.
    assert client.get(f"/api/transcriptions/{job_id}", headers=CLIENT_A).status_code == 404
    assert client.delete(f"/api/transcriptions/{job_id}", headers=_bearer(ravi)).status_code == 404
    assert client.delete(f"/api/transcriptions/{job_id}", headers=_bearer(asha)).status_code == 204
