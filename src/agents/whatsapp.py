
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

@router.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    if mode == "subscribe" and token == settings.verify_token:
        return int(challenge)
    raise HTTPException(status_code=403)

@router.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.json()
    try:
        messages = body["entry"][0]["changes"][0]["value"].get("messages", [])
        if messages:
            msg = messages[0]
            from_num = msg["from"]
            if settings.admin_number and from_num != settings.admin_number: return {"status": "ignored"}
            
            if msg["type"] == "text":
                from src.agents.whatsapp_controller import WhatsAppController
                WhatsAppController().handle_incoming(from_num, msg["text"]["body"])
    except Exception: pass
    return {"status": "ok"}
