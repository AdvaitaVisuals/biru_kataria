"""
Viral Cutter Agent — The Scissor Hands of BIRU_BHAI

Responsibilities:
  1. Take scored segments from Understanding Agent
  2. Group nearby high-scoring segments into clip windows
  3. Use FFmpeg to physically slice video
  4. Output: 9:16 vertical clips, ready for Reels/Shorts

Constraints (from SPECIFICATION):
  - MAX 25 clips per source asset
  - Target format: vertical 9:16
  - This agent does NOT decide what to post — only what to CUT

Input  → Source file + scored segments
Output → List of clip file paths
"""

import os
import json
import logging
import subprocess
from typing import Optional
from dataclasses import dataclass, field, asdict
from src.config import settings  # <--- Import settings

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
MAX_CLIPS_PER_ASSET = 25
MIN_CLIP_DURATION = 5.0    # seconds — shorter = too abrupt
MAX_CLIP_DURATION = 60.0   # seconds — longer = not a "short"
DEFAULT_CLIP_DURATION = 30.0  # seconds — default clip length
MERGE_GAP = 3.0            # If two segments are < 3s apart, merge them


@dataclass
class ClipSpec:
    """Specification for a single clip to cut."""
    start_time: float
    end_time: float
    duration: float = 0.0
    score: float = 0.0  # Combined hook + energy score
    source_segments: list = field(default_factory=list)  # Text from source segments

    def __post_init__(self):
        self.duration = round(self.end_time - self.start_time, 2)


@dataclass
class CutResult:
    """Result of cutting a single clip."""
    clip_spec: ClipSpec
    output_path: str
    success: bool = False
    error: Optional[str] = None
    file_size_mb: float = 0.0

    def to_dict(self) -> dict:
        return {
            "start_time": self.clip_spec.start_time,
            "end_time": self.clip_spec.end_time,
            "duration": self.clip_spec.duration,
            "score": self.clip_spec.score,
            "output_path": self.output_path,
            "success": self.success,
            "error": self.error,
            "file_size_mb": self.file_size_mb,
        }


# ============================================================
# SEGMENT GROUPING — Merge nearby high-scoring segments
# ============================================================

def build_clip_windows(segments: list, min_score: float = 0.3) -> list[ClipSpec]:
    """
    Group nearby high-scoring segments into clip windows.
    """
    # Filter: only keep high-scoring segments
    candidates = []
    for seg in segments:
        # Handle both dict and object segment formats
        if isinstance(seg, dict):
            combined = seg.get("hook_score", 0) * 0.6 + seg.get("energy_score", 0) * 0.4
            start, end, text = seg["start"], seg["end"], seg.get("text", "")
        else:
            combined = seg.hook_score * 0.6 + seg.energy_score * 0.4
            start, end, text = seg.start, seg.end, seg.text

        if combined >= min_score:
            candidates.append({
                "start": start,
                "end": end,
                "text": text,
                "score": round(combined, 3),
            })

    if not candidates:
        logger.warning("No segments above minimum score threshold")
        return []

    # Sort by time
    candidates.sort(key=lambda x: x["start"])

    # Merge nearby segments into windows
    windows = []
    current_window = {
        "start": candidates[0]["start"],
        "end": candidates[0]["end"],
        "score": candidates[0]["score"],
        "texts": [candidates[0]["text"]],
    }

    for seg in candidates[1:]:
        gap = seg["start"] - current_window["end"]
        if gap <= MERGE_GAP:
            # Merge: extend the window
            current_window["end"] = seg["end"]
            current_window["score"] = max(current_window["score"], seg["score"])
            current_window["texts"].append(seg["text"])
        else:
            # New window
            windows.append(current_window)
            current_window = {
                "start": seg["start"],
                "end": seg["end"],
                "score": seg["score"],
                "texts": [seg["text"]],
            }
    windows.append(current_window)

    # Convert to ClipSpecs with padding
    clip_specs = []
    for w in windows:
        duration = w["end"] - w["start"]

        # Pad short clips to minimum duration
        if duration < MIN_CLIP_DURATION:
            pad = (MIN_CLIP_DURATION - duration) / 2
            w["start"] = max(0, w["start"] - pad)
            w["end"] = w["end"] + pad

        # Cap long clips
        if (w["end"] - w["start"]) > MAX_CLIP_DURATION:
            w["end"] = w["start"] + MAX_CLIP_DURATION

        clip_specs.append(ClipSpec(
            start_time=round(w["start"], 2),
            end_time=round(w["end"], 2),
            score=w["score"],
            source_segments=w["texts"],
        ))

    # Sort by score (best first), cap at max
    clip_specs.sort(key=lambda c: c.score, reverse=True)
    clip_specs = clip_specs[:MAX_CLIPS_PER_ASSET]

    logger.info(f"Built {len(clip_specs)} clip windows from {len(candidates)} candidate segments")
    return clip_specs


# ============================================================
# FFMPEG CUTTING — The actual slicing
# ============================================================

def cut_clip(
    source_path: str,
    clip_spec: ClipSpec,
    output_path: str,
    vertical: bool = True,
) -> CutResult:
    """
    Cut a single clip from source video using FFmpeg.
    """
    result = CutResult(clip_spec=clip_spec, output_path=output_path)

    if not os.path.exists(source_path):
        result.error = f"Source file not found: {source_path}"
        logger.error(result.error)
        return result

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    try:
        # Use configured FFMPEG_PATH
        cmd = [
            settings.ffmpeg_path, "-y",  # Overwrite output
            "-ss", str(clip_spec.start_time),  # Start time (before -i for fast seek)
            "-i", source_path,
            "-t", str(clip_spec.duration),  # Duration
        ]

        if vertical:
            # Convert to 9:16 vertical (1080x1920)
            # Center-crop from horizontal to vertical
            cmd.extend([
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
            ])

        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",       # Balance speed vs quality
            "-crf", "23",            # Good quality
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",  # Web-friendly
            output_path,
        ])

        # IMPORTANT: Use list format for args to handle spaces in paths correctly
        logger.info(f"Cutting clip with: {settings.ffmpeg_path}")

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,  # 3 min timeout per clip just to be safe
        )

        if process.returncode == 0:
            result.success = True
            if os.path.exists(output_path):
                result.file_size_mb = round(os.path.getsize(output_path) / (1024 * 1024), 2)
            logger.info(f"Clip cut successfully: {result.file_size_mb}MB")
        else:
            result.error = f"FFmpeg error: {process.stderr[-500:]}"
            logger.error(result.error)

    except subprocess.TimeoutExpired:
        result.error = "FFmpeg timed out (>180s)"
        logger.error(result.error)
    except FileNotFoundError:
        result.error = f"FFmpeg executable not found at: {settings.ffmpeg_path}"
        logger.error(result.error)
    except Exception as e:
        result.error = f"Cutting failed: {str(e)}"
        logger.error(result.error, exc_info=True)

    return result


def cut_all_clips(
    source_path: str,
    clip_specs: list[ClipSpec],
    output_dir: str,
    vertical: bool = True,
) -> list[CutResult]:
    """
    Cut all clips from a source video.
    """
    os.makedirs(output_dir, exist_ok=True)
    results = []

    base_name = os.path.splitext(os.path.basename(source_path))[0]

    for i, spec in enumerate(clip_specs):
        output_path = os.path.join(
            output_dir,
            f"{base_name}_clip_{i+1:03d}_{spec.start_time:.0f}s_{spec.end_time:.0f}s.mp4"
        )
        result = cut_clip(source_path, spec, output_path, vertical=vertical)
        results.append(result)

    success_count = sum(1 for r in results if r.success)
    logger.info(f"Cutting complete: {success_count}/{len(results)} clips successful")

    return results


def get_video_metadata(file_path: str) -> Optional[dict]:
    """Get video metadata using configured ffprobe."""
    try:
        # Use configured FFPROBE_PATH
        cmd = [
            settings.ffprobe_path, "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            file_path
        ]
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if output.returncode == 0:
            data = json.loads(output.stdout)
            fmt = data.get("format", {})
            video_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                {}
            )
            return {
                "duration": float(fmt.get("duration", 0)),
                "size_mb": round(int(fmt.get("size", 0)) / (1024 * 1024), 2),
                "format": fmt.get("format_name", "unknown"),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": eval(video_stream.get("r_frame_rate", "0/1")) if video_stream.get("r_frame_rate") else 0,
                "codec": video_stream.get("codec_name", "unknown"),
            }
    except Exception as e:
        logger.warning(f"Could not get metadata for {file_path}: {e}")
    return None
