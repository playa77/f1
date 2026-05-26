"""Background job scheduler for the daily discovery job."""

import threading
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_session_local


_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def _now():
    return datetime.now(timezone.utc)


def start_scheduler():
    """Start the background scheduler for daily jobs."""
    global _scheduler

    with _lock:
        if _scheduler is not None:
            return

        settings = get_settings()
        _scheduler = BackgroundScheduler()

        schedule_parts = settings.daily_job_schedule.split(":")
        hour = int(schedule_parts[0]) if len(schedule_parts) > 1 else 3
        minute = int(schedule_parts[1]) if len(schedule_parts) > 1 else 0

        _scheduler.add_job(
            _run_daily_discovery,
            "cron",
            hour=hour,
            minute=minute,
            id="daily_discovery",
            name="Daily F1 Discovery Job",
            replace_existing=True,
        )
        _scheduler.start()


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    with _lock:
        if _scheduler is not None:
            _scheduler.shutdown(wait=False)
            _scheduler = None


def _run_daily_discovery():
    """Execute the daily discovery pipeline."""
    from app.services.discovery import run_discovery_pipeline

    db: Session = get_session_local()()
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run():
            return await run_discovery_pipeline(db, "daily_discovery")

        loop.run_until_complete(_run())
    except Exception:
        pass
    finally:
        db.close()


def trigger_manual_job(job_type: str) -> dict:
    """Trigger a manual job synchronously."""
    from app.services.discovery import run_discovery_pipeline

    db: Session = get_session_local()()
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _run():
            return await run_discovery_pipeline(db, job_type)

        result = loop.run_until_complete(_run())
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        db.close()
