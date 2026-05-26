"""Entity browser router."""

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Driver, Team, Car, PowerUnit, Circuit, RaceWeekend, StrategicAsset, Citation,
)

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/", response_class=HTMLResponse)
async def list_entities(
    request: Request,
    entity_type: str = Query("drivers"),
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates

    if entity_type == "drivers":
        items = db.query(Driver).filter(Driver.is_deleted == False).all()
        title = "Drivers"
    elif entity_type == "teams":
        items = db.query(Team).filter(Team.is_deleted == False).all()
        title = "Teams"
    elif entity_type == "cars":
        items = db.query(Car).filter(Car.is_deleted == False).all()
        title = "Cars"
    elif entity_type == "power_units":
        items = db.query(PowerUnit).filter(PowerUnit.is_deleted == False).all()
        title = "Power Units"
    elif entity_type == "circuits":
        items = db.query(Circuit).filter(Circuit.is_deleted == False).all()
        title = "Circuits"
    elif entity_type == "races":
        items = db.query(RaceWeekend).filter(RaceWeekend.is_deleted == False).order_by(RaceWeekend.race_order).all()
        title = "Race Weekends"
    elif entity_type == "assets":
        items = db.query(StrategicAsset).filter(StrategicAsset.is_deleted == False).all()
        title = "Strategic Assets"
    else:
        items = []
        title = "Unknown"

    return await templates.TemplateResponse("entities.html", {
        "request": request,
        "items": items,
        "title": title,
        "entity_type": entity_type,
    })


@router.get("/{entity_type}/{entity_id}", response_class=HTMLResponse)
async def entity_detail(
    request: Request,
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates

    model_map = {
        "drivers": Driver,
        "teams": Team,
        "cars": Car,
        "power_units": PowerUnit,
        "circuits": Circuit,
        "races": RaceWeekend,
        "assets": StrategicAsset,
    }

    model_class = model_map.get(entity_type)
    if not model_class:
        return await templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    entity = db.query(model_class).filter(model_class.id == entity_id).first()
    if not entity:
        return await templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    attr_map = {
        "drivers": "driver_id",
        "teams": "team_id",
        "cars": "car_id",
        "power_units": "power_unit_id",
        "circuits": "circuit_id",
        "races": "race_weekend_id",
        "assets": "strategic_asset_id",
    }

    citation_field = attr_map.get(entity_type)
    if citation_field:
        citations = db.query(Citation).filter(
            getattr(Citation, citation_field) == entity_id
        ).all()
    else:
        citations = []

    return await templates.TemplateResponse("entity_detail.html", {
        "request": request,
        "entity": entity,
        "entity_type": entity_type,
        "citations": citations,
    })
