"""F1 Strategic Agentic Analyzer — Main FastAPI Application."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings, validate_configuration
from app.database import init_db
from app.routers import dashboard, entities, events, scenarios, simulations, reports, agents, config


log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting F1 Strategic Agentic Analyzer...")

    warnings = validate_configuration()
    app.state.config_warnings = warnings
    for w in warnings:
        log.warning(w)

    init_db()
    log.info("Database initialized.")

    from app.services.scheduler import start_scheduler, trigger_manual_job
    start_scheduler()
    log.info("Background scheduler started.")

    yield

    from app.services.scheduler import stop_scheduler
    stop_scheduler()
    log.info("Application shutdown complete.")


app = FastAPI(
    title="F1 Strategic Agentic Analyzer",
    version="0.1.0",
    lifespan=lifespan,
)


templates = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(["html", "xml"]),
    enable_async=True,
)


def _template_context(request: Request):
    return {
        "request": request,
        "config_season": get_settings().f1_season,
    }


templates.globals["get_context"] = _template_context


class Jinja2Templates:
    def __init__(self, env: Environment):
        self.env = env

    async def TemplateResponse(self, name: str, context: dict, status_code: int = 200, headers: dict | None = None):
        from fastapi.responses import HTMLResponse as HTMLResp
        ctx = {**context}
        ctx.setdefault("config_season", get_settings().f1_season)
        template = self.env.get_template(name)

        try:
            rendered = await template.render_async(**ctx)
        except Exception:
            ctx_no_req = {k: v for k, v in ctx.items() if k != "request"}
            rendered = await template.render_async(**ctx_no_req)

        return HTMLResp(content=rendered, status_code=status_code, headers=headers)


app.state.templates = Jinja2Templates(templates)

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

app.include_router(dashboard.router)
app.include_router(entities.router)
app.include_router(events.router)
app.include_router(scenarios.router)
app.include_router(simulations.router)
app.include_router(reports.router)
app.include_router(agents.router)
app.include_router(config.router)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return RedirectResponse(url="/dashboard/")
