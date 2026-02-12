
import logging
import requests
from fastapi import APIRouter, Request, HTTPException, Response
from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

GRAPH_API_URL = "https://graph.facebook.com/v18.0"

def send_whatsapp_message(to_number: str, message_body: str):
    if not settings.whatsapp_token or not settings.phone_id: return
    url = f"{GRAPH_API_URL}/{settings.phone_id}/messages"
    headers = {"Authorization": f"Bearer {settings.whatsapp_token}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": message_body}}
    try:
        requests.post(url, headers=headers, json=payload, timeout=10)
    except Exception as e: logger.error(f"Failed to send: {e}")

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
            logger.info(f"Incoming WhatsApp message from: {from_num}")
            
            if settings.admin_number and from_num != settings.admin_number:
                logger.warning(f"Ignoring message from unauthorized number: {from_num}. Admin is {settings.admin_number}")
                return {"status": "ignored"}
            
            from src.agents.whatsapp_controller import WhatsAppController
            controller = WhatsAppController()

            if msg["type"] == "text":
                controller.handle_incoming(from_num, msg["text"]["body"])
            elif msg["type"] == "audio":
                media_id = msg["audio"]["id"]
                file_path = download_whatsapp_media(media_id)
                if file_path:
                    controller.handle_audio(from_num, file_path)
                    
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        
    return {"status": "ok"}
