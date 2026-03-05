# api/routes.py
# FastAPI router — all HTTP endpoints.
# This layer handles HTTP only: it reads requests, calls core/ or api/ modules,
# and returns responses. No business logic here.

from datetime import datetime

from fastapi import APIRouter, Request, Body
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from spotipy.exceptions import SpotifyException

from api.spotify import get_auth_manager, get_spotify_client, create_playlist, add_tracks_to_playlist
from core.profile import sync_user_profile
from core.generator import generate_playlist
from db.queries import update_playlist_spotify_info, get_playlist_history

router = APIRouter()

# ---------------------------------------------------------------------------
# Jinja2 templates setup
# ---------------------------------------------------------------------------

templates = Jinja2Templates(directory="templates")


def format_date(value: str) -> str:
    """
    Jinja2 filter: format an ISO datetime string to a readable French date.
    e.g. "2026-03-05T14:23:00" → "5 mars 2026"
    Registered below as a custom filter on the Jinja2 environment.
    """
    try:
        dt = datetime.fromisoformat(str(value))
        return dt.strftime("%-d %B %Y")  # e.g. "5 mars 2026"
    except (ValueError, TypeError):
        return str(value)


# Register the custom filter so {{ value | format_date }} works in templates
templates.env.filters["format_date"] = format_date


# ---------------------------------------------------------------------------
# Helper — extract current user info from session
# Returns a dict the templates can use, or None if not logged in.
# ---------------------------------------------------------------------------

def get_spotify_or_401(request: Request):
    """
    Attempt to build an authenticated Spotify client from the session token.

    Returns a tuple (sp, token_info) on success.
    Returns a JSONResponse(401) if:
    - No token in session (user not logged in)
    - Token refresh failed (token revoked or expired beyond repair)

    Callers should check: if isinstance(result, JSONResponse): return result
    """
    token_info = request.session.get("token_info")
    if not token_info:
        return JSONResponse(
            status_code=401,
            content={"error": "Not logged in", "action": "login"}
        )

    try:
        sp, refreshed_token = get_spotify_client(token_info)
        # Persist the (possibly refreshed) token back into the session
        request.session["token_info"] = refreshed_token
        return sp, refreshed_token
    except Exception as e:
        print(f"[routes] Spotify token refresh failed: {e}")
        # Token is irrecoverable — clear session and ask user to log in again
        request.session.clear()
        return JSONResponse(
            status_code=401,
            content={
                "error": "Spotify session expired. Please log in again.",
                "action": "login"
            }
        )


def get_current_user(request: Request) -> dict | None:
    """
    Build a simple user context object from the session.
    Passed to every TemplateResponse as 'current_user'.
    Returns None if the user is not authenticated.
    """
    token_info = request.session.get("token_info")
    if not token_info:
        return None

    return {
        "user_id":      request.session.get("user_id"),
        "display_name": request.session.get("display_name", ""),
        "avatar_url":   request.session.get("avatar_url", ""),
    }


# ---------------------------------------------------------------------------
# Page routes (Jinja2 templates)
# ---------------------------------------------------------------------------

@router.get("/")
async def index(request: Request):
    """
    Home page — playlist generator form.
    Passes authentication status and profile sync info to the template.
    """
    current_user = get_current_user(request)

    # Profile sync status — used by the profile bar in index.html
    profile_synced    = request.session.get("profile_synced", False)
    profile_synced_at = request.session.get("profile_synced_at", "")

    # Pre-fill the prompt textarea if redirected from history page
    # e.g. /  ?prompt=Post-rock+instrumental
    prefill_prompt = request.query_params.get("prompt", "")

    return templates.TemplateResponse("index.html", {
        "request":          request,   # required by Jinja2Templates
        "current_user":     current_user,
        "profile_synced":   profile_synced,
        "profile_synced_at": profile_synced_at,
        "prefill_prompt":   prefill_prompt,
    })


@router.get("/history")
async def history(request: Request):
    """
    Playlist history dashboard.
    Loads all playlists for the current user from DuckDB and passes them
    to history.html for rendering.
    """
    current_user = get_current_user(request)

    # Redirect to login if not authenticated
    if not current_user:
        return RedirectResponse(url="/login")

    user_id = current_user["user_id"]

    # Fetch playlists from DuckDB, most recent first
    try:
        playlists = get_playlist_history(user_id)
    except Exception as e:
        print(f"[routes] /history DuckDB error: {e}")
        playlists = []

    return templates.TemplateResponse("history.html", {
        "request":      request,
        "current_user": current_user,
        "playlists":    playlists,
    })


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@router.get("/login")
async def login(request: Request):
    """
    Step 1 of OAuth flow: redirect the user to Spotify's authorization page.
    Spotify will ask the user to log in and grant our requested permissions.
    After approval, Spotify redirects back to /callback with a 'code' param.
    """
    auth_manager = get_auth_manager()
    auth_url = auth_manager.get_authorize_url()
    return RedirectResponse(auth_url)


@router.get("/callback")
async def callback(request: Request, code: str = None, error: str = None):
    """
    Step 2 of OAuth flow: Spotify redirects here after user authorization.

    If the user approved: 'code' is a one-time authorization code.
    We exchange it for an access token + refresh token via Spotipy.
    The token dict is stored in the server-side session.

    If the user denied: 'error' contains the reason (e.g. 'access_denied').
    """
    # User denied access on Spotify's side
    if error:
        return JSONResponse(
            status_code=400,
            content={"error": f"Spotify authorization failed: {error}"}
        )

    if not code:
        return JSONResponse(
            status_code=400,
            content={"error": "No authorization code received from Spotify"}
        )

    # Exchange the authorization code for a token dict
    auth_manager = get_auth_manager()
    token_info = auth_manager.get_access_token(code, as_dict=True, check_cache=False)

    # Store the token in the session (server-side, signed by SECRET_KEY)
    request.session["token_info"] = token_info

    # Fetch basic user info to confirm login worked and store user_id
    sp, token_info = get_spotify_client(token_info)
    request.session["token_info"] = token_info  # persist refreshed token
    user = sp.current_user()
    request.session["user_id"]      = user["id"]
    request.session["display_name"] = user.get("display_name", user["id"])

    # Store avatar URL if available (used in the header user badge)
    images = user.get("images", [])
    if images:
        request.session["avatar_url"] = images[0].get("url", "")

    # Redirect to the home page now that login is complete
    return RedirectResponse(url="/")


# ---------------------------------------------------------------------------
# Auth status (useful for frontend to check if user is logged in)
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_me(request: Request):
    """
    Returns the logged-in user's basic info from the session.
    Returns 401 if not logged in.
    """
    token_info = request.session.get("token_info")

    if not token_info:
        return JSONResponse(
            status_code=401,
            content={"error": "Not logged in"}
        )

    return JSONResponse(content={
        "user_id":      request.session.get("user_id"),
        "display_name": request.session.get("display_name"),
        "avatar_url":   request.session.get("avatar_url", ""),
    })


# ---------------------------------------------------------------------------
# Profile sync
# ---------------------------------------------------------------------------

@router.post("/sync-profile")
async def sync_profile(request: Request):
    """
    Sync the user's musical profile from Spotify to DuckDB.
    Fetches top tracks, top artists, recently played, and computes audio features.
    Triggered manually by the user via the "Sync mon profil" button.

    Called by app.js via POST /sync-profile.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "Not logged in", "action": "login"})

    spotify_result = get_spotify_or_401(request)
    if isinstance(spotify_result, JSONResponse):
        return spotify_result
    sp, _ = spotify_result

    profile = sync_user_profile(user_id, sp)

    # Store sync status in session so the profile bar updates on next page load
    request.session["profile_synced"]    = True
    request.session["profile_synced_at"] = profile.synced_at.strftime("%-d %B %Y")

    return JSONResponse(content={
        "message":            "Profile synced successfully",
        "user_id":            profile.user_id,
        "synced_at":          profile.synced_at.isoformat(),
        "top_genres":         profile.top_genres[:10],
        "top_artists_count":  len(profile.top_artists),
        "top_tracks_count":   len(profile.top_tracks),
        "audio_features_avg": profile.audio_features_avg.model_dump(),
    })


# ---------------------------------------------------------------------------
# Playlist generation
# ---------------------------------------------------------------------------

@router.post("/generate")
async def generate(request: Request, body: dict = Body(...)):
    """
    Generate a playlist from a natural language prompt.

    Expects a JSON body: { "prompt": "Post-rock instrumental, influence japonaise" }

    Pipeline:
    1. Extract Spotify parameters from prompt via Claude
    2. Fetch tracks from Spotify via /search (ADR-008 — /recommendations unavailable)
    3. Generate title + description via Claude
    4. Save to DuckDB history
    5. Return tracks + metadata
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "Not logged in", "action": "login"})

    spotify_result = get_spotify_or_401(request)
    if isinstance(spotify_result, JSONResponse):
        return spotify_result
    sp, _ = spotify_result

    prompt = body.get("prompt", "").strip()
    if not prompt:
        return JSONResponse(
            status_code=400,
            content={"error": "prompt is required"}
        )

    try:
        result = generate_playlist(user_id, prompt, sp)
        return JSONResponse(content=result)

    except ValueError as e:
        return JSONResponse(
            status_code=422,
            content={"error": str(e)}
        )
    except Exception as e:
        print(f"[routes] /generate error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "An unexpected error occurred. Please try again."}
        )


# ---------------------------------------------------------------------------
# Save playlist to Spotify
# ---------------------------------------------------------------------------

@router.post("/save")
async def save_to_spotify(request: Request, body: dict = Body(...)):
    """
    Create a named playlist in the user's Spotify account.

    ADR-009 — Option A: POST /playlists/{id}/tracks returns 403 in Development
    mode. We create an empty playlist and return the URL. The user adds tracks
    manually from the individual track links in the frontend.

    Expects a JSON body:
    {
        "title":       "Playlist title",
        "description": "Playlist description",
        "track_count": 30,
        "llm_params":  { ... },
        "user_prompt": "original user prompt"
    }

    Note: 'tracks' array is no longer sent — no URIs needed since we cannot
    add tracks to the playlist anyway (ADR-009). track_count is stored in
    DuckDB for display in the history dashboard.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return JSONResponse(status_code=401, content={"error": "Not logged in", "action": "login"})

    spotify_result = get_spotify_or_401(request)
    if isinstance(spotify_result, JSONResponse):
        return spotify_result
    sp, _ = spotify_result

    title       = body.get("title", "My SpotifAI Playlist")
    description = body.get("description", "Generated by SpotifAI")
    track_count = body.get("track_count", 0)
    llm_params  = body.get("llm_params", {})
    user_prompt = body.get("user_prompt", "")

    try:
        # Step 1 — Create empty playlist in Spotify
        spotify_playlist = create_playlist(
            sp=sp,
            user_id=user_id,
            title=title,
            description=description,
            public=True,
        )

        spotify_playlist_id = spotify_playlist["id"]
        spotify_url         = spotify_playlist["external_urls"]["spotify"]

        # Step 2 — Attempt to add tracks (will gracefully fail in Dev mode — ADR-009)
        # track_uris not available in this payload by design, so we skip the attempt.
        # The try/except is kept as a reminder for when the restriction is lifted.
        tracks_added = False

        # Step 3 — Update DuckDB record with Spotify info
        # playlist_id here refers to the DuckDB UUID stored in llm_params or passed separately.
        # If generate_playlist() returned a playlist_id, the frontend should pass it back.
        # For now we update by title (simple for single-user Phase 2).
        playlist_id = body.get("playlist_id")
        if playlist_id:
            update_playlist_spotify_info(
                playlist_id=playlist_id,
                spotify_playlist_id=spotify_playlist_id,
                spotify_url=spotify_url,
            )

        return JSONResponse(content={
            "message":           "Playlist created in Spotify",
            "spotify_playlist_id": spotify_playlist_id,
            "spotify_url":       spotify_url,
            "tracks_added":      tracks_added,
            "track_count":       track_count,
        })

    except Exception as e:
        import traceback
        print(f"[routes] /save error type: {type(e).__name__}")
        print(f"[routes] /save error detail: {e}")
        print(f"[routes] /save traceback:\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "type": type(e).__name__}
        )


@router.get("/logout")
async def logout(request: Request):
    """
    Clear the session (logs the user out of SpotifAI).
    Note: this does NOT revoke the Spotify token — the user stays
    logged into Spotify itself. It only clears our local session.
    """
    request.session.clear()
    return RedirectResponse(url="/")


# ---------------------------------------------------------------------------
# Health check + dev utilities
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check():
    """Simple endpoint to verify the server is running."""
    return {"status": "ok", "app": "SpotifAI"}


# NOTE: /debug/token endpoint removed before public release.
# It exposed the raw Spotify access_token in plain text.
# To re-add for local debugging only: check git history.