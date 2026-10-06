from fastapi import APIRouter

from app.api.routes import auth, health, history, transcription

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(auth.router)
# history first: it owns the collection route GET /api/transcriptions.
api_router.include_router(history.router)
api_router.include_router(transcription.router)
