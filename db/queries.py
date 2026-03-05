# db/queries.py
# CRUD operations for DuckDB.
# All database reads and writes go through this module — never raw SQL in routes.

import json
from datetime import datetime, timezone

from db.database import get_connection
from db.models import UserProfile, Playlist, PlaylistCreate


# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------

def upsert_user_profile(profile: UserProfile) -> None:
    """
    Insert or update the user's musical profile in DuckDB.

    INSERT OR REPLACE handles both the first sync and subsequent re-syncs.
    JSON fields are serialized to strings (DuckDB stores them as JSON type).
    """
    conn = get_connection()

    conn.execute("""
        INSERT OR REPLACE INTO user_profile
            (user_id, synced_at, top_genres, top_artists, top_tracks, audio_features_avg)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [
        profile.user_id,
        profile.synced_at,
        json.dumps(profile.top_genres),
        json.dumps(profile.top_artists),
        json.dumps(profile.top_tracks),
        json.dumps(profile.audio_features_avg.model_dump()),
    ])

    conn.close()


def get_user_profile(user_id: str) -> UserProfile | None:
    """
    Retrieve the latest synced profile for a given user.
    Returns None if the user has never synced.
    """
    conn = get_connection()

    result = conn.execute("""
        SELECT user_id, synced_at, top_genres, top_artists, top_tracks, audio_features_avg
        FROM user_profile
        WHERE user_id = ?
    """, [user_id]).fetchone()

    conn.close()

    if not result:
        return None

    # DuckDB returns JSON columns as strings — parse them back to Python objects
    return UserProfile(
        user_id=result[0],
        synced_at=result[1],
        top_genres=json.loads(result[2]),
        top_artists=json.loads(result[3]),
        top_tracks=json.loads(result[4]),
        audio_features_avg=json.loads(result[5]),
    )


# ---------------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------------

def save_playlist(playlist: PlaylistCreate, user_id: str) -> Playlist:
    """
    Persist a generated playlist to the DuckDB history table.
    Generates a UUID as the playlist ID.
    Returns the full Playlist model including the generated ID and timestamp.
    """
    import uuid

    playlist_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)

    conn = get_connection()

    conn.execute("""
        INSERT INTO playlists
            (id, created_at, user_prompt, llm_params,
             spotify_playlist_id, spotify_url, title, track_count, tracks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        playlist_id,
        created_at,
        playlist.user_prompt,
        json.dumps(playlist.llm_params.model_dump()),
        playlist.spotify_playlist_id,
        playlist.spotify_url,
        playlist.title,
        playlist.track_count,
        json.dumps(playlist.tracks),
    ])

    conn.close()

    return Playlist(id=playlist_id, created_at=created_at, **playlist.model_dump())


def get_playlist_history(user_id: str) -> list[Playlist]:
    """
    Retrieve all playlists for a user, ordered by most recent first.

    Note: currently the playlists table has no user_id column — in Phase 2
    this is a single-user app, so all playlists belong to the logged-in user.
    A user_id column should be added if multi-user support is needed.
    """
    conn = get_connection()

    results = conn.execute("""
        SELECT id, created_at, user_prompt, llm_params,
               spotify_playlist_id, spotify_url, title, track_count, tracks
        FROM playlists
        ORDER BY created_at DESC
    """).fetchall()

    conn.close()

    playlists = []
    for row in results:
        from db.models import LLMCriteriaOutput
        playlists.append(Playlist(
            id=row[0],
            created_at=row[1],
            user_prompt=row[2],
            llm_params=LLMCriteriaOutput(**json.loads(row[3])),
            spotify_playlist_id=row[4],
            spotify_url=row[5],
            title=row[6],
            track_count=row[7],
            tracks=json.loads(row[8]) if row[8] else [],
        ))

    return playlists


def update_playlist_spotify_info(
    playlist_id: str,
    spotify_playlist_id: str,
    spotify_url: str,
) -> None:
    """
    Update an existing playlist record with its Spotify playlist ID and URL.
    Called after the playlist has been successfully created in Spotify.
    """
    conn = get_connection()
    conn.execute("""
        UPDATE playlists
        SET spotify_playlist_id = ?,
            spotify_url = ?
        WHERE id = ?
    """, [spotify_playlist_id, spotify_url, playlist_id])
    conn.close()


def delete_playlists(ids: list[str]) -> int:
    """
    Delete playlists by a list of UUIDs.
    Returns the number of rows deleted.
    Only deletes from DuckDB — does not touch the Spotify playlist.
    """
    if not ids:
        return 0

    conn = get_connection()

    # Build a parameterised IN clause: DELETE ... WHERE id IN (?, ?, ?)
    placeholders = ", ".join(["?"] * len(ids))
    conn.execute(
        f"DELETE FROM playlists WHERE id IN ({placeholders})",
        ids,
    )

    # DuckDB doesn't expose rowcount directly — we return len(ids) as a proxy
    conn.close()
    return len(ids)


def get_playlist_by_id(playlist_id: str) -> Playlist | None:
    """
    Retrieve a single playlist by its ID.
    Returns None if not found.
    """
    conn = get_connection()

    row = conn.execute("""
        SELECT id, created_at, user_prompt, llm_params,
               spotify_playlist_id, spotify_url, title, track_count, tracks
        FROM playlists
        WHERE id = ?
    """, [playlist_id]).fetchone()

    conn.close()

    if not row:
        return None

    from db.models import LLMCriteriaOutput
    return Playlist(
        id=row[0],
        created_at=row[1],
        user_prompt=row[2],
        llm_params=LLMCriteriaOutput(**json.loads(row[3])),
        spotify_playlist_id=row[4],
        spotify_url=row[5],
        title=row[6],
        track_count=row[7],
        tracks=json.loads(row[8]) if row[8] else [],
    )
