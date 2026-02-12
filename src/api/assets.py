
import os
import shutil
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import ContentAsset, Clip
from src.enums import ContentStatus, ClipStatus, ContentType, Platform
from src.schemas import (
    AssetUploadResponse, AssetStatusResponse,
    ClipResponse, YouTubeUploadRequest, YouTubeSummaryRequest, YouTubeSummaryResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assets", tags=["Assets"])

# Media upload directory
BASE_PATH = "/tmp" if os.environ.get("VERCEL") else os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
MEDIA_DIR = os.path.join(BASE_PATH, "media")
UPLOADS_DIR = os.path.join(MEDIA_DIR, "uploads")

def _ensure_dirs():
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(os.path.join(MEDIA_DIR, "clips"), exist_ok=True)
    os.makedirs(os.path.join(MEDIA_DIR, "frames"), exist_ok=True)


@router.post("/upload", response_model=AssetUploadResponse, status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    _ensure_dirs()
    allowed_extensions = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".mp3", ".wav"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = f"{timestamp}_{file.filename}"
    file_path = os.path.join(UPLOADS_DIR, safe_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    asset = ContentAsset(
        title=title or os.path.splitext(file.filename)[0],
        source_url=file_path,
        source_type=Platform.LOCAL,
        content_type=ContentType.VIDEO,
        file_path=file_path,
        status=ContentStatus.PENDING,
        meta_data={"size_bytes": os.path.getsize(file_path)},
        pipeline_step=1,
        pipeline_step_status="PENDING",
        pipeline_data={},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return AssetUploadResponse(
        id=asset.id,
        title=asset.title,
        status="PENDING",
        file_path=file_path,
        message="Asset uploaded. Use /pipeline/{id}/advance to start processing.",
    )


@router.post("/youtube", response_model=AssetUploadResponse, status_code=201)
async def upload_youtube(
    req: YouTubeUploadRequest,
    db: Session = Depends(get_db),
):
    _ensure_dirs()
    asset = ContentAsset(
        title=req.title or "YouTube Video",
        source_url=req.url,
        source_type=Platform.YOUTUBE,
        content_type=ContentType.VIDEO,
        status=ContentStatus.PENDING,
        meta_data={"url": req.url},
        pipeline_step=1,
        pipeline_step_status="PENDING",
        pipeline_data={},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return AssetUploadResponse(
        id=asset.id,
        title=asset.title,
        status="PENDING",
        file_path="CLOUD",
        message="YouTube link received. Pipeline ready — use /pipeline/{id}/advance to start.",
    )


@router.post("/youtube/summary", response_model=YouTubeSummaryResponse)
async def get_youtube_summary(req: YouTubeSummaryRequest):
    from src.agents.youtube_summary_mcp import call_summarizer_api
    try:
        summary = await call_summarizer_api(req.url)
        return YouTubeSummaryResponse(summary=summary)
    except Exception as e:
        logger.error(f"Summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{asset_id}", response_model=AssetStatusResponse)
async def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404)

    clips = db.query(Clip).filter(Clip.asset_id == asset_id).all()

    return AssetStatusResponse(
        id=asset.id,
        title=asset.title,
        status=asset.status.value if hasattr(asset.status, 'value') else asset.status,
        error_message=asset.error_message,
        clips=[ClipResponse(
            id=c.id, asset_id=c.asset_id, start_time=c.start_time, end_time=c.end_time,
            duration=c.duration, status=c.status.value if hasattr(c.status, 'value') else c.status,
            file_path=c.file_path,
            virality_score=c.virality_score, transcription=c.transcription
        ).model_dump() for c in clips]
    )


@router.get("", response_model=list[AssetStatusResponse])
async def list_assets(db: Session = Depends(get_db)):
    assets = db.query(ContentAsset).order_by(ContentAsset.created_at.desc()).all()

    # Zombie Check: Self-heal assets stuck in PROCESSING for > 2 minutes
    now = datetime.now(timezone.utc)
    updated = False
    for a in assets:
        if a.status == ContentStatus.PROCESSING or a.pipeline_step_status == "RUNNING":
            last_active = a.updated_at or a.created_at
            if last_active:
                # Handle timezone awareness (SQLite usually naive UTC)
                if last_active.tzinfo is None:
                     last_active = last_active.replace(tzinfo=timezone.utc)
                
                delta = now - last_active
                if delta.total_seconds() > 120: # 2 minutes timeout
                    logger.warning(f"Detected Zombie Asset {a.id}. Auto-failing.")
                    a.status = ContentStatus.FAILED
                    a.error_message = "Timeout: Process took too long (Serverless Limit)"
                    a.pipeline_step_status = "FAILED"
                    updated = True
    
    if updated:
        db.commit()

    return [AssetStatusResponse(
        id=a.id,
        title=a.title,
        status=a.status.value if hasattr(a.status, 'value') else a.status,
        error_message=a.error_message,
        created_at=a.created_at,
        updated_at=a.updated_at,
        pipeline_step=a.pipeline_step,
        pipeline_step_status=a.pipeline_step_status
    ) for a in assets]
