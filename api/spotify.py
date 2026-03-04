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
