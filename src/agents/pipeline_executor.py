import os
import json
import logging
import tempfile
from datetime import datetime
from openai import OpenAI
from sqlalchemy.orm import Session

from src.config import settings
from src.models import ContentAsset, Clip, Post
from src.enums import ContentStatus, ClipStatus, PostStatus, Platform

logger = logging.getLogger(__name__)

try:
    import yt_dlp
except ImportError:
    logger.warning("yt_dlp not installed - video operations will fail")
    yt_dlp = None


class PipelineExecutor:
    """
    Core pipeline engine for BIRU BHAI.
    Each step is designed to complete within Vercel's 60s serverless limit.
    """

    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)

    def execute_step(self, asset_id: int, step: int, db: Session) -> dict:
        handlers = {
            1: self._step_fetch,
            2: self._step_transcribe,
            3: self._step_analyze,
            4: self._step_clip,
            5: self._step_caption_post,
        }
        handler = handlers.get(step)
        if not handler:
            return {"error": f"Invalid step {step}", "status": "FAILED"}

        logger.info(f"Executing step {step} for asset {asset_id}")
        return handler(asset_id, db)

    def _step_fetch(self, asset_id: int, db: Session) -> dict:
        """Step 1: Extract video metadata from YouTube URL using yt-dlp."""
        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")
        if not yt_dlp:
            raise RuntimeError("yt_dlp is not installed")

        logger.info(f"Fetching metadata from {asset.source_url}")

        ydl_opts = {'skip_download': True, 'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(asset.source_url, download=False)

        metadata = {
            'title': info.get('title', 'Unknown'),
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
            'description': (info.get('description', '') or '')[:500],
            'view_count': info.get('view_count', 0),
            'uploader': info.get('uploader', ''),
            'video_id': info.get('id', ''),
        }

        asset.title = metadata['title']
        if not asset.pipeline_data:
            asset.pipeline_data = {}
        asset.pipeline_data['step_1_fetch'] = {
            'status': 'COMPLETED',
            'timestamp': datetime.utcnow().isoformat(),
            'result': metadata,
        }
        db.commit()

        logger.info(f"Metadata fetched: title='{metadata['title']}', duration={metadata['duration']}s")
        return {'status': 'COMPLETED', 'result': metadata}

    def _step_transcribe(self, asset_id: int, db: Session) -> dict:
        """Step 2: Transcribe audio via OpenAI Whisper API."""
        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")
        if not yt_dlp:
            raise RuntimeError("yt_dlp is not installed")

        logger.info(f"Starting transcription for asset {asset_id}")

        audio_file_path = None
        try:
            # Download audio using yt-dlp
            tmp_dir = tempfile.gettempdir()
            audio_template = os.path.join(tmp_dir, f"audio_{asset_id}")

            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio',
                'outtmpl': audio_template,
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([asset.source_url])

            # Find the downloaded file
            for ext in ['.m4a', '.webm', '.wav', '.mp3', '.opus', '']:
                candidate = audio_template + ext
                if os.path.exists(candidate):
                    audio_file_path = candidate
                    break

            if not audio_file_path:
                raise FileNotFoundError(f"Audio file not found after download")

            file_size = os.path.getsize(audio_file_path)
            logger.info(f"Audio downloaded: {audio_file_path} ({file_size / 1024 / 1024:.1f}MB)")

            # Check OpenAI 25MB limit
            if file_size > 25 * 1024 * 1024:
                msg = f"Audio too large ({file_size / 1024 / 1024:.1f}MB > 25MB limit). Skipping transcription."
                logger.warning(msg)
                if not asset.pipeline_data:
                    asset.pipeline_data = {}
                asset.pipeline_data['step_2_transcribe'] = {
                    'status': 'SKIPPED', 'message': msg,
                    'timestamp': datetime.utcnow().isoformat(),
                    'result': {'full_text': '', 'language': 'unknown', 'duration': 0, 'segments_count': 0},
                }
                db.commit()
                return {'status': 'SKIPPED', 'message': msg}

            # Send to Whisper
            logger.info("Sending to OpenAI Whisper API...")
            with open(audio_file_path, 'rb') as f:
                transcript = self.openai_client.audio.transcriptions.create(
                    file=f,
                    model="whisper-1",
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )

            result = {
                'full_text': transcript.text,
                'language': getattr(transcript, 'language', 'unknown'),
                'duration': getattr(transcript, 'duration', 0),
                'segments_count': len(getattr(transcript, 'segments', [])),
            }

            if not asset.pipeline_data:
                asset.pipeline_data = {}
            asset.pipeline_data['step_2_transcribe'] = {
                'status': 'COMPLETED',
                'timestamp': datetime.utcnow().isoformat(),
                'result': result,
            }
            db.commit()

            logger.info(f"Transcription complete: {result['segments_count']} segments, {result['duration']}s")
            return {'status': 'COMPLETED', 'result': result}

        finally:
            if audio_file_path and os.path.exists(audio_file_path):
                try:
                    os.remove(audio_file_path)
                except Exception:
                    pass

    def _step_analyze(self, asset_id: int, db: Session) -> dict:
        """Step 3: AI analysis with GPT-4o — identify viral segments, hooks, emotions."""
        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")

        pd = asset.pipeline_data or {}
        step2 = pd.get('step_2_transcribe', {})
        transcript = step2.get('result', {}).get('full_text', '')

        # If transcription was skipped, use video title/description for basic analysis
        if not transcript:
            step1 = pd.get('step_1_fetch', {})
            title = step1.get('result', {}).get('title', '')
            desc = step1.get('result', {}).get('description', '')
            transcript = f"Title: {title}\nDescription: {desc}"

        logger.info(f"Starting AI analysis for asset {asset_id}")

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a viral content analyst. Return ONLY valid JSON."},
                {"role": "user", "content": f"""Analyze this video transcript for viral clip potential:

TRANSCRIPT:
{transcript[:8000]}

Return JSON:
{{
  "viral_segments": [{{"start_time": 0, "end_time": 30, "hook": "...", "virality_score": 8, "emotion": "..."}}],
  "content_summary": "2-3 sentences",
  "best_posting_times": ["9 PM IST", "..."],
  "hashtags": ["#viral", "..."],
  "target_audience": "..."
}}"""},
            ],
            response_format={"type": "json_object"},
            max_tokens=2000,
        )

        analysis = json.loads(response.choices[0].message.content)

        if not asset.pipeline_data:
            asset.pipeline_data = {}
        asset.pipeline_data['step_3_analyze'] = {
            'status': 'COMPLETED',
            'timestamp': datetime.utcnow().isoformat(),
            'result': analysis,
        }
        db.commit()

        logger.info(f"Analysis complete: {len(analysis.get('viral_segments', []))} viral segments found")
        return {'status': 'COMPLETED', 'result': analysis}

    def _step_clip(self, asset_id: int, db: Session) -> dict:
        """Step 4: Submit to Vizard AI for clip generation + poll for results."""
        from src.agents.vizard_agent import VizardAgent

        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")

        if not asset.meta_data:
            asset.meta_data = {}
        if not asset.pipeline_data:
            asset.pipeline_data = {}

        vizard = VizardAgent()
        vizard_project_id = asset.meta_data.get('vizard_project_id')

        # Create Vizard project if not exists
        if not vizard_project_id:
            logger.info(f"Creating Vizard project for {asset.source_url}")
            vizard_project_id = vizard.create_project(asset.source_url, project_name=asset.title)
            if not vizard_project_id:
                raise ValueError("Vizard project creation returned no project ID")
            asset.meta_data['vizard_project_id'] = vizard_project_id
            db.commit()
            logger.info(f"Vizard project created: {vizard_project_id}")

        # Poll for clips
        logger.info(f"Polling Vizard for clips (project: {vizard_project_id})")
        clips_data = vizard.get_clips(vizard_project_id)

        if not clips_data:
            asset.pipeline_data['step_4_clip'] = {
                'status': 'POLLING',
                'message': 'Vizard is still processing clips...',
                'project_id': vizard_project_id,
                'timestamp': datetime.utcnow().isoformat(),
            }
            db.commit()
            return {'status': 'POLLING', 'message': 'Vizard is processing. Check back later.', 'project_id': vizard_project_id}

        # Clips found — create Clip records
        logger.info(f"Found {len(clips_data)} clips from Vizard")
        created = []
        for v_clip in clips_data[:15]:
            clip_url = v_clip.get('videoUrl')
            if not clip_url:
                continue

            # Avoid duplicates
            existing = db.query(Clip).filter(Clip.asset_id == asset_id, Clip.file_path == clip_url).first()
            if existing:
                continue

            clip = Clip(
                asset_id=asset_id,
                start_time=0.0,
                end_time=0.0,
                duration=v_clip.get('duration', 0),
                file_path=clip_url,
                status=ClipStatus.READY,
                virality_score=v_clip.get('viralScore', 0.0),
            )
            db.add(clip)
            created.append({'url': clip_url, 'duration': clip.duration})

        asset.pipeline_data['step_4_clip'] = {
            'status': 'COMPLETED',
            'clips_count': len(created),
            'timestamp': datetime.utcnow().isoformat(),
        }
        db.commit()

        logger.info(f"Created {len(created)} clip records for asset {asset_id}")
        return {'status': 'COMPLETED', 'result': {'clips_created': len(created)}}

    def _step_caption_post(self, asset_id: int, db: Session) -> dict:
        """Step 5: Generate captions for clips + trigger auto-posting."""
        from src.agents.captioner import CaptionAgent
        from src.agents.auto_poster import AutoPoster

        asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")

        pd = asset.pipeline_data or {}
        transcript = pd.get('step_2_transcribe', {}).get('result', {}).get('full_text', '')
        analysis = pd.get('step_3_analyze', {}).get('result', {})
        hashtags = ' '.join(analysis.get('hashtags', []))

        clips = db.query(Clip).filter(Clip.asset_id == asset_id, Clip.status == ClipStatus.READY).all()
        if not clips:
            if not asset.pipeline_data:
                asset.pipeline_data = {}
            asset.pipeline_data['step_5_caption_post'] = {
                'status': 'COMPLETED', 'message': 'No clips to caption',
                'timestamp': datetime.utcnow().isoformat(),
            }
            db.commit()
            return {'status': 'COMPLETED', 'message': 'No clips available'}

        captioner = CaptionAgent()
        poster = AutoPoster()
        captions_generated = 0
        posts_created = 0

        for clip in clips:
            # Generate caption
            if not clip.transcription:
                try:
                    caps = captioner.generate_caption(transcript or asset.title)
                    clip.transcription = json.dumps(caps)
                    captions_generated += 1
                except Exception as e:
                    logger.error(f"Caption failed for clip {clip.id}: {e}")

            # Auto-post
            if clip.file_path and clip.file_path.startswith('http'):
                caps_data = json.loads(clip.transcription) if clip.transcription else {}
                ig_caption = caps_data.get('ig', f"{asset.title} {hashtags}")
                yt_title = caps_data.get('yt', asset.title)

                results = poster.post_clip(
                    video_url=clip.file_path,
                    caption=ig_caption,
                    title=yt_title,
                    platforms=["INSTAGRAM", "YOUTUBE"],
                )

                for r in results:
                    if r.get('status') == 'POSTED':
                        platform_name = r.get('platform', 'UNKNOWN')
                        post = Post(
                            clip_id=clip.id,
                            platform=Platform[platform_name] if platform_name in Platform.__members__ else Platform.LOCAL,
                            status=PostStatus.POSTED,
                            caption=ig_caption,
                            post_url=r.get('post_id', '') or r.get('video_id', ''),
                            platform_post_id=r.get('post_id', '') or r.get('video_id', ''),
                        )
                        db.add(post)
                        posts_created += 1
                        clip.status = ClipStatus.POSTED

        if not asset.pipeline_data:
            asset.pipeline_data = {}
        asset.pipeline_data['step_5_caption_post'] = {
            'status': 'COMPLETED',
            'captions_generated': captions_generated,
            'posts_created': posts_created,
            'timestamp': datetime.utcnow().isoformat(),
        }
        db.commit()

        logger.info(f"Step 5 done: {captions_generated} captions, {posts_created} posts")
        return {'status': 'COMPLETED', 'result': {'captions': captions_generated, 'posts': posts_created}}
