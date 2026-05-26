# F1 Strategic Agentic Analyzer

A local-first, single-operator Formula 1 strategic analysis workstation for the current/next season. Ingests F1 data, discovers source-attributed events, models entities in relational and embedding space, supports scenario simulation, and generates exportable reports with citations.

## Architecture

Single-process Python web application:

- **Backend:** FastAPI (async Python)
- **Database:** SQLite via SQLAlchemy ORM
- **Frontend:** Server-rendered Jinja2 templates + vanilla JavaScript
- **Scheduler:** APScheduler for daily discovery job
- **LLM:** OpenRouter API (`deepseek/deepseek-v4-pro`, `deepseek/deepseek-v4-flash`, `perplexity/pplx-embed-v1-0.6b`)
- **Search:** Brave Search API
- **PDF:** WeasyPrint
- **Storage:** Local SQLite + filesystem for exports

## Quick Start

### Prerequisites

- Python 3.11+
- OpenRouter API key (https://openrouter.ai/keys)
- Brave Search API key (https://brave.com/search/api/)

### Setup

```bash
# Clone the repository
git clone https://github.com/playa77/f1.git
cd f1

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `.env`:

```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
BRAVE_SEARCH_API_KEY=BSA-your-key-here
OPENROUTER_STRONG_MODEL=deepseek/deepseek-v4-pro
OPENROUTER_FAST_MODEL=deepseek/deepseek-v4-flash
OPENROUTER_EMBEDDING_MODEL=perplexity/pplx-embed-v1-0.6b
F1_SEASON=2026
APP_HOST=127.0.0.1
APP_PORT=8080
```

### Run

```bash
python run.py
```

Open http://127.0.0.1:8080 in your browser.

### First-Time Setup

1. Open http://127.0.0.1:8080/config/
2. Click **Seed Static Data** to populate the 2026 F1 season (teams, drivers, circuits, race schedule)
3. Optionally click **Run Discovery** to search for current F1 events via Brave Search (requires API keys)

## Features

### Entity Browser
View drivers, teams, cars, power units, circuits, races, and strategic assets with source citations.

### Source/Event Feed
Discover F1 events via Brave Search with LLM-powered extraction. Events include:
- Performance and reliability signals
- Driver conditions (injuries, contract issues)
- Team internal conflicts
- Regulatory/FIA actions
- Race logistics and geopolitical disruptions
- Financial/sponsor pressure
- Weather/circuit risks

### Scenario Director
- Create scenarios with goals/questions
- Ask the director to propose scenario branches
- Accept or reject proposed branches
- Immutable versioned scenario history

### Simulation Engine
- Run baseline simulations (no scenario branches)
- Run scenario simulations with accepted branches
- Compare baseline vs. scenario results
- Outputs: race result probabilities, driver/constructor championship projections, DNF risk, qualitative risk scores

### Strategic Advisor
LLM-generated recommendations for teams and drivers based on simulation outputs and events, including rationale, confidence, and citations.

### Agent Chat
Ask questions about the current F1 season. The agent answers from local context and can suggest scenario branches.

### Reports
Export simulation results as Markdown, PDF, or JSON with full citation lists.

### Daily Job
Automatic daily discovery job (configurable schedule) to keep event data fresh.

### Data Management
- Delete individual scenarios
- Delete source-ingested records
- Delete all data (with confirmation)

## Project Structure

```
f1/
├── .env.example          # Configuration template
├── .gitignore
├── .opencodeignore
├── requirements.txt
├── run.py                # Application entry point
├── README.md
├── data/                 # SQLite database (auto-created)
├── exports/              # Generated reports
└── app/
    ├── main.py           # FastAPI application
    ├── config.py         # Configuration from .env
    ├── database.py       # SQLAlchemy setup
    ├── models/
    │   └── __init__.py   # All ORM models
    ├── schemas/
    │   └── __init__.py   # Pydantic validation schemas
    ├── routers/
    │   ├── dashboard.py  # Dashboard view
    │   ├── entities.py   # Entity browser
    │   ├── events.py     # Source/event feed
    │   ├── scenarios.py  # Scenario builder
    │   ├── simulations.py # Simulation runner
    │   ├── agents.py     # Agent chat
    │   ├── reports.py    # Report downloads
    │   └── config.py     # Configuration/admin
    ├── services/
    │   ├── brave_search.py  # Brave Search API client
    │   ├── openrouter.py    # OpenRouter API client
    │   ├── discovery.py     # Event discovery pipeline
    │   ├── simulation.py    # Simulation engine
    │   ├── advisor.py       # Strategic advisor
    │   ├── reports.py       # Report generator
    │   ├── embeddings.py    # Embedding service
    │   ├── scheduler.py     # Background job scheduler
    │   └── seed_data.py     # F1 2026 seed data
    ├── templates/        # Jinja2 HTML templates
    └── static/           # CSS and JavaScript
```

## Key Design Decisions

1. **Single local monolith** — One process, SQLite, local file storage
2. **Explicit relational truth + embeddings** — Canonical relationships in SQL, embeddings for semantic retrieval
3. **Strict structured LLM outputs** — All model outputs validated before persistence
4. **No raw prompt/response persistence** — Only structured outputs and sanitized metadata stored
5. **Source attribution mandatory** — Every sourced fact carries citations
6. **Human-in-the-loop via scenarios** — Refinement through scenario creation and branch acceptance, not weight editing
7. **Agent autonomy bounded by validation** — Multi-step reasoning allowed, state changes require validation
8. **No auth in v1** — Localhost-only by default, warning on non-local binding
9. **Daily job without notifications** — Status visible in UI
10. **Hybrid simulation with calibrated humility** — Numeric for race/championship, qualitative labels for risk

## Backup

Copy these directories while the app is stopped:

```bash
cp data/f1_analyzer.sqlite backup/
cp -r exports/ backup/
```

Restore by placing them back in their original locations.

## Minimum Viability Checklist

- [x] `.env` configuration with OpenRouter and Brave keys
- [x] Local startup with SQLite
- [x] Import/refresh F1 season entities
- [x] Brave-based discovery trigger
- [x] Structured, cited F1 event extraction
- [x] Entity, relationship, source, and event browsing
- [x] Scenario creation
- [x] Scenario director branch proposals
- [x] Branch accept/reject
- [x] Baseline and scenario simulations
- [x] Numeric forecast outputs
- [x] Strategic recommendations
- [x] Markdown, PDF, and JSON export
- [x] Daily job with status display
- [x] Secrets never exposed in UI, logs, database, or reports
- [x] No raw LLM prompts/responses or Brave payloads persisted
- [x] Deletion workflows (all data, single scenario, source records)

## License

Private research tool. Not licensed for redistribution.
