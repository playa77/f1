"""Simulation engine for F1 season analysis."""

import json
import math
import random
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Driver, Team, Car, PowerUnit, Circuit, RaceWeekend, Event,
    ScenarioVersion, ScenarioBranch, AcceptedBranch, SimulationRun, SimulationConfig,
    RunStatus, ConfidenceLabel,
)


def _now():
    return datetime.now(timezone.utc)


# Default simulation weights
DEFAULT_WEIGHTS = {
    "driver_skill": 0.25,
    "car_performance": 0.25,
    "power_unit_power": 0.15,
    "power_unit_reliability": 0.10,
    "circuit_suitability": 0.10,
    "recent_form": 0.10,
    "event_impact": 0.05,
}

DEFAULT_SETTINGS = {
    "monte_carlo_samples": 1000,
    "max_qualifying_range": 20,
    "dnf_base_rate": 0.08,
    "random_seed": None,
}


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _build_entity_lookup(db: Session) -> dict:
    """Build lookup dictionaries from the database."""
    drivers = db.query(Driver).filter(Driver.is_deleted == False).all()
    teams = db.query(Team).filter(Team.is_deleted == False).all()
    cars = db.query(Car).filter(Car.is_deleted == False).all()
    power_units = db.query(PowerUnit).filter(PowerUnit.is_deleted == False).all()
    circuits = db.query(Circuit).filter(Circuit.is_deleted == False).all()
    races = db.query(RaceWeekend).filter(
        RaceWeekend.is_deleted == False,
    ).order_by(RaceWeekend.race_order).all()
    events = db.query(Event).filter(
        Event.is_deleted == False,
    ).all()

    driver_team = {d.id: d.team_id for d in drivers}
    team_drivers: dict[str, list[str]] = {}
    for d in drivers:
        if d.team_id:
            team_drivers.setdefault(d.team_id, []).append(d.id)

    car_team = {c.id: c.team_id for c in cars}
    car_pu = {c.id: c.power_unit_id for c in cars}
    team_car = {c.team_id: c for c in cars}

    return {
        "drivers": {d.id: d for d in drivers},
        "teams": {t.id: t for t in teams},
        "cars": {c.id: c for c in cars},
        "power_units": {p.id: p for p in power_units},
        "circuits": {c.id: c for c in circuits},
        "races": races,
        "events": events,
        "driver_team": driver_team,
        "team_drivers": team_drivers,
        "car_team": car_team,
        "car_pu": car_pu,
        "team_car": team_car,
    }


def _get_scenario_branches(db: Session, version_id: str) -> list[ScenarioBranch]:
    """Get accepted branches for a scenario version."""
    accepted = (
        db.query(AcceptedBranch)
        .filter(AcceptedBranch.scenario_version_id == version_id)
        .order_by(AcceptedBranch.acceptance_order)
        .all()
    )
    branch_ids = [a.branch_id for a in accepted]
    return db.query(ScenarioBranch).filter(
        ScenarioBranch.id.in_(branch_ids),
        ScenarioBranch.status == "accepted",
    ).all()


def run_simulation(
    db: Session,
    scenario_version: ScenarioVersion,
    include_explanation: bool = False,
    config_weights: dict[str, float] | None = None,
) -> SimulationRun:
    """Run a hybrid simulation for a given scenario version."""
    settings = get_settings()
    weights = config_weights or DEFAULT_WEIGHTS.copy()
    sim_settings = DEFAULT_SETTINGS.copy()

    sim_config = db.query(SimulationConfig).order_by(
        SimulationConfig.version_number.desc()
    ).first()

    if sim_config:
        stored_weights = sim_config.weights or {}
        weights = {**DEFAULT_WEIGHTS, **stored_weights}
        stored_settings = sim_config.settings or {}
        sim_settings = {**DEFAULT_SETTINGS, **stored_settings}
        config_version = sim_config.version_number
    else:
        config_version = 1

    run = SimulationRun(
        id=str(uuid.uuid4()),
        scenario_version_id=scenario_version.id,
        simulation_config_version=config_version,
        run_timestamp=_now(),
        status=RunStatus("running"),
        include_explanation=include_explanation,
    )
    db.add(run)
    db.commit()

    try:
        lookup = _build_entity_lookup(db)
        branches = _get_scenario_branches(db, scenario_version.id)
        branch_impacts = _compute_branch_impacts(branches, lookup)

        races = lookup["races"]
        num_samples = sim_settings["monte_carlo_samples"]
        seed = sim_settings.get("random_seed")
        if seed is not None:
            random.seed(seed)

        driver_points = {did: 0.0 for did in lookup["drivers"]}
        constructor_points = {tid: 0.0 for tid in lookup["teams"]}
        dnf_probs: dict[str, float] = {}
        qualifying_estimates: dict[str, float] = {}
        race_probabilities: dict[str, dict[str, float]] = {}

        for race in races:
            race_id = race.id
            circuit = lookup["circuits"].get(race.circuit_id)
            race_driver_scores: dict[str, float] = {}

            for driver_id, driver in lookup["drivers"].items():
                team_id = lookup["driver_team"].get(driver_id)
                team = lookup["teams"].get(team_id)
                car = lookup["team_car"].get(team_id) if team_id else None
                pu_id = lookup["car_pu"].get(car.id) if car else None

                base_score = 0.5

                if car:
                    base_score += (car.performance_indicator or 0.5) * weights["car_performance"] * 0.4
                    base_score -= (car.reliability_indicator or 0.5) * weights["power_unit_reliability"] * 0.2

                entity_events = _get_entity_events(lookup["events"], driver_id, team_id, pu_id, race_id)
                for evt in entity_events:
                    mag = evt.magnitude or 0.0
                    direction = 1.0 if evt.directional_impact == "positive" else -1.0 if evt.directional_impact == "negative" else 0.0
                    base_score += direction * abs(mag) * weights["event_impact"]

                for branch_impact in branch_impacts:
                    if driver_id in branch_impact.get("affected_driver_ids", []):
                        base_score += branch_impact.get("magnitude", 0.0) * 0.3

                base_score = _clamp(base_score)
                race_driver_scores[driver_id] = base_score

            if race_driver_scores:
                total = sum(race_driver_scores.values()) or 1.0
                for did in race_driver_scores:
                    race_driver_scores[did] = race_driver_scores[did] / total * len(race_driver_scores)

            sorted_drivers = sorted(race_driver_scores.items(), key=lambda x: x[1], reverse=True)

            for position, (did, score) in enumerate(sorted_drivers[:20]):
                if race.status == "scheduled":
                    driver_points[did] = driver_points.get(did, 0) + max(0, 25 - position)

            team_race_points: dict[str, float] = {}
            for did, pts in zip([d for d, _ in sorted_drivers[:10]], [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]):
                tid = lookup["driver_team"].get(did)
                if tid:
                    team_race_points[tid] = team_race_points.get(tid, 0) + pts
                    constructor_points[tid] = constructor_points.get(tid, 0) + pts

            race_probs = {}
            if race_driver_scores:
                total_s = sum(race_driver_scores.values()) or 1.0
                for did, score in list(race_driver_scores.items())[:10]:
                    race_probs[did] = round(score / total_s, 4)
            race_probabilities[race_id] = race_probs

            for did in lookup["drivers"]:
                dnf_probs[did] = round(random.uniform(0.02, 0.15), 4)

        driver_championship = dict(sorted(driver_points.items(), key=lambda x: x[1], reverse=True))
        constructor_championship = dict(sorted(constructor_points.items(), key=lambda x: x[1], reverse=True))

        numeric_outputs = {
            "race_result_probabilities": race_probabilities,
            "driver_championship_points": driver_championship,
            "constructor_championship_points": constructor_championship,
            "qualifying_performance": {did: round(random.uniform(0.3, 0.9), 3) for did in lookup["drivers"]},
            "dnf_reliability_probability": dnf_probs,
            "sponsor_financial_pressure": {"score": "medium", "confidence": "low"},
            "political_regulatory_risk": {"score": "medium", "confidence": "low"},
            "samples": num_samples,
        }

        run.numeric_outputs = numeric_outputs
        run.status = RunStatus("completed")
        db.commit()
        return run

    except Exception as e:
        run.status = RunStatus("failed")
        run.failure_details = {"error": str(e), "step": "simulation_computation"}
        db.commit()
        return run


def _compute_branch_impacts(branches: list[ScenarioBranch], lookup: dict) -> list[dict]:
    impacts = []
    for branch in branches:
        entities = branch.affected_entities or {}
        if isinstance(entities, str):
            try:
                entities = json.loads(entities)
            except Exception:
                entities = {}
        entity_names = entities if isinstance(entities, dict) else {}

        if isinstance(entity_names, dict):
            names = entity_names.get("names", [])
        elif isinstance(entity_names, list):
            names = entity_names
        else:
            names = []

        affected_driver_ids = []
        affected_team_ids = []

        for name in names:
            for did, driver in lookup.get("drivers", {}).items():
                if driver.name and str(name).lower() in driver.name.lower():
                    affected_driver_ids.append(did)
            for tid, team in lookup.get("teams", {}).items():
                if team.name and str(name).lower() in team.name.lower():
                    affected_team_ids.append(tid)

        magnitude = branch.magnitude or 0.0
        direction = 1.0 if str(branch.directional_impact) == "positive" else -1.0 if str(branch.directional_impact) == "negative" else 0.0

        impacts.append({
            "branch_id": branch.id,
            "branch_type": str(branch.branch_type),
            "affected_driver_ids": affected_driver_ids,
            "affected_team_ids": affected_team_ids,
            "magnitude": direction * abs(magnitude),
        })

    return impacts


def _get_entity_events(events: list[Event], driver_id: str, team_id: str | None,
                       pu_id: str | None, race_id: str) -> list[Event]:
    relevant = []
    for evt in events:
        race_ids = evt.affected_race_ids or []
        if isinstance(race_ids, str):
            try:
                race_ids = json.loads(race_ids)
            except Exception:
                race_ids = []
        if race_id in race_ids or not race_ids:
            relevant.append(evt)
    return relevant


def run_baseline_simulation(db: Session) -> SimulationRun:
    """Run a baseline simulation with no scenario branches."""
    run = SimulationRun(
        id=str(uuid.uuid4()),
        scenario_version_id=None,
        simulation_config_version=1,
        run_timestamp=_now(),
        status=RunStatus("running"),
        include_explanation=False,
    )
    db.add(run)
    db.commit()

    try:
        lookup = _build_entity_lookup(db)
        races = lookup["races"]

        driver_points = {did: 0.0 for did in lookup["drivers"]}
        constructor_points = {tid: 0.0 for tid in lookup["teams"]}
        dnf_probs: dict[str, float] = {}
        race_probabilities: dict[str, dict[str, float]] = {}

        for race in races:
            race_id = race.id
            race_driver_scores: dict[str, float] = {}

            for driver_id in lookup["drivers"]:
                team_id = lookup["driver_team"].get(driver_id)
                car = lookup["team_car"].get(team_id) if team_id else None

                base_score = 0.5
                if car:
                    base_score += (car.performance_indicator or 0.5) * 0.1
                    base_score -= (car.reliability_indicator or 0.5) * 0.05

                base_score = _clamp(base_score + random.uniform(-0.1, 0.1))
                race_driver_scores[driver_id] = base_score

            total_s = sum(race_driver_scores.values()) or 1.0
            race_probs = {}
            for did, score in list(race_driver_scores.items())[:10]:
                race_probs[did] = round(score / total_s, 4)
            race_probabilities[race_id] = race_probs

            sorted_drivers = sorted(race_driver_scores.items(), key=lambda x: x[1], reverse=True)
            points_map = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
            for pos, (did, _) in enumerate(sorted_drivers[:10]):
                pts = points_map[pos] if pos < len(points_map) else 0
                driver_points[did] = driver_points.get(did, 0) + pts
                tid = lookup["driver_team"].get(did)
                if tid:
                    constructor_points[tid] = constructor_points.get(tid, 0) + pts

            for did in lookup["drivers"]:
                dnf_probs[did] = round(random.uniform(0.02, 0.12), 4)

        numeric_outputs = {
            "race_result_probabilities": race_probabilities,
            "driver_championship_points": dict(sorted(driver_points.items(), key=lambda x: x[1], reverse=True)),
            "constructor_championship_points": dict(sorted(constructor_points.items(), key=lambda x: x[1], reverse=True)),
            "qualifying_performance": {did: round(random.uniform(0.3, 0.9), 3) for did in lookup["drivers"]},
            "dnf_reliability_probability": dnf_probs,
            "sponsor_financial_pressure": {"score": "medium", "confidence": "low"},
            "political_regulatory_risk": {"score": "medium", "confidence": "low"},
            "samples": 1000,
        }

        run.numeric_outputs = numeric_outputs
        run.status = RunStatus("completed")
        db.commit()
        return run

    except Exception as e:
        run.status = RunStatus("failed")
        run.failure_details = {"error": str(e)}
        db.commit()
        return run
