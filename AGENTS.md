# AGENTS.md — Persistent Memory for the F1 Project

## Persistent Memory

### 2026-05-26: Always update README.md on any change

- **Rule**: Whenever introducing, changing, or deleting functionality, UI, configuration, or architecture — **always** update `README.md` to reflect the changes.
- This includes: new features, removed features, config key additions/removals, UI changes, API changes, architecture shifts, design decision updates.
- The README.md is the single source of truth documentation for this project.
- The user considers forgetting to update README.md a serious oversight.

### 2026-05-26: Nightly pipeline replaces old daily discovery job

- The daily scheduler now runs a comprehensive 6-stage `NightlyPipeline` (discovery → deduplication → embeddings → simulation → advisory → maintenance).
- Job type is `nightly_pipeline` (in `app/services/scheduler.py`).
- Old `daily_discovery` discovery pipeline still works but is no longer the scheduled default.
- Config keys: `DAILY_JOB_SCHEDULE` (hour:minute), `DAILY_JOB_TIMEZONE` (default Europe/Berlin), `DATA_RETENTION_DAYS` (default 90).
- Manual trigger via API/UI uses `"full_refresh"` or `"nightly_pipeline"` as job_type.
- Each stage is isolated: one failure does not halt remaining stages.
- `dashboard.py` and `config.py` routers were updated to display the new job type and timezone.

### 2026-05-26: Project uses .venv virtual environment

- The project Python virtual environment is at `.venv/`.
- Use `.venv/bin/python3` and `.venv/bin/pip` for all Python commands.
- Dependencies are listed in `requirements.txt`.
