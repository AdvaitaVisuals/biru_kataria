
import logging
import requests
from fastapi import APIRouter, Request, HTTPException, Response, Depends
from sqlalchemy.orm import Session
from src.config import settings
from src.database import get_db
from src.schemas import WhatsAppMessageResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

GRAPH_API_URL = "https://graph.facebook.com/v18.0"

def send_whatsapp_message(to_number: str, message_body: str):
    if not settings.whatsapp_token or not settings.phone_id: 
        logger.error("Token or Phone ID missing")
        return None
    url = f"{GRAPH_API_URL}/{settings.phone_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": message_body}}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error(f"WhatsApp API Error: {resp.status_code} - {resp.text}")
        else:
            logger.info(f"Message sent successfully to {to_number}")
        return resp
    except Exception as e:
        logger.error(f"Technical failure sending WhatsApp: {e}")
        return None

@router.get("/messages", response_model=list[WhatsAppMessageResponse])
async def list_whatsapp_messages(db: Session = Depends(get_db)):
    from src.models import WhatsAppMessage
    messages = db.query(WhatsAppMessage).order_by(WhatsAppMessage.timestamp.desc()).limit(50).all()
    return messages

@router.get("/test-msg")
async def test_whatsapp_message():
    def mask(s): return f"{s[:4]}...{s[-4:]}" if len(s) > 8 else "SET" if s else "NOT SET"
    
    diag = {
        "admin_number": settings.admin_number,
        "token_masked": mask(settings.whatsapp_token),
        "phone_id_masked": mask(settings.phone_id),
        "phone_id_actual": settings.phone_id
    }
    
    if not settings.whatsapp_token or not settings.phone_id:
        return {"status": "Config Missing in Vercel", "diag": diag}
        
    if not settings.admin_number:
        return {"status": "Error", "message": "ADMIN_NUMBER (Bhai's Phone) is missing in Vercel Settings"}
        
    try:
        resp = send_whatsapp_message(settings.admin_number, "🧬 *Biru Bhai System Check*\n\nBhai, testing message dispatched!")
        if resp is None:
            return {"status": "Technical Error", "details": "Function returned None"}
        return {
            "status_code": resp.status_code,
            "api_response": resp.json() if resp.status_code == 200 else resp.text,
            "diag": diag
        }
    except Exception as e:
        return {"status": "Exception", "error": str(e)}

from fastapi.responses import PlainTextResponse

@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    if mode == "subscribe" and token == settings.verify_token:
        logger.info("Webhook verified successfully")
        return challenge
    
    logger.warning(f"Webhook verification failed. Token mismatch: {token} != {settings.verify_token}")
    return Response(content="Verification failed", status_code=403)

def download_whatsapp_media(media_id: str) -> str:
    """Downloads media from WhatsApp and returns the local file path."""
    if not settings.whatsapp_token: return ""
    
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}"}
    try:
        # Get Media URL
        res = requests.get(f"{GRAPH_API_URL}/{media_id}", headers=headers, timeout=10)
        res.raise_for_status()
        url = res.json().get("url")
        if not url: return ""

        # Download file
        res = requests.get(url, headers=headers, timeout=30)
        res.raise_for_status()
        
        # Save to /tmp
        import os
        os.makedirs("/tmp/media", exist_ok=True)
        file_path = f"/tmp/media/{media_id}.ogg"
        with open(file_path, "wb") as f:
            f.write(res.content)
        return file_path
    except Exception as e:
        logger.error(f"Media Download Failed: {e}")
        return ""

@router.post("/webhook")
async def receive_webhook(request: Request):
    logger.info(f"Incoming Webhook Header: {dict(request.headers)}")
    body = await request.json()
    logger.info(f"Incoming Webhook Body: {body}")
    try:
        value = body["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])
        if messages:
            msg = messages[0]
            from_num = msg["from"]
            logger.info(f"Incoming WhatsApp message from: {from_num}")
            
            # Format numbers for comparison (remove + and any non-numeric chars)
            clean_from = "".join(filter(str.isdigit, from_num))
            clean_admin = "".join(filter(str.isdigit, settings.admin_number))

            if settings.admin_number and clean_from != clean_admin:
                logger.warning(f"Ignoring message from unauthorized number: {from_num}. Admin is {settings.admin_number}")
                return {"status": "ignored"}
            
            from src.agents.whatsapp_controller import WhatsAppController
            controller = WhatsAppController()

            if msg["type"] == "text":
                await controller.handle_incoming(from_num, msg["text"]["body"])
            elif msg["type"] == "audio":
                media_id = msg["audio"]["id"]
                file_path = download_whatsapp_media(media_id)
                if file_path:
                    await controller.handle_audio(from_num, file_path)
                    
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        
    return {"status": "ok"}
