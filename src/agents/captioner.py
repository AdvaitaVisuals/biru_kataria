
import logging
from openai import OpenAI
from src.config import settings

logger = logging.getLogger(__name__)

class CaptionAgent:
    """
    Agent #4: Generates Haryanvi/Hinglish captions for social media.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)

    def generate_caption(self, text: str, tone: str = "Attitude") -> dict:
        """
        Generates platform-specific captions.
        """
        if not settings.openai_api_key:
            return {"ig": "System offline", "yt": "#Error"}

        prompt = (
            f"Context: {text}\n"
            f"Tone: {tone} (Haryanvi Style)\n"
            "Generate 3 variants of social media captions:\n"
            "1. Instagram Reel (Hinglish + Emojis + Haryanvi Slang)\n"
            "2. YouTube Shorts (Bold title + Hashtags)\n"
            "3. Haryanvi lyrics focus.\n"
            "Return JSON only: { 'ig': '...', 'yt': '...', 'lyrics': '...' }"
        )

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            import json
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Captioning failed: {e}")
            return {"ig": f"Check this out! #Viral", "yt": "New Video out now!"}
