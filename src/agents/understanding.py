"""
Understanding Agent — The Ears & Eyes of BIRU_BHAI

Responsibilities:
  1. Transcribe audio/video → text (Whisper, small model)
  2. Detect timestamps of speech segments
  3. Score segments for "hook potential" (energy, pace, keywords)

This agent does NOT make decisions. It only produces structured data.
Input  → Raw file path
Output → Transcription + scored segments
"""

import os
import json
import logging
import subprocess
from typing import Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class Segment:
    """A single transcribed segment with scoring."""
    start: float
    end: float
    text: str
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0
    # Derived scores (calculated after transcription)
    hook_score: float = 0.0  # 0.0 - 1.0: how "hooky" is this segment?
    energy_score: float = 0.0  # 0.0 - 1.0: energy/pace of delivery


@dataclass
class TranscriptionResult:
    """Complete output of the Understanding Agent."""
    file_path: str
    language: str = "hi"  # Default: Hindi (Haryanvi creator)
    full_text: str = ""
    duration: float = 0.0
    segments: list = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "full_text": self.full_text,
            "duration": self.duration,
            "segments": [asdict(s) if isinstance(s, Segment) else s for s in self.segments],
            "error": self.error,
        }


# ============================================================
# HOOK DETECTION — Keyword-based scoring for Haryanvi content
# ============================================================

# High-energy Haryanvi/Hindi keywords that signal viral potential
HOOK_KEYWORDS = [
    # Attention grabbers
    "bhai", "yaar", "dekh", "sun", "sach", "asli", "real",
    # Emotion triggers
    "dil", "pyaar", "dard", "rula", "hasa", "mast", "jhakas",
    # Viral signals
    "viral", "trending", "hit", "super", "best", "top",
    # Action words
    "chal", "kar", "bol", "bata", "sikha",
]


def _score_segment_hook(segment: Segment) -> float:
    """Score a segment's hook potential based on keywords + delivery signals."""
    score = 0.0
    text_lower = segment.text.lower()

    # 1. Keyword hits (0.0 - 0.4)
    keyword_hits = sum(1 for kw in HOOK_KEYWORDS if kw in text_lower)
    score += min(keyword_hits * 0.1, 0.4)

    # 2. Short, punchy segments are hookier (0.0 - 0.3)
    duration = segment.end - segment.start
    if 2.0 <= duration <= 8.0:
        score += 0.3  # Sweet spot for hooks
    elif duration <= 15.0:
        score += 0.15

    # 3. Confidence penalty — low confidence = mumbling = not a hook
    if segment.avg_logprob < -1.0:
        score *= 0.5  # Halve score for low-confidence transcription

    # 4. Beginning of content gets a boost (first 30 seconds)
    if segment.start <= 30.0:
        score += 0.1

    return min(score, 1.0)


def _score_segment_energy(segment: Segment) -> float:
    """Estimate energy from speech density (words per second)."""
    duration = segment.end - segment.start
    if duration <= 0:
        return 0.0

    word_count = len(segment.text.split())
    words_per_second = word_count / duration

    # Hindi/Haryanvi average is ~2-3 wps. Fast = high energy.
    if words_per_second >= 4.0:
        return 0.9
    elif words_per_second >= 3.0:
        return 0.7
    elif words_per_second >= 2.0:
        return 0.5
    elif words_per_second >= 1.0:
        return 0.3
    else:
        return 0.1


# ============================================================
# CORE: Transcription with Whisper
# ============================================================

def transcribe(file_path: str, model_size: str = "base") -> TranscriptionResult:
    """
    Transcribe a video/audio file using OpenAI Whisper (local model).

    Args:
        file_path: Absolute path to the media file
        model_size: Whisper model size — "tiny", "base", "small" (default: "base")
                    Bigger = more accurate but slower. "base" is the sweet spot for MVP.

    Returns:
        TranscriptionResult with full text, segments, and scores
    """
    result = TranscriptionResult(file_path=file_path)

    if not os.path.exists(file_path):
        result.error = f"File not found: {file_path}"
        logger.error(result.error)
        return result

    try:
        import whisper

        logger.info(f"Loading Whisper model: {model_size}")
        model = whisper.load_model(model_size)

        logger.info(f"Transcribing: {file_path}")
        whisper_result = model.transcribe(
            file_path,
            language=None,  # Auto-detect (works for Hindi/Haryanvi)
            verbose=False,
        )

        result.language = whisper_result.get("language", "hi")
        result.full_text = whisper_result.get("text", "").strip()

        # Process segments
        raw_segments = whisper_result.get("segments", [])
        for seg in raw_segments:
            segment = Segment(
                start=round(seg["start"], 2),
                end=round(seg["end"], 2),
                text=seg["text"].strip(),
                avg_logprob=seg.get("avg_logprob", 0.0),
                no_speech_prob=seg.get("no_speech_prob", 0.0),
            )
            # Score the segment
            segment.hook_score = round(_score_segment_hook(segment), 3)
            segment.energy_score = round(_score_segment_energy(segment), 3)
            result.segments.append(segment)

        # Calculate total duration from last segment
        if result.segments:
            result.duration = result.segments[-1].end

        logger.info(
            f"Transcription complete: {len(result.segments)} segments, "
            f"{result.duration:.1f}s, language={result.language}"
        )

    except ImportError:
        result.error = (
            "Whisper is not installed. Install with: pip install openai-whisper\n"
            "Also requires FFmpeg to be installed on the system."
        )
        logger.error(result.error)
    except Exception as e:
        result.error = f"Transcription failed: {str(e)}"
        logger.error(result.error, exc_info=True)

    return result


def get_top_segments(result: TranscriptionResult, top_n: int = 10) -> list[Segment]:
    """Get the top N most hookable segments, sorted by combined score."""
    if not result.segments:
        return []

    scored = sorted(
        result.segments,
        key=lambda s: (s.hook_score * 0.6 + s.energy_score * 0.4),
        reverse=True,
    )
    return scored[:top_n]


def get_media_duration(file_path: str) -> Optional[float]:
    """Get media file duration using FFprobe (no Whisper needed)."""
    try:
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json",
            file_path
        ]
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if output.returncode == 0:
            data = json.loads(output.stdout)
            return float(data["format"]["duration"])
    except Exception as e:
        logger.warning(f"Could not get duration for {file_path}: {e}")
    return None
