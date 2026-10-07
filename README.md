# LyricalAI

**An end-to-end multilingual automatic lyric transcription system.**

Upload a song or a music video and get timestamped lyrics back. LyricalAI extracts the
audio with **FFmpeg**, isolates the singing voice with **Demucs**, and transcribes it with
**Whisper** in **English, Hindi or Telugu** - then shows the lyrics in sync with playback
and lets you download them as TXT, SRT or VTT.

Everything runs on your own machine or server. No paid AI API is involved.

---

## Contents

1. [Quick start (Docker)](#1-quick-start-docker)
2. [Using the app](#2-using-the-app)
3. [Run locally without Docker](#3-run-locally-without-docker)
4. [Features](#4-features)
5. [Architecture](#5-architecture)
6. [AI pipeline](#6-ai-pipeline)
7. [Environment variables](#7-environment-variables)
8. [Model configuration and GPU](#8-model-configuration-and-gpu)
9. [API](#9-api)
10. [Database](#10-database)
11. [Production deployment and HTTPS](#11-production-deployment-and-https)
12. [Testing](#12-testing)
13. [Evaluation (WER / CER)](#13-evaluation-wer--cer)
14. [Troubleshooting](#14-troubleshooting)
15. [Limitations](#15-limitations)
16. [Future scope](#16-future-scope)

---

## 1. Quick start (Docker)

This is the easiest way to run LyricalAI, and it is exactly what you deploy. You only
need [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / macOS)
or Docker Engine with the Compose plugin (Linux). Python, Node, PostgreSQL and FFmpeg all
live inside the containers.

```bash
cd lyrical-ai

# 1. Create your environment file (a .env with placeholder values is already present;
#    if it is missing, copy the example)
cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env

# 2. Open .env and change at least these two placeholders
#       POSTGRES_PASSWORD=change_me
#       JWT_SECRET_KEY=change_me_to_a_long_random_string

# 3. Build and start
docker compose up --build
```

Then open **http://localhost:8080**.

| What                | URL                              |
| ------------------- | -------------------------------- |
| Web app             | http://localhost:8080            |
| API docs (Swagger)  | http://localhost:8080/docs       |
| API docs (ReDoc)    | http://localhost:8080/redoc      |
| Health check        | http://localhost:8080/api/health |

**First start takes a while.** The first build downloads PyTorch and friends (the backend
image is about 2.6 GB), and on first start the backend downloads the model weights
(about 550 MB for the default models) into a Docker volume. Both happen only once.
`http://localhost:8080/api/health` shows `"modelsLoaded": {"whisper": true, "demucs": true}`
when the models are ready; uploads made before that simply wait in the queue.

Useful commands:

```bash
docker compose up -d --build     # run in the background
docker compose logs -f backend   # follow the processing logs
docker compose down              # stop (data is kept)
docker compose down -v           # stop and delete database, uploads and model cache
```

> Change the port with `APP_PORT` in `.env` if 8080 is taken.
> Changing `POSTGRES_PASSWORD` after the first start does not change the password of the
> already-created database; either keep it, or run `docker compose down -v` to start fresh.

---

## 2. Using the app

1. Open the site and click **Generate Lyrics** (or go to **Upload**).
2. Drag in or browse for a file:
   - audio: MP3, WAV, M4A, AAC, FLAC
   - video: MP4, MOV, MKV (the audio is extracted for you - no manual conversion)
   - up to 50 MB and 15 minutes by default
3. Pick the language - **Auto Detect**, English, Hindi or Telugu. If you know the
   language, choosing it is more reliable than auto-detection.
4. Click **Generate Lyrics**. The processing page shows the real backend stage:
   validating, extracting audio (video only), preprocessing, separating vocals,
   detecting language, transcribing (with a real progress bar) and post-processing.
5. On the result page:
   - play the audio/video; the current lyric line is highlighted and scrolls into view
   - click any line to jump to that moment
   - **Copy** the lyrics, or download **TXT**, **SRT** or **VTT**
6. **History** lists your earlier transcriptions; view, download or delete them.

**Accounts are optional.** Without logging in, your history is tied to your browser
(an anonymous id stored in local storage). If you register and log in, new
transcriptions are saved to your account and are available from any browser.

**How long does it take?** On a CPU, expect roughly 0.5x-1.5x the song's length with the
default `small` model (a 4-minute song takes about 2-6 minutes). A GPU is many times faster.
Jobs are processed one at a time; others wait in a queue and show their position.

---

## 3. Run locally without Docker

Use this for development. You need:

- **Python 3.11 or 3.12** (PyTorch/Demucs wheels are not available for every newer version)
- **Node.js 20+**
- **FFmpeg** on your `PATH` (`ffmpeg -version` must work)
  - Windows: `winget install Gyan.FFmpeg` - macOS: `brew install ffmpeg` - Ubuntu: `sudo apt install ffmpeg`

No PostgreSQL is needed locally: `backend/.env` defaults to a SQLite file.

### Backend (terminal 1)

Windows PowerShell:

```powershell
cd lyrical-ai\backend
py -3.11 -m venv .venv            # or: uv venv --python 3.11 .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt -c constraints.txt
Copy-Item .env.example .env       # already present with placeholder values; skip if it exists
uvicorn app.main:app --reload --port 8000
```

macOS / Linux:

```bash
cd lyrical-ai/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt -c constraints.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

> If you created the environment with `uv`, install with
> `uv pip install -r requirements-dev.txt -c constraints.txt` instead of `pip`.

The API is now on http://localhost:8000 (docs at http://localhost:8000/docs). Database
tables are created automatically on start-up (Alembic migrations).

### Frontend (terminal 2)

```bash
cd lyrical-ai/frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The dev server proxies `/api` to `http://localhost:8000`.

The first upload downloads the model weights (about 550 MB) into `lyrical-ai/models/`,
so it is slow once and fast afterwards.

---

## 4. Features

- Audio upload (MP3, WAV, M4A, AAC, FLAC) and video upload (MP4, MOV, MKV)
- Automatic video-to-audio extraction (FFmpeg)
- Vocal separation (Demucs) before transcription, with an automatic fallback to the
  full mix (and a visible warning) if separation fails
- Lyric transcription with Whisper in English, Hindi and Telugu
- Automatic language detection or explicit language selection
- Timestamped lyrics, synchronised and highlighted during audio/video playback
- Copy to clipboard; TXT, SRT and VTT downloads built from the real segment timestamps
- Background processing with real, stage-by-stage status and a queue
- History with view / download / delete, private per browser or per account
- Optional accounts (JWT + bcrypt)
- PostgreSQL persistence with Alembic migrations
- Automatic cleanup of intermediate files and of old uploads
- Responsive, accessible dark UI
- OpenAPI docs, structured logs, clean error messages (no stack traces)
- CPU by default, optional NVIDIA GPU
- One-command Docker deployment behind Nginx

---

## 5. Architecture

```
Browser ── React + TypeScript + Tailwind (Vite build, served by Nginx)
   │
   │  REST  /api/*
   ▼
Nginx (frontend container) ── reverse proxy, upload limit, rate limit on /api/auth
   │
   ▼
FastAPI (backend container, not exposed publicly)
   ├── File handling & validation
   ├── Authentication (optional, JWT)
   ├── Job management (single background worker thread + queue)
   ├── Database access (SQLAlchemy)
   └── AI pipeline ── FFmpeg → Demucs → Whisper
   │
   ▼
PostgreSQL (postgres container)
```

One Python service does both the API and the AI work - no microservices, no message
broker. Jobs run one at a time on a worker thread inside the API process, so each model
is loaded exactly once and reused for every request.

### Technology stack

| Layer      | Technology                                                               |
| ---------- | ------------------------------------------------------------------------ |
| Frontend   | React 18, TypeScript, Vite, Tailwind CSS, React Router, Lucide, Axios     |
| Backend    | Python 3.11, FastAPI, Uvicorn, Pydantic                                   |
| AI / audio | PyTorch, Demucs (`htdemucs`), Whisper via faster-whisper, FFmpeg          |
| Database   | PostgreSQL 16, SQLAlchemy 2, Alembic                                      |
| Deployment | Docker, Docker Compose, Nginx                                             |
| Tests      | pytest, Vitest + Testing Library                                          |

> **Whisper implementation.** LyricalAI uses [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
> an open-source re-implementation that runs OpenAI's original Whisper weights on the
> CTranslate2 engine. Same models and accuracy, roughly 4x faster on CPU with less memory.

### Project layout

```
lyrical-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                  # app factory, lifecycle, error handlers
│   │   ├── api/routes/              # auth, transcription, history, health
│   │   ├── core/                    # config, security, logging, errors, middleware
│   │   ├── models/                  # SQLAlchemy models
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── services/                # pipeline, FFmpeg, Demucs, Whisper, lyrics, queue, cleanup
│   │   ├── database/                # engine, session, migrations runner
│   │   └── utils/                   # file validation, storage paths, ffmpeg wrapper
│   ├── alembic/                     # database migrations
│   ├── evaluation/                  # WER/CER research script + dataset format
│   ├── tests/
│   ├── requirements.txt  constraints.txt  Dockerfile  .env.example
├── frontend/
│   ├── src/ (components, pages, hooks, services, types, utils)
│   └── Dockerfile
├── nginx/nginx.conf
├── storage/                         # local-dev uploads (Docker uses a volume)
├── docker-compose.yml
├── docker-compose.gpu.yml           # optional GPU override
├── .env.example
└── README.md
```

---

## 6. AI pipeline

```
Upload ─► VALIDATING ─► EXTRACTING_AUDIO ─► PREPROCESSING ─► SEPARATING_VOCALS
                         (video only)
        ─► DETECTING_LANGUAGE ─► TRANSCRIBING ─► POST_PROCESSING ─► COMPLETED
                                                    (any failure ─► FAILED)
```

| Stage              | What really happens                                                                                    |
| ------------------ | ------------------------------------------------------------------------------------------------------ |
| QUEUED             | The upload is saved and the job id is returned immediately.                                             |
| VALIDATING         | `ffprobe` checks the file decodes, has an audio stream and is within the length limit.                   |
| EXTRACTING_AUDIO   | Video only: the audio track to use is chosen (the one tagged with the selected language, else the default track). It is decoded straight from the video, on the video's timeline, by the same FFmpeg pass audio uploads go through. |
| PREPROCESSING      | Silence check, then one FFmpeg pass: loudness normalisation and conversion to mono 16 kHz FLAC (cloud) or stereo 44.1 kHz WAV (local). |
| SEPARATING_VOCALS  | Local backend only: Demucs splits the song into stems; only the vocal stem is kept.                     |
| DETECTING_LANGUAGE | Local backend only: with Auto Detect, Whisper picks the most likely of the supported languages.         |
| TRANSCRIBING       | Whisper (cloud API or local model) transcribes the audio into segments with start/end times. A selected language is passed as Whisper's `language`, which turns language detection off for that job. |
| POST_PROCESSING    | Whitespace/punctuation clean-up, removal of known artifacts ("[Music]", "Thanks for watching"), merging of tiny fragments. Repeated lines are kept; nothing is invented. |
| COMPLETED / FAILED | Lyrics and segments are stored; intermediate files are deleted.                                         |

**Backends.** `TRANSCRIPTION_BACKEND=cloud` (default) sends the audio to an
OpenAI-compatible Whisper API and loads no model, so the backend runs in a few hundred
MB of RAM. `TRANSCRIPTION_BACKEND=local` runs Demucs + Whisper in-process; it needs
`backend/requirements-local.txt` (Docker: `INSTALL_LOCAL_MODELS=true`) and the RAM
described in section 8.

**Fallback.** With the local backend, if Demucs fails (for example, out of memory) and `ENABLE_SEPARATION_FALLBACK=true`,
the full mix is transcribed instead and the result carries a warning that accuracy may be lower.

**Supported languages.** English (`en`), Hindi (`hi`), Telugu (`te`). To add another
Whisper language, add one line to `SUPPORTED_LANGUAGES` in
`backend/app/services/language_service.py`; the API and UI pick it up automatically.

---

## 7. Environment variables

Docker reads the root **`.env`**. Local (non-Docker) development reads **`backend/.env`**.
Both files ship with placeholder values and are git-ignored - **never commit them**.

| Variable                     | Default (Docker)          | Purpose                                                                 |
| ---------------------------- | ------------------------- | ----------------------------------------------------------------------- |
| `POSTGRES_DB`                | `lyricalai`               | Database name                                                           |
| `POSTGRES_USER`              | `lyricalai`               | Database user                                                           |
| `POSTGRES_PASSWORD`          | `change_me`               | **Change this.** Database password                                      |
| `DATABASE_URL`               | *(empty)*                 | Optional full URL for an external database; empty = bundled Postgres    |
| `JWT_SECRET_KEY`             | `change_me_to_...`        | **Change this.** Signs login tokens                                     |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `10080`                   | Login lifetime (7 days)                                                 |
| `CORS_ORIGINS`               | `http://localhost:5173,…` | Comma-separated origins allowed to call the API cross-origin            |
| `MAX_FILE_SIZE_MB`           | `50`                      | Upload size limit                                                       |
| `NGINX_CLIENT_MAX_BODY_SIZE` | `60m`                     | Nginx request limit; keep slightly above `MAX_FILE_SIZE_MB`             |
| `MAX_DURATION_MINUTES`       | `15`                      | Longest audio/video accepted                                            |
| `FILE_RETENTION_HOURS`       | `72`                      | How long uploads are kept for playback (lyrics are kept until deleted)  |
| `STORAGE_PATH`               | `/app/storage`            | Where uploads and working files live                                    |
| `TRANSCRIPTION_BACKEND`      | `cloud`                   | `cloud` (Whisper API, no local model) or `local` (Demucs + Whisper)     |
| `OPENAI_API_KEY`             | *(empty)*                 | **Set this.** API key for the cloud transcription service               |
| `OPENAI_BASE_URL`            | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint, e.g. `https://api.groq.com/openai/v1` |
| `OPENAI_TRANSCRIPTION_MODEL` | `whisper-1`               | Model name; must return segment timestamps (`verbose_json`)             |
| `INSTALL_LOCAL_MODELS`       | `false`                   | Docker build: install PyTorch, Demucs and Whisper for the local backend |
| `WHISPER_MODEL`              | `small`                   | Local only: `tiny`, `base`, `small` or `medium`                         |
| `DEVICE`                     | `auto`                    | Local only: `auto`, `cpu` or `cuda`                                     |
| `DEMUCS_MODEL`               | `htdemucs`                | Local only: Demucs model name                                           |
| `PRELOAD_MODELS`             | `true`                    | Local only: load models at start-up instead of on the first upload      |
| `ENABLE_SEPARATION_FALLBACK` | `true`                    | Local only: transcribe the full mix if Demucs fails                     |
| `MODEL_CACHE_DIR`            | `/app/models` (volume)    | Local only: where model weights are stored                              |
| `APP_PORT` / `APP_BIND`      | `8080` / `0.0.0.0`        | Host port / address the site is published on                            |
| `LOG_LEVEL`                  | `INFO`                    | Log verbosity                                                           |

Generate a strong secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

---

## 8. Model configuration and GPU

This section applies to `TRANSCRIPTION_BACKEND=local` only. The default cloud backend
loads no model and needs none of this.

| `WHISPER_MODEL` | Download | RAM (CPU, approx.) | Notes                                                |
| --------------- | -------- | ------------------ | ---------------------------------------------------- |
| `tiny`          | 75 MB    | 1 GB               | Fastest; weak on Hindi/Telugu                        |
| `base`          | 145 MB   | 1 GB               | Fast; fine for clear English                         |
| `small`         | 465 MB   | 2 GB               | **Default** - best CPU trade-off                     |
| `medium`        | 1.5 GB   | 5 GB               | Noticeably better for Hindi/Telugu; slow without GPU |

Demucs (`htdemucs`) adds about 80 MB of weights and 2-3 GB of RAM while separating.
**Plan for at least 4 GB of RAM (8 GB recommended) for the backend container.**

Models are downloaded once, cached (`model_cache` volume in Docker, `models/` locally),
loaded once per process and reused for every job.

**GPU (optional).** With an NVIDIA GPU and the
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
installed on the host:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

`DEVICE=auto` then selects CUDA automatically, and falls back to CPU if it cannot be used.
The GPU override was written to the libraries' documentation but has not been run on GPU
hardware; check `docker compose logs backend` for `loaded on cuda` after the first job.

---

## 9. API

Interactive documentation is generated by FastAPI: **`/docs`** (Swagger UI) and
**`/redoc`**. All endpoints are under `/api`.

| Method   | Path                                        | Description                                        |
| -------- | ------------------------------------------- | -------------------------------------------------- |
| `GET`    | `/api/health`                               | Database, FFmpeg, device and model status          |
| `GET`    | `/api/config`                               | Upload limits, supported languages and file types  |
| `POST`   | `/api/transcriptions`                       | Upload a file (`file`, `language`) → `202` + job id |
| `GET`    | `/api/transcriptions/{jobId}/status`        | Current stage, progress, queue position            |
| `GET`    | `/api/transcriptions/{jobId}`               | Job details, full text and timestamped segments    |
| `GET`    | `/api/transcriptions`                       | Your history (`limit`, `offset`)                   |
| `DELETE` | `/api/transcriptions/{jobId}`               | Delete a job, its lyrics and its files             |
| `GET`    | `/api/transcriptions/{jobId}/download/txt`  | Lyrics as text (`?timestamps=true` for `[mm:ss]`)  |
| `GET`    | `/api/transcriptions/{jobId}/download/srt`  | Lyrics as SubRip subtitles                         |
| `GET`    | `/api/transcriptions/{jobId}/download/vtt`  | Lyrics as WebVTT subtitles                         |
| `GET`    | `/api/transcriptions/{jobId}/media`         | Stream the original upload (supports Range)        |
| `POST`   | `/api/auth/register`                        | Create an account → token                          |
| `POST`   | `/api/auth/login`                           | Log in → token                                     |
| `GET`    | `/api/auth/me`                              | Current user                                       |

Example:

```bash
# Upload
curl -X POST http://localhost:8080/api/transcriptions \
  -H "X-Client-Id: my-client-0001" \
  -F "file=@song.mp3" -F "language=auto"
# → {"jobId":"1fd5f0a1-…","status":"QUEUED","createdAt":"…"}

# Poll
curl -H "X-Client-Id: my-client-0001" http://localhost:8080/api/transcriptions/<jobId>/status

# Result
curl -H "X-Client-Id: my-client-0001" http://localhost:8080/api/transcriptions/<jobId>
# → {"detectedLanguage":"te","duration":212.4,"modelName":"whisper-small",
#    "fullText":"…","segments":[{"index":0,"start":12.3,"end":17.2,"text":"…"}], …}
```

**Identity.** Requests carry either `Authorization: Bearer <token>` (logged-in user) or an
anonymous `X-Client-Id` header (8-64 letters, digits, `-` or `_`). Jobs are only visible to
the identity that created them; anyone else gets `404`. The media endpoint is keyed by the
unguessable job id alone, because `<audio>`/`<video>` elements cannot send headers.

**Errors** always have the same shape and never contain stack traces or file paths:

```json
{ "detail": "The file is too large. The maximum size is 50 MB.", "code": "FILE_TOO_LARGE" }
```

---

## 10. Database

PostgreSQL in Docker (SQLite by default for local development). The schema is managed by
Alembic and applied automatically when the backend starts.

| Table                    | Columns                                                                                                   |
| ------------------------ | --------------------------------------------------------------------------------------------------------- |
| `users`                  | `id`, `name`, `email` (unique), `password_hash`, `created_at`                                              |
| `transcription_jobs`     | `id` (UUID), `user_id`, `client_id`, `original_filename`, `stored_filename`, `file_type`, `file_size`, `requested_language`, `detected_language`, `status`, `transcription_progress`, `duration`, `warning`, `error_message`, `created_at`, `started_at`, `completed_at` |
| `transcription_segments` | `id`, `job_id`, `sequence_number`, `start_time`, `end_time`, `text`                                        |
| `transcription_results`  | `id`, `job_id`, `full_text`, `model_name`, `device`, `processing_time`, `created_at`                        |

Create a new migration after changing the models:

```bash
cd backend
alembic revision --autogenerate -m "describe the change"
```

Back up the Docker database:

```bash
docker compose exec postgres pg_dump -U lyricalai lyricalai > backup.sql
```

---

## 11. Production deployment and HTTPS

Target: an Ubuntu server with Docker. **Recommended size: 4 vCPU, 8 GB RAM, 20 GB disk**
(2 vCPU / 4 GB works with `WHISPER_MODEL=base`, slowly).

```bash
# 1. Install Docker (once)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

# 2. Copy the project to the server (git clone, scp, rsync …) and enter it
cd lyrical-ai

# 3. Configure
cp .env.example .env
nano .env
#   POSTGRES_PASSWORD=<long random password>
#   JWT_SECRET_KEY=<output of: python3 -c "import secrets; print(secrets.token_urlsafe(48))">
#   CORS_ORIGINS=https://your-domain.example
#   APP_BIND=127.0.0.1        # only the host's HTTPS proxy may reach the app
#   APP_PORT=8080

# 4. Start
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8080/api/health
```

Only the Nginx container publishes a port. The AI backend and PostgreSQL are reachable
only on the internal Docker network.

### HTTPS with Nginx and Let's Encrypt

Terminate TLS on the host and proxy to the app. Replace `your-domain.example` with your
domain (its DNS A record must already point at the server).

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
sudo nano /etc/nginx/sites-available/lyricalai
```

```nginx
server {
    listen 80;
    server_name your-domain.example;

    client_max_body_size 60m;          # match NGINX_CLIENT_MAX_BODY_SIZE

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_request_buffering off;
        proxy_read_timeout 300s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/lyricalai /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Obtain the certificate and let certbot switch the site to HTTPS
sudo certbot --nginx -d your-domain.example

# Renewal is automatic; verify it with
sudo certbot renew --dry-run
```

Open only ports 80 and 443 in the firewall (`sudo ufw allow 'Nginx Full'`).

### Updating

```bash
git pull            # or copy the new files
docker compose up -d --build
```

Uploads, the database and the model cache live in Docker volumes and survive rebuilds.

### Production checklist

- [ ] `POSTGRES_PASSWORD` and `JWT_SECRET_KEY` are long, random and not the placeholders
- [ ] `.env` is not committed anywhere
- [ ] `APP_BIND=127.0.0.1` and HTTPS is terminated by the host Nginx
- [ ] `CORS_ORIGINS` is your real `https://` origin
- [ ] The firewall exposes only 80/443 (and SSH)
- [ ] Database backups are scheduled

---

## 12. Testing

### Backend

```bash
cd backend
pytest                      # 77 tests, about 10 seconds
```

Covers file validation, filename sanitising and path-traversal protection, every API
endpoint, error formats, ownership rules, authentication, job status, history,
TXT/SRT/VTT generation, media range requests, and the full pipeline against **real
FFmpeg** (audio, video, corrupt files, silent files, videos without audio, fallback,
mid-job deletion). In these fast tests Demucs and Whisper are replaced by stubs.

The real models are exercised by an opt-in end-to-end test (slow; downloads the weights):

```bash
# PowerShell:  $env:LYRICALAI_TEST_AUDIO="C:\path\song.mp3"; pytest -m integration
LYRICALAI_TEST_AUDIO=/path/to/song.mp3 LYRICALAI_TEST_LANGUAGE=en pytest -m integration
```

### Frontend

```bash
cd frontend
npm test                    # Vitest: upload validation, language selector,
                            # processing status, lyrics rendering/highlighting
npm run build               # type-check + production build
```

---

## 13. Evaluation (WER / CER)

`backend/evaluation/evaluate.py` measures whether vocal separation helps. For every sample
it runs both pipelines and records word error rate, character error rate, processing time,
audio duration, model and device:

- **baseline**: song → Whisper
- **separated**: song → Demucs → vocals → Whisper

```bash
cd backend
cp evaluation/dataset/manifest.example.json evaluation/dataset/manifest.json
# add your audio + ground-truth lyrics (see evaluation/dataset/README.md), then:
python -m evaluation.evaluate --manifest evaluation/dataset/manifest.json
python -m evaluation.evaluate --language-mode auto      # also tests language detection
```

It prints a per-sample table and per-language averages and writes JSON + CSV to
`evaluation/results/`. CER is the more informative metric for Hindi and Telugu.

**No audio ships with the project**: songs are copyrighted and must not be redistributed.
`evaluation/dataset/README.md` explains the format and where to find legally usable
recordings (your own, Creative Commons, public domain).

---

## 14. Troubleshooting

| Symptom                                              | Fix                                                                                                             |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| `docker compose up` says `Set POSTGRES_PASSWORD`     | The root `.env` is missing: `cp .env.example .env`.                                                              |
| Port 8080 is already in use                          | Set `APP_PORT=9090` (any free port) in `.env`.                                                                   |
| Backend restarts / "password authentication failed"  | `POSTGRES_PASSWORD` was changed after the database was created. Restore it, or `docker compose down -v`.         |
| First job sits in "Separating vocals" for minutes    | Models are still downloading. Watch `docker compose logs -f backend`.                                           |
| Backend container is killed during a job             | Out of memory. Give Docker more RAM (Docker Desktop → Settings → Resources) or use `WHISPER_MODEL=base`.         |
| "The file is too large" / HTTP 413                   | Raise `MAX_FILE_SIZE_MB` **and** `NGINX_CLIENT_MAX_BODY_SIZE` (and the host Nginx limit, if used).               |
| "This file is too long"                              | Raise `MAX_DURATION_MINUTES`.                                                                                    |
| Lyrics are in the wrong language                     | Pick the language explicitly instead of Auto Detect.                                                             |
| Lyrics are poor for Hindi/Telugu                     | Use `WHISPER_MODEL=medium` (ideally with a GPU).                                                                 |
| "Media no longer available" on an old result         | Uploads are deleted after `FILE_RETENTION_HOURS`; the lyrics remain.                                             |
| Local: "media processing tool is not available"      | FFmpeg is not on `PATH`. Install it and reopen the terminal.                                                     |
| Local: `pip install` fails building packages         | Use Python 3.11 or 3.12.                                                                                         |
| Local: frontend shows "Can't reach the server"       | The backend is not running on port 8000.                                                                         |

Logs include the job id, stage, model, device and timings, for example:

```
job=1fd5f0a1-… stage=SEPARATING_VOCALS
job=1fd5f0a1-… stage=COMPLETED model=whisper-small device=cpu duration=25.0s processing_time=26.3s lines=3
```

---

## 15. Limitations

- Singing is harder than speech. Expect mistakes with fast rap, heavy vocal effects,
  dense backing choirs, or code-mixed lyrics (for example Hindi-English in one line).
- Timestamps are per lyric segment (phrase level), not per word.
- Auto Detect chooses only among the supported languages, so a song in another language
  is transcribed as the closest of English/Hindi/Telugu.
- Jobs are processed one at a time, in a single backend process. This is deliberate
  (simple, and one copy of each model), but it does not scale horizontally as is.
- Jobs that were mid-processing when the server restarts are marked failed and must be
  uploaded again (queued jobs are resumed).
- CPU processing is slow for long songs; the default limits are 50 MB and 15 minutes.
- The anonymous history is tied to one browser; clearing site data loses access to it.

## 16. Future scope

- Fine-tuning Whisper on Indian-language singing data; language-specific adaptation
- Word-level alignment for karaoke-style highlighting
- More languages (Tamil, Kannada, Malayalam, Punjabi …)
- Music-aware punctuation and verse/chorus structure detection
- Better separation models and an option to download the isolated vocal track
- Lyric editing in the browser before export
- A dedicated worker queue (Redis + RQ/Celery) for multi-GPU or multi-node deployments

---

*Built with pretrained open-source models: [Demucs](https://github.com/facebookresearch/demucs)
(MIT) and [Whisper](https://github.com/openai/whisper) (MIT). Upload only audio you have
the right to process.*
