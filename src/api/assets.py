
import os
import shutil
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import ContentAsset, Clip
from src.enums import ContentStatus, ContentType, Platform
from src.schemas import AssetUploadResponse, AssetStatusResponse, ProcessResponse, ClipResponse, YouTubeUploadRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assets", tags=["Assets"])

# Media upload directory
MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media")
UPLOADS_DIR = os.path.join(MEDIA_DIR, "uploads")

def _ensure_dirs():
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(os.path.join(MEDIA_DIR, "clips"), exist_ok=True)
    os.makedirs(os.path.join(MEDIA_DIR, "frames"), exist_ok=True)

def _dispatch_process(asset_id: int, background_tasks: BackgroundTasks, is_youtube: bool = False):
    """Internal helper to dispatch processing task."""
    try:
        from src.workers.tasks import process_asset, process_youtube_asset
        task_func = process_youtube_asset if is_youtube else process_asset
        task = task_func.delay(asset_id)
        return task.id
    except Exception as e:
        logger.warning(f"Celery unavailable ({e}), using sync fallback")
        from src.workers.tasks import _process_asset_sync
        # For YouTube, we'd need a sync_youtube helper, 
        # but for now we'll just run the main pipeline sync
        background_tasks.add_task(_process_asset_sync, asset_id)
        return f"sync-{asset_id}"

@router.post("/upload", response_model=AssetUploadResponse, status_code=201)
async def upload_asset(
    background_tasks: BackgroundTasks,
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
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    # AUTOMATION: Trigger processing immediately
    _dispatch_process(asset.id, background_tasks)

    return AssetUploadResponse(
        id=asset.id,
        title=asset.title,
        status="PROCESSING",
        file_path=file_path,
        message="Asset uploaded and AI processing started automatically.",
    )

@router.post("/youtube", response_model=AssetUploadResponse, status_code=201)
async def upload_youtube(
    req: YouTubeUploadRequest,
    background_tasks: BackgroundTasks,
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
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    # AUTOMATION: Trigger YouTube download and process
    _dispatch_process(asset.id, background_tasks, is_youtube=True)

    return AssetUploadResponse(
        id=asset.id,
        title=asset.title,
        status="PROCESSING",
        file_path="CLOUD",
        message="YouTube link received. AI is downloading and processing in background.",
    )

@router.post("/{asset_id}/process", response_model=ProcessResponse)
async def process_asset_endpoint(asset_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task_id = _dispatch_process(asset_id, background_tasks)
    return ProcessResponse(asset_id=asset_id, task_id=task_id, status="PROCESSING")

@router.get("/{asset_id}", response_model=AssetStatusResponse)
async def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
    if not asset: raise HTTPException(status_code=404)

    # LAZY POLLING: If it's still processing, check Vizard
    if asset.status == ContentStatus.PROCESSING and asset.meta_data.get("vizard_project_id"):
        from src.agents.vizard_agent import VizardAgent
        from src.agents.captioner import CaptionAgent
        import json
        
        vizard = VizardAgent()
        clips_data = vizard.get_clips(asset.meta_data["vizard_project_id"])
        
        if clips_data:
            logger.info(f"Lazy Polling: Found {len(clips_data)} clips for asset {asset_id}")
            captioner = CaptionAgent()
            for v_clip in clips_data[:15]:
                clip_url = v_clip.get("videoUrl")
                if not clip_url: continue
                
                # Check if clip already exists to avoid duplicates
                existing = db.query(Clip).filter(Clip.asset_id == asset_id, Clip.file_path == clip_url).first()
                if existing: continue

                caps = captioner.generate_caption(v_clip.get("transcript", ""))
                clip = Clip(
                    asset_id=asset_id,
                    start_time=0.0,
                    end_time=0.0,
                    duration=v_clip.get("duration", 0),
                    file_path=clip_url,
                    status=ClipStatus.READY,
                    virality_score=v_clip.get("viralScore", 0.0),
                    transcription=json.dumps(caps)
                )
                db.add(clip)
            
            asset.status = ContentStatus.READY
            db.commit()
            db.refresh(asset)

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
    return [AssetStatusResponse(id=a.id, title=a.title, status=a.status.value) for a in assets]
