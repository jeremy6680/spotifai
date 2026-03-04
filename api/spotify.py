# api/spotify.py
# Spotify API wrapper.
# Handles OAuth2 Authorization Code Flow via Spotipy,
# and all data-fetching functions used by core/ modules.

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import settings

# ---------------------------------------------------------------------------
# OAuth scopes — define exactly what permissions we request from the user.
# Principle of least privilege: only request what we actually need.
# ---------------------------------------------------------------------------

SPOTIFY_SCOPES = " ".join([
    "user-top-read",             # Read top artists and tracks
    "user-read-recently-played", # Read recently played tracks
    "playlist-modify-public",    # Create and edit public playlists
    "playlist-modify-private",   # Create and edit private playlists
])


def get_auth_manager(cache_path: str = ".cache") -> SpotifyOAuth:
    """
    Build and return a SpotifyOAuth manager.

    SpotifyOAuth handles the full Authorization Code Flow:
    - Generates the authorization URL (redirects user to Spotify login)
    - Exchanges the authorization code for an access token
    - Automatically refreshes the token when it expires

    cache_path: where Spotipy stores the token locally.
    We use ".cache" (gitignored) for dev. In a multi-user setup,
    this would be per-user (e.g. ".cache-{user_id}").
    """
    return SpotifyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=settings.spotify_redirect_uri,
        scope=SPOTIFY_SCOPES,
        cache_path=cache_path,
        show_dialog=True,  # Always show Spotify login dialog (useful during dev)
    )


def get_spotify_client(token_info: dict) -> spotipy.Spotify:
    """
    Build and return an authenticated Spotipy client from a token dict.

    token_info is the dict returned by SpotifyOAuth after the callback.
    It contains: access_token, refresh_token, expires_at, scope, etc.
    We store this dict in the FastAPI session after login.
    """
    auth_manager = get_auth_manager()

    # If the token has expired, SpotifyOAuth refreshes it automatically
    if auth_manager.is_token_expired(token_info):
        token_info = auth_manager.refresh_access_token(token_info["refresh_token"])

    return spotipy.Spotify(auth=token_info["access_token"])


# ---------------------------------------------------------------------------
# User profile data fetching
# ---------------------------------------------------------------------------

def get_user_top_tracks(sp: spotipy.Spotify) -> list[dict]:
    """
    Fetch the user's top tracks across three time ranges.

    Spotify defines three time ranges:
    - short_term:  last ~4 weeks
    - medium_term: last ~6 months
    - long_term:   all time

    We fetch all three and deduplicate by track ID, keeping the earliest
    time range as a proxy for "most relevant recently".
    Returns a flat list of simplified track dicts.
    """
    seen_ids = set()
    tracks = []

    for term in ["short_term", "medium_term", "long_term"]:
        results = sp.current_user_top_tracks(limit=50, time_range=term)
        for item in results.get("items", []):
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                tracks.append({
                    "id": item["id"],
                    "name": item["name"],
                    "artists": [a["name"] for a in item["artists"]],
                    "uri": item["uri"],
                    "time_range": term,
                })

    return tracks


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def get_recommendations(sp: spotipy.Spotify, criteria: dict) -> list[dict]:
    """
    Call Spotify /recommendations with extracted LLM criteria.

    Spotify constraints (CDC section 9.1):
    - seed_genres + seed_artists combined: max 5 items total
    - Some markets may not have all tracks available
    - audio features (target_energy, target_valence, etc.) are hints, not filters

    Returns a list of simplified track dicts.
    """
    # Build seeds — Spotify expects separate seed_genres and seed_artists params
    seed_genres = criteria.get("seed_genres", [])
    seed_artists = criteria.get("seed_artists", [])

    # Safety check: enforce 5-seed limit (already enforced in llm.py but defensive here)
    total = len(seed_genres) + len(seed_artists)
    if total > 5:
        allowed_artists = max(0, 5 - len(seed_genres))
        seed_artists = seed_artists[:allowed_artists]

    # Build kwargs for Spotipy — only include non-null audio feature targets
    kwargs = {
        "seed_genres": seed_genres if seed_genres else None,
        "seed_artists": seed_artists if seed_artists else None,
        "limit": criteria.get("limit", 30),
        "country": criteria.get("market", "FR"),
    }

    # Map optional audio feature targets
    feature_map = {
        "target_energy": "target_energy",
        "target_valence": "target_valence",
        "target_tempo": "target_tempo",
        "target_danceability": "target_danceability",
        "target_acousticness": "target_acousticness",
    }
    for criteria_key, spotify_key in feature_map.items():
        value = criteria.get(criteria_key)
        if value is not None:
            kwargs[spotify_key] = value

    # Remove None values — Spotipy doesn't accept None kwargs
    kwargs = {k: v for k, v in kwargs.items() if v is not None}

    print(f"[spotify] Calling /recommendations with: {kwargs}")
    results = sp.recommendations(**kwargs)

    tracks = []
    for item in results.get("tracks", []):
        # Filter by year range if specified
        release_date = item["album"].get("release_date", "")
        year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

        year_min = criteria.get("year_min")
        year_max = criteria.get("year_max")

        if year_min and year and year < year_min:
            continue
        if year_max and year and year > year_max:
            continue

        tracks.append({
            "id": item["id"],
            "uri": item["uri"],
            "name": item["name"],
            "artists": [a["name"] for a in item["artists"]],
            "album": item["album"]["name"],
            "release_date": release_date,
            "duration_ms": item["duration_ms"],
            "preview_url": item.get("preview_url"),
            "external_url": item["external_urls"].get("spotify"),
            "image_url": item["album"]["images"][0]["url"] if item["album"]["images"] else None,
        })

    print(f"[spotify] Got {len(tracks)} tracks after year filtering")
    return tracks


# ---------------------------------------------------------------------------
# Search-based track discovery (replaces /recommendations — see ADR-008)
# ---------------------------------------------------------------------------

def search_tracks(
    sp: spotipy.Spotify,
    queries: list[str],
    criteria: dict,
    target_count: int = 30,
) -> list[dict]:
    """
    Search for tracks using multiple query strings and return a deduplicated,
    filtered list.

    Strategy:
    - Run each query against Spotify /search (10 results per query)
    - Deduplicate by track ID
    - Filter by year range if specified in criteria
    - Sort by popularity (descending) and return top target_count tracks
    """
    seen_ids = set()
    tracks = []

    year_min = criteria.get("year_min")
    year_max = criteria.get("year_max")
    market = criteria.get("market", "FR")

    for query in queries:
        print(f"[spotify] Searching: '{query}'")
        try:
            results = sp.search(
                q=query,
                type="track",
                limit=10,
                market=market,
            )
        except Exception as e:
            print(f"[spotify] Search failed for '{query}': {e}")
            continue

        for item in results.get("tracks", {}).get("items", []):
            if not item or item["id"] in seen_ids:
                continue

            # Filter by year range if specified
            release_date = item["album"].get("release_date", "")
            year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

            if year_min and year and year < year_min:
                continue
            if year_max and year and year > year_max:
                continue

            seen_ids.add(item["id"])
            tracks.append({
                "id": item["id"],
                "uri": item["uri"],
                "name": item["name"],
                "artists": [a["name"] for a in item["artists"]],
                "album": item["album"]["name"],
                "release_date": release_date,
                "duration_ms": item["duration_ms"],
                "popularity": item.get("popularity", 0),
                "preview_url": item.get("preview_url"),
                "external_url": item["external_urls"].get("spotify"),
                "image_url": item["album"]["images"][0]["url"] if item["album"]["images"] else None,
            })

    # Sort by popularity and cap at target_count
    tracks.sort(key=lambda t: t["popularity"], reverse=True)
    tracks = tracks[:target_count]

    print(f"[spotify] Got {len(tracks)} tracks after dedup and filtering")
    return tracks


# ---------------------------------------------------------------------------
# Playlist management
# ---------------------------------------------------------------------------

def create_playlist(
    sp: spotipy.Spotify,
    user_id: str,
    title: str,
    description: str,
    public: bool = False
) -> dict:
    """
    Create an empty playlist in the user's Spotify account.
    Returns the Spotify playlist object (id, url, etc.).
    """
    playlist = sp.user_playlist_create(
        user=user_id,
        name=title,
        public=public,
        description=description,
    )
    print(f"[spotify] Created playlist: {playlist['id']} — {title}")
    return playlist


def add_tracks_to_playlist(
    sp: spotipy.Spotify,
    playlist_id: str,
    track_uris: list[str]
) -> None:
    """
    Add tracks to an existing Spotify playlist.
    Spotify accepts max 100 tracks per call — we chunk if needed.
    """
    # Chunk into batches of 100 (Spotify API limit)
    chunk_size = 100
    for i in range(0, len(track_uris), chunk_size):
        chunk = track_uris[i:i + chunk_size]
        sp.playlist_add_items(playlist_id, chunk)
        print(f"[spotify] Added {len(chunk)} tracks to playlist {playlist_id}")


def get_user_top_artists(sp: spotipy.Spotify) -> tuple[list[dict], list[str]]:
    """
    Fetch the user's top artists and extract their associated genres.

    Returns a tuple:
    - artists: list of simplified artist dicts
    - genres: deduplicated flat list of all genres across all top artists
    """
    seen_ids = set()
    artists = []
    genre_counts: dict[str, int] = {}

    for term in ["short_term", "medium_term", "long_term"]:
        results = sp.current_user_top_artists(limit=50, time_range=term)
        for item in results.get("items", []):
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                artists.append({
                    "id": item["id"],
                    "name": item["name"],
                    "genres": item.get("genres", []),
                    "uri": item["uri"],
                    "time_range": term,
                })
                # Count genre occurrences to weight by popularity
                for genre in item.get("genres", []):
                    genre_counts[genre] = genre_counts.get(genre, 0) + 1

    # Sort genres by frequency (most listened-to genres first)
    genres = sorted(genre_counts, key=genre_counts.get, reverse=True)

    return artists, genres


def get_recently_played(sp: spotipy.Spotify) -> list[dict]:
    """
    Fetch the user's recently played tracks (up to 100).

    The Spotify API caps this endpoint at 50 tracks per call.
    We make two paginated calls using the 'before' cursor to get up to 100.
    Note from CDC section 9.1: audio features are deprecated for new tracks
    since 2024, so we don't fetch them here.
    """
    tracks = []
    seen_ids = set()

    # First call — most recent 50
    results = sp.current_user_recently_played(limit=50)
    items = results.get("items", [])

    for item in items:
        track = item["track"]
        if track["id"] not in seen_ids:
            seen_ids.add(track["id"])
            tracks.append({
                "id": track["id"],
                "name": track["name"],
                "artists": [a["name"] for a in track["artists"]],
                "uri": track["uri"],
                "played_at": item["played_at"],
            })

    # Second call — next 50 using the cursor from the first response
    cursors = results.get("cursors")
    if cursors and cursors.get("before"):
        results2 = sp.current_user_recently_played(
            limit=50,
            before=cursors["before"]
        )
        for item in results2.get("items", []):
            track = item["track"]
            if track["id"] not in seen_ids:
                seen_ids.add(track["id"])
                tracks.append({
                    "id": track["id"],
                    "name": track["name"],
                    "artists": [a["name"] for a in track["artists"]],
                    "uri": track["uri"],
                    "played_at": item["played_at"],
                })

    return tracks
