"""Simulation router."""

import json
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    SimulationRun, Scenario, ScenarioVersion, Driver, Team,
    RunStatus,
)
from app.services.simulation import run_baseline_simulation as _run_baseline
from app.services.simulation import run_simulation as _run_scenario
from app.services.advisor import generate_recommendations
from app.services.reports import generate_report
from app.services.openrouter import OpenRouterError

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.get("/", response_class=HTMLResponse)
async def list_simulations(
    request: Request,
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates

    runs = db.query(SimulationRun).order_by(
        SimulationRun.run_timestamp.desc()
    ).limit(50).all()

    scenarios = {s.id: s.name for s in db.query(Scenario).all()}

    for run in runs:
        run._scenario_name = None
        if run.scenario_version_id:
            sv = db.query(ScenarioVersion).filter(
                ScenarioVersion.id == run.scenario_version_id
            ).first()
            if sv:
                run._scenario_name = scenarios.get(sv.scenario_id)

    return await templates.TemplateResponse("simulations.html", {
        "request": request,
        "runs": runs,
    })


@router.get("/run/{run_id}", response_class=HTMLResponse)
async def simulation_detail(
    request: Request,
    run_id: str,
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates

    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run:
        return await templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    drivers = db.query(Driver).filter(Driver.is_deleted == False).all()
    teams = db.query(Team).filter(Team.is_deleted == False).all()
    driver_names = {d.id: d.name for d in drivers}
    team_names = {t.id: t.name for t in teams}

    numeric = run.numeric_outputs or {}

    drv_champ = [(driver_names.get(k, k[:8]), v) for k, v in numeric.get("driver_championship_points", {}).items()]
    cst_champ = [(team_names.get(k, k[:8]), v) for k, v in numeric.get("constructor_championship_points", {}).items()]

    return await templates.TemplateResponse("simulation_detail.html", {
        "request": request,
        "run": run,
        "numeric": numeric,
        "driver_championship": drv_champ,
        "constructor_championship": cst_champ,
        "driver_names": driver_names,
        "team_names": team_names,
    })


@router.post("/run/baseline")
async def run_baseline_simulation(
    request: Request,
    db: Session = Depends(get_db),
):
    run = _run_baseline(db)
    return JSONResponse({
        "run_id": run.id,
        "status": str(run.status),
        "message": "Baseline simulation started" if run.status == RunStatus("completed") else "Simulation failed",
    })


@router.post("/run/scenario/{scenario_id}")
async def run_scenario_simulation(
    request: Request,
    scenario_id: str,
    include_explanation: bool = Query(False),
    db: Session = Depends(get_db),
):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        return JSONResponse({"error": "Scenario not found"}, status_code=404)

    version = db.query(ScenarioVersion).filter(
        ScenarioVersion.id == scenario.current_version_id,
    ).first()
    if not version:
        return JSONResponse({"error": "Scenario has no accepted version"}, status_code=400)

    run = _run_scenario(db, version, include_explanation=include_explanation)

    if run.status == RunStatus("completed") and include_explanation:
        try:
            advisory = await generate_recommendations(db, run)
            run.advisory_outputs = json.loads(advisory.model_dump_json())
            db.commit()
        except Exception:
            pass

    return JSONResponse({
        "run_id": run.id,
        "status": str(run.status),
        "message": "Simulation completed" if run.status == RunStatus("completed") else "Simulation failed or partially completed",
    })


@router.post("/run/{run_id}/export")
async def export_simulation(
    request: Request,
    run_id: str,
    db: Session = Depends(get_db),
):
    data = await request.json()
    output_format = data.get("format", "markdown")

    run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
    if not run:
        return JSONResponse({"error": "Simulation run not found"}, status_code=404)

    report = generate_report(db, run, "simulation_report", output_format)

    return JSONResponse({
        "report_id": report.id,
        "format": output_format,
        "status": str(report.status),
        "file_path": report.file_path,
    })


@router.get("/compare/{run_id_a}/{run_id_b}", response_class=HTMLResponse)
async def compare_simulations(
    request: Request,
    run_id_a: str,
    run_id_b: str,
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates

    run_a = db.query(SimulationRun).filter(SimulationRun.id == run_id_a).first()
    run_b = db.query(SimulationRun).filter(SimulationRun.id == run_id_b).first()

    if not run_a or not run_b:
        return await templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    numeric_a = run_a.numeric_outputs or {}
    numeric_b = run_b.numeric_outputs or {}

    diff = {}
    for key in set(list(numeric_a.keys()) + list(numeric_b.keys())):
        a_val = numeric_a.get(key, {})
        b_val = numeric_b.get(key, {})
        if isinstance(a_val, dict) and isinstance(b_val, dict):
            key_diff = {}
            for sub_key in set(list(a_val.keys()) + list(b_val.keys())):
                a_v = a_val.get(sub_key, 0)
                b_v = b_val.get(sub_key, 0)
                if isinstance(a_v, (int, float)) and isinstance(b_v, (int, float)):
                    key_diff[sub_key] = round(b_v - a_v, 3)
            diff[key] = key_diff
        elif isinstance(a_val, (int, float)) and isinstance(b_val, (int, float)):
            diff[key] = round(b_val - a_val, 3)

    return await templates.TemplateResponse("simulation_compare.html", {
        "request": request,
        "run_a": run_a,
        "run_b": run_b,
        "diff": diff,
    })
