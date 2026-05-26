"""Scenario builder router."""

import json
import uuid

from fastapi import APIRouter, Depends, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import (
    Scenario, ScenarioVersion, ScenarioBranch, AcceptedBranch, Event, Citation,
    BranchStatus, ConfidenceLabel, ImpactDirection,
)
from app.schemas import BranchProposalResult, BranchProposal
from app.services.openrouter import chat_completion, OpenRouterError

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("/", response_class=HTMLResponse)
async def list_scenarios(request: Request, db: Session = Depends(get_db)):
    templates = request.app.state.templates

    scenarios = db.query(Scenario).filter(
        Scenario.is_deleted == False,
    ).order_by(Scenario.created_at.desc()).all()

    for s in scenarios:
        s.runnable = s.current_version_id is not None

    return await templates.TemplateResponse("scenarios.html", {
        "request": request,
        "scenarios": scenarios,
    })


@router.get("/new", response_class=HTMLResponse)
async def new_scenario_form(request: Request):
    templates = request.app.state.templates
    return await templates.TemplateResponse("scenario_new.html", {"request": request})


@router.post("/create")
async def create_scenario(
    request: Request,
    name: str = Form(...),
    goal: str = Form(""),
    db: Session = Depends(get_db),
):
    scenario = Scenario(
        id=str(uuid.uuid4()),
        name=name,
        goal=goal,
    )
    db.add(scenario)
    db.commit()

    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/scenarios/{scenario.id}", status_code=303)


@router.get("/{scenario_id}", response_class=HTMLResponse)
async def scenario_detail(
    request: Request,
    scenario_id: str,
    db: Session = Depends(get_db),
):
    templates = request.app.state.templates

    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        return await templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    versions = db.query(ScenarioVersion).filter(
        ScenarioVersion.scenario_id == scenario_id,
    ).order_by(ScenarioVersion.version_number.desc()).all()

    return await templates.TemplateResponse("scenario_detail.html", {
        "request": request,
        "scenario": scenario,
        "versions": versions,
    })


@router.post("/{scenario_id}/propose-branches")
async def propose_branches(
    scenario_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Ask the scenario director to propose branches."""
    settings = get_settings()

    scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    events = db.query(Event).filter(
        Event.is_deleted == False,
    ).order_by(Event.created_at.desc()).limit(20).all()

    event_summaries = [
        {"type": str(e.event_type), "summary": e.summary, "impact": str(e.directional_impact),
         "magnitude": e.magnitude, "confidence": str(e.confidence)}
        for e in events
    ]

    prompt = (
        "You are an F1 scenario director. Based on the current season context, events, "
        "and the scenario goal, propose 3-6 plausible scenario branches. "
        "Each branch must: identify the branch type, summarize the change, list affected entities, "
        "state directional impact and confidence. Output as JSON: "
        '{"branches": [{"branch_type": "...", "summary": "...", '
        '"affected_entity_types": [...], "affected_entity_names": [...], '
        '"affected_dimensions": [...], "directional_impact": "positive|negative|mixed|unknown", '
        '"magnitude": -1.0 to 1.0, "confidence": "low|medium|high", '
        '"rationale": "...", "is_hypothetical": true/false}], "proposal_notes": "..."}'
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps({
            "scenario_name": scenario.name,
            "scenario_goal": scenario.goal,
            "recent_events": event_summaries,
        })},
    ]

    try:
        result = await chat_completion(
            model=settings.openrouter_strong_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.6,
        )
    except OpenRouterError as e:
        return JSONResponse({
            "error": f"Scenario director model call failed: {e.message}",
            "provider": "openrouter",
        }, status_code=502)

    try:
        content = result["content"]
        parsed = json.loads(content)
        proposal_result = BranchProposalResult(**parsed)
    except Exception as e:
        return JSONResponse({"error": f"Failed to parse branch proposals: {str(e)}"}, status_code=422)

    next_version = db.query(ScenarioVersion).filter(
        ScenarioVersion.scenario_id == scenario_id,
    ).count() + 1

    version = ScenarioVersion(
        id=str(uuid.uuid4()),
        scenario_id=scenario_id,
        version_number=next_version,
        baseline_type="current_season_state",
    )
    db.add(version)
    db.flush()

    created_branches = []
    for bp in proposal_result.branches:
        branch = ScenarioBranch(
            id=str(uuid.uuid4()),
            version_id=version.id,
            branch_type=bp.branch_type,
            summary=bp.summary,
            affected_entities=json.dumps({
                "types": bp.affected_entity_types,
                "names": bp.affected_entity_names,
            }) if bp.affected_entity_types or bp.affected_entity_names else None,
            affected_dimensions=bp.affected_dimensions,
            directional_impact=ImpactDirection(bp.directional_impact),
            magnitude=bp.magnitude,
            confidence=ConfidenceLabel(bp.confidence),
            is_hypothetical=bp.is_hypothetical,
            status=BranchStatus("proposed"),
            rationale=bp.rationale,
        )
        db.add(branch)
        db.flush()
        created_branches.append({
            "id": branch.id,
            "branch_type": str(branch.branch_type),
            "summary": branch.summary,
            "directional_impact": str(branch.directional_impact),
            "magnitude": branch.magnitude,
            "confidence": str(branch.confidence),
            "rationale": branch.rationale,
            "is_hypothetical": branch.is_hypothetical,
        })

    scenario.current_version_id = version.id
    db.commit()

    return JSONResponse({
        "version_id": version.id,
        "version_number": next_version,
        "branches": created_branches,
        "proposal_notes": proposal_result.proposal_notes,
    })


@router.post("/{scenario_id}/branches/{branch_id}/respond")
async def respond_to_branch(
    scenario_id: str,
    branch_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Accept or reject a proposed branch."""
    data = await request.json()
    action = data.get("action", "reject")

    branch = db.query(ScenarioBranch).filter(ScenarioBranch.id == branch_id).first()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    version = db.query(ScenarioVersion).filter(
        ScenarioVersion.id == branch.version_id
    ).first()
    if not version or version.scenario_id != scenario_id:
        raise HTTPException(status_code=404, detail="Version not found")

    if action == "accept":
        branch.status = BranchStatus("accepted")

        existing_order = db.query(AcceptedBranch).filter(
            AcceptedBranch.scenario_version_id == version.id,
        ).count()

        ab = AcceptedBranch(
            id=str(uuid.uuid4()),
            scenario_version_id=version.id,
            branch_id=branch_id,
            acceptance_order=existing_order + 1,
        )
        db.add(ab)

        scenario = db.query(Scenario).filter(Scenario.id == scenario_id).first()
        if scenario:
            scenario.current_version_id = version.id
    else:
        branch.status = BranchStatus("rejected")

    db.commit()

    return JSONResponse({"status": "ok", "branch_status": str(branch.status)})
