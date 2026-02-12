
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from src.database import SessionLocal
from src.models import Event

logger = logging.getLogger(__name__)

class CalendarAgent:
    """
    Agent #14: The Scheduler.
    Handles appointments, recordings, and viral event timing.
    """
    
    def create_event(self, title: str, start_time: str, end_time: str = None, description: str = "", event_type: str = "MEETING"):
        db = SessionLocal()
        try:
            # Parse ISO strings
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00')) if end_time else start_dt
            
            event = Event(
                title=title,
                description=description,
                start_time=start_dt,
                end_time=end_dt,
                event_type=event_type
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            return {"success": True, "event_id": event.id, "title": event.title}
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def list_events(self, limit: int = 10):
        db = SessionLocal()
        try:
            events = db.query(Event).order_by(Event.start_time.asc()).limit(limit).all()
            return [{
                "id": e.id,
                "title": e.title,
                "time": e.start_time.strftime("%Y-%m-%d %H:%M"),
                "status": e.status,
                "type": e.event_type
            } for e in events]
        finally:
            db.close()
