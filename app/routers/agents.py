"""Agent chat router."""

import json
import uuid

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Event, Driver, Team, RaceWeekend, Citation, ScenarioBranch, ScenarioVersion, Scenario, BranchStatus, ConfidenceLabel, ImpactDirection
from app.services.openrouter import chat_completion, OpenRouterError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    templates = request.app.state.templates
    return await templates.TemplateResponse("chat.html", {"request": request})


@router.post("/send")
async def chat_send(
    request: Request,
    message: str = Form(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()

    events = db.query(Event).filter(
        Event.is_deleted == False,
    ).order_by(Event.created_at.desc()).limit(15).all()

    drivers = db.query(Driver).filter(Driver.is_deleted == False).all()
    teams = db.query(Team).filter(Team.is_deleted == False).all()
    races = db.query(RaceWeekend).filter(
        RaceWeekend.is_deleted == False,
    ).order_by(RaceWeekend.race_order).all()

    context = {
        "season": settings.f1_season,
        "drivers": [{"name": d.name, "team": d.team_id, "status": str(d.status)} for d in drivers],
        "teams": [{"name": t.name} for t in teams],
        "races": [{"name": r.grand_prix_name, "status": str(r.status), "order": r.race_order} for r in races],
        "recent_events": [
            {"type": str(e.event_type), "summary": e.summary, "impact": str(e.directional_impact),
             "confidence": str(e.confidence)}
            for e in events
        ],
    }

    prompt = (
        "You are an F1 strategic analyst assistant. Answer questions about the current F1 season "
        "using only the provided context and your general F1 knowledge. Cite sources when you "
        "reference specific events. If the question involves scenario planning, you may suggest "
        "scenario branches. Be concise and analytical. "
        "Output as JSON: "
        '{"answer": "...", "citations": [{"url": "", "title": "", "excerpt": ""}], "proposed_actions": []}'
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Context: {json.dumps(context)}\n\nQuestion: {message}"},
    ]

    try:
        result = await chat_completion(
            model=settings.openrouter_strong_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.5,
        )
    except OpenRouterError as e:
        return JSONResponse({
            "answer": f"I'm unable to respond due to a model service error: {e.message}",
            "citations": [],
            "proposed_actions": [],
        })

    try:
        content = result["content"]
        parsed = json.loads(content)
    except Exception:
        parsed = {"answer": content if isinstance(content, str) else str(content), "citations": [], "proposed_actions": []}

    return JSONResponse(parsed)
