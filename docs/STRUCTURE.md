# SpotifAI — Project Structure

Last updated: 2026-03-05

```
spotifai/
│
├── docs/                          # Project documentation & tracking
│   ├── SpotifAI_CDC_v2.md         # Full project specification (cahier des charges)
│   ├── STRUCTURE.md               # This file — project tree with file roles
│   ├── NEXT_STEPS.md              # Task tracking (done / todo / known issues)
│   └── DECISIONS.md               # Architecture decision log
│
├── data/                          # DuckDB database files (gitignored)
│   └── spotifai.duckdb            # Created automatically on first run
│
├── api/                           # External API wrappers (Spotify, Claude)
│   ├── __init__.py
│   ├── spotify.py                 # Spotipy wrapper: OAuth, user data, search
│   ├── llm.py                     # Anthropic SDK wrapper: criteria extraction, title gen
│   └── routes.py                  # FastAPI router: all HTTP endpoints
│
├── db/                            # Database layer (DuckDB)
│   ├── __init__.py
│   ├── database.py                # Connection management + schema init (CREATE TABLE)
│   ├── models.py                  # Pydantic models: data validation & type safety
│   └── queries.py                 # CRUD operations: all SQL lives here
│
├── core/                          # Business logic
│   ├── __init__.py
│   ├── profile.py                 # User musical profile sync & computation
│   ├── generator.py               # Playlist generation pipeline orchestrator
│   └── prompts.py                 # LLM prompt templates (versioned here)
│
├── static/                        # Frontend static assets
│   ├── css/
│   │   └── main.css               # Dark theme, CSS design system, WCAG AA contrast
│   └── js/
│       └── app.js                 # Generation flow, Spotify save, profile sync, audio preview
│
├── templates/                     # Jinja2 HTML templates
│   ├── partials/                  # Reusable HTML components (header, nav, etc.)
│   ├── index.html                 # Main page: prompt input + results + track list
│   └── history.html               # Playlist history dashboard (relaunch, multi-delete)
│
├── main.py                        # FastAPI app entry point
├── config.py                      # Settings loaded from .env (pydantic-settings)
├── requirements.txt               # Python dependencies
├── .env.example                   # Environment variable template (safe to commit)
├── .env                           # Actual credentials (gitignored — never commit)
└── .gitignore                     # Files excluded from version control
```

## Module responsibilities

| Module              | Responsibility                               |
| ------------------- | -------------------------------------------- |
| `config.py`         | Single source of truth for all env variables |
| `main.py`           | App wiring: middleware, static files, router |
| `api/spotify.py`    | All Spotify API calls (auth + data + search) |
| `api/llm.py`        | All Claude API calls + JSON parsing + retry  |
| `api/routes.py`     | HTTP layer only — delegates to core/         |
| `db/database.py`    | DB connection + table creation               |
| `db/models.py`      | Data contracts (Pydantic)                    |
| `db/queries.py`     | All SQL queries (CRUD)                       |
| `core/profile.py`   | Profile sync business logic                  |
| `core/generator.py` | Playlist generation orchestration            |
| `core/prompts.py`   | LLM prompt templates                         |

## Phase 2 status

All Phase 2 modules are implemented and functional. The app runs end-to-end:
login → profile sync → generation → Spotify save → history dashboard.

See `docs/NEXT_STEPS.md` for the Phase 3 roadmap.
