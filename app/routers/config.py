"""Configuration and admin router."""

import json
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import (
    Driver, Team, Car, PowerUnit, Circuit, RaceWeekend, StrategicAsset,
    Event, Source, Citation, Scenario, SimulationRun, JobStatus, Report,
)
from app.services.seed_data import seed_database
from app.services.scheduler import trigger_manual_job

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/", response_class=HTMLResponse)
async def config_page(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates
    settings = get_settings()

    latest_jobs = db.query(JobStatus).order_by(
        JobStatus.created_at.desc()
    ).limit(10).all()

    config_info = {
        "season": settings.f1_season,
        "host": settings.app_host,
        "port": settings.app_port,
        "strong_model": settings.openrouter_strong_model,
        "fast_model": settings.openrouter_fast_model,
        "embedding_model": settings.openrouter_embedding_model,
        "page_fetch_enabled": settings.page_fetch_enabled,
        "daily_job_schedule": settings.daily_job_schedule,
        "database_path": settings.sqlite_path,
        "reports_dir": settings.reports_dir,
        "openrouter_configured": bool(settings.openrouter_api_key and not settings.openrouter_api_key.startswith("sk-or-v1-your-")),
        "brave_configured": bool(settings.brave_search_api_key and not settings.brave_search_api_key.startswith("BSA-your-")),
    }

    return await templates.TemplateResponse("config.html", {
        "request": request,
        "config": config_info,
        "latest_jobs": latest_jobs,
    })


@router.post("/seed")
async def seed_data(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        stats = seed_database(db)
        return JSONResponse({"status": "success", "stats": stats})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@router.post("/refresh")
async def trigger_refresh(
    request: Request,
    db: Session = Depends(get_db),
):
    data = await request.json()
    refresh_type = data.get("refresh_type", "manual_discovery")

    if refresh_type == "seed_data":
        stats = seed_database(db)
        return JSONResponse({"status": "success", "stats": stats})
    elif refresh_type == "manual_discovery":
        result = trigger_manual_job("manual_discovery")
        return JSONResponse({"status": "completed", "result": result})
    else:
        result = trigger_manual_job(refresh_type)
        return JSONResponse({"status": "completed", "result": result})


@router.post("/delete")
async def delete_data(
    request: Request,
    db: Session = Depends(get_db),
):
    data = await request.json()
    delete_type = data.get("delete_type")
    target_id = data.get("target_id")

    try:
        if delete_type == "all":
            from app.models import (
                Citation, Report, SimulationRun, AcceptedBranch, ScenarioBranch,
                ScenarioVersion, Scenario, Event, Source, EntityRelationship,
                EmbeddingRecord, EntityVersion, JobStatus,
            )
            db.query(Citation).delete()
            db.query(Report).delete()
            db.query(SimulationRun).delete()
            db.query(AcceptedBranch).delete()
            db.query(ScenarioBranch).delete()
            db.query(ScenarioVersion).delete()
            db.query(Scenario).update({"is_deleted": True})
            db.query(Event).update({"is_deleted": True})
            db.query(Source).update({"is_deleted": True})
            db.query(EntityRelationship).update({"is_deleted": True})
            db.query(EmbeddingRecord).delete()
            db.query(EntityVersion).delete()
            for model in [Driver, Team, Car, PowerUnit, Circuit, RaceWeekend, StrategicAsset]:
                db.query(model).update({"is_deleted": True})
            db.query(JobStatus).delete()
            db.commit()
            return JSONResponse({"status": "success", "message": "All data deleted"})

        elif delete_type == "scenario" and target_id:
            scenario = db.query(Scenario).filter(Scenario.id == target_id).first()
            if scenario:
                scenario.is_deleted = True
                db.commit()
            return JSONResponse({"status": "success", "message": "Scenario deleted"})

        elif delete_type == "source_record" and target_id:
            source = db.query(Source).filter(Source.id == target_id).first()
            if source:
                source.is_deleted = True
            events = db.query(Event).filter(Event.id == target_id).first()
            if events:
                events.is_deleted = True
            db.commit()
            return JSONResponse({"status": "success", "message": "Source records deleted"})

        else:
            return JSONResponse({"status": "error", "error": "Invalid delete type"}, status_code=400)

    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
