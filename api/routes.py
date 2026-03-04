# api/routes.py
# FastAPI router — all HTTP endpoints.
# This layer handles HTTP only: it reads requests, calls core/ or api/ modules,
# and returns responses. No business logic here.

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse

from api.spotify import get_auth_manager, get_spotify_client

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
    sp = get_spotify_client(token_info)
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
