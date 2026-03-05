# api/routes.py
# FastAPI router — all HTTP endpoints.
# This layer handles HTTP only: it reads requests, calls core/ or api/ modules,
# and returns responses. No business logic here.

from fastapi import APIRouter, Request, Body
from fastapi.responses import RedirectResponse, JSONResponse
from api.spotify import get_auth_manager, get_spotify_client, create_playlist, add_tracks_to_playlist
from core.profile import sync_user_profile
from core.generator import generate_playlist
from db.queries import update_playlist_spotify_info

router = APIRouter()


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
    request.session["user_id"] = user["id"]
    request.session["display_name"] = user.get("display_name", user["id"])

    # TODO: redirect to index.html once the frontend exists
    return JSONResponse(content={
        "message": "Login successful",
        "user_id": user["id"],
        "display_name": user.get("display_name"),
    })


# ---------------------------------------------------------------------------
# Auth status (useful for frontend to check if user is logged in)
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_current_user(request: Request):
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
        "user_id": request.session.get("user_id"),
        "display_name": request.session.get("display_name"),
    })


# ---------------------------------------------------------------------------
# Profile sync
# ---------------------------------------------------------------------------

@router.post("/sync")
async def sync_profile(request: Request):
    """
    Sync the user's musical profile from Spotify to DuckDB.
    Fetches top tracks, top artists, recently played, and computes audio features.
    Triggered manually by the user via the "Sync mon profil" button.
    """
    token_info = request.session.get("token_info")
    user_id = request.session.get("user_id")

    if not token_info or not user_id:
        return JSONResponse(
            status_code=401,
            content={"error": "Not logged in"}
        )

    sp, token_info = get_spotify_client(token_info)
    request.session["token_info"] = token_info  # persist refreshed token
    profile = sync_user_profile(user_id, sp)

    return JSONResponse(content={
        "message": "Profile synced successfully",
        "user_id": profile.user_id,
        "synced_at": profile.synced_at.isoformat(),
        "top_genres": profile.top_genres[:10],  # Return top 10 for display
        "top_artists_count": len(profile.top_artists),
        "top_tracks_count": len(profile.top_tracks),
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
    2. Fetch recommendations from Spotify
    3. Generate title + description via Claude
    4. Save to DuckDB history
    5. Return tracks + metadata
    """
    token_info = request.session.get("token_info")
    user_id = request.session.get("user_id")

    if not token_info or not user_id:
        return JSONResponse(
            status_code=401,
            content={"error": "Not logged in"}
        )

    prompt = body.get("prompt", "").strip()
    if not prompt:
        return JSONResponse(
            status_code=400,
            content={"error": "prompt is required"}
        )

    try:
        sp, token_info = get_spotify_client(token_info)
        request.session["token_info"] = token_info  # persist refreshed token
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
    Create the generated playlist in the user's Spotify account.

    Expects a JSON body:
    {
        "playlist_id": "<DuckDB playlist UUID>",
        "title": "Playlist title",
        "description": "Playlist description",
        "tracks": [
            {
                "uri": "spotify:track:xxx",
                "name": "Track name",
                "artists": ["Artist 1"],
                "external_url": "https://open.spotify.com/track/xxx",
                "image_url": "https://..."
            },
            ...
        ]
    }

    Steps:
    1. Create an empty playlist in Spotify
    2. Attempt to add tracks (may fail due to Spotify API restrictions — see ADR-009)
    3. Update the DuckDB record with the Spotify playlist ID and URL
    4. Return the Spotify playlist URL + track list for Option A fallback display
    """
    token_info = request.session.get("token_info")
    user_id = request.session.get("user_id")

    if not token_info or not user_id:
        return JSONResponse(
            status_code=401,
            content={"error": "Not logged in"}
        )

    playlist_id = body.get("playlist_id")
    title = body.get("title", "My SpotifAI Playlist")
    description = body.get("description", "Generated by SpotifAI")
    tracks = body.get("tracks", [])  # Full track objects, not just URIs

    if not playlist_id:
        return JSONResponse(
            status_code=400,
            content={"error": "playlist_id is required"}
        )

    if not tracks:
        return JSONResponse(
            status_code=400,
            content={"error": "tracks is required and cannot be empty"}
        )

    track_uris = [t["uri"] for t in tracks if t.get("uri")]

    try:
        sp, token_info = get_spotify_client(token_info)
        request.session["token_info"] = token_info  # persist refreshed token

        # Step 1 — Create empty playlist in Spotify
        spotify_playlist = create_playlist(
            sp=sp,
            user_id=user_id,
            title=title,
            description=description,
            public=True,  # Must be public — Spotify Dev mode restricts private playlist modification
        )

        spotify_url = spotify_playlist["external_urls"]["spotify"]
        tracks_added = False

        # Step 2 — Attempt to add tracks
        # NOTE (ADR-009): POST /playlists/{id}/tracks returns 403 for Development-mode apps.
        # Extended Quota (required to lift this restriction) is no longer available to
        # individuals since May 2025. We degrade gracefully: playlist is created,
        # tracks are returned to the frontend for Option A display (manual add via links).
        try:
            add_tracks_to_playlist(
                sp=sp,
                playlist_id=spotify_playlist["id"],
                track_uris=track_uris,
            )
            tracks_added = True
            print(f"[routes] /save tracks added successfully")
        except Exception as tracks_error:
            print(f"[routes] /save tracks error (expected in Dev mode — ADR-009): {tracks_error}")

        # Step 3 — Update DuckDB record with Spotify info
        update_playlist_spotify_info(
            playlist_id=playlist_id,
            spotify_playlist_id=spotify_playlist["id"],
            spotify_url=spotify_url,
        )

        return JSONResponse(content={
            "message": "Playlist saved to Spotify" if tracks_added else "Playlist created in Spotify",
            "spotify_playlist_id": spotify_playlist["id"],
            "spotify_url": spotify_url,
            "tracks_added": tracks_added,
            # Always return tracks so the frontend can display them
            # (essential for Option A: user opens each track in Spotify manually)
            "tracks": tracks,
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
    return JSONResponse(content={"message": "Logged out successfully"})


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@router.get("/health")
async def health_check():
    """Simple endpoint to verify the server is running."""
    return {"status": "ok", "app": "SpotifAI"}


@router.get("/debug/token")
async def debug_token(request: Request):
    """
    DEV ONLY — inspect the current session token.
    Shows scopes, expiry, and user_id to diagnose 403 issues.
    Remove before shipping to production.
    """
    token_info = request.session.get("token_info")
    user_id = request.session.get("user_id")

    if not token_info:
        return JSONResponse(status_code=401, content={"error": "No token in session"})

    return JSONResponse(content={
        "user_id": user_id,
        "scope": token_info.get("scope"),
        "expires_at": token_info.get("expires_at"),
        "has_access_token": bool(token_info.get("access_token")),
        "has_refresh_token": bool(token_info.get("refresh_token")),
        # DEV ONLY — remove before production
        "access_token": token_info.get("access_token"),
    })
