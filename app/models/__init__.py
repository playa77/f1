"""SQLAlchemy ORM models for the F1 Analyzer."""

import uuid
import enum as _py_enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Enum as _SAEnum,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _uid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


def _sa_enum(enum_cls, **kwargs):
    return _SAEnum(enum_cls, **kwargs)


# ---------------------------------------------------------------------------
# Python Enums
# ---------------------------------------------------------------------------

class DriverStatus(_py_enum.Enum):
    active = "active"
    reserve = "reserve"
    inactive = "inactive"

class RaceStatus(_py_enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    postponed = "postponed"
    canceled = "canceled"
    at_risk = "at_risk"

class AssetType(_py_enum.Enum):
    car_development_package = "car_development_package"
    reliability_upgrade = "reliability_upgrade"
    budget_pressure_signal = "budget_pressure_signal"
    internal_conflict_signal = "internal_conflict_signal"
    political_regulatory_influence_signal = "political_regulatory_influence_signal"
    logistics_disruption_signal = "logistics_disruption_signal"

class ImpactDirection(_py_enum.Enum):
    positive = "positive"
    negative = "negative"
    mixed = "mixed"
    unknown = "unknown"

class EventType(_py_enum.Enum):
    performance = "performance"
    reliability = "reliability"
    driver_condition = "driver_condition"
    team_internal_conflict = "team_internal_conflict"
    regulatory_fia = "regulatory_fia"
    race_logistics = "race_logistics"
    geopolitical_disruption = "geopolitical_disruption"
    financial_sponsor_pressure = "financial_sponsor_pressure"
    weather_circuit_risk = "weather_circuit_risk"
    other = "other"

class TimeRelevance(_py_enum.Enum):
    immediate = "immediate"
    next_race = "next_race"
    multi_race = "multi_race"
    season_long = "season_long"
    unknown = "unknown"

class BranchType(_py_enum.Enum):
    race_canceled_postponed = "race_canceled_postponed"
    driver_performance_impact = "driver_performance_impact"
    team_performance_impact = "team_performance_impact"
    car_reliability_impact = "car_reliability_impact"
    power_unit_reliability_impact = "power_unit_reliability_impact"
    regulatory_fia_impact = "regulatory_fia_impact"
    financial_pressure_impact = "financial_pressure_impact"
    political_geopolitical_risk_impact = "political_geopolitical_risk_impact"
    internal_conflict_impact = "internal_conflict_impact"
    circuit_session_condition_impact = "circuit_session_condition_impact"

class BranchStatus(_py_enum.Enum):
    proposed = "proposed"
    accepted = "accepted"
    rejected = "rejected"
    superseded = "superseded"

class RunStatus(_py_enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    partially_completed = "partially_completed"

class ReportFormat(_py_enum.Enum):
    markdown = "markdown"
    pdf = "pdf"
    json = "json"

class ReportStatus(_py_enum.Enum):
    pending = "pending"
    generating = "generating"
    completed = "completed"
    failed = "failed"

class CircuitCategory(_py_enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    very_high = "very_high"

class ConfidenceLabel(_py_enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"

class DiscoveryMethod(_py_enum.Enum):
    brave_search = "brave_search"
    static_dataset_import = "static_dataset_import"
    page_fetch = "page_fetch"

class JobType(_py_enum.Enum):
    daily_discovery = "daily_discovery"
    nightly_pipeline = "nightly_pipeline"
    manual_discovery = "manual_discovery"
    static_data_refresh = "static_data_refresh"
    embedding_refresh = "embedding_refresh"
    full_refresh = "full_refresh"


# ---------------------------------------------------------------------------
# Entity models
# ---------------------------------------------------------------------------

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(String, primary_key=True, default=_uid)
    name = Column(String, nullable=False)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    driver_number = Column(String, nullable=True)
    status = Column(_SAEnum(DriverStatus), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    team = relationship("Team", back_populates="drivers")
    attribute_versions = relationship("EntityVersion", back_populates="driver",
                                       foreign_keys="EntityVersion.driver_id")
    citations = relationship("Citation", back_populates="driver",
                              foreign_keys="Citation.driver_id")


class Team(Base):
    __tablename__ = "teams"

    id = Column(String, primary_key=True, default=_uid)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    drivers = relationship("Driver", back_populates="team")
    cars = relationship("Car", back_populates="team")
    attribute_versions = relationship("EntityVersion", back_populates="team",
                                       foreign_keys="EntityVersion.team_id")
    citations = relationship("Citation", back_populates="team",
                              foreign_keys="Citation.team_id")


class Car(Base):
    __tablename__ = "cars"

    id = Column(String, primary_key=True, default=_uid)
    chassis_name = Column(String, nullable=True)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    power_unit_id = Column(String, ForeignKey("power_units.id"), nullable=True)
    reliability_indicator = Column(Float, nullable=True)
    performance_indicator = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    team = relationship("Team", back_populates="cars")
    power_unit = relationship("PowerUnit", back_populates="cars")
    citations = relationship("Citation", back_populates="car",
                              foreign_keys="Citation.car_id")


class PowerUnit(Base):
    __tablename__ = "power_units"

    id = Column(String, primary_key=True, default=_uid)
    manufacturer = Column(String, nullable=False)
    reliability_indicator = Column(Float, nullable=True)
    performance_indicator = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    cars = relationship("Car", back_populates="power_unit")
    citations = relationship("Citation", back_populates="power_unit",
                              foreign_keys="Citation.power_unit_id")


class Circuit(Base):
    __tablename__ = "circuits"

    id = Column(String, primary_key=True, default=_uid)
    name = Column(String, nullable=False)
    country = Column(String, nullable=True)
    overtaking_difficulty = Column(_SAEnum(CircuitCategory), nullable=True)
    power_sensitivity = Column(_SAEnum(CircuitCategory), nullable=True)
    aero_sensitivity = Column(_SAEnum(CircuitCategory), nullable=True)
    reliability_stress = Column(_SAEnum(CircuitCategory), nullable=True)
    weather_volatility = Column(_SAEnum(CircuitCategory), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    races = relationship("RaceWeekend", back_populates="circuit")
    citations = relationship("Citation", back_populates="circuit",
                              foreign_keys="Citation.circuit_id")


class RaceWeekend(Base):
    __tablename__ = "race_weekends"

    id = Column(String, primary_key=True, default=_uid)
    grand_prix_name = Column(String, nullable=False)
    circuit_id = Column(String, ForeignKey("circuits.id"), nullable=True)
    scheduled_date = Column(DateTime, nullable=True)
    status = Column(_SAEnum(RaceStatus), nullable=False, default="scheduled")
    has_sprint = Column(Boolean, nullable=False, default=False)
    race_order = Column(Integer, nullable=True)
    season = Column(Integer, nullable=False)
    sessions = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    circuit = relationship("Circuit", back_populates="races")
    citations = relationship("Citation", back_populates="race_weekend",
                              foreign_keys="Citation.race_weekend_id")


class FIABody(Base):
    __tablename__ = "fia_bodies"

    id = Column(String, primary_key=True, default=_uid)
    name = Column(String, nullable=False)
    role_category = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    citations = relationship("Citation", back_populates="fia_body",
                              foreign_keys="Citation.fia_body_id")


class StrategicAsset(Base):
    __tablename__ = "strategic_assets"

    id = Column(String, primary_key=True, default=_uid)
    name = Column(String, nullable=False)
    asset_type = Column(_SAEnum(AssetType), nullable=False)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    driver_id = Column(String, ForeignKey("drivers.id"), nullable=True)
    race_weekend_id = Column(String, ForeignKey("race_weekends.id"), nullable=True)
    fia_body_id = Column(String, ForeignKey("fia_bodies.id"), nullable=True)
    status = Column(String, nullable=True)
    directional_impact = Column(_SAEnum(ImpactDirection), nullable=False, default="unknown")
    confidence = Column(_SAEnum(ConfidenceLabel), nullable=False, default="medium")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    citations = relationship("Citation", back_populates="strategic_asset",
                              foreign_keys="Citation.strategic_asset_id")


# ---------------------------------------------------------------------------
# Relationship, Source, Citation, Event, Embedding models
# ---------------------------------------------------------------------------

class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id = Column(String, primary_key=True, default=_uid)
    source_entity_type = Column(String, nullable=False)
    source_entity_id = Column(String, nullable=False)
    target_entity_type = Column(String, nullable=False)
    target_entity_id = Column(String, nullable=False)
    relationship_type = Column(String, nullable=False)
    valid_from = Column(DateTime, nullable=True)
    valid_until = Column(DateTime, nullable=True)
    confidence = Column(_SAEnum(ConfidenceLabel), nullable=False, default="high")
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    citations = relationship("Citation", back_populates="entity_rel",
                              foreign_keys="Citation.relationship_id")


class Source(Base):
    __tablename__ = "sources"

    id = Column(String, primary_key=True, default=_uid)
    url = Column(String, nullable=False)
    domain = Column(String, nullable=True)
    title = Column(String, nullable=True)
    retrieval_timestamp = Column(DateTime, nullable=False, default=_now)
    discovery_method = Column(_SAEnum(DiscoveryMethod), nullable=False, default="brave_search")
    content_policy = Column(String, nullable=False, default="metadata_only")
    excerpt_snippet = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_now)

    citations = relationship("Citation", back_populates="source")


class Event(Base):
    __tablename__ = "events"

    id = Column(String, primary_key=True, default=_uid)
    event_type = Column(_SAEnum(EventType), nullable=False)
    summary = Column(Text, nullable=False)
    affected_entities = Column(JSON, nullable=True)
    affected_race_ids = Column(JSON, nullable=True)
    time_relevance = Column(_SAEnum(TimeRelevance), nullable=False, default="unknown")
    directional_impact = Column(_SAEnum(ImpactDirection), nullable=False, default="unknown")
    magnitude = Column(Float, nullable=True)
    confidence = Column(_SAEnum(ConfidenceLabel), nullable=False, default="medium")
    duplicate_group_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    version = Column(Integer, nullable=False, default=1)
    is_deleted = Column(Boolean, nullable=False, default=False)

    citations = relationship("Citation", back_populates="event", foreign_keys="Citation.event_id")


class Citation(Base):
    __tablename__ = "citations"

    id = Column(String, primary_key=True, default=_uid)
    source_id = Column(String, ForeignKey("sources.id"), nullable=False)
    url = Column(String, nullable=True)
    title = Column(String, nullable=True)
    domain = Column(String, nullable=True)
    excerpt_snippet = Column(Text, nullable=True)
    retrieval_timestamp = Column(DateTime, nullable=False, default=_now)
    claim_supported = Column(Text, nullable=True)
    confidence = Column(_SAEnum(ConfidenceLabel), nullable=False, default="medium")
    created_at = Column(DateTime, nullable=False, default=_now)

    driver_id = Column(String, ForeignKey("drivers.id"), nullable=True)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    car_id = Column(String, ForeignKey("cars.id"), nullable=True)
    power_unit_id = Column(String, ForeignKey("power_units.id"), nullable=True)
    circuit_id = Column(String, ForeignKey("circuits.id"), nullable=True)
    race_weekend_id = Column(String, ForeignKey("race_weekends.id"), nullable=True)
    fia_body_id = Column(String, ForeignKey("fia_bodies.id"), nullable=True)
    strategic_asset_id = Column(String, ForeignKey("strategic_assets.id"), nullable=True)
    relationship_id = Column(String, ForeignKey("entity_relationships.id"), nullable=True)
    event_id = Column(String, ForeignKey("events.id"), nullable=True)

    source = relationship("Source", back_populates="citations")
    driver = relationship("Driver", back_populates="citations", foreign_keys=[driver_id])
    team = relationship("Team", back_populates="citations", foreign_keys=[team_id])
    car = relationship("Car", back_populates="citations", foreign_keys=[car_id])
    power_unit = relationship("PowerUnit", back_populates="citations", foreign_keys=[power_unit_id])
    circuit = relationship("Circuit", back_populates="citations", foreign_keys=[circuit_id])
    race_weekend = relationship("RaceWeekend", back_populates="citations", foreign_keys=[race_weekend_id])
    fia_body = relationship("FIABody", back_populates="citations", foreign_keys=[fia_body_id])
    strategic_asset = relationship("StrategicAsset", back_populates="citations", foreign_keys=[strategic_asset_id])
    entity_rel = relationship("EntityRelationship", back_populates="citations", foreign_keys=[relationship_id])
    event = relationship("Event", back_populates="citations", foreign_keys=[event_id])


class EmbeddingRecord(Base):
    __tablename__ = "embedding_records"

    id = Column(String, primary_key=True, default=_uid)
    target_record_type = Column(String, nullable=False)
    target_record_id = Column(String, nullable=False)
    model_name = Column(String, nullable=False)
    dimension_count = Column(Integer, nullable=False)
    vector_data = Column(JSON, nullable=False)
    content_hash = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    version_ref = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        Index("ix_embedding_target", "target_record_type", "target_record_id"),
    )


# ---------------------------------------------------------------------------
# Scenario models
# ---------------------------------------------------------------------------

class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True, default=_uid)
    name = Column(String, nullable=False)
    goal = Column(Text, nullable=True)
    current_version_id = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
    is_deleted = Column(Boolean, nullable=False, default=False)

    versions = relationship("ScenarioVersion", back_populates="scenario")


class ScenarioVersion(Base):
    __tablename__ = "scenario_versions"

    id = Column(String, primary_key=True, default=_uid)
    scenario_id = Column(String, ForeignKey("scenarios.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    baseline_type = Column(String, nullable=True)
    baseline_ref = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)
    creator = Column(String, nullable=False, default="operator")

    scenario = relationship("Scenario", back_populates="versions")
    branches = relationship("ScenarioBranch", back_populates="version")
    AcceptedBranch = None  # populated after ScenarioBranch definition

    __table_args__ = (
        UniqueConstraint("scenario_id", "version_number", name="uq_scenario_version"),
    )


class ScenarioBranch(Base):
    __tablename__ = "scenario_branches"

    id = Column(String, primary_key=True, default=_uid)
    version_id = Column(String, ForeignKey("scenario_versions.id"), nullable=False)
    branch_type = Column(_SAEnum(BranchType), nullable=False)
    summary = Column(Text, nullable=False)
    affected_entities = Column(JSON, nullable=True)
    affected_dimensions = Column(JSON, nullable=True)
    directional_impact = Column(_SAEnum(ImpactDirection), nullable=False, default="unknown")
    magnitude = Column(Float, nullable=True)
    confidence = Column(_SAEnum(ConfidenceLabel), nullable=False, default="medium")
    is_hypothetical = Column(Boolean, nullable=False, default=False)
    status = Column(_SAEnum(BranchStatus), nullable=False, default="proposed")
    rationale = Column(Text, nullable=True)
    citation_ids = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)

    version = relationship("ScenarioVersion", back_populates="branches")


class AcceptedBranch(Base):
    __tablename__ = "accepted_branches"

    id = Column(String, primary_key=True, default=_uid)
    scenario_version_id = Column(String, ForeignKey("scenario_versions.id"), nullable=False)
    branch_id = Column(String, ForeignKey("scenario_branches.id"), nullable=False)
    acceptance_order = Column(Integer, nullable=False)


# ---------------------------------------------------------------------------
# Simulation models
# ---------------------------------------------------------------------------

class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(String, primary_key=True, default=_uid)
    scenario_version_id = Column(String, ForeignKey("scenario_versions.id"), nullable=True)
    baseline_snapshot_ref = Column(String, nullable=True)
    simulation_config_version = Column(Integer, nullable=False, default=1)
    run_timestamp = Column(DateTime, nullable=False, default=_now)
    status = Column(_SAEnum(RunStatus), nullable=False, default="pending")

    numeric_outputs = Column(JSON, nullable=True)
    explanation_outputs = Column(JSON, nullable=True)
    advisory_outputs = Column(JSON, nullable=True)
    failure_details = Column(JSON, nullable=True)

    include_explanation = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_now)

    version = relationship("ScenarioVersion", foreign_keys=[scenario_version_id])


class SimulationConfig(Base):
    __tablename__ = "simulation_configs"

    id = Column(String, primary_key=True, default=_uid)
    version_number = Column(Integer, nullable=False)
    weights = Column(JSON, nullable=False, default=dict)
    settings = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=_now)


# ---------------------------------------------------------------------------
# Report models
# ---------------------------------------------------------------------------

class Report(Base):
    __tablename__ = "reports"

    id = Column(String, primary_key=True, default=_uid)
    report_type = Column(String, nullable=False)
    scenario_version_id = Column(String, ForeignKey("scenario_versions.id"), nullable=True)
    simulation_run_id = Column(String, ForeignKey("simulation_runs.id"), nullable=True)
    format = Column(_SAEnum(ReportFormat), nullable=False)
    generated_at = Column(DateTime, nullable=False, default=_now)
    file_path = Column(String, nullable=True)
    citation_list = Column(JSON, nullable=True)
    status = Column(_SAEnum(ReportStatus), nullable=False, default="pending")
    failure_details = Column(JSON, nullable=True)


# ---------------------------------------------------------------------------
# Job models
# ---------------------------------------------------------------------------

class JobStatus(Base):
    __tablename__ = "job_statuses"

    id = Column(String, primary_key=True, default=_uid)
    job_type = Column(_SAEnum(JobType), nullable=False)
    status = Column(_SAEnum(RunStatus), nullable=False, default="pending")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failure_details = Column(JSON, nullable=True)
    stats = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_now)


# ---------------------------------------------------------------------------
# Entity version model (for versioned attributes)
# ---------------------------------------------------------------------------

class EntityVersion(Base):
    __tablename__ = "entity_versions"

    id = Column(String, primary_key=True, default=_uid)
    entity_type = Column(String, nullable=False)
    driver_id = Column(String, ForeignKey("drivers.id"), nullable=True)
    team_id = Column(String, ForeignKey("teams.id"), nullable=True)
    car_id = Column(String, ForeignKey("cars.id"), nullable=True)
    power_unit_id = Column(String, ForeignKey("power_units.id"), nullable=True)
    circuit_id = Column(String, ForeignKey("circuits.id"), nullable=True)
    race_weekend_id = Column(String, ForeignKey("race_weekends.id"), nullable=True)
    version_number = Column(Integer, nullable=False)
    snapshot = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now)

    driver = relationship("Driver", back_populates="attribute_versions", foreign_keys=[driver_id])
    team = relationship("Team", back_populates="attribute_versions", foreign_keys=[team_id])


class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(String, primary_key=True, default=_uid)
    key = Column(String, nullable=False, unique=True)
    value = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=_now, onupdate=_now)
