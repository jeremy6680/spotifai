# SpotifAI — Next Steps

Last updated: 2026-03-05

---

## ✅ Done

- [x] Initialize Git repo + push to GitHub
- [x] Write project specification (SpotifAI_CDC_v2.md)
- [x] Create project folder structure (all directories)
- [x] Create skeleton files for all modules (with TODOs)
- [x] Create `.gitignore`, `.env.example`, `requirements.txt`
- [x] Create `config.py` (pydantic-settings)
- [x] Create `main.py` (FastAPI app skeleton)
- [x] Create `docs/` tracking files (STRUCTURE, NEXT_STEPS, DECISIONS)

### Step 1 — Spotify OAuth ✅

- [x] Create Spotify Developer App at developer.spotify.com
- [x] Add credentials to `.env`
- [x] Implement `api/spotify.py` — SpotifyOAuth flow
- [x] Implement `GET /login` route → redirect to Spotify
- [x] Implement `GET /callback` route → handle token, store in session
- [x] Test: full login flow in browser

### Step 2 — DuckDB setup ✅

- [x] Implement `db/database.py` — connection + `init_db()`
- [x] Implement Pydantic models in `db/models.py`
- [x] Call `init_db()` on FastAPI startup event
- [x] Test: tables created on first run

### Step 3 — User profile sync ✅

- [x] Implement `api/spotify.py` — `get_user_top_tracks()`, `get_user_top_artists()`, `get_recently_played()`
- [x] Implement `core/profile.py` — `sync_user_profile()`, `compute_audio_features_avg()`
- [x] Implement `db/queries.py` — `upsert_user_profile()`, `get_user_profile()`
- [x] Implement `POST /sync-profile` route
- [x] Test: profile stored in DuckDB after sync

### Step 4 — LLM integration ✅

- [x] Implement `core/prompts.py` — `build_criteria_extraction_prompt()`
- [x] Implement `api/llm.py` — `extract_criteria()` with retry logic
- [x] Unit test: valid JSON returned for various user prompts

### Step 5 — Playlist generation ✅

- [x] Implement `api/spotify.py` — `get_recommendations()` replaced by `/search` strategy (ADR-008)
- [x] Implement `core/generator.py` — `generate_playlist()`
- [x] Implement `core/prompts.py` — `build_title_generation_prompt()`
- [x] Implement `api/llm.py` — `generate_playlist_title()`
- [x] Implement `POST /generate` route
- [x] Test: full generation pipeline end-to-end

### Step 6 — Save to Spotify ✅

- [x] Implement `api/spotify.py` — `create_playlist()`, `add_tracks_to_playlist()`
- [x] Implement `db/queries.py` — `update_playlist_spotify_info()`
- [x] Implement `POST /save` route
- [x] Fix token refresh not persisted to session (intermittent 403)
- [x] Fix `POST /users/{id}/playlists` → migrated to `POST /me/playlists` (ADR-009)
- [x] Graceful degradation: playlist created, tracks returned for Option A
- [x] Test: playlist appears in user's Spotify account

### Step 7 — Frontend ✅

- [x] Create `templates/index.html` — prompt form + results display + Option A track list
- [x] Create `templates/history.html` — playlist history dashboard
- [x] Create `static/css/main.css` — dark theme, CSS design system, WCAG AA contrast
- [x] Create `static/js/app.js` — generation flow, Spotify save, profile sync, audio preview
- [x] Wire up all routes to templates — `GET /`, `GET /history`, Jinja2 TemplateResponse
- [x] Fix fetch calls — removed `/api` prefix, aligned with route declarations (ADR-010)
- [x] Fix Spotify link visibility — always green, not hidden on dark background
- [x] Fix text contrast — `--color-text-muted` and `--color-text-faint` raised to WCAG AA
- [x] Test: full flow in browser (login → sync → generate → save)

### Step 8 — Polish & docs ✅

- [x] Review all error states (invalid token, API failures, empty results, network errors)
- [x] Improve Save button discoverability — sticky CTA displayed after generation
- [x] Add prompt prefill from history page (`?prompt=` query param handled in JS)
- [x] Write `README.md` — setup, usage, env vars, architecture, known limitations
- [x] Remove `/debug/token` endpoint (dev-only, removed before final release)
- [x] Auto-save playlist to DuckDB on generation (no manual save step required)
- [x] Persist full track list to DuckDB alongside playlist metadata
- [x] Multi-delete playlists from history dashboard
- [x] Final end-to-end test

---

## 🔜 Up Next — Phase 3 (roadmap)

> Phase 2 is complete. The app is fully functional as a single-user personal tool.
> Phase 3 targets a production-grade, multi-agent, data-pipeline architecture.

### Step 9 — dbt medallion pipeline

- [ ] Add dbt to the project (install, init, configure DuckDB adapter)
- [ ] Define bronze layer: raw DuckDB tables as dbt sources
- [ ] Define silver layer: cleaned + typed models (playlists, tracks, profiles)
- [ ] Define gold layer: analytical models (genre trends, listening patterns)
- [ ] Write dbt tests for data quality

### Step 10 — CrewAI multi-agent system

- [ ] Define agent roles: Music Profiler, Criteria Interpreter, Playlist Curator
- [ ] Migrate `core/prompts.py` templates to CrewAI agent system prompts
- [ ] Implement agent orchestration replacing `core/generator.py` pipeline
- [ ] Test: multi-agent generation vs. current single-prompt generation

### Step 11 — Airflow event-driven sync

- [ ] Replace manual `POST /sync-profile` with Airflow DAG
- [ ] Define polling interval (daily or on-demand trigger)
- [ ] Test: profile auto-refreshes without user action

### Step 12 — React frontend

- [ ] Scaffold React app (Vite or CRA)
- [ ] Add `prefix="/api"` to `app.include_router(router)` in `main.py`
- [ ] Migrate Jinja2 templates to React components
- [ ] Test: full flow through React frontend

---

## ⚠️ Architecture Change

**`/recommendations` endpoint inaccessible** — Spotify restricted this endpoint to apps
in Extended Quota Mode (organizations with 250k+ MAUs minimum) since late 2024.
SpotifAI uses a `/search` + filtering strategy instead. See ADR-008.

---

## ⚠️ Spotify API Restriction (ADR-009)

**`POST /playlists/{id}/tracks` blocked in Development mode** — Spotify returns 403
when adding tracks to a playlist for non-approved Extended Quota apps. Extended Quota
is no longer available to individuals since May 2025 (organizations only).

Strategy: **Option A** — playlist is created empty in Spotify, frontend displays the
track list with an individual "Open in Spotify" link per track. The user can add them
manually. The code still attempts the add and degrades gracefully on failure — if
Spotify lifts the restriction, it will work without modification.

---

## 🐛 Known Issues

- **Empty Spotify genres**: `current_user_top_artists` returns `genres: []` for all
  artists (Spotify API degradation, March 2026). Workaround: genres inferred by LLM
  from artist names. See ADR-007.
- **Audio features unavailable**: Spotify deprecated this endpoint for new tracks in 2024. `audio_features_avg` returns default values (0.5). Profile relies solely on
  artists and tracks for LLM context.
- **Low track count on some queries**: `/search`-based strategy can return fewer than
  30 tracks for niche genres (observed: 14 tracks for a punk 90s query). Improving
  query diversity in `core/prompts.py` is a Phase 3 item.
