# db/database.py
# DuckDB connection management and schema initialization.
# Called once at FastAPI startup to ensure all tables exist.

import duckdb
from config import settings


def get_connection() -> duckdb.DuckDBPyConnection:
    """
    Open and return a DuckDB connection to the configured database file.
    DuckDB is file-based (like SQLite) — the file is created automatically
    if it doesn't exist yet.
    """
    return duckdb.connect(settings.duckdb_path)


def init_db() -> None:
    """
    Create all required tables if they don't already exist.
    Safe to call on every startup — IF NOT EXISTS prevents data loss.
    """
    conn = get_connection()

    # Store the user's musical profile synced from Spotify.
    # audio_features_avg, top_genres, top_artists, top_tracks are stored
    # as JSON strings (DuckDB supports JSON natively).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            user_id            TEXT PRIMARY KEY,
            synced_at          TIMESTAMP,
            top_genres         JSON,
            top_artists        JSON,
            top_tracks         JSON,
            audio_features_avg JSON
        )
    """)

    # Store every generated playlist for the history dashboard.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            id                  TEXT PRIMARY KEY,
            created_at          TIMESTAMP,
            user_prompt         TEXT,
            llm_params          JSON,
            spotify_playlist_id TEXT,
            spotify_url         TEXT,
            title               TEXT,
            track_count         INTEGER
        )
    """)

    conn.close()
