# db/models.py
# Pydantic models — define the shape of data exchanged between layers.
#
# These are runtime data contracts, not database table definitions.
# Pydantic validates data automatically and raises clear errors if something
# doesn't match the expected shape (wrong type, missing field, etc.).
#
# Convention:
#   - Models ending in "Base" define shared fields
#   - Models ending in "Create" are used when inserting new records
#   - Models without suffix are the full representation (including DB-generated fields)

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# User Profile
# Represents the musical profile synced from Spotify and stored in DuckDB.
# ---------------------------------------------------------------------------

class AudioFeaturesAvg(BaseModel):
    """
    Average audio features computed across the user's top/recent tracks.
    All values are Spotify's normalized float range [0.0, 1.0] except tempo.
    """
    energy: float = Field(0.5, ge=0.0, le=1.0)
    valence: float = Field(0.5, ge=0.0, le=1.0)       # 0 = sad, 1 = happy
    danceability: float = Field(0.5, ge=0.0, le=1.0)
    acousticness: float = Field(0.5, ge=0.0, le=1.0)
    tempo: float = Field(120.0, ge=0.0)                # BPM, not normalized


class UserProfile(BaseModel):
    """
    Full user musical profile as stored in DuckDB.
    top_genres, top_artists, top_tracks are raw Spotify API data.
    """
    user_id: str
    synced_at: datetime
    top_genres: list[str] = []
    top_artists: list[dict] = []
    top_tracks: list[dict] = []
    audio_features_avg: AudioFeaturesAvg = Field(default_factory=AudioFeaturesAvg)


# ---------------------------------------------------------------------------
# LLM Criteria Output
# Represents the structured JSON returned by Claude after parsing the user prompt.
# This is validated before being sent to Spotify /recommendations.
# ---------------------------------------------------------------------------

class LLMCriteriaOutput(BaseModel):
    """
    Structured parameters extracted by Claude from the user's natural language prompt.
    All fields are optional — Claude may not always extract every parameter.

    Spotify /recommendations constraints (documented in CDC section 9.1):
    - seed_genres + seed_artists combined must not exceed 5 items total
    - target_* values must be in [0.0, 1.0] except target_tempo
    """
    seed_genres: list[str] = Field(default_factory=list)
    seed_artists: list[str] = Field(default_factory=list)  # Spotify artist URIs
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    target_energy: Optional[float] = Field(None, ge=0.0, le=1.0)
    target_valence: Optional[float] = Field(None, ge=0.0, le=1.0)
    target_tempo: Optional[float] = Field(None, ge=0.0)
    target_danceability: Optional[float] = Field(None, ge=0.0, le=1.0)
    target_acousticness: Optional[float] = Field(None, ge=0.0, le=1.0)
    market: str = "FR"
    limit: int = Field(30, ge=1, le=100)


# ---------------------------------------------------------------------------
# Playlist
# Represents a generated playlist stored in DuckDB history.
# ---------------------------------------------------------------------------

class PlaylistCreate(BaseModel):
    """
    Data required to save a new playlist to DuckDB.
    spotify_playlist_id and spotify_url are optional — the user may not
    have saved the playlist to their Spotify account yet.
    tracks stores the full track list as returned by the Spotify search —
    used to display previously generated tracks on the home page.
    """
    user_prompt: str
    llm_params: LLMCriteriaOutput
    title: str
    track_count: int
    tracks: list[dict] = Field(default_factory=list)
    spotify_playlist_id: Optional[str] = None
    spotify_url: Optional[str] = None


class Playlist(PlaylistCreate):
    """
    Full playlist record as stored in DuckDB (includes DB-generated fields).
    """
    id: str                  # UUID generated at save time
    created_at: datetime
