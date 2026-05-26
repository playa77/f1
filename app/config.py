"""Application configuration loaded from .env file."""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openrouter_api_key: str
    brave_search_api_key: str

    openrouter_strong_model: str = "deepseek/deepseek-v4-pro"
    openrouter_fast_model: str = "deepseek/deepseek-v4-flash"
    openrouter_embedding_model: str = "perplexity/pplx-embed-v1-0.6b"

    f1_season: int = 2026
    app_host: str = "127.0.0.1"
    app_port: int = 8080
    sqlite_path: str = "data/f1_analyzer.sqlite"
    reports_dir: str = "exports"
    page_fetch_enabled: bool = True

    search_timeout: int = 30
    model_task_timeout: int = 120
    simulation_timeout: int = 300
    report_timeout: int = 60

    daily_job_schedule: str = "03:00"
    daily_job_timezone: str = "Europe/Berlin"
    min_embedding_dimension: int = 1536
    data_retention_days: int = 90

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.sqlite_path}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def validate_configuration() -> list[str]:
    """Validate required configuration on startup. Returns list of warnings/errors."""
    settings = get_settings()
    warnings: list[str] = []

    if not settings.openrouter_api_key or settings.openrouter_api_key.startswith("sk-or-v1-your-"):
        warnings.append("OPENROUTER_API_KEY is missing or using placeholder value")

    if not settings.brave_search_api_key or settings.brave_search_api_key.startswith("BSA-your-"):
        warnings.append("BRAVE_SEARCH_API_KEY is missing or using placeholder value")

    if settings.app_host not in ("127.0.0.1", "localhost", "::1"):
        warnings.append(
            f"WARNING: App binding to non-localhost address ({settings.app_host}) "
            "without authentication. This is unsafe for production.")


    Path(settings.reports_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)

    return warnings
