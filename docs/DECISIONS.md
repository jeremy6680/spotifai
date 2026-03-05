# SpotifAI — Architecture Decisions

Last updated: 2026-03-05

---

## ADR-001 — FastAPI over Flask

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** The CDC mentions Flask for Phase 1 and FastAPI for Phase 2.

**Decision:** Use FastAPI from the start, even though Flask would be simpler for a beginner.

**Rationale:**

- FastAPI is the target stack per the CDC Phase 2
- Pydantic validation is built-in — important for validating LLM JSON output
- Auto-generated OpenAPI docs will be useful when building the Phase 3 React frontend
- Async support prepares for Phase 3 (Airflow triggers, concurrent API calls)
- No meaningful extra complexity for this project size

**Phase 3 impact:** FastAPI routes remain unchanged when replacing Jinja2 templates with React frontend.

---

## ADR-002 — pydantic-settings for configuration

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** Need to load environment variables from `.env` securely.

**Decision:** Use `pydantic-settings` (`BaseSettings`) instead of raw `os.getenv()`.

**Rationale:**

- Validates that all required env variables are present at startup (fails fast if missing)
- Type coercion: strings from `.env` are cast to the correct Python types
- Single `settings` object importable anywhere — no scattered `os.getenv()` calls
- Consistent with Pydantic already used for models

**Phase 3 impact:** None — config layer stays the same.

---

## ADR-003 — DuckDB for local persistence

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** Need a database to store user profiles and playlist history.

**Decision:** Use DuckDB with a local `.duckdb` file.

**Rationale:**

- Zero infrastructure: no separate database process to run
- SQL-native: analytical queries will be useful in Phase 3 (dbt medallion)
- The `.duckdb` file becomes the bronze layer in Phase 3 with zero migration cost
- Sufficient for single-user Phase 2 use case

**Phase 3 impact:** DuckDB stays as the foundation. dbt models are added on top as silver/gold layers.

---

## ADR-004 — Session-based token storage (single user)

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** Need to store the Spotify OAuth token after login.

**Decision:** Store the token in the server-side session (Starlette `SessionMiddleware`).

**Rationale:**

- Phase 2 is a single-user personal tool — no multi-user requirements
- Session storage is simpler and secure enough for this scope
- Token is signed by `SECRET_KEY`, so it cannot be tampered with client-side

**Trade-off:** Not scalable to multiple users. For multi-user Phase 3, tokens would need to be stored encrypted in DuckDB, keyed by `user_id`.

**Phase 3 impact:** If multi-user is needed, migrate to encrypted DuckDB token storage.

---

## ADR-005 — Prompts centralized in core/prompts.py

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** LLM prompts could live inline in `api/llm.py` or in a dedicated module.

**Decision:** All prompt templates live in `core/prompts.py`.

**Rationale:**

- Prompts are business logic, not API implementation details
- Centralizing them makes iteration, testing, and versioning easier
- In Phase 3, CrewAI agent instructions will be built from these same templates

**Phase 3 impact:** `core/prompts.py` becomes the foundation for CrewAI agent system prompts.

---

## ADR-006 — Redirect URI: 127.0.0.1 rather than localhost

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** Spotify blocks `http://localhost:8000/callback` in its dashboard (non-bypassable security warning).

**Decision:** Use `http://127.0.0.1:8000/callback` as redirect URI.

**Rationale:** `127.0.0.1` is the loopback IP address — strictly equivalent to `localhost` in practice. Spotify accepts it without blocking.

**Phase 3 impact:** Replace with a real `https://` URL in production.

---

## ADR-007 — Genres inferred by LLM rather than extracted from Spotify

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** Spotify's `current_user_top_artists` endpoint returns empty `genres: []` arrays for most artists (progressive API degradation, observed March 2026). Audio features are also deprecated since 2024.

**Decision:** Do not rely on Spotify genres in the user profile. Instead, pass top artist names directly to the LLM and let Claude infer associated genres.

**Rationale:**

- Claude has precise knowledge of genres associated with popular artists
- LLM inference is more nuanced than Spotify tags (which were very broad anyway)
- No added complexity — artists are already in the profile

**Impact on prompt engineering:** The enriched system prompt sent to Claude includes the list of top artists (names) rather than a genre list. Claude uses these artists as context to infer the musical profile.

**Phase 3 impact:** None — this logic lives in `core/prompts.py` and can be refined independently.

---

## ADR-008 — Replacing /recommendations with /search + filtering

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** Spotify's `/recommendations` endpoint is inaccessible in Development Mode since late 2024. Extended Quota Mode is reserved for organizations with 250k+ MAUs — out of reach for a personal project.

**Decision:** Replace `/recommendations` with a `/search`-based strategy:

1. Claude extracts the same criteria as before (genres, artists, mood, period)
2. Multiple targeted search queries are built from these criteria
3. Results are deduplicated and filtered (year, popularity)
4. A coherent playlist is returned

**Rationale:**

- `/search` is available in Development Mode
- The result is less "magic" than `/recommendations` but remains relevant
- The upstream LLM logic stays identical — only `api/spotify.py` changes
- Good angle for the blog article (CDC section 10)

**Trade-off:** Results are less personalized than with `/recommendations` (no audio feature seeds). Compensated by passing the user's top artists as additional context to Claude so it generates more targeted search queries.

**Phase 3 impact:** None — if Spotify reopens `/recommendations`, the fix is contained in `api/spotify.py`.

---

## ADR-009 — Partial Spotify save (playlist created without tracks)

**Date:** 2026-03-05  
**Status:** Accepted (external constraint)

**Context:** `POST /v1/playlists/{id}/tracks` consistently returns 403 for Spotify apps in Development mode, even with `playlist-modify-public` and `playlist-modify-private` scopes correctly configured and a whitelisted account. Tested via direct browser call (full backend bypass) — confirmed blocked on Spotify's side.

Since May 2025, Spotify no longer accepts Extended Quota requests from individuals (organizations only, 250k+ MAUs minimum).

**Decision:** Option A — Step 6 creates an empty playlist in the user's Spotify account and returns in the JSON response: a direct link to the playlist + the full track list with individual Spotify links. The frontend (Step 7) displays this list with an "Open in Spotify" link per track, allowing the user to manually add tracks of interest. Degraded but functional and honest UX.

**Workarounds explored and rejected:**

- `sp.playlist_add_items()` → 403
- `sp._post("playlists/{id}/tracks")` → 403
- Direct AJAX call from browser → 403 (confirms Spotify is blocking, not our code)
- Public vs private playlist → no difference

**Rationale:** The code is correct. The restriction is external and documented.

**Phase 3 impact:** If Spotify reopens the endpoint or the project moves under an organization entity, the fix is removing the try/except and reactivating `add_tracks_to_playlist()` in `routes.py`.

---

## ADR-010 — No /api prefix on routes

**Date:** 2026-03-05  
**Status:** Accepted

**Context:** During Step 7 frontend development, `app.js` was initially written with an `/api` prefix on all fetch calls (`/api/generate`, `/api/save`, `/api/sync-profile`). FastAPI routes were declared without this prefix, causing 404s.

**Decision:** No `/api` prefix anywhere — neither in `main.py` (`include_router` without prefix), nor in the JS fetch calls, nor in the route declarations.

**Rationale:**

- Phase 2 is a simple single-purpose app — an `/api` prefix adds no value
- Keeping all routes flat (`/generate`, `/save`, `/sync-profile`) is simpler and more readable
- Page routes (`/`, `/history`, `/login`) and API routes coexist cleanly without a prefix

**Trade-off:** If a public API layer is ever needed (e.g. for the Phase 3 React frontend consuming the same backend), adding a prefix at that point is a one-line change in `main.py` + a JS update.

**Phase 3 impact:** When replacing Jinja2 with React, add `prefix="/api"` to `app.include_router(router)` in `main.py` and update fetch calls accordingly.
