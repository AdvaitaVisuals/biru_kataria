
import logging
from datetime import datetime
from src.workers.tasks import process_youtube_asset
from src.agents.whatsapp import send_whatsapp_message
from src.database import SessionLocal
from src.models import ContentAsset, WhatsAppMessage
from src.enums import Platform, ContentStatus, ContentType
from src.agents.openai_brain import OpenAIBrain

logger = logging.getLogger(__name__)

class WhatsAppController:
    """
    Agent #12: The command center on your phone.
    """
    def __init__(self):
        self.brain = OpenAIBrain()
    
    async def handle_incoming(self, sender: str, text: str):
        # 0. Log incoming message to DB
        db = SessionLocal()
        try:
            msg_log = WhatsAppMessage(sender=sender, message=text)
            db.add(msg_log)
            db.commit()
            db.refresh(msg_log)
            msg_id = msg_log.id
        except Exception as e:
            logger.error(f"Failed to log WA message: {e}")
            msg_id = None
        finally:
            db.close()

        cmd = text.strip().lower()
        response_text = ""
        
        # 1. Handle YouTube Links
        if "youtube.com" in cmd or "youtu.be" in cmd:
            if "summarize" in cmd or "summary" in cmd:
                response_text = await self._handle_yt_summary(sender, text.strip())
            else:
                response_text = await self._handle_yt_link(sender, text.strip())
        
        # 2. Handle System Commands
        elif cmd == "help":
            response_text = "👊 *Biru Bhai is here!*\n\n1. Send YT link -> Viral clips start.\n2. Send YT link + 'summarize' -> Get wisdom fast.\n3. Type 'status' -> Check the system.\n4. Just talk to me, Bhai. I'm listening."
            send_whatsapp_message(sender, response_text)
        else:
            # 3. AI CHAT
            response_text = self.brain.chat_response(text)
            send_whatsapp_message(sender, response_text)

        # Update log with response
        if msg_id:
            db = SessionLocal()
            try:
                msg_log = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == msg_id).first()
                if msg_log:
                    msg_log.response = response_text
                    db.commit()
            finally:
                db.close()

    async def _handle_yt_summary(self, sender: str, text: str):
        """Extracts URL and gets summary via MCP logic."""
        import re
        urls = re.findall(r'(https?://[^\s]+)', text)
        if not urls:
            send_whatsapp_message(sender, "❌ Bhai, link toh bhej summarize karne ke liye!")
            return
            
        url = urls[0]
        send_whatsapp_message(sender, "🚬 Biru Bhai is watching the video... Sahi cheez nikal ke deta hoon, rukiye.")
        
        from src.agents.youtube_summary_mcp import call_summarizer_api
        
        try:
            summary = await call_summarizer_api(url)
            response = f"📝 *Bhai, ye rahi summary:*\n\n{summary}"
            send_whatsapp_message(sender, response)
            return response
        except Exception as e:
            logger.error(f"WA Summary Failed: {e}")
            err_msg = "❌ Summary nikalne mein thoda locha ho gaya. Baad mein try kar."
            send_whatsapp_message(sender, err_msg)
            return err_msg


    async def handle_audio(self, sender: str, file_path: str):
        """Transcribes audio and processes it as text."""
        send_whatsapp_message(sender, "🎧 Sun raha hoon, Bhai... (Transcribing)")
        text = self.brain.transcribe_audio(file_path)
        if text:
            send_whatsapp_message(sender, f"📝 *Bhai, tune bola:* \"{text}\"")
            await self.handle_incoming(sender, text)
        else:
            send_whatsapp_message(sender, "❌ Kuch sunai nahi diya, Bhai. Dubara bol.")

    async def _handle_yt_link(self, sender: str, url: str):
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
            response = f"🚀 *AI Pipeline Started!* ID: {asset.id}\nI'm extracting clips now. View it here: https://biru-kataria.vercel.app"
            send_whatsapp_message(sender, response)
            return response
        except Exception as e:
            logger.error(f"WhatsApp link handling failed: {e}")
            err_msg = f"❌ Link process mein error: {e}"
            send_whatsapp_message(sender, err_msg)
            return err_msg
        finally:
            db.close()
