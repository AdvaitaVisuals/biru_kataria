
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
    
    # Meta API expects digits only (no +)
    clean_to = "".join(filter(str.isdigit, to_number))
    
    url = f"{GRAPH_API_URL}/{settings.phone_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": clean_to, "type": "text", "text": {"body": message_body}}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.error(f"WhatsApp API Error: Status {resp.status_code}, Body: {resp.text}")
        else:
            logger.info(f"Message sent successfully to {clean_to}")
        return resp
    except Exception as e:
        logger.error(f"Technical failure sending WhatsApp: {e}")
        return None

@router.get("/messages", response_model=list[WhatsAppMessageResponse])
async def list_whatsapp_messages(db: Session = Depends(get_db)):
    from src.models import WhatsAppMessage
    messages = db.query(WhatsAppMessage).order_by(WhatsAppMessage.timestamp.desc()).limit(50).all()
    return messages

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

@router.get("/ping")
async def whatsapp_ping(test: int = 0):
    res = {
        "status": "online",
        "admin_set": bool(settings.admin_number),
        "phone_id": settings.phone_id[:4] + "..." if settings.phone_id else "MISSING",
        "token_len": len(settings.whatsapp_token) if settings.whatsapp_token else 0
    }
    if test == 1 and settings.admin_number:
        resp = send_whatsapp_message(settings.admin_number, "🧬 *Quick Diagnostic*: Testing transmission from Biru Bhai.")
        res["test_sent"] = True
        res["api_status"] = resp.status_code if resp else "FAILED"
        res["api_body"] = resp.json() if resp and resp.status_code == 200 else (resp.text if resp else "No Response")
    return res

@router.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.json()
    logger.info(f"Incoming Webhook Body: {body}")
    try:
        value = body["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])
        if messages:
            msg = messages[0]
            from_num = msg["from"]
            
            clean_from = "".join(filter(str.isdigit, from_num))
            clean_admin = "".join(filter(str.isdigit, settings.admin_number))
            
            logger.info(f"WA Message from {clean_from}. Admin is {clean_admin}")

            if settings.admin_number and clean_from != clean_admin:
                logger.warning("Ignoring message: Number mismatch")
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
