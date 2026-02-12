
import os
import logging
import json
import time
from datetime import datetime, timezone

from src.workers.celery_app import celery_app
from src.database import SessionLocal
from src.models import ContentAsset, Clip
from src.enums import ContentStatus, ClipStatus
from src.agents.vizard_agent import VizardAgent
from src.agents.captioner import CaptionAgent
from src.agents.frame_power import FramePowerAgent
from src.utils.youtube import download_youtube_video

logger = logging.getLogger(__name__)

def _get_db():
    db = SessionLocal()
    try: return db
    except Exception:
        db.close()
        raise

@celery_app.task(name="src.workers.tasks.process_vizard_pipeline")
def process_vizard_pipeline(asset_id: int):
    """
    NEW VIZARD-ONLY PIPELINE:
    1. Send URL to Vizard AI.
    2. Poll for Clips.
    3. Save results.
    """
    db = _get_db()
    vizard = VizardAgent()
    captioner = CaptionAgent()
    
    try:
        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        if not asset: return

        asset.status = ContentStatus.PROCESSING
        db.commit()

        # Get URL (If local, we'd need to upload, but user prefers YT/Cloud links)
        video_url = asset.source_url
        if "http" not in video_url:
            # Fallback if it's a local file path (unlikely in Vizard-only mode)
            asset.status = ContentStatus.FAILED
            asset.error_message = "Vizard requires a public URL (YouTube/Cloud). Local files not supported in serverless mode yet."
            db.commit()
            return

        # 1. Create Project in Vizard
        project_id = vizard.create_project(video_url, project_name=asset.title)
        if not project_id:
            asset.status = ContentStatus.FAILED
            asset.error_message = "Vizard project creation failed."
            db.commit()
            return

        asset.meta_data["vizard_project_id"] = project_id
        db.commit()

        # 2. Polling for clips (In a real worker, we'd use a separate polling task, 
        # but for MVP we will sleep-poll for a few minutes)
        max_attempts = 20
        clips_data = []
        for _ in range(max_attempts):
            logger.info(f"Polling Vizard for project {project_id}...")
            clips_data = vizard.get_clips(project_id)
            if clips_data: 
                break
            time.sleep(30) # Wait 30s between polls

        if not clips_data:
            asset.status = ContentStatus.FAILED
            asset.error_message = "Vizard timeout: Clips not ready after 10 minutes."
            db.commit()
            return

        # 3. Process and Save Clips
        for v_clip in clips_data[:15]: # Take top viral clips
            clip_url = v_clip.get("videoUrl")
            if not clip_url: continue

            # Generate Captions via Agent #4
            caps = captioner.generate_caption(v_clip.get("transcript", "Haryanvi viral clip"))
            
            clip = Clip(
                asset_id=asset_id,
                start_time=0.0, # Vizard gives relative clips
                end_time=0.0,
                duration=v_clip.get("duration", 0),
                file_path=clip_url, # External URL for direct playback
                status=ClipStatus.READY,
                virality_score=v_clip.get("viralScore", 0.0),
                transcription=json.dumps(caps)
            )
            db.add(clip)

        asset.status = ContentStatus.READY
        db.commit()
        logger.info(f"Vizard processing complete for asset {asset_id}")

    except Exception as e:
        logger.error(f"Vizard Pipeline Failed: {e}")
        if asset:
            asset.status = ContentStatus.FAILED
            asset.error_message = str(e)
            db.commit()
    finally:
        db.close()

# Alias the old name to new pipeline for existing API calls
@celery_app.task(name="src.workers.tasks.process_asset")
def process_asset(asset_id: int):
    return process_vizard_pipeline(asset_id)

@celery_app.task(name="src.workers.tasks.process_youtube_asset")
def process_youtube_asset(asset_id: int):
    return process_vizard_pipeline(asset_id)

def _process_asset_sync(asset_id: int):
    """Sync wrapper for Vizard pipeline."""
    return process_vizard_pipeline(asset_id)
