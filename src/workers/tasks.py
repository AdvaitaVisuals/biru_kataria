
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
    2. Poll for Clips (handled by Lazy Polling in API).
    """
    db = SessionLocal()
    vizard = VizardAgent()
    
    asset = None
    try:
        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        if not asset: 
            logger.error(f"Asset {asset_id} not found in DB")
            return

        asset.status = ContentStatus.PROCESSING
        db.commit()

        # Get URL (If local, we'd need to upload, but user prefers YT/Cloud links)
        video_url = asset.source_url
        if "http" not in video_url:
            asset.status = ContentStatus.FAILED
            asset.error_message = "Vizard requires a public URL (YouTube/Cloud). Local files not supported in serverless mode yet."
            db.commit()
            return

        # 1. Create Project in Vizard
        project_id = vizard.create_project(video_url, project_name=asset.title)
        if not project_id:
            asset.status = ContentStatus.FAILED
            asset.error_message = "Vizard project creation failed. (Check API Key or URL)"
            db.commit()
            return

        if not asset.meta_data: asset.meta_data = {}
        asset.meta_data["vizard_project_id"] = project_id
        db.commit()
        logger.info(f"Vizard project {project_id} initialized for asset {asset_id}")

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
