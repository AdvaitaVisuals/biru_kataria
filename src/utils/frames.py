
import os
import cv2
import logging
from typing import List

logger = logging.getLogger(__name__)

def extract_frames(video_path: str, output_dir: str, interval_seconds: int = 10) -> List[str]:
    """
    Extract frames from a video at specific intervals.
    Returns a list of file paths to the extracted frames.
    """
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return []

    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        logger.error("Could not get FPS for video")
        return []

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / fps
    
    frame_paths = []
    
    for i in range(0, int(duration), interval_seconds):
        frame_id = int(i * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ret, frame = cap.read()
        
        if ret:
            frame_name = f"frame_{i:04d}s.jpg"
            frame_path = os.path.join(output_dir, frame_name)
            # Resize for AI consumption (GPT-4o recommend smaller/mid size for cost/speed)
            # We'll stick to a reasonable size
            cv2.imwrite(frame_path, frame)
            frame_paths.append(frame_path)
        else:
            break
            
    cap.release()
    logger.info(f"Extracted {len(frame_paths)} frames from {video_path}")
    return frame_paths
