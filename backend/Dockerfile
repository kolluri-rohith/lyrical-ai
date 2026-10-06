# LyricalAI backend: FastAPI + FFmpeg + Demucs + Whisper in one image.
FROM python:3.11-slim

# CPU wheels by default. For an NVIDIA GPU build pass
#   --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG TORCH_VERSION=2.5.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STORAGE_PATH=/app/storage \
    MODEL_CACHE_DIR=/app/models \
    TORCH_HOME=/app/models/torch \
    HF_HOME=/app/models/huggingface

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# PyTorch first, from the chosen wheel index, so the big layer is cached.
RUN pip install "torch==${TORCH_VERSION}" "torchaudio==${TORCH_VERSION}" --index-url "${TORCH_INDEX_URL}"

COPY requirements.txt constraints.txt ./
RUN pip install -r requirements.txt -c constraints.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app

# Run as an unprivileged user; storage and the model cache are volumes it owns.
RUN useradd --create-home --uid 1000 lyricalai \
    && mkdir -p /app/storage /app/models \
    && chown -R lyricalai:lyricalai /app
USER lyricalai

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# A single worker process: the models are loaded once and jobs run on one background thread.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
