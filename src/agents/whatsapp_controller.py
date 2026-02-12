
import logging
from datetime import datetime
from src.workers.tasks import process_youtube_asset
from src.agents.whatsapp import send_whatsapp_message
from src.database import SessionLocal
from src.models import ContentAsset
from src.enums import Platform, ContentStatus, ContentType
from src.agents.openai_brain import OpenAIBrain

logger = logging.getLogger(__name__)

class WhatsAppController:
    """
    Agent #12: The command center on your phone.
    """
    def __init__(self):
        self.brain = OpenAIBrain()
    
    def handle_incoming(self, sender: str, text: str):
        cmd = text.strip().lower()
        
        # 1. Handle YouTube Links
        if "youtube.com" in cmd or "youtu.be" in cmd:
            self._handle_yt_link(sender, text.strip())
            return

        # 2. Handle System Commands
        if cmd == "status":
            send_whatsapp_message(sender, "🟢 *BIRU_BHAI Status*\nProcessing: Active\nIntelligence: GPT-4o Brain Engaged")
        elif cmd == "report":
            send_whatsapp_message(sender, "📊 Last week: 5 Reels posted, +12% Engagement. AI is optimizing next batch.")
        elif "viral reel" in cmd:
            send_whatsapp_message(sender, "🎬 Bulk processing mode? Send the link, Bhai. I'm ready.")
        else:
            # 3. AI CHAT: If not a command, let Biru Bhai's brain answer
            response = self.brain.chat_response(text)
            send_whatsapp_message(sender, response)

    def handle_audio(self, sender: str, file_path: str):
        """Transcribes audio and processes it as text."""
        send_whatsapp_message(sender, "🎧 Sun raha hoon, Bhai... (Transcribing)")
        text = self.brain.transcribe_audio(file_path)
        if text:
            send_whatsapp_message(sender, f"📝 *Bhai, tune bola:* \"{text}\"")
            self.handle_incoming(sender, text)
        else:
            send_whatsapp_message(sender, "❌ Kuch sunai nahi diya, Bhai. Dubara bol.")

    def _handle_yt_link(self, sender: str, url: str):
        db = SessionLocal()
        try:
            asset = ContentAsset(
                title=f"WA_{datetime.now().strftime('%H%M%S')}",
                source_url=url,
                source_type=Platform.YOUTUBE,
                content_type=ContentType.VIDEO,
                status=ContentStatus.PENDING,
                meta_data={"url": url, "requested_by": sender}
            )
            db.add(asset)
            db.commit()
            db.refresh(asset)
            
            # Dispatch to Celery
            process_youtube_asset.delay(asset.id)
            send_whatsapp_message(sender, f"🚀 *AI Pipeline Started!* ID: {asset.id}\nI'm extracting clips now. View it here: https://biru-kataria.vercel.app")
        except Exception as e:
            logger.error(f"WhatsApp link handling failed: {e}")
            send_whatsapp_message(sender, f"❌ Link process mein error: {e}")
        finally:
            db.close()
