# SpotifAI — Architecture Decisions

Last updated: 2026-03-04

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

## ADR-006 — Redirect URI : 127.0.0.1 plutôt que localhost

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** Spotify bloque désormais `http://localhost:8000/callback` dans son dashboard (avertissement de sécurité non contournable).

**Decision:** Utiliser `http://127.0.0.1:8000/callback` comme redirect URI.

**Rationale:** `127.0.0.1` est l'adresse IP de loopback — c'est strictement équivalent à `localhost` en pratique. Spotify l'accepte sans blocage.

**Phase 3 impact:** En production, remplacer par une vraie URL `https://`.

---

## ADR-007 — Genres inférés par le LLM plutôt qu'extraits de Spotify

**Date:** 2026-03-04  
**Status:** Accepted

**Context:** L'endpoint Spotify `current_user_top_artists` retourne des tableaux `genres` vides pour la majorité des artistes (dégradation progressive de l'API publique Spotify, constatée en mars 2026). Les audio features sont également dépréciées depuis 2024.

**Decision:** Ne pas s'appuyer sur les genres Spotify dans le profil utilisateur. À la place, passer les noms des top artistes directement au LLM et laisser Claude inférer les genres associés.

**Rationale:**
- Claude connaît précisément les genres associés aux artistes populaires
- L'inférence LLM est plus nuancée que les tags Spotify (qui étaient de toute façon très larges)
- Pas de complexité supplémentaire — les artistes sont déjà dans le profil

**Impact sur le prompt engineering:** Le system prompt enrichi envoyé à Claude inclura la liste des top artistes (noms) plutôt qu'une liste de genres. Claude utilisera ces artistes comme contexte pour inférer le profil musical.

**Phase 3 impact:** Aucun — cette logique vit dans `core/prompts.py` et peut être affinée indépendamment.

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
