"""Source/event discovery pipeline."""

import json
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Source, Citation, Event, JobStatus,
    DiscoveryMethod, EventType, ImpactDirection, TimeRelevance, ConfidenceLabel,
    RunStatus, JobType,
)
from app.schemas import (
    SearchQueryPlan, SearchQuery, RelevanceClassification,
    PageIngestionDecision, EventExtractionResult, EventExtraction, SourceCitation,
)
from app.services.brave_search import brave_search, fetch_page_content, BraveSearchError
from app.services.openrouter import chat_completion, OpenRouterError


def _now():
    return datetime.now(timezone.utc)


async def generate_search_queries() -> SearchQueryPlan:
    """Use the strong model to generate targeted F1 search queries."""
    settings = get_settings()
    season = settings.f1_season

    system_prompt = (
        f"You are an F1 research analyst. Generate search queries to find current "
        f"events and risk signals relevant to the {season} Formula 1 season. "
        f"Topics: performance, reliability, driver conditions, team internal conflicts, "
        f"regulatory/FIA actions, race logistics, geopolitical disruptions, "
        f"financial/sponsor pressures, weather/circuit risks. "
        f"Output strictly as JSON with the following structure: "
        f'{{"queries": [{{"query": "...", "rationale": "..."}}], "topic_summary": "..."}}'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Generate 5-8 targeted search queries for F1 {season} season risk discovery."},
    ]

    result = await chat_completion(
        model=settings.openrouter_fast_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    content = result["content"]
    parsed = json.loads(content)
    return SearchQueryPlan(**parsed)


async def classify_search_results(results: list[dict], season: int) -> list[RelevanceClassification]:
    """Classify search results for relevance using the fast model."""
    settings = get_settings()

    items_json = json.dumps([
        {"index": i, "url": r.get("url", ""), "title": r.get("title", ""),
         "description": r.get("description", "")}
        for i, r in enumerate(results)
    ])

    system_prompt = (
        f"You classify search results for relevance to the {season} F1 season. "
        f"Relevant: driver/team/race/circuit/power unit news, FIA/stewards/regulatory actions, "
        f"geopolitical or logistics affecting races, reliability/performance reports, "
        f"financial/sponsor signals. "
        f"Irrelevant: historical pre-{season} results not about current season, "
        f"gambling/odds/fantasy, merchandise sales, unrelated sports. "
        f"Output strictly as JSON array: "
        f'[{{"url": "...", "title": "...", "domain": "...", "is_relevant": true/false, '
        f'"confidence": 0.0-1.0, "reason": "..."}}]'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Classify these search results: {items_json}"},
    ]

    result = await chat_completion(
        model=settings.openrouter_fast_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    content = result["content"]
    parsed = json.loads(content)

    if isinstance(parsed, dict) and "results" in parsed:
        items = parsed["results"]
    elif isinstance(parsed, list):
        items = parsed
    else:
        items = [parsed]

    return [RelevanceClassification(**item) for item in items]


async def decide_page_ingestion(relevant_items: list[RelevanceClassification]) -> list[PageIngestionDecision]:
    """Decide whether to fetch full page content for each relevant result."""
    settings = get_settings()

    items_json = json.dumps([
        {"index": i, "url": item.url, "title": item.title, "domain": item.domain,
         "confidence": item.confidence, "reason": item.reason}
        for i, item in enumerate(relevant_items)
    ])

    system_prompt = (
        "Decide whether to fetch full page content for each F1 news result. "
        "Rules: 'metadata_sufficient' if title+description is enough to classify. "
        "'fetch_page' if more content is needed to extract events. "
        "'skip' if irrelevant, gated, or unsupported content type. "
        "Output strictly as JSON array: "
        '[{"url": "...", "action": "metadata_sufficient|fetch_page|skip", "reason": "..."}]'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Decide page ingestion for: {items_json}"},
    ]

    result = await chat_completion(
        model=settings.openrouter_fast_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    content = result["content"]
    parsed = json.loads(content)
    if isinstance(parsed, dict) and "decisions" in parsed:
        items = parsed["decisions"]
    elif isinstance(parsed, list):
        items = parsed
    else:
        items = [parsed]

    return [PageIngestionDecision(**item) for item in items]


async def extract_events(content: str, url: str, title: str, season: int) -> EventExtractionResult:
    """Extract structured events from page content."""
    settings = get_settings()

    truncated = content[:20000] if len(content) > 20000 else content

    system_prompt = (
        f"Extract structured F1 events relevant to the {season} season. "
        "For each event found, output: event_type (performance|reliability|driver_condition|"
        "team_internal_conflict|regulatory_fia|race_logistics|geopolitical_disruption|"
        "financial_sponsor_pressure|weather_circuit_risk|other), "
        "summary (concise), affected_entity_types (list), affected_entity_names (list), "
        "time_relevance (immediate|next_race|multi_race|season_long|unknown), "
        "directional_impact (positive|negative|mixed|unknown), magnitude (-1.0 to 1.0), "
        "confidence (low|medium|high). "
        "Also output source citation info. "
        "Output strictly as JSON: "
        '{{"events": [...], "citations": [...], "extraction_notes": "..."}}'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Source: {title}\nURL: {url}\n\nContent: {truncated}"},
    ]

    result = await chat_completion(
        model=settings.openrouter_strong_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.2,
    )

    content_out = result["content"]
    parsed = json.loads(content_out)

    try:
        return EventExtractionResult(**parsed)
    except Exception:
        if "events" in parsed:
            parsed["events"] = [e for e in parsed["events"] if isinstance(e, dict)]
        return EventExtractionResult(**parsed)


async def run_discovery_pipeline(db: Session, job_type: str = "manual_discovery") -> dict:
    """Run the full source/event discovery pipeline."""
    job = JobStatus(
        id=str(uuid.uuid4()),
        job_type=JobType(job_type),
        status=RunStatus("running"),
        started_at=_now(),
    )
    db.add(job)
    db.commit()

    stats = {"sources_created": 0, "events_created": 0, "errors": [], "failed_provider": None}
    season = get_settings().f1_season

    try:
        query_plan = await generate_search_queries()

        all_results = []
        for sq in query_plan.queries[:5]:
            try:
                search_result = await brave_search(sq.query, count=10)
                for r in search_result.get("results", []):
                    r["_query"] = sq.query
                all_results.extend(search_result.get("results", []))
            except BraveSearchError as e:
                stats["errors"].append(f"Brave search failed for query '{sq.query}': {e.message}")
                stats["failed_provider"] = "brave"
                continue

        if not all_results:
            job.status = RunStatus("failed")
            job.failure_details = stats
            job.completed_at = _now()
            db.commit()
            return stats

        classifications = await classify_search_results(all_results, season)
        relevant = [c for c in classifications if c.is_relevant and c.confidence >= 0.3]

        for rc in relevant:
            source = Source(
                url=rc.url,
                domain=rc.domain,
                title=rc.title,
                discovery_method=DiscoveryMethod("brave_search"),
                content_policy="metadata_only",
            )
            db.add(source)
            stats["sources_created"] += 1
        db.commit()

        if get_settings().page_fetch_enabled:
            decisions = await decide_page_ingestion(relevant)
            fetch_items = [d for d in decisions if d.action == "fetch_page"]

            for decision in fetch_items:
                try:
                    page_content = await fetch_page_content(decision.url)
                    extraction = await extract_events(
                        page_content, decision.url, decision.url, season
                    )

                    source = Source(
                        url=decision.url,
                        domain=decision.url.split("/")[2] if "://" in decision.url else decision.url,
                        title=decision.url,
                        discovery_method=DiscoveryMethod("page_fetch"),
                        content_policy="structured_extraction_only",
                    )
                    db.add(source)
                    db.flush()

                    for event_data in extraction.events:
                        try:
                            EventExtraction(**event_data.model_dump())
                        except Exception:
                            continue

                        event_id = str(uuid.uuid4())
                        event = Event(
                            id=event_id,
                            event_type=EventType(event_data.event_type),
                            summary=event_data.summary,
                            affected_entities=json.dumps({
                                "types": event_data.affected_entity_types,
                                "names": event_data.affected_entity_names,
                            }) if event_data.affected_entity_types or event_data.affected_entity_names else None,
                            time_relevance=TimeRelevance(event_data.time_relevance),
                            directional_impact=ImpactDirection(event_data.directional_impact),
                            magnitude=event_data.magnitude,
                            confidence=ConfidenceLabel(event_data.confidence),
                        )
                        db.add(event)

                        for cit in extraction.citations:
                            citation = Citation(
                                source_id=source.id,
                                url=cit.url,
                                title=cit.title,
                                domain=cit.domain,
                                excerpt_snippet=cit.excerpt,
                                claim_supported=cit.claim_supported,
                                confidence=ConfidenceLabel(cit.confidence),
                                event_id=event_id,
                            )
                            db.add(citation)

                        stats["events_created"] += 1
                    stats["sources_created"] += 1
                    db.commit()

                except BraveSearchError as e:
                    stats["errors"].append(f"Page fetch failed for {decision.url}: {e.message}")
                    continue
                except OpenRouterError as e:
                    stats["errors"].append(f"Extraction failed for {decision.url}: {e.message}")
                    if not stats["failed_provider"]:
                        stats["failed_provider"] = "openrouter"
                    continue
                except Exception as e:
                    stats["errors"].append(f"Unexpected error processing {decision.url}: {str(e)}")
                    continue

        job.status = RunStatus("completed")
        job.stats = stats
        job.completed_at = _now()
        db.commit()

    except OpenRouterError as e:
        stats["failed_provider"] = "openrouter"
        stats["errors"].append(f"OpenRouter failure: {e.message}")
        job.status = RunStatus("failed")
        job.failure_details = stats
        job.completed_at = _now()
        db.commit()
    except BraveSearchError as e:
        stats["failed_provider"] = "brave"
        stats["errors"].append(f"Brave failure: {e.message}")
        job.status = RunStatus("failed")
        job.failure_details = stats
        job.completed_at = _now()
        db.commit()
    except Exception as e:
        stats["errors"].append(f"Pipeline failure: {str(e)}")
        job.status = RunStatus("failed")
        job.failure_details = stats
        job.completed_at = _now()
        db.commit()

    return stats
