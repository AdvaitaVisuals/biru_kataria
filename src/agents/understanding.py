
import os
import json
import logging
from typing import Optional
from dataclasses import dataclass, field, asdict
from openai import OpenAI
from src.config import settings

logger = logging.getLogger(__name__)

@dataclass
class Segment:
    start: float
    end: float
    text: str
    avg_logprob: float = 0.0
    no_speech_prob: float = 0.0
    hook_score: float = 0.0
    energy_score: float = 0.0

@dataclass
class TranscriptionResult:
    file_path: str
    language: str = "hi"
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
            "segments": [asdict(s) if hasattr(s, 'start') else s for s in self.segments],
            "error": self.error,
        }

def transcribe(file_path: str, model_size: str = "unused") -> TranscriptionResult:
    """
    Transcribe via OpenAI API (Serverless Friendly).
    Removes dependency on local 'whisper' and 'torch' (800MB+).
    """
    result = TranscriptionResult(file_path=file_path)
    
    if not settings.openai_api_key:
        result.error = "OpenAI API Key is missing. Required for serverless transcription."
        return result

    client = OpenAI(api_key=settings.openai_api_key)

    try:
        logger.info(f"Uploading for API Transcription: {file_path}")
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )

        result.full_text = transcript.text
        result.language = transcript.language
        result.duration = transcript.duration

        for seg in transcript.segments:
            s = Segment(
                start=seg['start'],
                end=seg['end'],
                text=seg['text'],
                avg_logprob=seg.get('avg_logprob', 0.0),
                no_speech_prob=seg.get('no_speech_prob', 0.0)
            )
            # Basic score
            s.hook_score = 0.5 if len(s.text.split()) > 5 else 0.2
            result.segments.append(s)

        return result
    except Exception as e:
        logger.error(f"API Transcription failed: {e}")
        result.error = str(e)
        return result
