
import logging
from openai import OpenAI
from src.config import settings

logger = logging.getLogger(__name__)

class OpenAIBrain:
    """
    Agent #13: The Personality & Voice of Biru Bhai.
    Handles general chat and voice note transcription.
    """
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)

    def chat_response(self, user_message: str) -> str:
        """Generates a witty Biru Bhai style response."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": (
                        "You are Biru Bhai, a wealthy, alpha, yet helpful Solo Creator from Haryana. "
                        "You speak a mix of Hindi, English, and Haryanvi. You are confident, "
                        "slightly arrogant but very supportive of your 'Bhai' (the user). "
                        "Your tone is: 'Main hoon na, tension mat le'. "
                        "Keep responses short, impactful, and full of personality."
                    )},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=200
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI Chat Failed: {e}")
            return "Bhai, dimaag thoda garam hai abhi (OpenAI Error). Thodi der me baat karte hain."

    def transcribe_audio(self, audio_file_path: str) -> str:
        """Transcribes a voice note using Whisper."""
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file
                )
            return transcript.text
        except Exception as e:
            logger.error(f"Whisper Transcription Failed: {e}")
            return ""
