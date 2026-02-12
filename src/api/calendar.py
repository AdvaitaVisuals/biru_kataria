
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel
from src.agents.calendar_agent import CalendarAgent

router = APIRouter(prefix="/calendar", tags=["Calendar"])

class EventCreate(BaseModel):
    title: str
    start_time: str
    end_time: Optional[str] = None
    description: Optional[str] = ""
    event_type: Optional[str] = "MEETING"

@router.get("/events")
def get_events(limit: int = 10):
    agent = CalendarAgent()
    return agent.list_events(limit=limit)

@router.post("/events")
def create_event(event: EventCreate):
    agent = CalendarAgent()
    result = agent.create_event(
        title=event.title,
        start_time=event.start_time,
        end_time=event.end_time,
        description=event.description,
        event_type=event.event_type
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result
