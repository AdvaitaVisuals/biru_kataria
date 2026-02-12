
import os
import yt_dlp
import logging

logger = logging.getLogger(__name__)

def download_youtube_video(url: str, output_path: str) -> bool:
    """
    Download a YouTube video to a local path.
    """
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        logger.error(f"YouTube Download Failed: {e}")
        return False
