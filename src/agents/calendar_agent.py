import os
import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from src.database import SessionLocal
from src.models import Event

logger = logging.getLogger(__name__)

class CalendarAgent:
    """
    Agent #14: The Scheduler.
    Handles appointments, recordings, and viral event timing.
    """
    
    def _get_service(self):
        """Authenticated Google Calendar Service"""
        if not os.path.exists("google_token.json"):
            return None
        
        try:
            with open("google_token.json", "r") as f:
                token_data = json.load(f)
            
            creds = Credentials(
                token=token_data['token'],
                refresh_token=token_data['refresh_token'],
                token_uri=token_data['token_uri'],
                client_id=token_data['client_id'],
                client_secret=token_data['client_secret'],
                scopes=token_data['scopes']
            )
            return build('calendar', 'v3', credentials=creds)
        except Exception as e:
            logger.error(f"Google Auth Failed: {e}")
            return None
    
    def create_event(self, title: str, start_time: str, end_time: str = None, description: str = "", event_type: str = "MEETING", location: str = None, attendees: str = None):
        db = SessionLocal()
        try:
            # Parse ISO strings
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00')) if end_time else start_dt
            
            # 1. Create in DB first
            event = Event(
                title=title,
                description=description,
                start_time=start_dt,
                end_time=end_dt,
                event_type=event_type,
                location=location,
                attendees=attendees
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            
            # 2. Sync to Google Calendar
            service = self._get_service()
            google_id = None
            if service:
                try:
                    g_event = {
                        'summary': title,
                        'location': location or "",
                        'description': description,
                        'start': {'dateTime': start_dt.isoformat()},
                        'end': {'dateTime': end_dt.isoformat()},
                        'attendees': [{'email': a.strip()} for a in (attendees or "").split(",") if "@" in a]
                    }
                    g_res = service.events().insert(calendarId='primary', body=g_event).execute()
                    google_id = g_res.get('id')
                    logger.info(f"Synced to Google Calendar: {google_id}")
                    
                    # Update DB with Google ID (Need migration for this field, but for now we proceed without, 
                    # or misuse description/meta if schema update is hard. 
                    # Actually, let's just log it. Sync back is tricky without ID in DB.)
                except Exception as e:
                    logger.error(f"Google Sync Failed: {e}")

            return {"success": True, "event_id": event.id, "title": event.title, "google_id": google_id}
        except Exception as e:
            logger.error(f"Failed to create event: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close()

    def list_events(self, limit: int = 10):
        # Hybrid: Fetch from DB + Fetch from Google (next 7 days)
        db = SessionLocal()
        try:
            # DB Events
            db_events = db.query(Event).order_by(Event.start_time.asc()).limit(limit).all()
            final_list = []
            
            # Google Events
            service = self._get_service()
            if service:
                try:
                    now = datetime.utcnow().isoformat() + 'Z'
                    events_result = service.events().list(
                        calendarId='primary', timeMin=now,
                        maxResults=limit, singleEvents=True,
                        orderBy='startTime'
                    ).execute()
                    g_events = events_result.get('items', [])
                    
                    # For now, just return Google Events directly as they are source of truth?
                    # Or mix them? Mixing is confusing.
                    # Let's pivot: If Google is connected, SHOW Google Events primarily.
                    if g_events:
                        return [{
                            "id": ge.get('id'), # Google ID is string
                            "title": ge.get('summary', 'No Title'),
                            "time": ge['start'].get('dateTime', ge['start'].get('date')),
                            "status": ge.get('status'),
                            "type": "GOOGLE_EVENT",
                            "location": ge.get('location'),
                            "source": "GOOGLE"
                        } for ge in g_events]
                except Exception as e:
                    logger.error(f"Google List Failed: {e}")
            
            # Fallback to DB
            return [{
                "id": str(e.id),
                "title": e.title,
                "time": e.start_time.strftime("%Y-%m-%d %H:%M"),
                "status": e.status,
                "type": e.event_type,
                "location": e.location,
                "attendees": e.attendees,
                "source": "LOCAL_DB"
            } for e in db_events]
        finally:
            db.close()

    def update_event(self, event_id: str, **kwargs):
        """Update an event. If ID is alphanumeric, treat as Google ID."""
        is_google = not event_id.isdigit()
        
        if is_google:
            service = self._get_service()
            if not service: return {"success": False, "error": "Google Auth missing"}
            try:
                # First get event
                event = service.events().get(calendarId='primary', eventId=event_id).execute()
                
                if 'title' in kwargs: event['summary'] = kwargs['title']
                if 'location' in kwargs: event['location'] = kwargs['location']
                if 'description' in kwargs: event['description'] = kwargs['description']
                # Times... complex
                
                updated_event = service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
                return {"success": True, "title": updated_event.get('summary')}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            # DB Update
            db = SessionLocal()
            try:
                event = db.query(Event).get(int(event_id))
                if not event: return {"success": False, "error": "Event not found"}
                
                for k, v in kwargs.items():
                    if hasattr(event, k) and v:
                        setattr(event, k, v)
                db.commit()
                return {"success": True, "title": event.title}
            finally:
                db.close()
                
    def cancel_event(self, event_id: str):
        is_google = not event_id.isdigit()
        if is_google:
            service = self._get_service()
            if not service: return {"success": False, "error": "Google Auth missing"}
            try:
                service.events().delete(calendarId='primary', eventId=event_id).execute()
                return {"success": True, "status": "DELETED"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
             db = SessionLocal()
             try:
                event = db.query(Event).get(int(event_id))
                if not event: return {"success": False, "error": "Event not found"}
                db.delete(event)
                db.commit()
                return {"success": True, "status": "DELETED"}
             finally:
                db.close()
