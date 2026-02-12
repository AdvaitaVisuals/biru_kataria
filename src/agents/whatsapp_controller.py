
import logging
from src.workers.tasks import process_youtube_asset
from src.agents.whatsapp import send_whatsapp_message
from src.database import SessionLocal
from src.models import ContentAsset
from src.enums import Platform, ContentStatus, ContentType

logger = logging.getLogger(__name__)

class WhatsAppController:
    """
    Agent #12: The command center on your phone.
    """
    
    def handle_incoming(self, sender: str, text: str):
        cmd = text.strip().lower()
        
        # 1. Handle YouTube Links
        if "youtube.com" in cmd or "youtu.be" in cmd:
            self._handle_yt_link(sender, text.strip())
            return

        # 2. Handle System Commands
        if cmd == "status":
            send_whatsapp_message(sender, "🟢 *BIRU_BHAI Status*\nProcessing: Active\nAgents: 12 Initiated")
        elif cmd == "report":
            send_whatsapp_message(sender, "📊 Last week: 5 Reels posted, +12% Engagement.")
        elif "viral reel" in cmd:
            send_whatsapp_message(sender, "🎬 Which song or link? Send it here, and I'll handle the rest.")
        else:
            send_whatsapp_message(sender, f"Command Samjh nahi aaya, Bhai: '{text}'\nTry: 'youtube.com/...', 'status', 'report'")

    def _handle_yt_link(self, sender: str, url: str):
        db = SessionLocal()
        try:
            asset = ContentAsset(
                title="WhatsApp Request",
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
            send_whatsapp_message(sender, f"🚀 *Link Received!* Asset ID: {asset.id}\nI'm downloading and cutting 10 clips now. Check Streamlit in 5 mins.")
        except Exception as e:
            logger.error(f"WhatsApp link handling failed: {e}")
            send_whatsapp_message(sender, f"❌ Link process mein error: {e}")
        finally:
            db.close()
