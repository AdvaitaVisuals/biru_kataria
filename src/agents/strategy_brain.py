
import os
import base64
import json
import logging
from openai import OpenAI
from src.config import settings

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.openai_api_key)

def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

class StrategyBrain:
    """
    The High-Level Intelligence Layer.
    Uses Vision AI to 'see' the video and find viral moments.
    """
    
    def analyze_content(self, transcription_text: str, frame_paths: list) -> list:
        """
        Send transcript and frames to GPT-4o to get clipping decisions.
        """
        if not settings.openai_api_key:
            logger.error("OpenAI API Key missing")
            return []

        # Construct payload with frames
        content = [
            {
                "type": "text", 
                "text": f"You are Biru Bhai's Strategy Brain. Analyze this video's frames and transcript. \n\n"
                        f"TRANSCRIPT: {transcription_text}\n\n"
                        f"Identify exactly 10 viral segments of 30 seconds each. \n"
                        f"Focus on visual energy, hook delivery, and high engagement moments. \n"
                        f"Return ONLY a clean JSON list of objects with 'start', 'end', and 'reason'."
            }
        ]

        # Add subsampled frames to keep context window manageable
        # We take up to 10-15 frames max
        step = max(1, len(frame_paths) // 15)
        for i in range(0, len(frame_paths), step):
            base64_image = encode_image(frame_paths[i])
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": content}],
                max_tokens=1000,
                response_format={ "type": "json_object" }
            )
            
            result = json.loads(response.choices[0].message.content)
            # Expecting {"segments": [{"start": 10, "end": 40, "reason": "..."}, ...]}
            segments = result.get("segments", [])
            logger.info(f"Brain identified {len(segments)} segments")
            return segments

        except Exception as e:
            logger.error(f"Strategy Brain failed: {e}")
            return []
