"""
BIRU_BHAI — The Solo Creator OS
FastAPI Application Entry Point

Phase 2: Intelligence Layer Active
- Upload video/audio files
- Transcribe with Whisper
- Cut viral clips with FFmpeg
- All processing runs in the background (Celery) or sync fallback
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from src.api.assets import router as assets_router
from src.agents.whatsapp import router as whatsapp_router
from src.schemas import HealthResponse

# ============================================================
# LOGGING
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# APP
# ============================================================
app = FastAPI(
    title="BIRU_BHAI API",
    version="0.2.0",
    description=(
        "🎬 Autonomous Personal Content OS — Single Creator Mode\n\n"
        "Upload a video → Get viral clips automatically.\n\n"
        "**Pipeline**: Upload → Transcribe (Whisper) → Score → Cut (FFmpeg) → Done"
    ),
)

# CORS — allow all origins for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# ROUTES
# ============================================================
app.include_router(assets_router)
app.include_router(whatsapp_router)

# Mount Media for static access (Clips/Uploads)
for d in ["media", "media/uploads", "media/clips", "media/frames", "media/posters"]:
    if not os.path.exists(d):
        os.makedirs(d)
app.mount("/media", StaticFiles(directory="media"), name="media")


@app.get("/", tags=["System"])
def read_root():
    return {
        "name": "BIRU_BHAI",
        "tagline": "Autonomous Personal Content OS",
        "status": "🟢 Active",
        "phase": "Phase 2: Intelligence Layer",
        "endpoints": {
            "upload": "POST /assets/upload",
            "process": "POST /assets/{id}/process",
            "status": "GET /assets/{id}",
            "list": "GET /assets",
            "docs": "GET /docs",
        },
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    return HealthResponse()


# ============================================================
# STARTUP
# ============================================================
import os
from src.config import settings

# ...

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("BIRU_BHAI is starting up...")
    logger.info("Phase 2: Intelligence Layer Active")
    logger.info("=" * 50)

    # Ensure FFmpeg is in PATH for Whisper
    if settings.ffmpeg_path and os.path.exists(settings.ffmpeg_path):
        ffmpeg_dir = os.path.dirname(settings.ffmpeg_path)
        if ffmpeg_dir not in os.environ["PATH"]:
            os.environ["PATH"] += os.pathsep + ffmpeg_dir
            logger.info(f"Added FFmpeg to PATH: {ffmpeg_dir}")

    # Create DB tables if they don't exist (fallback — Alembic is primary)
    from src.database import engine, Base
    from src.models import ContentAsset, Clip, Post, StrategyDecision  # noqa: ensure models are loaded
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
