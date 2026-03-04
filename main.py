# main.py
# FastAPI application entry point.
# Registers routes, mounts static files, configures sessions, and starts the server.

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config import settings

# ---------------------------------------------------------------------------
# App initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SpotifAI",
    description="AI-powered Spotify playlist generator",
    version="0.1.0",
)

# Session middleware — needed to store the Spotify OAuth token server-side
# SECRET_KEY signs the session cookie to prevent tampering
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# Serve static files (CSS, JS) at /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------------------------------------------------------------
# Routes — will be imported from api/routes.py once implemented
# ---------------------------------------------------------------------------

# TODO: from api.routes import router
# TODO: app.include_router(router)


# ---------------------------------------------------------------------------
# Health check endpoint (useful for testing the server is up)
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Simple endpoint to verify the server is running."""
    return {"status": "ok", "app": "SpotifAI"}


# ---------------------------------------------------------------------------
# Dev server entry point
# Run with: uvicorn main:app --reload --port 8000
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
