#!/usr/bin/env bash

set -u

# Always run from the repository root, even when invoked from elsewhere.
cd "$(dirname "$0")" || exit 1

# Brings the whole local LyricalAI stack up without Docker: creates the Python
# virtualenv and installs dependencies when they are missing or out of date,
# then runs the FastAPI backend (uvicorn, 8000) and the web app (Vite, 5173).
# The backend uses the SQLite file from backend/.env, so no database is needed.
# Usage: ./script.sh

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

API_PORT=8000
WEB_PORT=5173

echo -e "${CYAN}${BOLD}"
echo "=========================================================="
echo "           LyricalAI - Local Service Launcher             "
echo "=========================================================="
echo -e "${NC}"

API_PID=""
WEB_PID=""
TAIL_PID=""
CLEANED_UP=false

free_port() {
  local port=$1
  local pids=""

  if command -v netstat >/dev/null 2>&1 && command -v taskkill >/dev/null 2>&1; then
    pids=$(netstat -ano 2>/dev/null | grep LISTENING | grep -E "[:.]$port[[:space:]]" | awk '{print $NF}' | sort -u | grep -v '^0$' || true)
    for pid in $pids; do
      if [ -n "$pid" ] && [ "$pid" -gt 0 ] 2>/dev/null; then
        taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true
      fi
    done
  fi

  if command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti tcp:"$port" -sTCP:LISTEN 2>/dev/null || true)
    for pid in $pids; do
      kill -9 "$pid" >/dev/null 2>&1 || true
    done
  fi
}

# Git Bash's kill only ends the process it started; uvicorn --reload and Vite
# both spawn children, so on Windows the whole tree is taken down by taskkill.
kill_tree() {
  local pid=$1
  [ -z "$pid" ] && return

  if [ -r "/proc/$pid/winpid" ] && command -v taskkill >/dev/null 2>&1; then
    taskkill //F //T //PID "$(cat "/proc/$pid/winpid")" >/dev/null 2>&1 || true
  else
    pkill -P "$pid" >/dev/null 2>&1 || true
  fi
  kill "$pid" >/dev/null 2>&1 || true
}

cleanup() {
  if [ "$CLEANED_UP" = "true" ]; then
    return
  fi
  CLEANED_UP=true
  trap - SIGINT SIGTERM EXIT

  echo -e "\n\n${YELLOW}[SHUTDOWN] Stopping LyricalAI services...${NC}"

  [ -n "$TAIL_PID" ] && kill "$TAIL_PID" 2>/dev/null || true
  kill_tree "$API_PID"
  kill_tree "$WEB_PID"

  free_port "$API_PORT"
  free_port "$WEB_PORT"
  rm -f .health.json

  echo -e "${GREEN}All LyricalAI services stopped.${NC}\n"
}

trap cleanup SIGINT SIGTERM EXIT

echo -n "1. Checking required tools... "
MISSING_TOOLS=""
for tool in node npm curl ffmpeg ffprobe; do
  command -v "$tool" >/dev/null 2>&1 || MISSING_TOOLS="$MISSING_TOOLS $tool"
done
if [ -n "$MISSING_TOOLS" ]; then
  echo -e "${RED}[FAILED]${NC}"
  echo -e "${RED}Missing:$MISSING_TOOLS${NC}"
  echo -e "${YELLOW}FFmpeg: winget install Gyan.FFmpeg | brew install ffmpeg | sudo apt install ffmpeg${NC}"
  exit 1
fi
echo -e "${GREEN}[OK]${NC}"

echo -n "2. Checking environment... "
if [ ! -f backend/.env ]; then
  if [ -f backend/.env.example ]; then
    cp backend/.env.example backend/.env
    echo -e "${YELLOW}[Created backend/.env from backend/.env.example]${NC}"
  else
    echo -e "${RED}[FAILED] backend/.env and backend/.env.example are missing.${NC}"
    exit 1
  fi
else
  echo -e "${GREEN}[OK]${NC}"
fi

echo -n "3. Checking backend dependencies... "
if [ -d backend/.venv/Scripts ]; then
  PY="$PWD/backend/.venv/Scripts/python.exe"
else
  PY="$PWD/backend/.venv/bin/python"
fi

if [ ! -x "$PY" ]; then
  echo -e "${YELLOW}[creating virtualenv]${NC}"
  # PyTorch/Demucs wheels are not published for every newer Python.
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.11 backend/.venv
  elif command -v py >/dev/null 2>&1; then
    py -3.11 -m venv backend/.venv
  elif command -v python3.11 >/dev/null 2>&1; then
    python3.11 -m venv backend/.venv
  else
    echo -e "${RED}[FAILED] Python 3.11 was not found (install it, or install uv).${NC}"
    exit 1
  fi
  if [ -d backend/.venv/Scripts ]; then
    PY="$PWD/backend/.venv/Scripts/python.exe"
  else
    PY="$PWD/backend/.venv/bin/python"
  fi
  if [ ! -x "$PY" ]; then
    echo -e "${RED}[FAILED] Could not create backend/.venv.${NC}"
    exit 1
  fi
  echo -n "   Backend dependencies... "
fi

DEPS_STAMP=backend/.venv/.deps-stamp
NEED_INSTALL=false
if ! "$PY" -c "import uvicorn, fastapi, httpx, pytest" >/dev/null 2>&1; then
  NEED_INSTALL=true
elif [ -f "$DEPS_STAMP" ]; then
  for req in backend/requirements.txt backend/requirements-dev.txt backend/constraints.txt; do
    [ "$req" -nt "$DEPS_STAMP" ] && NEED_INSTALL=true
  done
fi
if [ "$NEED_INSTALL" = "true" ]; then
  echo -e "${YELLOW}[installing]${NC}"
  echo "   Installing Python packages..."
  # A virtualenv made by uv has no pip of its own.
  if command -v uv >/dev/null 2>&1; then
    INSTALL=(uv pip install --python "$PY")
  else
    INSTALL=("$PY" -m pip install)
  fi
  if ! (cd backend && "${INSTALL[@]}" -r requirements-dev.txt -c constraints.txt); then
    echo -e "${RED}[FAILED] Backend dependency install failed.${NC}"
    exit 1
  fi
else
  echo -e "${GREEN}[OK]${NC}"
fi
touch "$DEPS_STAMP"

echo -n "4. Checking frontend dependencies... "
NEED_INSTALL=false
if [ ! -f frontend/node_modules/vite/bin/vite.js ] || [ ! -f frontend/node_modules/.package-lock.json ]; then
  NEED_INSTALL=true
elif [ frontend/package-lock.json -nt frontend/node_modules/.package-lock.json ]; then
  NEED_INSTALL=true
fi
if [ "$NEED_INSTALL" = "true" ]; then
  echo -e "${YELLOW}[installing]${NC}"
  if ! (cd frontend && npm install); then
    echo -e "${RED}[FAILED] npm install failed.${NC}"
    exit 1
  fi
else
  echo -e "${GREEN}[OK]${NC}"
fi

echo -n "5. Cleaning stale dev ports ($API_PORT, $WEB_PORT)... "
free_port "$API_PORT"
free_port "$WEB_PORT"
echo -e "${GREEN}[OK]${NC}"

echo -n "6. Launching API (uvicorn, $API_PORT) and Web (Vite, $WEB_PORT)... "
rm -f backend.log frontend.log .health.json
touch backend.log frontend.log

# Database tables are created by the Alembic migrations on start-up.
# PYTHONUNBUFFERED keeps the log file live instead of arriving in blocks.
(cd backend && PYTHONUNBUFFERED=1 exec "$PY" -m uvicorn app.main:app --reload --port "$API_PORT") >backend.log 2>&1 &
API_PID=$!
# --strictPort: the dev proxy and CORS_ORIGINS both assume this exact port.
(cd frontend && exec node node_modules/vite/bin/vite.js --port "$WEB_PORT" --strictPort) >frontend.log 2>&1 &
WEB_PID=$!
echo -e "${GREEN}[OK]${NC}"

echo -n "   Waiting for API and Web to become ready"
API_OK=false
WEB_OK=false
WAIT=0
MAX_WAIT=120

while [ "$WAIT" -lt "$MAX_WAIT" ]; do
  echo -n "."

  if [ "$API_OK" = "false" ]; then
    if ! kill -0 "$API_PID" 2>/dev/null; then
      echo -e "\n${RED}[FAILED] API exited before becoming ready.${NC}"
      tail -n 40 backend.log 2>/dev/null || true
      exit 1
    fi
    HEALTH_CODE=$(curl -s -m 3 -o .health.json -w '%{http_code}' "http://localhost:$API_PORT/api/health" 2>/dev/null || echo 000)
    [ "$HEALTH_CODE" = "200" ] && API_OK=true
  fi

  if [ "$WEB_OK" = "false" ]; then
    if ! kill -0 "$WEB_PID" 2>/dev/null; then
      echo -e "\n${RED}[FAILED] Web exited before becoming ready.${NC}"
      tail -n 40 frontend.log 2>/dev/null || true
      exit 1
    fi
    curl -s -m 3 "http://localhost:$WEB_PORT" >/dev/null 2>&1 && WEB_OK=true
  fi

  if [ "$API_OK" = "true" ] && [ "$WEB_OK" = "true" ]; then
    break
  fi

  sleep 1
  WAIT=$((WAIT + 1))
done
echo ""

if [ "$API_OK" != "true" ] || [ "$WEB_OK" != "true" ]; then
  echo -e "${RED}${BOLD}One or more services failed to become ready.${NC}"
  echo -e "API: $API_OK (HTTP ${HEALTH_CODE:-000}) | Web: $WEB_OK"
  echo -e "${YELLOW}Last API log lines:${NC}"
  tail -n 40 backend.log 2>/dev/null || true
  echo -e "${YELLOW}Last Web log lines:${NC}"
  tail -n 40 frontend.log 2>/dev/null || true
  exit 1
fi

echo -e "${GREEN}${BOLD}==========================================================${NC}"
echo -e "${GREEN}${BOLD}         ALL LYRICALAI SERVICES ARE READY                 ${NC}"
echo -e "${GREEN}${BOLD}==========================================================${NC}"
echo -e "  ${CYAN}${BOLD}Web:${NC}      http://localhost:$WEB_PORT"
echo -e "  ${CYAN}${BOLD}API:${NC}      http://localhost:$API_PORT"
echo -e "  ${CYAN}${BOLD}API docs:${NC} http://localhost:$API_PORT/docs"
echo -e "  ${CYAN}${BOLD}Health:${NC}   http://localhost:$API_PORT/api/health"
echo -e "${GREEN}==========================================================${NC}"
echo -e "${YELLOW}The first upload downloads the model weights (about 550 MB).${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop all services.${NC}\n"
echo -e "${CYAN}Streaming live server logs:${NC}\n"

tail -f backend.log frontend.log &
TAIL_PID=$!

wait "$API_PID" "$WEB_PID" 2>/dev/null || true
