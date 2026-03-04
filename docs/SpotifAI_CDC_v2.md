# SpotifAI — Cahier des charges v1.0

> Générateur de playlists personnalisées · *powered by Spotify API + LLM*

| | |
|---|---|
| **Projet** | SpotifAI — Playlist Generator |
| **Auteur** | Jeremy Marchandeau |
| **Version** | 1.0 — Version Intermédiaire (avec roadmap Phase 3) |
| **Date** | Mars 2026 |
| **Stack cible** | Python · FastAPI · Spotipy · Claude API · DuckDB · HTML/JS |

---

## 1. Contexte & Objectifs

### 1.1 Problème résolu

L'algorithme de Spotify enferme progressivement l'utilisateur dans une "bulle de filtrage" : plus on écoute certains artistes ou genres, plus les recommandations convergent vers les mêmes propositions. Le résultat est une expérience musicale qui tourne en rond, peu propice à la découverte de nouveaux groupes ou de styles inattendus.

Par ailleurs, les recommandations natives sont peu contrôlables : il est impossible de combiner librement un genre de niche, une zone géographique culturelle, une période temporelle et un mood en une seule requête.

**SpotifAI brise cette boucle** en proposant une interface en langage naturel, pilotée par l'utilisateur, enrichie — mais non enfermée — par son profil musical réel.

### 1.2 Objectifs du projet

- Permettre la génération de playlists via des critères en langage naturel (ex : "Post-rock instrumental, influence japonaise, depuis 2010")
- Personnaliser les recommandations en s'appuyant sur l'historique Spotify réel de l'utilisateur
- Sauvegarder automatiquement les playlists dans le compte Spotify de l'utilisateur
- Conserver un historique local des playlists générées
- Poser des fondations solides permettant une évolution vers un système multi-agents et un pipeline data complet

### 1.3 Positionnement portfolio

Ce projet démontre la maîtrise combinée de : OAuth2, appels API externes, orchestration LLM avec contexte dynamique, persistance DuckDB, et architecture évolutive. Il constitue un projet de reconversion idéal pour un profil web developer → analytics/AI engineering.

---

## 2. Vision & Roadmap

Le projet est conçu dès le départ pour évoluer en trois phases. Chaque phase est fonctionnelle de façon autonome et constitue une étape naturelle vers la suivante.

| 🟢 Phase 1 — MVP (non incluse) | 🟡 Phase 2 — Intermédiaire (ce document) | 🔴 Phase 3 — Avancée (roadmap) |
|---|---|---|
| Client Credentials Flow | Auth OAuth complète | Pipeline dbt medallion |
| Critères → paramètres Spotify | Profil musical personnel | Système multi-agents CrewAI |
| Flask · résultats en mémoire | FastAPI · DuckDB | Sync Airflow event-driven |
| Pas de login utilisateur | Création playlist dans Spotify | Frontend React |
| | Historique des playlists | Open-sourceable |

---

## 3. Fonctionnalités — Version Intermédiaire

### 3.1 Authentification Spotify

- Authorization Code Flow via `spotipy.SpotifyOAuth`
- Scopes requis : `user-top-read`, `user-read-recently-played`, `playlist-modify-public`, `playlist-modify-private`
- Token refresh automatique
- Session utilisateur stockée côté serveur (DuckDB)

### 3.2 Synchronisation du profil musical

- Récupération des top tracks (`short_term`, `medium_term`, `long_term`)
- Récupération des top artists et de leurs genres associés
- Récupération des `recently_played` (100 derniers morceaux — note : l'API Spotify plafonne à 50 par appel, deux appels paginés sont donc nécessaires)
- Calcul des audio features moyennes (`energy`, `valence`, `tempo`, `danceability`, `acousticness`)
- Stockage structuré dans DuckDB — table `user_profile`
- Rafraîchissement manuel déclenché depuis l'UI (bouton "Sync mon profil")

### 3.3 Génération de playlist

- Saisie libre en langage naturel dans un champ texte
- Appel à Claude API avec un system prompt enrichi du profil musical
- Extraction structurée (JSON) des paramètres : `genres`, `seed_artists`, `year_min`, `year_max`, `energy_range`, `valence_range`, `market`
- Appel à Spotify `/recommendations` avec les paramètres extraits
- Affichage des résultats : pochettes, artistes, durée, preview audio si disponible
- Titre et description de playlist générés par le LLM

### 3.4 Sauvegarde dans Spotify

- Création de la playlist dans le compte Spotify de l'utilisateur
- Ajout des tracks via `/playlists/{id}/tracks`
- Lien direct vers la playlist dans Spotify

### 3.5 Historique local

- Toutes les playlists générées sont enregistrées dans DuckDB — table `playlists`
- Affichage de l'historique dans un dashboard minimaliste
- Relance possible d'une génération depuis un prompt historique

---

## 4. Architecture Technique

### 4.1 Structure du projet

```
spotifai/
├── main.py                    # Point d'entrée FastAPI
├── config.py                  # Variables d'environnement (.env)
├── requirements.txt
├── .env.example
│
├── api/
│   ├── spotify.py             # Wrapper spotipy (auth, top data, recommendations)
│   ├── llm.py                 # Wrapper Claude API (extraction critères, génération titre)
│   └── routes.py              # Endpoints FastAPI
│
├── db/
│   ├── database.py            # Connexion DuckDB, création tables
│   ├── models.py              # Schémas Pydantic
│   └── queries.py             # CRUD DuckDB
│
├── core/
│   ├── profile.py             # Logique sync profil musical
│   ├── generator.py           # Orchestration génération playlist
│   └── prompts.py             # Templates de prompts LLM
│
├── static/
│   ├── css/main.css
│   └── js/app.js
│
└── templates/
    ├── index.html             # Page principale
    ├── history.html           # Historique playlists
    └── partials/              # Composants HTML réutilisables
```

### 4.2 Flux de données principal

```
[UI] Saisie des critères en texte libre
     ↓
[FastAPI /generate] Récupération du profil depuis DuckDB
     ↓
[LLM — Claude API] Interprétation des critères + contexte profil → JSON paramètres
     ↓
[Spotify /recommendations] Appel avec seed_artists + seed_genres + audio_features
     ↓
[LLM — Claude API] Génération du titre et de la description
     ↓
[Spotify /playlists] Création et peuplement de la playlist
     ↓
[DuckDB] Enregistrement de la playlist dans l'historique
     ↓
[UI] Affichage des résultats + lien Spotify
```

### 4.3 Schéma DuckDB

**Table `user_profile` :**
```sql
user_id            TEXT,
synced_at          TIMESTAMP,
top_genres         JSON,
top_artists        JSON,
top_tracks         JSON,
audio_features_avg JSON
```

**Table `playlists` :**
```sql
id                  TEXT,
created_at          TIMESTAMP,
user_prompt         TEXT,
llm_params          JSON,
spotify_playlist_id TEXT,
spotify_url         TEXT,
title               TEXT,
track_count         INTEGER
```

---

## 5. Prompt Engineering

### 5.1 System prompt (extraction de critères)

Le system prompt est construit dynamiquement à partir du profil DuckDB de l'utilisateur. Il inclut :

- Les top genres (pondérés par fréquence d'écoute)
- Les top artists avec leurs caractéristiques
- Les audio features moyennes (`energy`, `valence`, `tempo`...)
- Une instruction stricte de retour JSON uniquement

Structure cible du JSON retourné :

```json
{
  "seed_genres": ["post-rock", "shoegaze"],
  "seed_artists": ["spotify:artist:id1"],
  "year_min": 2010,
  "year_max": 2024,
  "target_energy": 0.6,
  "target_valence": 0.4,
  "target_tempo": 110,
  "market": "FR",
  "limit": 30
}
```

### 5.2 Second appel LLM (titre + description)

Après récupération des tracks, un second appel génère un titre évocateur et une description courte pour la playlist, en tenant compte des critères initiaux et des artistes effectivement retenus.

### 5.3 Gestion des erreurs LLM

- Retry automatique si le JSON retourné est invalide (max 2 tentatives)
- Fallback sur des paramètres Spotify par défaut si l'extraction échoue
- Log des prompts et réponses pour debug et amélioration itérative

---

## 6. Stack & Dépendances

| Librairie | Rôle |
|---|---|
| Python 3.11+ | |
| FastAPI | Backend web — routes, gestion sessions |
| Uvicorn | Serveur ASGI |
| Spotipy | Wrapper Python pour l'API Spotify |
| Anthropic SDK | Appels à l'API Claude |
| DuckDB | Base de données locale légère |
| Pydantic | Validation des schémas de données |
| python-dotenv | Gestion des variables d'environnement |
| httpx | Client HTTP async (fallback si besoin) |
| Jinja2 | Templates HTML (inclus avec FastAPI) |

### 6.1 Variables d'environnement (`.env`)

```env
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://localhost:8000/callback
ANTHROPIC_API_KEY=...
SECRET_KEY=...           # Pour les sessions FastAPI
DUCKDB_PATH=./data/spotifai.duckdb
```

---

## 7. Estimation & Planning

| Tâche | Estimation |
|---|---|
| Setup Spotify Developer App + OAuth flow | 2-3h |
| Structure FastAPI + config + DuckDB init | 2h |
| Module sync profil musical | 3h |
| Module prompt engineering + appel LLM | 3-4h |
| Module recommandations Spotify | 2h |
| Module création playlist dans Spotify | 1-2h |
| UI HTML/CSS/JS (form + résultats + historique) | 4-5h |
| Tests, debug, polish | 2-3h |
| Documentation README | 1h |
| **TOTAL estimé** | **~20-23h (2-3 semaines à temps partiel)** |

---

## 8. Roadmap Phase 3 — Version Avancée

Les choix d'architecture de la Phase 2 sont pensés pour faciliter la migration vers la Phase 3. Voici les évolutions prévues et comment elles s'articulent avec l'existant.

### 8.1 Pipeline dbt + architecture medallion

DuckDB est déjà en place en Phase 2. La Phase 3 y ajoute une couche dbt pour structurer les données en trois couches :

- **Bronze** : raw data Spotify (listening history, saves, follows) — inchangé depuis Phase 2
- **Silver** : tracks nettoyées, audio features normalisées, taxonomie des genres
- **Gold** : `user_music_profile` (features moyennes par période), `genre_evolution_over_time`, `mood_patterns` (par heure, jour, saison)

Migration douce : les tables DuckDB de Phase 2 deviennent les sources bronze sans modification.

### 8.2 Système multi-agents CrewAI

Le module `generator.py` de Phase 2 est refactoré en 3 agents spécialisés :

- **Agent 1 — Music Profiler** : analyse les données gold DuckDB, produit un "music DNA" structuré
- **Agent 2 — Criteria Interpreter** : combine le music DNA et les critères utilisateur, retourne les paramètres Spotify optimaux
- **Agent 3 — Playlist Curator** : query Spotify, score et filtre les tracks, rédige la description

La logique LLM existante dans `prompts.py` et `llm.py` constitue la base des instructions de chaque agent.

### 8.3 Synchronisation automatique — Airflow

Remplacement du bouton "Sync" manuel par un pipeline Airflow déclenché par événement Spotify plutôt que par schedule fixe :

- **Triggers** : ajout d'un morceau, album, artiste ou playlist en favori (polling Spotify `/me/following` et `/me/tracks/contains` via un sensor Airflow)
- À chaque trigger : resync du profil musical + exécution des modèles dbt (bronze → silver → gold)
- **Note technique** : l'API Spotify ne propose pas de webhooks natifs, le sensor Airflow interroge donc l'API toutes les 15-30 minutes (polling léger)

### 8.4 Frontend React

Remplacement des templates Jinja2/HTML par une SPA React :

- Composants : `PlaylistForm`, `PlaylistCard`, `HistoryDashboard`, `ProfileOverview`
- L'API FastAPI reste inchangée — seul le frontend change
- Bonne occasion de pratiquer React dans un contexte projet réel

### 8.5 Open-source readiness

- Ajout d'un fichier `CONTRIBUTING.md`
- Dockerisation (`docker-compose` avec FastAPI + DuckDB)
- GitHub Actions pour les tests et le lint
- Documentation complète des endpoints FastAPI (auto-générée par FastAPI/OpenAPI)

---

## 9. Points d'Attention

### 9.1 Limites de l'API Spotify

- L'endpoint `/recommendations` accepte **max 5** `seed_genres` + `seed_artists` combinés
- Certains marchés géographiques ne sont pas disponibles pour toutes les tracks
- Les audio features ne sont plus accessibles pour les nouvelles tracks depuis 2024 via l'API publique — prévoir un fallback sur les critères genre uniquement
- Rate limiting : max 30 requêtes/minute sur certains endpoints

### 9.2 Sécurité

- Jamais de credentials dans le code — uniquement via `.env`
- Le token Spotify doit être stocké chiffré si multi-utilisateurs
- Pour une version solo, le stockage en session côté serveur est suffisant
- Ne pas commiter le fichier `.duckdb` — l'ajouter au `.gitignore`

### 9.3 Coûts API

- **Claude API** : ~$0.003 par génération de playlist (Sonnet) — négligeable pour un usage perso
- **Spotify API** : gratuite pour usage non-commercial

---

## 10. Idées d'Articles Web2Data

| Article | Angle |
|---|---|
| **Article 1 (Phase 2)** | "Comment j'ai utilisé mon historique Spotify comme contexte LLM" — RAG-like sans vrai RAG, personnalisation par injection de profil |
| **Article 2 (Phase 2)** | "Spotify OAuth + FastAPI en 2h" — tutorial technique court, très SEO-friendly |
| **Article 3 (Phase 3)** | "Spotify + dbt : construire un data warehouse de ses goûts musicaux" — medallion architecture appliquée à la musique |
| **Article 4 (Phase 3)** | "Multi-agents CrewAI pour la recommandation musicale" — comparaison avec l'approche single-LLM de Phase 2 |
| **Série complète** | "SpotifAI : de l'idée au projet open-source data/AI" — 4 articles, idéal pour positionner le blog Web2Data |

---

*SpotifAI — Cahier des charges v1.0 · Jeremy Marchandeau · web2data.jeremymarchandeau.com*
# spotifai
