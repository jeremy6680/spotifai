# api/routes.py
# FastAPI router — defines all HTTP endpoints.
# This is the "glue" layer: it receives HTTP requests, calls the appropriate
# core/ modules, and returns HTTP responses.

from fastapi import APIRouter

router = APIRouter()

# TODO: GET  /           → serve index.html
# TODO: GET  /login      → redirect to Spotify OAuth
# TODO: GET  /callback   → handle OAuth callback, store token
# TODO: POST /sync       → sync user profile from Spotify to DuckDB
# TODO: POST /generate   → generate playlist (LLM + Spotify recommendations)
# TODO: POST /save       → save generated playlist to user's Spotify account
# TODO: GET  /history    → serve history.html with past playlists
