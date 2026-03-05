# SpotifAI — AI-Powered Playlist Generator

> Describe what you want to hear. SpotifAI turns natural language into a Spotify playlist, personalised with your real listening history.

**Stack:** Python · FastAPI · Spotipy · Claude API (Anthropic) · DuckDB · Jinja2 · Vanilla JS

---

## 🎙️ Live Demo

**[spotifai.lumafinch.com](https://spotifai.lumafinch.com)**

> SpotifAI is currently in **Spotify Development mode**, which limits access to 25 whitelisted users.
> To try the demo, send your Spotify account email to [hey@jeremymarchandeau.com](mailto:hey@jeremymarchandeau.com) and I’ll add you.

---

## What it does

SpotifAI breaks Spotify's filter bubble by letting you generate playlists from free-text descriptions:

> *"Post-rock instrumental, Japanese influence, since 2010"*
> *"Late-night jazz fusion, low energy"*
> *"French 90s boom bap hip-hop with jazz samples"*

Your prompt is interpreted by Claude, enriched with your actual Spotify listening profile (top artists, top tracks, recently played), and turned into a curated track list saved directly to your Spotify account.

---

## Features

- **Natural language input** — describe any genre, mood, era, tempo, geography, or artist influence
- **Personalised recommendations** — your Spotify listening history is used as context for Claude
- **Spotify save** — generates a playlist in your account with one click
- **Listening history** — all generated playlists stored locally in DuckDB
- **Re-use prompts** — relaunch any past playlist from the history dashboard
- **30s preview** — inline audio previews directly in the track list

---

## Architecture overview

```
[Browser] — natural language prompt
    ↓
[FastAPI /generate]
    ↓ load user profile from DuckDB
[Claude API] — extract criteria (genres, artists, mood, year range…) → JSON
    ↓
[Spotify /search] — multiple targeted queries, deduplicated + filtered
    ↓
[Claude API] — generate playlist title + description
    ↓
[Spotify /me/playlists] — create playlist in user's account
    ↓
[DuckDB] — save to history
    ↓
[Browser] — display results + Spotify link
```

### Project structure

```
spotifai/
├── api/
│   ├── spotify.py       # Spotipy wrapper: OAuth, user data, search
│   ├── llm.py           # Claude API: criteria extraction, title generation
│   └── routes.py        # FastAPI endpoints
├── core/
│   ├── profile.py       # User profile sync logic
│   ├── generator.py     # Playlist generation pipeline
│   └── prompts.py       # LLM prompt templates
├── db/
│   ├── database.py      # DuckDB connection + schema init
│   ├── models.py        # Pydantic models
│   └── queries.py       # CRUD operations
├── static/              # CSS + JS (vanilla, no build step)
├── templates/           # Jinja2 HTML templates
├── docs/                # Architecture decisions, task tracking, spec
├── main.py              # FastAPI entry point
├── config.py            # Settings via pydantic-settings
└── .env.example         # Environment variable template
```

---

## Setup

### Prerequisites

- Python 3.11+
- A [Spotify Developer App](https://developer.spotify.com/dashboard) (free)
- An [Anthropic API key](https://console.anthropic.com/) (Claude)

### 1. Clone and install

```bash
git clone https://github.com/jeremy6680/spotifai.git
cd spotifai
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/callback

ANTHROPIC_API_KEY=your_anthropic_api_key

# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_random_secret_key

DUCKDB_PATH=./data/spotifai.duckdb
```

### 3. Configure your Spotify Developer App

In your [Spotify Developer Dashboard](https://developer.spotify.com/dashboard):

1. Open your app → **Edit Settings**
2. Add `http://127.0.0.1:8000/callback` to **Redirect URIs**
3. Add your Spotify account email to **User Management** (required in Development mode)
4. Save

> **Note:** Use `127.0.0.1`, not `localhost` — Spotify blocks `localhost` redirect URIs in Development mode.

### 4. Run

```bash
uvicorn main:app --reload --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Usage

1. **Log in** with your Spotify account
2. **Sync your profile** — click "Sync mon profil" to load your listening history into DuckDB (takes ~5s)
3. **Describe your playlist** in the text field, or click a suggestion chip
4. **Generate** — Claude interprets your prompt and Spotify returns matching tracks
5. **Save to Spotify** — creates a playlist in your account (use the track links to add songs manually, see Known Limitations)
6. **History** — all generated playlists are saved locally and relaunchable

---

## Known Limitations

### Spotify API restrictions (Development mode)

Spotify imposes significant restrictions on apps in Development mode (i.e. not approved for Extended Quota):

| Endpoint | Status | Workaround |
|---|---|---|
| `GET /recommendations` | ❌ Blocked since late 2024 | Replaced by `/search` + LLM-generated queries |
| `POST /playlists/{id}/tracks` | ❌ Returns 403 | Playlist created empty; tracks displayed with individual Spotify links |
| `GET /audio-features` | ❌ Deprecated since 2024 | Genres inferred by Claude from artist names |
| `GET /artists` genres | ⚠️ Returns empty arrays | Same workaround as above |

**In practice:** SpotifAI creates an empty playlist in your Spotify account and displays the generated track list with an "Open in Spotify" link per track. You add the tracks you want manually.

This is an external Spotify constraint, not a code issue. If Spotify lifts these restrictions, full functionality can be restored with minimal changes to `api/spotify.py`.

### User Management

Spotify's Development mode limits access to **25 whitelisted users**. To add a user: Spotify Developer Dashboard → your app → User Management.

---

## Architecture decisions

Key technical decisions are documented in [`docs/DECISIONS.md`](docs/DECISIONS.md):

- **ADR-007** — Genres inferred by LLM instead of Spotify API (empty arrays)
- **ADR-008** — `/search` strategy replacing `/recommendations`
- **ADR-009** — Partial Spotify save (empty playlist + individual track links)
- **ADR-010** — No `/api` prefix on routes

---

## Roadmap — Phase 3

This project is designed to evolve. Phase 2 (this version) is a functional single-user tool. Phase 3 targets:

- **dbt medallion pipeline** — bronze/silver/gold layers on top of the existing DuckDB
- **CrewAI multi-agent system** — Music Profiler, Criteria Interpreter, Playlist Curator
- **Airflow event-driven sync** — replace manual profile sync with polling-based triggers
- **React frontend** — replace Jinja2 templates (FastAPI routes stay unchanged)
- **Open-source release** — Docker, GitHub Actions, full documentation

Full roadmap in [`docs/SpotifAI_CDC_v2.md`](docs/SpotifAI_CDC_v2.md).

---

## Deployment

SpotifAI is deployed via Docker on a self-hosted [Coolify](https://coolify.io) instance (Hetzner).

```bash
# Build and run locally with Docker Compose
docker compose up --build
```

For production deployment:
- Build pack: `Dockerfile` (multi-stage, `python:3.11-slim`)
- Exposed port: `8000`
- Persistent volume: `/app/data` (DuckDB file)
- All credentials injected via environment variables — never baked into the image

See `Dockerfile` and `docker-compose.yml` at the project root.

---

## Cost

- **Spotify API** — free for non-commercial use
- **Claude API** — ~$0.003 per playlist generation (claude-sonnet-4, as of March 2026)

---

## Author

Jeremy Marchandeau — [web2data.jeremymarchandeau.com](https://web2data.jeremymarchandeau.com)

This project is part of a web developer → data/AI engineering transition. See the [blog series](https://web2data.jeremymarchandeau.com) for articles covering the technical choices made here.
