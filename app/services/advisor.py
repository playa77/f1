"""Strategic advisor service for generating recommendations."""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    SimulationRun, ScenarioVersion, Event, Citation, Driver, Team,
    RunStatus,
)
from app.schemas import AdvisoryResult, StrategicRecommendation
from app.services.openrouter import chat_completion, OpenRouterError


async def generate_recommendations(
    db: Session,
    simulation_run: SimulationRun,
) -> AdvisoryResult:
    """Generate strategic recommendations from simulation outputs."""
    settings = get_settings()

    numeric = simulation_run.numeric_outputs or {}
    scenario_version = None
    if simulation_run.scenario_version_id:
        scenario_version = db.query(ScenarioVersion).filter(
            ScenarioVersion.id == simulation_run.scenario_version_id
        ).first()

    drivers = db.query(Driver).filter(Driver.is_deleted == False).all()
    teams = db.query(Team).filter(Team.is_deleted == False).all()

    driver_names = {d.id: d.name for d in drivers}
    team_names = {t.id: t.name for t in teams}

    events = db.query(Event).filter(
        Event.is_deleted == False,
    ).order_by(Event.created_at.desc()).limit(20).all()

    context = {
        "driver_championship": {driver_names.get(k, k): v for k, v in numeric.get("driver_championship_points", {}).items()},
        "constructor_championship": {team_names.get(k, k): v for k, v in numeric.get("constructor_championship_points", {}).items()},
        "dnf_probabilities": {driver_names.get(k, k): v for k, v in numeric.get("dnf_reliability_probability", {}).items()},
        "political_risk": numeric.get("political_regulatory_risk", {}),
        "financial_pressure": numeric.get("sponsor_financial_pressure", {}),
        "recent_events": [
            {"type": str(e.event_type), "summary": e.summary, "impact": str(e.directional_impact)}
            for e in events[:10]
        ],
    }

    prompt = (
        "You are an F1 strategic advisor. Based on the simulation outputs and recent events, "
        "generate 4-7 structured strategic recommendations for teams/drivers. "
        "Each recommendation must identify a target entity, provide clear actionable advice, "
        "explain rationale, and state confidence (low/medium/high). "
        "Also provide an overall summary. Output as JSON: "
        '{"recommendations": [{"target_entity": "...", "target_type": "...", '
        '"recommendation": "...", "rationale": "...", "confidence": "medium|low|high", '
        '"citation_urls": [], "priority": "low|medium|high|critical"}], "summary": "..."}'
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Simulation context: {json.dumps(context)}"},
    ]

    try:
        result = await chat_completion(
            model=settings.openrouter_strong_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=3000,
        )
    except OpenRouterError as e:
        return AdvisoryResult(
            recommendations=[],
            summary=f"Advisor generation failed: {e.message}",
        )

    try:
        content = result["content"]
        parsed = json.loads(content)

        recommendations = []
        for rec_data in parsed.get("recommendations", []):
            try:
                recommendations.append(StrategicRecommendation(**rec_data))
            except Exception:
                continue

        return AdvisoryResult(
            recommendations=recommendations,
            summary=parsed.get("summary", ""),
            generated_at=datetime.now(timezone.utc),
        )
    except Exception as e:
        return AdvisoryResult(
            recommendations=[],
            summary=f"Failed to parse recommendations: {str(e)}",
        )
