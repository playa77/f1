"""Events and sources router."""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Event, Source, Citation

router = APIRouter(tags=["events"])


@router.get("/events", response_class=HTMLResponse)
async def list_events(
    request: Request,
    event_type: str = Query(""),
    confidence: str = Query(""),
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates

    query = db.query(Event).filter(Event.is_deleted == False)
    if event_type:
        query = query.filter(Event.event_type == event_type)
    if confidence:
        query = query.filter(Event.confidence == confidence)

    events = query.order_by(Event.created_at.desc()).limit(100).all()

    return await templates.TemplateResponse("events.html", {
        "request": request,
        "events": events,
        "event_type": event_type,
        "confidence": confidence,
    })


@router.get("/sources", response_class=HTMLResponse)
async def list_sources(
    request: Request,
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates

    sources = db.query(Source).filter(
        Source.is_deleted == False,
    ).order_by(Source.created_at.desc()).limit(100).all()

    return await templates.TemplateResponse("sources.html", {
        "request": request,
        "sources": sources,
    })
