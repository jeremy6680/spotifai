# SpotifAI — Next Steps

Last updated: 2026-03-04

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

---

## 🔜 Up Next (prioritized)

### Step 1 — Spotify OAuth (branch: `feature/spotify-auth`)
- [ ] Create Spotify Developer App at developer.spotify.com
- [ ] Add credentials to `.env`
- [ ] Implement `api/spotify.py` — SpotifyOAuth flow
- [ ] Implement `GET /login` route → redirect to Spotify
- [ ] Implement `GET /callback` route → handle token, store in session
- [ ] Test: full login flow in browser

### Step 2 — DuckDB setup (branch: `feature/db-setup`)
- [ ] Implement `db/database.py` — connection + `init_db()`
- [ ] Implement Pydantic models in `db/models.py`
- [ ] Call `init_db()` on FastAPI startup event
- [ ] Test: tables created on first run

### Step 3 — User profile sync (branch: `feature/profile-sync`)
- [ ] Implement `api/spotify.py` — `get_user_top_tracks()`, `get_user_top_artists()`, `get_recently_played()`
- [ ] Implement `core/profile.py` — `sync_user_profile()`, `compute_audio_features_avg()`
- [ ] Implement `db/queries.py` — `upsert_user_profile()`, `get_user_profile()`
- [ ] Implement `POST /sync` route
- [ ] Test: profile stored in DuckDB after sync

### Step 4 — LLM integration (branch: `feature/llm-integration`)
- [ ] Implement `core/prompts.py` — `build_criteria_extraction_prompt()`
- [ ] Implement `api/llm.py` — `extract_criteria()` with retry logic
- [ ] Unit test: valid JSON returned for various user prompts

### Step 5 — Playlist generation (branch: `feature/playlist-generation`)
- [ ] Implement `api/spotify.py` — `get_recommendations()`
- [ ] Implement `core/generator.py` — `generate_playlist()`
- [ ] Implement `core/prompts.py` — `build_title_generation_prompt()`
- [ ] Implement `api/llm.py` — `generate_playlist_title()`
- [ ] Implement `POST /generate` route
- [ ] Test: full generation pipeline end-to-end

### Step 6 — Save to Spotify (branch: `feature/save-playlist`)
- [ ] Implement `api/spotify.py` — `create_playlist()`, `add_tracks_to_playlist()`
- [ ] Implement `db/queries.py` — `save_playlist()`
- [ ] Implement `POST /save` route
- [ ] Test: playlist appears in user's Spotify account

### Step 7 — Frontend (branch: `feature/frontend`)
- [ ] Create `templates/index.html` — prompt form + results display
- [ ] Create `templates/history.html` — playlist history
- [ ] Create `static/css/main.css`
- [ ] Create `static/js/app.js`
- [ ] Wire up all routes to templates

### Step 8 — Polish & docs (branch: `feature/polish`)
- [ ] Error handling throughout (invalid tokens, API failures, etc.)
- [ ] Write `README.md`
- [ ] Final testing

---

## 🐛 Known Issues

*None yet.*
