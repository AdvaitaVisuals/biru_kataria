
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
        logger.error("SEND FAILED: Token or Phone ID missing")
        return None
    url = f"{GRAPH_API_URL}/{settings.phone_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": message_body}}
    logger.info(f"Sending WhatsApp message to {to_number} via {url}")
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        logger.info(f"WhatsApp API Response: {resp.status_code} - {resp.text}")
        if resp.status_code != 200:
            logger.error(f"SEND FAILED: {resp.status_code} - {resp.text}")
        else:
            logger.info(f"Message sent successfully to {to_number}")
        return resp
    except Exception as e:
        logger.error(f"SEND FAILED (exception): {e}")
        return None

@router.get("/test")
async def manual_test():
    diag = {
        "admin_number": settings.admin_number,
        "has_token": bool(settings.whatsapp_token),
        "has_phone_id": bool(settings.phone_id),
        "token_prefix": settings.whatsapp_token[:5] if settings.whatsapp_token else "NONE",
        "phone_id": settings.phone_id
    }
    
    if not settings.whatsapp_token or not settings.phone_id:
        return {"error": "Configuration Missing on Server", "diag": diag}
        
    try:
        resp = send_whatsapp_message(settings.admin_number, "🧬 *Biru Bhai System Test*\n\nBhai, agar ye message mil raha hai toh pipeline ekdum 'Chaka-chak' hai! 🥃")
        if resp is None:
            return {"error": "Technical Failure (Check Logs)", "diag": diag}
            
        if resp.status_code == 200:
            return {"status": "Success! Check your WhatsApp.", "diag": diag}
        else:
            return {"error": f"Meta API Error: {resp.status_code}", "details": resp.text, "diag": diag}
    except Exception as e:
        return {"error": "Exception Caught", "message": str(e), "diag": diag}

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

@router.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.json()
    try:
        value = body["entry"][0]["changes"][0]["value"]
        messages = value.get("messages", [])
        if messages:
            msg = messages[0]
            from_num = msg["from"]
            
            # Simple number matching
            clean_from = "".join(filter(str.isdigit, from_num))
            clean_admin = "".join(filter(str.isdigit, settings.admin_number))

            if settings.admin_number and clean_from != clean_admin:
                logger.warning(f"Ignoring message from: {from_num}")
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
