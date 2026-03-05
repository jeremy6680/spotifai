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

### Step 6 — Save to Spotify (branch: `feature/save-playlist`) ✅
- [x] Implement `api/spotify.py` — `create_playlist()`, `add_tracks_to_playlist()`
- [x] Implement `db/queries.py` — `update_playlist_spotify_info()`
- [x] Implement `POST /save` route
- [x] Fix token refresh not persisted to session (intermittent 403)
- [x] Fix `POST /users/{id}/playlists` → migrated to `POST /me/playlists` (ADR-009)
- [x] Graceful degradation : playlist créée, tracks retournées pour Option A
- [x] Test : playlist apparaît dans le compte Spotify de l'utilisateur

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

## ⚠️ Architecture Change

**`/recommendations` endpoint inaccessible** — Spotify a restreint cet endpoint aux apps en Extended Quota Mode (organisations avec 250k MAUs minimum) depuis fin 2024. SpotifAI utilise à la place une stratégie de recherche via `/search` + filtrage. Voir ADR-008.

---

## ⚠️ Spotify API Restriction (ADR-009)

**`POST /playlists/{id}/tracks` bloqué en Development mode** — Spotify retourne 403 sur l'ajout de tracks à une playlist pour les apps non approuvées Extended Quota. L'Extended Quota n'est plus disponible aux individus depuis mai 2025 (organisations uniquement).

Stratégie retenue : **Option A** — la playlist est créée vide dans Spotify, et le frontend affiche la liste des tracks avec un lien "Ouvrir dans Spotify" par morceau. L'utilisateur peut les ajouter manuellement. Le code tente toujours l'ajout automatique et se dégrade gracieusement si ça échoue — le jour où Spotify lève la restriction, ça fonctionnera sans modification.

---

## 🐛 Known Issues

- **Spotify genres vides** : `current_user_top_artists` retourne `genres: []` pour tous les artistes (dégradation API Spotify, mars 2026). Contournement : genres inférés par le LLM à partir des noms d'artistes. Voir ADR-007.
- **Audio features indisponibles** : Spotify a déprécié cet endpoint pour les nouvelles tracks en 2024. `audio_features_avg` retourne les valeurs par défaut (0.5). Le profil s'appuiera donc uniquement sur les artistes et tracks pour le contexte LLM.
