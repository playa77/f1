"""Background job scheduler for the comprehensive nightly pipeline.

Runs once per 24h at a configurable time (default: 03:00 Europe/Berlin).
Executes a multi-stage pipeline: discovery, deduplication, embedding refresh,
baseline simulation, advisory generation, and data maintenance.
Each stage is independently tracked; a single stage failure does not halt
the remaining stages.
"""

import asyncio
import json
import logging
import threading
import time
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session_local
from app.models import (
    Citation,
    Driver,
    Team,
    Car,
    PowerUnit,
    Circuit,
    Event,
    JobStatus,
    JobType,
    RaceStatus,
    RaceWeekend,
    RunStatus,
    SimulationRun,
    Source,
)

log = logging.getLogger("f1.scheduler")

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()

STAGES = (
    "discovery",
    "deduplication",
    "embeddings",
    "simulation",
    "advisory",
    "maintenance",
)


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------


def start_scheduler():
    """Start the background scheduler for the nightly pipeline."""
    global _scheduler

    with _lock:
        if _scheduler is not None:
            return

        settings = get_settings()
        _scheduler = BackgroundScheduler(timezone=settings.daily_job_timezone)

        schedule_parts = settings.daily_job_schedule.split(":")
        hour = int(schedule_parts[0]) if schedule_parts else 3
        minute = int(schedule_parts[1]) if len(schedule_parts) > 1 else 0

        _scheduler.add_job(
            _run_nightly_pipeline,
            "cron",
            hour=hour,
            minute=minute,
            id="nightly_pipeline",
            name="Nightly F1 Pipeline",
            replace_existing=True,
        )
        _scheduler.start()

        tz_name = settings.daily_job_timezone
        log.info(
            "Nightly pipeline scheduler started. Will run daily at %02d:%02d (%s).",
            hour,
            minute,
            tz_name,
        )


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    with _lock:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None
            log.info("Nightly pipeline scheduler stopped.")


# ---------------------------------------------------------------------------
# Nightly pipeline entry point (runs in APScheduler's background thread)
# ---------------------------------------------------------------------------


def _run_nightly_pipeline():
    """APScheduler job target. Runs the full nightly pipeline synchronously."""
    log.info("Nightly pipeline starting...")
    db: Session = get_session_local()()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        pipeline = NightlyPipeline()
        loop.run_until_complete(pipeline.run(db))
    except Exception:
        log.exception("Nightly pipeline crashed with unhandled exception")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Manual / API triggering
# ---------------------------------------------------------------------------


def trigger_manual_job(job_type: str) -> dict:
    """Trigger a job synchronously via the API. Returns stats dict."""
    db: Session = get_session_local()()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if job_type in ("full_refresh", "nightly_pipeline"):
            pipeline = NightlyPipeline()
            result = loop.run_until_complete(pipeline.run(db))
            return result

        from app.services.discovery import run_discovery_pipeline
        result = loop.run_until_complete(run_discovery_pipeline(db, job_type))
        return result
    except Exception as e:
        log.exception("Manual job '%s' failed", job_type)
        return {"error": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# NightlyPipeline — the comprehensive multi-stage data refresh
# ---------------------------------------------------------------------------


class NightlyPipeline:
    """Orchestrates the full nightly data-refresh pipeline.

    Stages (executed sequentially):
      1. discovery     – search the web for new F1 events and sources
      2. deduplication – detect and group duplicate events
      3. embeddings    – refresh entity embeddings for changed entities
      4. simulation    – run a baseline season simulation
      5. advisory      – generate strategic recommendations
      6. maintenance   – prune stale data, update race statuses
    """

    # ------------------------------------------------------------------
    # Top-level runner
    # ------------------------------------------------------------------

    async def run(self, db: Session) -> dict:
        """Execute every stage and persist a single JobStatus record."""
        job_id = str(uuid.uuid4())
        job = JobStatus(
            id=job_id,
            job_type=JobType("nightly_pipeline"),
            status=RunStatus("running"),
            started_at=_now(),
        )
        db.add(job)
        db.commit()

        stage_defs = (
            (self._stage_discovery, "discovery"),
            (self._stage_deduplication, "deduplication"),
            (self._stage_embeddings, "embeddings"),
            (self._stage_simulation, "simulation"),
            (self._stage_advisory, "advisory"),
            (self._stage_maintenance, "maintenance"),
        )
        failed_stages: list[str] = []

        for fn, name in stage_defs:
            log.info("Nightly pipeline — stage '%s' starting...", name)
            t0 = time.monotonic()
            try:
                result = await fn(db)
                result["status"] = "ok"
                self._stage_results[name] = result
            except Exception:
                log.exception("Nightly pipeline — stage '%s' FAILED", name)
                self._stage_results[name] = {
                    "status": "failed",
                    "error": traceback.format_exc(),
                }
                failed_stages.append(name)
            finally:
                self._stage_durations[name] = round(time.monotonic() - t0, 1)

        total_stages = len(stage_defs)
        all_failed = len(failed_stages) == total_stages if failed_stages else False
        some_failed = len(failed_stages) > 0

        discovery_result = self._stage_results.get("discovery", {})
        embed_result = self._stage_results.get("embeddings", {})
        dedup_result = self._stage_results.get("deduplication", {})
        maint_result = self._stage_results.get("maintenance", {})

        stats = {
            "stages": self._stage_results,
            "durations_s": self._stage_durations,
            "sources_created": discovery_result.get("sources_created", 0),
            "events_created": discovery_result.get("events_created", 0),
            "duplicate_groups": dedup_result.get("groups_created", 0),
            "embeddings_refreshed": embed_result.get("records_generated", 0),
            "sources_pruned": maint_result.get("sources_pruned", 0),
            "records_purged": maint_result.get("records_purged", 0),
            "failed_stages": failed_stages,
        }

        if all_failed:
            job.status = RunStatus("failed")
        elif some_failed:
            job.status = RunStatus("partially_completed")
        else:
            job.status = RunStatus("completed")

        job.stats = stats
        job.completed_at = _now()
        db.commit()

        log.info(
            "Nightly pipeline finished: status=%s sources=%d events=%d "
            "embeddings=%d dup_groups=%d pruned=%d failed_stages=%s",
            job.status.value,
            stats["sources_created"],
            stats["events_created"],
            stats["embeddings_refreshed"],
            stats["duplicate_groups"],
            stats["sources_pruned"],
            failed_stages,
        )
        return stats

    # ------------------------------------------------------------------
    # Stage 1: Discovery
    # ------------------------------------------------------------------

    async def _stage_discovery(self, db: Session) -> dict:
        from app.services.discovery import run_discovery_pipeline

        return await run_discovery_pipeline(db, "daily_discovery")

    # ------------------------------------------------------------------
    # Stage 2: Deduplication
    # ------------------------------------------------------------------

    async def _stage_deduplication(self, db: Session) -> dict:
        """Detect duplicate events via LLM comparison and group them."""
        settings = get_settings()
        lookback = datetime.now(timezone.utc) - timedelta(days=7)

        recent = (
            db.query(Event)
            .filter(
                Event.is_deleted == False,
                Event.duplicate_group_id == None,  # noqa: E711
                Event.created_at >= lookback,
            )
            .order_by(Event.created_at.desc())
            .limit(200)
            .all()
        )

        if len(recent) < 2:
            return {"groups_created": 0, "events_scanned": len(recent)}

        batches = [recent[i : i + 30] for i in range(0, len(recent), 30)]
        groups_created = 0

        for batch in batches:
            if len(batch) < 2:
                continue

            items = [
                {
                    "id": e.id,
                    "type": str(e.event_type) if e.event_type else "",
                    "summary": (e.summary or "")[:300],
                }
                for e in batch
            ]

            try:
                from app.services.openrouter import chat_completion, OpenRouterError

                result = await chat_completion(
                    model=settings.openrouter_fast_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a deduplication assistant for an F1 event database. "
                                "Compare events and identify pairs that describe the same "
                                "real-world occurrence. Two events are duplicates if they "
                                "describe the same incident, decision, or development — "
                                "even if worded differently. Group sizes should be 2-5. "
                                "Output strictly as JSON: "
                                '{"duplicate_groups": [[id1, id2, ...], ...]} '
                                "Return an empty list if no duplicates are found."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Find duplicate groups among: {json.dumps(items)}",
                        },
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.0,
                )
                content = result["content"]
                parsed = json.loads(content)
                groups = parsed.get("duplicate_groups", [])
            except (OpenRouterError, json.JSONDecodeError, KeyError):
                continue

            for group in groups:
                if not isinstance(group, list) or len(group) < 2:
                    continue
                group_id = str(uuid.uuid4())
                group_set = {str(g) for g in group}
                for evt in batch:
                    if evt.id in group_set:
                        evt.duplicate_group_id = group_id
                groups_created += 1

        db.commit()
        return {"groups_created": groups_created, "events_scanned": len(recent)}

    # ------------------------------------------------------------------
    # Stage 3: Embeddings
    # ------------------------------------------------------------------

    async def _stage_embeddings(self, db: Session) -> dict:
        """Refresh embeddings for entities with changed summaries."""
        from app.models import EmbeddingRecord
        from app.services.embeddings import build_entity_summary, embed_texts, _content_hash

        total_generated = 0
        entity_types = [
            (Driver, "driver"),
            (Team, "team"),
            (Car, "car"),
            (PowerUnit, "power_unit"),
            (Circuit, "circuit"),
        ]

        for model_cls, record_type in entity_types:
            entities = db.query(model_cls).filter(
                model_cls.is_deleted == False,
            ).all()

            if not entities:
                continue

            pending: list[tuple[str, str]] = []
            for ent in entities:
                summary = build_entity_summary(ent)
                if not summary.strip():
                    continue
                content_hash = _content_hash(summary)

                existing = (
                    db.query(EmbeddingRecord)
                    .filter(
                        EmbeddingRecord.target_record_type == record_type,
                        EmbeddingRecord.target_record_id == ent.id,
                    )
                    .first()
                )

                if existing and existing.content_hash == content_hash:
                    continue

                pending.append((ent.id, summary))

            if not pending:
                continue

            ids = [eid for eid, _ in pending]
            texts = [s for _, s in pending]

            db.query(EmbeddingRecord).filter(
                EmbeddingRecord.target_record_type == record_type,
                EmbeddingRecord.target_record_id.in_(ids),
            ).delete()
            db.commit()

            try:
                await embed_texts(texts, record_type, ids, db)
                total_generated += len(texts)
            except Exception:
                log.exception("Embedding refresh failed for '%s' entity type", record_type)
                continue

        return {"records_generated": total_generated}

    # ------------------------------------------------------------------
    # Stage 4: Baseline simulation
    # ------------------------------------------------------------------

    async def _stage_simulation(self, db: Session) -> dict:
        from app.services.simulation import run_baseline_simulation

        sim_run = run_baseline_simulation(db)
        return {
            "simulation_id": sim_run.id,
            "status": str(sim_run.status) if sim_run.status else "unknown",
        }

    # ------------------------------------------------------------------
    # Stage 5: Advisory
    # ------------------------------------------------------------------

    async def _stage_advisory(self, db: Session) -> dict:
        from app.services.advisor import generate_recommendations

        latest_sim = (
            db.query(SimulationRun)
            .filter(SimulationRun.status == "completed")
            .order_by(SimulationRun.run_timestamp.desc())
            .first()
        )

        if not latest_sim:
            return {"recommendations": 0, "note": "no completed simulation available"}

        advisory = await generate_recommendations(db, latest_sim)
        rec_count = len(advisory.recommendations)

        latest_sim.advisory_outputs = {
            "recommendations": [r.model_dump() for r in advisory.recommendations],
            "summary": advisory.summary,
        }
        db.commit()

        return {"recommendations": rec_count, "simulation_id": latest_sim.id}

    # ------------------------------------------------------------------
    # Stage 6: Maintenance
    # ------------------------------------------------------------------

    async def _stage_maintenance(self, db: Session) -> dict:
        """Prune stale data and perform housekeeping."""
        settings = get_settings()
        retention_days = settings.data_retention_days
        soft_cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

        sources_pruned = 0
        uncited_sources = (
            db.query(Source.id)
            .outerjoin(Citation, Citation.source_id == Source.id)
            .filter(
                Source.is_deleted == False,
                Source.created_at < soft_cutoff,
                Citation.id == None,  # noqa: E711
            )
            .all()
        )
        uncited_ids = [row[0] for row in uncited_sources]
        if uncited_ids:
            db.query(Source).filter(Source.id.in_(uncited_ids)).update(
                {"is_deleted": True}, synchronize_session=False
            )
            sources_pruned = len(uncited_ids)

        records_purged = 0
        hard_cutoff = soft_cutoff - timedelta(days=30)

        stale_events = db.query(Event).filter(
            Event.is_deleted == True, Event.created_at < hard_cutoff
        ).all()
        for evt in stale_events:
            db.query(Citation).filter(Citation.event_id == evt.id).delete()
            db.delete(evt)
            records_purged += 1

        stale_sources = db.query(Source).filter(
            Source.is_deleted == True, Source.created_at < hard_cutoff
        ).all()
        for src in stale_sources:
            db.query(Citation).filter(Citation.source_id == src.id).delete()
            db.delete(src)
            records_purged += 1

        race_status_updates = 0
        if RaceStatus:
            past_races = (
                db.query(RaceWeekend)
                .filter(
                    RaceWeekend.is_deleted == False,
                    RaceWeekend.scheduled_date.isnot(None),
                    RaceWeekend.scheduled_date < datetime.now(timezone.utc),
                )
                .all()
            )
            for race in past_races:
                if race.status and race.status.value == "scheduled":
                    race.status = RaceStatus("at_risk")
                    race_status_updates += 1

        db.commit()

        return {
            "sources_pruned": sources_pruned,
            "records_purged": records_purged,
            "race_status_updates": race_status_updates,
            "retention_days": retention_days,
        }

