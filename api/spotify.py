# api/spotify.py
# Spotify API wrapper.
# Handles OAuth2 Authorization Code Flow via Spotipy,
# and will contain all data-fetching functions in later steps.

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
