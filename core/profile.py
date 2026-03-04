# core/profile.py
# Business logic for syncing and building the user's musical profile.
# Coordinates between api/spotify.py (data fetching) and db/queries.py (persistence).

from datetime import datetime, timezone

import spotipy

from api.spotify import get_user_top_tracks, get_user_top_artists, get_recently_played
from db.models import UserProfile, AudioFeaturesAvg
from db.queries import upsert_user_profile


def compute_audio_features_avg(tracks: list[dict]) -> AudioFeaturesAvg:
    """
    Compute average audio features across a list of tracks.

    Note (CDC section 9.1): Spotify deprecated audio features for new tracks
    in 2024. Many tracks will return None. We skip those and average only
    the tracks that have valid feature data.

    Returns an AudioFeaturesAvg with default values (0.5) if no data available.
    """
    feature_keys = ["energy", "valence", "danceability", "acousticness", "tempo"]
    totals = {k: 0.0 for k in feature_keys}
    counts = {k: 0 for k in feature_keys}

    for track in tracks:
        features = track.get("audio_features")
        if not features:
            continue
        for key in feature_keys:
            value = features.get(key)
            if value is not None:
                totals[key] += value
                counts[key] += 1

    # Compute averages — fall back to neutral defaults if no data
    averages = {}
    defaults = {"energy": 0.5, "valence": 0.5, "danceability": 0.5,
                "acousticness": 0.5, "tempo": 120.0}
    for key in feature_keys:
        if counts[key] > 0:
            averages[key] = round(totals[key] / counts[key], 3)
        else:
            averages[key] = defaults[key]

    return AudioFeaturesAvg(**averages)


def sync_user_profile(user_id: str, sp: spotipy.Spotify) -> UserProfile:
    """
    Fetch the user's musical data from Spotify and persist it to DuckDB.

    Steps:
    1. Fetch top tracks, top artists, recently played
    2. Compute average audio features (where available)
    3. Build a UserProfile model
    4. Save to DuckDB via upsert (insert or update if already exists)
    5. Return the profile

    This function is called by the POST /sync route.
    """
    print(f"[profile] Starting sync for user: {user_id}")

    # Step 1 — Fetch data from Spotify
    top_tracks = get_user_top_tracks(sp)
    top_artists, top_genres = get_user_top_artists(sp)
    recently_played = get_recently_played(sp)

    print(f"[profile] Fetched {len(top_tracks)} top tracks, "
          f"{len(top_artists)} top artists, "
          f"{len(recently_played)} recently played")

    # Step 2 — Compute audio features average
    # We use top_tracks as the base since recently_played may have more gaps
    audio_features_avg = compute_audio_features_avg(top_tracks)

    # Step 3 — Build the profile model
    profile = UserProfile(
        user_id=user_id,
        synced_at=datetime.now(timezone.utc),
        top_genres=top_genres,
        top_artists=top_artists,
        top_tracks=top_tracks,
        audio_features_avg=audio_features_avg,
    )

    # Step 4 — Persist to DuckDB
    upsert_user_profile(profile)
    print(f"[profile] Profile saved to DuckDB for user: {user_id}")

    return profile
