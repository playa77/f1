"""Pydantic schemas for structured LLM output validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Optional

from pydantic import BaseModel, Field, field_validator


class SearchQuery(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    rationale: str = Field("", max_length=500)


class SearchQueryPlan(BaseModel):
    queries: list[SearchQuery] = Field(..., min_length=1, max_length=10)
    topic_summary: str = Field("", max_length=1000)


class RelevanceClassification(BaseModel):
    url: str
    title: str = ""
    domain: str = ""
    is_relevant: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field("", max_length=500)

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError(f"confidence must be 0-1, got {v}")
        return v


class PageIngestionDecision(BaseModel):
    url: str
    action: str = Field(...)
    reason: str = Field("", max_length=500)


class EventExtraction(BaseModel):
    event_type: str = Field(...)
    summary: str = Field(..., max_length=2000)
    affected_entity_types: list[str] = Field(default_factory=list)
    affected_entity_names: list[str] = Field(default_factory=list)
    time_relevance: str = Field("unknown")
    directional_impact: str = Field("unknown")
    magnitude: Optional[float] = Field(None, ge=-1.0, le=1.0)
    confidence: str = Field("medium")

    VALID_EVENT_TYPES: ClassVar[set[str]] = {
        "performance", "reliability", "driver_condition", "team_internal_conflict",
        "regulatory_fia", "race_logistics", "geopolitical_disruption",
        "financial_sponsor_pressure", "weather_circuit_risk", "other",
    }
    VALID_TIME_RELEVANCE: ClassVar[set[str]] = {"immediate", "next_race", "multi_race", "season_long", "unknown"}
    VALID_IMPACTS: ClassVar[set[str]] = {"positive", "negative", "mixed", "unknown"}
    VALID_CONFIDENCE: ClassVar[set[str]] = {"low", "medium", "high"}

    @field_validator("event_type")
    @classmethod
    def check_event_type(cls, v: str) -> str:
        if v not in cls.VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event_type: {v}. Must be one of {cls.VALID_EVENT_TYPES}")
        return v

    @field_validator("time_relevance")
    @classmethod
    def check_time_relevance(cls, v: str) -> str:
        if v not in cls.VALID_TIME_RELEVANCE:
            raise ValueError(f"Invalid time_relevance: {v}")
        return v

    @field_validator("directional_impact")
    @classmethod
    def check_directional_impact(cls, v: str) -> str:
        if v not in cls.VALID_IMPACTS:
            raise ValueError(f"Invalid directional_impact: {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: str) -> str:
        if v not in cls.VALID_CONFIDENCE:
            raise ValueError(f"Invalid confidence: {v}")
        return v


class SourceCitation(BaseModel):
    url: str
    title: str = ""
    domain: str = ""
    excerpt: str = Field("", max_length=1000)
    claim_supported: str = Field("", max_length=500)
    confidence: str = "medium"


class EventExtractionResult(BaseModel):
    events: list[EventExtraction] = Field(default_factory=list)
    citations: list[SourceCitation] = Field(default_factory=list)
    extraction_notes: str = Field("", max_length=1000)


class BranchProposal(BaseModel):
    branch_type: str = Field(...)
    summary: str = Field(..., max_length=1000)
    affected_entity_types: list[str] = Field(default_factory=list)
    affected_entity_names: list[str] = Field(default_factory=list)
    affected_dimensions: list[str] = Field(default_factory=list)
    directional_impact: str = Field("unknown")
    magnitude: float = Field(0.0, ge=-1.0, le=1.0)
    confidence: str = Field("medium")
    rationale: str = Field("", max_length=1000)
    is_hypothetical: bool = False

    VALID_BRANCH_TYPES: ClassVar[set[str]] = {
        "race_canceled_postponed", "driver_performance_impact", "team_performance_impact",
        "car_reliability_impact", "power_unit_reliability_impact",
        "regulatory_fia_impact", "financial_pressure_impact",
        "political_geopolitical_risk_impact", "internal_conflict_impact",
        "circuit_session_condition_impact",
    }
    VALID_IMPACTS: ClassVar[set[str]] = {"positive", "negative", "mixed", "unknown"}
    VALID_CONFIDENCE: ClassVar[set[str]] = {"low", "medium", "high"}

    @field_validator("branch_type")
    @classmethod
    def check_branch_type(cls, v: str) -> str:
        if v not in cls.VALID_BRANCH_TYPES:
            raise ValueError(f"Invalid branch_type: {v}")
        return v

    @field_validator("directional_impact")
    @classmethod
    def check_impact(cls, v: str) -> str:
        if v not in cls.VALID_IMPACTS:
            raise ValueError(f"Invalid directional_impact: {v}")
        return v


class BranchProposalResult(BaseModel):
    branches: list[BranchProposal] = Field(default_factory=list)
    proposal_notes: str = Field("", max_length=1000)


class SimulationExplanation(BaseModel):
    delta_type: str = Field(...)
    affected_entity: str = Field("", max_length=200)
    description: str = Field("", max_length=1000)
    confidence: str = Field("medium")
    key_factor: str = Field("", max_length=500)


class StrategicRecommendation(BaseModel):
    target_entity: str = Field(..., max_length=200)
    target_type: str = Field("season_wide", max_length=50)
    recommendation: str = Field(..., max_length=1000)
    rationale: str = Field(..., max_length=1000)
    confidence: str = Field("medium")
    citation_urls: list[str] = Field(default_factory=list)
    priority: str = Field("medium")

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: str) -> str:
        if v not in ("low", "medium", "high"):
            raise ValueError(f"Invalid confidence: {v}")
        return v

    @field_validator("priority")
    @classmethod
    def check_priority(cls, v: str) -> str:
        if v not in ("low", "medium", "high", "critical"):
            raise ValueError(f"Invalid priority: {v}")
        return v


class AdvisoryResult(BaseModel):
    recommendations: list[StrategicRecommendation] = Field(default_factory=list)
    summary: str = Field("", max_length=2000)
    generated_at: Optional[datetime] = None


class ReportNarrative(BaseModel):
    section: str = Field(..., max_length=100)
    content: str = Field(..., max_length=5000)
    citations: list[str] = Field(default_factory=list)


class ReportNarrativeResult(BaseModel):
    sections: list[ReportNarrative] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str = Field(..., max_length=5000)
    citations: list[dict[str, str]] = Field(default_factory=list)
    proposed_actions: list[str] = Field(default_factory=list)
