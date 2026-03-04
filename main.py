# main.py
# FastAPI application entry point.
# Registers routes, mounts static files, configures sessions,
# and initializes the database on startup.

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config import settings
from api.routes import router
from db.database import init_db

# ---------------------------------------------------------------------------
# App initialization
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SpotifAI",
    description="AI-powered Spotify playlist generator",
    version="0.1.0",
)

# Session middleware — stores the Spotify OAuth token server-side.
# SECRET_KEY signs the session cookie to prevent client-side tampering.
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

# Serve static files (CSS, JS) at /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register all routes from api/routes.py
app.include_router(router)


# ---------------------------------------------------------------------------
# Startup event — runs once when the server starts
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def on_startup():
    """
    Initialize the DuckDB database on server startup.
    Creates tables if they don't exist yet — safe to run every time.
    """
    init_db()


# ---------------------------------------------------------------------------
# Dev server entry point
# Run with: uvicorn main:app --reload --port 8000
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
