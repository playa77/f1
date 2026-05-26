#!/usr/bin/env python3
"""F1 Strategic Agentic Analyzer - Application entry point."""
import uvicorn
from app.config import get_settings


def main():
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
