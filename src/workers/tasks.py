
import os
import logging
import json
import time
from datetime import datetime, timezone

from src.workers.celery_app import celery_app
from src.database import SessionLocal
from src.models import ContentAsset, Clip
from src.enums import ContentStatus, ClipStatus
from src.agents import understanding, viral_cutter
from src.agents.strategy_brain import StrategyBrain
from src.agents.frame_power import FramePowerAgent
from src.agents.captioner import CaptionAgent
from src.utils.frames import extract_frames
from src.utils.youtube import download_youtube_video

logger = logging.getLogger(__name__)

# Media storage directory
MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "media")
UPLOADS_DIR = os.path.join(MEDIA_DIR, "uploads")
CLIPS_DIR = os.path.join(MEDIA_DIR, "clips")
POSTERS_DIR = os.path.join(MEDIA_DIR, "posters")
FRAMES_DIR = os.path.join(MEDIA_DIR, "frames")

def _get_db():
    db = SessionLocal()
    try: return db
    except Exception:
        db.close()
        raise

@celery_app.task(name="src.workers.tasks.process_youtube_asset")
def process_youtube_asset(asset_id: int):
    db = _get_db()
    try:
        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        if not asset: return
        
        url = asset.meta_data.get("url")
        filename = f"yt_{asset_id}_{int(time.time())}.mp4"
        output_path = os.path.join(UPLOADS_DIR, filename)
        
        asset.status = ContentStatus.PROCESSING
        db.commit()
        
        if download_youtube_video(url, output_path):
            asset.file_path = output_path
            db.commit()
            process_asset(asset_id)
        else:
            asset.status = ContentStatus.FAILED
            asset.error_message = "YouTube download failed"
            db.commit()
    finally:
        db.close()

@celery_app.task(bind=True, name="src.workers.tasks.process_asset")
def process_asset(self, asset_id: int):
    """
    12-AGENT PIPELINE (Phase 1: First 6 Agents)
    """
    db = _get_db()
    try:
        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        if not asset or not asset.file_path: return

        asset.status = ContentStatus.PROCESSING
        db.commit()

        # Agent 1: Understanding (Transcription)
        logger.info("Agent 1: Transcribing...")
        trans = understanding.transcribe(asset.file_path)

        # Agent 3 Preparation: Extract Frames for Vision
        logger.info("Extracting frames for visual brain...")
        asset_frames_dir = os.path.join(FRAMES_DIR, str(asset_id))
        frames = extract_frames(asset.file_path, asset_frames_dir, interval_seconds=15)

        # Agent 6: Strategy Brain (Visual AI Decision)
        logger.info("Agent 6: Strategic AI Perception...")
        brain = StrategyBrain()
        decisions = brain.analyze_content(trans.text, frames)
        
        # Mapping decisions to 10 clips of 30s as requested
        from src.agents.viral_cutter import ClipSpec
        specs = []
        for d in decisions[:10]: # Limit to 10
            specs.append(ClipSpec(
                start_time=d['start'],
                end_time=d.get('end', d['start'] + 30.0),
                score=1.0,
                source_segments=[d.get('reason', '')]
            ))

        # Agent 2: Viral Cutter (Clipping)
        logger.info(f"Agent 2: Cutting {len(specs)} clips...")
        asset_clips_dir = os.path.join(CLIPS_DIR, str(asset_id))
        cut_results = viral_cutter.cut_all_clips(asset.file_path, specs, asset_clips_dir)

        # Agent 3 & 4: Poster & Captions
        poster_agent = FramePowerAgent()
        caption_agent = CaptionAgent()
        
        os.makedirs(POSTERS_DIR, exist_ok=True)

        for res in cut_results:
            # Generate Captions
            caps = caption_agent.generate_caption(res.clip_spec.source_segments[0])
            
            # Generate Poster from first frame of clip
            poster_filename = f"poster_{asset_id}_{int(res.clip_spec.start_time)}.jpg"
            poster_path = os.path.join(POSTERS_DIR, poster_filename)
            # Use original frames as source for simplicity
            source_frame = frames[0] if frames else None # Fallback
            if source_frame:
                poster_agent.create_viral_poster(source_frame, "HAR YANVI VIBE", poster_path)

            clip = Clip(
                asset_id=asset_id,
                start_time=res.clip_spec.start_time,
                end_time=res.clip_spec.end_time,
                duration=res.clip_spec.duration,
                file_path=res.output_path if res.success else None,
                status=ClipStatus.READY if res.success else ClipStatus.FAILED,
                error_message=res.error,
                virality_score=res.clip_spec.score,
                # Store Captions in transcription field for now
                transcription=json.dumps(caps)
            )
            db.add(clip)

        asset.status = ContentStatus.READY
        db.commit()
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if asset:
            asset.status = ContentStatus.FAILED
            asset.error_message = str(e)
            db.commit()
    finally:
        db.close()

def _process_asset_sync(asset_id: int):
    return process_asset.run(None, asset_id)
