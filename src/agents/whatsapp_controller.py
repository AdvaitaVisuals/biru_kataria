
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
    
    async def handle_incoming(self, sender: str, text: str):
        cmd = text.strip().lower()
        
        # 1. Handle YouTube Links
        if "youtube.com" in cmd or "youtu.be" in cmd:
            if "summarize" in cmd or "summary" in cmd:
                await self._handle_yt_summary(sender, text.strip())
            else:
                await self._handle_yt_link(sender, text.strip())
            return

        # 2. Handle System Commands
        if cmd == "status":
            send_whatsapp_message(sender, "🟢 *BIRU_BHAI Status*\nProcessing: Active\nIntelligence: GPT-4o Brain Engaged\nTools: YouTube Summarizer & Viral Cutter Active")
        elif cmd == "help":
            send_whatsapp_message(sender, "👊 *Biru Bhai is here!*\n\n1. Send YT link -> Viral clips start.\n2. Send YT link + 'summarize' -> Get wisdom fast.\n3. Type 'status' -> Check the system.\n4. Just talk to me, Bhai. I'm listening.")
        else:
            # 3. AI CHAT: If not a command, let Biru Bhai's brain answer
            # This is the 'LLM interaction' requested
            response = self.brain.chat_response(text)
            send_whatsapp_message(sender, response)

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
            send_whatsapp_message(sender, f"📝 *Bhai, ye rahi summary:*\n\n{summary}")
        except Exception as e:
            logger.error(f"WA Summary Failed: {e}")
            send_whatsapp_message(sender, "❌ Summary nikalne mein thoda locha ho gaya. Baad mein try kar.")


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
            send_whatsapp_message(sender, f"🚀 *AI Pipeline Started!* ID: {asset.id}\nI'm extracting clips now. View it here: https://biru-kataria.vercel.app")
        except Exception as e:
            logger.error(f"WhatsApp link handling failed: {e}")
            send_whatsapp_message(sender, f"❌ Link process mein error: {e}")
        finally:
            db.close()
