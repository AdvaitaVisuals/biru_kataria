
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
            },
            {
                "type": "function",
                "function": {
                    "name": "create_event",
                    "description": "Schedule a new event, meeting, or recording in Biru Bhai's calendar. Extract date, time, location (venue), and attendees (person name).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Title of the event"},
                            "start_time": {"type": "string", "description": "ISO format start time (e.g. 2024-02-13T10:00:00). Ensure the date is correct relative to today."},
                            "description": {"type": "string", "description": "Details about the event"},
                            "location": {"type": "string", "description": "Location or Venue of the event"},
                            "attendees": {"type": "string", "description": "Name(s) of person/people involved"},
                            "event_type": {"type": "string", "enum": ["MEETING", "RECORDING", "VIRAL_DROP"]}
                        },
                        "required": ["title", "start_time"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_upcoming_events",
                    "description": "List the upcoming 5-10 events from the calendar.",
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

            elif name == "create_event":
                from src.agents.calendar_agent import CalendarAgent
                cal = CalendarAgent()
                return cal.create_event(
                    title=args.get("title"),
                    start_time=args.get("start_time"),
                    description=args.get("description", ""),
                    event_type=args.get("event_type", "MEETING"),
                    location=args.get("location"),
                    attendees=args.get("attendees")
                )

            elif name == "list_upcoming_events":
                from src.agents.calendar_agent import CalendarAgent
                cal = CalendarAgent()
                return cal.list_events(limit=args.get("limit", 5))

        finally:
            db.close()

    def chat_response(self, user_message: str, sender: str = None) -> str:
        """Generates a witty Biru Bhai style response, using tools if needed. Can include context from 'sender' history."""
        from datetime import datetime
        from src.database import SessionLocal
        from src.models import WhatsAppMessage
        
        today_date = datetime.now().strftime("%d %b %Y, %A")
        
        # Build context from DB if sender is known
        context_messages = []
        if sender:
            db = SessionLocal()
            try:
                # Fetch last 5 interactions (excluding current pending one)
                # We skip the most recent one (offset 1) because it is the current message we are processing.
                history = db.query(WhatsAppMessage).filter(WhatsAppMessage.sender == sender).order_by(WhatsAppMessage.timestamp.desc()).offset(1).limit(5).all()
                history.reverse()
                
                for msg in history:
                    if msg.message:
                        context_messages.append({"role": "user", "content": msg.message})
                    if msg.response:
                        context_messages.append({"role": "assistant", "content": msg.response})
            except Exception as e:
                logger.error(f"Failed to fetch context: {e}")
            finally:
                db.close()

        try:
            # System Prompt
            system_prompt = {
                "role": "system", 
                "content": (
                    f"You are Biru Bhai, a wealthy, alpha, yet helpful Solo Creator from Haryana. "
                    f"Today is {today_date}. "
                    "You are the master of your craft. You speak a mix of Hindi, English, and Haryanvi. "
                    "Personality: Confident, alpha, extremely protective of 'Bhai' (the user). "
                    "Key phrases: 'Main hoon na, tension mat le', 'System paad denge', 'Bhai hai tu mera'. "
                    "You have access to TOOLS to check system status, list assets, check pipeline, and MANAGE THE CALENDAR. "
                    "IMPORTANT: "
                    "1. If user asks to create/set a Meeting/Event -> You MUST call the 'create_event' tool immediately. Do not just say you will do it. "
                    "2. If details (Who, When, Where) are missing -> ASK for them. Do not guess. "
                    "3. If user asks to Post -> You MUST explain you need the media file first unless they sent one. "
                    "Keep responses short, impactful, and full of raw Haryana energy. No 'AI' talk."
                )
            }
            
            messages = [system_prompt] + context_messages + [{"role": "user", "content": user_message}]
            
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
