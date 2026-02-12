
import json
import logging
from openai import OpenAI
from src.config import settings

logger = logging.getLogger(__name__)

class OpenAIBrain:
    """
    Agent #13: The Personality & Voice of Biru Bhai.
    Handles general chat, voice notes, and now SYSTEM TOOLS.
    """
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)

    def _get_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_system_status",
                    "description": "Check overall system health, asset counts, and platform connectivity.",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_recent_content",
                    "description": "List the last 5-10 content assets with their IDs, titles, and processing status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "default": 5}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_asset_pipeline_details",
                    "description": "Get the detailed step-by-step pipeline progress for a specific asset ID.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "asset_id": {"type": "integer", "description": "The ID of the content asset to check"}
                        },
                        "required": ["asset_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_recent_messages",
                    "description": "List the last 5-10 WhatsApp messages and replies.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "default": 5}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_recent_posts",
                    "description": "List the last 5-10 social media posts (Instagram/YouTube).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "default": 5}
                        }
                    }
                }
            }
        ]

    def _execute_tool(self, tool_call):
        from src.database import SessionLocal
        from src.models import ContentAsset, Clip, WhatsAppMessage
        from src.enums import PIPELINE_STEP_NAMES
        
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        db = SessionLocal()
        
        try:
            if name == "get_system_status":
                assets_count = db.query(ContentAsset).count()
                ready_count = db.query(ContentAsset).filter(ContentAsset.status == "READY").count()
                wa_logs_count = db.query(WhatsAppMessage).count()
                return {
                    "status": "ONLINE",
                    "total_assets": assets_count,
                    "ready_assets": ready_count,
                    "whatsapp_logs_total": wa_logs_count,
                    "brain": "GPT-4o Agentic"
                }
                
            elif name == "list_recent_content":
                limit = args.get("limit", 5)
                assets = db.query(ContentAsset).order_by(ContentAsset.created_at.desc()).limit(limit).all()
                return [{
                    "id": a.id, "title": a.title, "status": a.status, 
                    "step": PIPELINE_STEP_NAMES.get(a.pipeline_step, "Unknown"),
                    "created": a.created_at.strftime("%Y-%m-%d %H:%M")
                } for a in assets]
                
            elif name == "get_asset_pipeline_details":
                asset_id = args.get("asset_id")
                asset = db.query(ContentAsset).filter(ContentAsset.id == asset_id).first()
                if not asset: return {"error": "Asset not found"}
                
                return {
                    "id": asset.id,
                    "title": asset.title,
                    "current_step": PIPELINE_STEP_NAMES.get(asset.pipeline_step),
                    "step_status": asset.pipeline_step_status,
                    "meta": asset.meta_data,
                    "error": asset.error_message
                }
                
            elif name == "list_recent_messages":
                limit = args.get("limit", 5)
                msgs = db.query(WhatsAppMessage).order_by(WhatsAppMessage.timestamp.desc()).limit(limit).all()
                return [{
                    "from": m.sender, "msg": m.message, "reply": m.response,
                    "time": m.timestamp.strftime("%H:%M")
                } for m in msgs]
                
            elif name == "list_recent_posts":
                from src.models import Post
                limit = args.get("limit", 5)
                posts = db.query(Post).order_by(Post.created_at.desc()).limit(limit).all()
                return [{
                    "platform": p.platform, "status": p.status, 
                    "url": p.post_url, "time": p.created_at.strftime("%Y-%m-%d %H:%M")
                } for p in posts]
        finally:
            db.close()

    def chat_response(self, user_message: str) -> str:
        """Generates a witty Biru Bhai style response, using tools if needed."""
        try:
            messages = [
                {"role": "system", "content": (
                    "You are Biru Bhai, a wealthy, alpha, yet helpful Solo Creator from Haryana. "
                    "You are the master of your craft. You speak a mix of Hindi, English, and Haryanvi. "
                    "Personality: Confident, alpha, extremely protective of 'Bhai' (the user). "
                    "Key phrases: 'Main hoon na, tension mat le', 'System paad denge', 'Bhai hai tu mera'. "
                    "You have access to TOOLS to check the system status, list assets, and check pipeline progress. "
                    "If the user asks 'Where is my video?' or 'How is the system?', USE YOUR TOOLS first. "
                    "Keep responses short, impactful, and full of raw Haryana energy. No 'AI' talk."
                )},
                {"role": "user", "content": user_message}
            ]
            
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=self._get_tools(),
                tool_choice="auto"
            )
            
            # Handle tool calls
            tool_calls = response.choices[0].message.tool_calls
            if tool_calls:
                messages.append(response.choices[0].message)
                for tool_call in tool_calls:
                    result = self._execute_tool(tool_call)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": json.dumps(result)
                    })
                
                # Final response after tool execution
                final_response = self.client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages
                )
                return final_response.choices[0].message.content
                
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI Chat Failed: {e}")
            return "Bhai, dimaag thoda garam hai abhi. System check kar raha hoon ruk."

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
