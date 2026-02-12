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
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from src.api.assets import router as assets_router
from src.api.pipeline import router as pipeline_router
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
app.include_router(pipeline_router)
app.include_router(whatsapp_router)

# Mount Media for static access (Clips/Uploads)
base_dir = "/tmp" if os.environ.get("VERCEL") else "."
for d in ["media", "media/uploads", "media/clips", "media/frames", "media/posters"]:
    full_path = os.path.join(base_dir, d)
    if not os.path.exists(full_path):
        os.makedirs(full_path)
app.mount("/media", StaticFiles(directory=os.path.join(base_dir, "media")), name="media")


@app.get("/", response_class=HTMLResponse, tags=["System"])
def read_root():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(template_path):
        return "Dashboard template not found. Please upload src/templates/index.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


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
    logger.info(f"BIRU_BHAI is starting up (Env: {os.environ.get('VERCEL', 'Local')})")
    logger.info("=" * 50)

    # Skip local FFmpeg setup on Vercel
    if not os.environ.get("VERCEL"):
        if settings.ffmpeg_path and os.path.exists(settings.ffmpeg_path):
            ffmpeg_dir = os.path.dirname(settings.ffmpeg_path)
            if ffmpeg_dir not in os.environ["PATH"]:
                os.environ["PATH"] += os.pathsep + ffmpeg_dir
                logger.info(f"Added FFmpeg to PATH")

    # Create DB tables safely
    try:
        from src.database import engine, Base
        from src.models import ContentAsset, Clip, Post  # ensure models loaded
        Base.metadata.create_all(bind=engine)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
