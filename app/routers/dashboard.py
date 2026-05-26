"""Dashboard router."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Driver, Team, RaceWeekend, Event, Scenario, SimulationRun, JobStatus,
    RunStatus,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates

    drivers_count = db.query(Driver).filter(Driver.is_deleted == False).count()
    teams_count = db.query(Team).filter(Team.is_deleted == False).count()
    races_count = db.query(RaceWeekend).filter(RaceWeekend.is_deleted == False).count()
    events_count = db.query(Event).filter(Event.is_deleted == False).count()
    scenarios_count = db.query(Scenario).filter(Scenario.is_deleted == False).count()
    simulations_count = db.query(SimulationRun).count()

    recent_events = db.query(Event).filter(
        Event.is_deleted == False,
    ).order_by(Event.created_at.desc()).limit(5).all()

    recent_scenarios = db.query(Scenario).filter(
        Scenario.is_deleted == False,
    ).order_by(Scenario.created_at.desc()).limit(5).all()

    recent_simulations = db.query(SimulationRun).order_by(
        SimulationRun.run_timestamp.desc()
    ).limit(5).all()

    last_discovery = db.query(JobStatus).filter(
        JobStatus.job_type.in_(["nightly_pipeline", "daily_discovery", "manual_discovery"]),
    ).order_by(JobStatus.created_at.desc()).first()

    failed_jobs = db.query(JobStatus).filter(
        JobStatus.status == "failed"
    ).order_by(JobStatus.created_at.desc()).limit(5).all()

    config_warnings = getattr(request.app.state, "config_warnings", [])

    return await templates.TemplateResponse("dashboard.html", {
        "request": request,
        "drivers_count": drivers_count,
        "teams_count": teams_count,
        "races_count": races_count,
        "events_count": events_count,
        "scenarios_count": scenarios_count,
        "simulations_count": simulations_count,
        "recent_events": recent_events,
        "recent_scenarios": recent_scenarios,
        "recent_simulations": recent_simulations,
        "last_discovery": last_discovery,
        "failed_jobs": failed_jobs,
        "config_warnings": config_warnings,
    })
