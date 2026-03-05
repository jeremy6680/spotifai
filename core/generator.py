# core/generator.py
# Orchestrates the full playlist generation pipeline.
# This is the heart of the application — it wires together LLM, Spotify, and DuckDB.
#
# Pipeline:
# 1. Load user profile from DuckDB
# 2. Build prompt and call Claude to extract Spotify parameters
# 3. Call Spotify /recommendations with extracted parameters
# 4. Call Claude to generate playlist title + description
# 5. Save playlist to DuckDB history
# 6. Return result to the route handler

import spotipy

from api.spotify import search_tracks, create_playlist
from api.llm import extract_criteria, generate_search_queries, generate_playlist_title
from core.prompts import build_criteria_extraction_prompt, build_search_queries_prompt, build_title_generation_prompt
from db.queries import get_user_profile, save_playlist, update_playlist_spotify_info
from db.models import PlaylistCreate


def generate_playlist(
    user_id: str,
    user_prompt: str,
    sp: spotipy.Spotify,
) -> dict:
    """
    Run the full playlist generation pipeline for a given user prompt.

    Returns a dict with everything the frontend needs to display results:
    - title, description
    - tracks list (name, artists, album, preview_url, image_url, etc.)
    - llm_params (the Spotify parameters Claude extracted)
    - playlist_id (DuckDB record ID)
    """
    print(f"[generator] Starting generation for user {user_id}: '{user_prompt}'")

    # -------------------------------------------------------------------------
    # Step 1 — Load user profile from DuckDB
    # Profile may be None if the user hasn't synced yet — prompts handle this case
    # -------------------------------------------------------------------------
    profile = get_user_profile(user_id)
    if profile:
        print(f"[generator] Profile loaded — {len(profile.top_artists)} artists, "
              f"{len(profile.top_tracks)} tracks")
    else:
        print("[generator] No profile found — generating without personalization")

    # -------------------------------------------------------------------------
    # Step 2 — Extract Spotify parameters from user prompt via Claude
    # -------------------------------------------------------------------------
    system_msg, user_msg = build_criteria_extraction_prompt(user_prompt, profile)
    criteria = extract_criteria(system_msg, user_msg)
    print(f"[generator] Criteria extracted: {criteria.model_dump()}")

    # -------------------------------------------------------------------------
    # Step 3 — Generate search queries via Claude, then search Spotify
    # Using /search instead of /recommendations (see ADR-008)
    # -------------------------------------------------------------------------
    search_system, search_user = build_search_queries_prompt(criteria.model_dump(), profile)
    queries = generate_search_queries(search_system, search_user)
    print(f"[generator] Search queries: {queries}")

    tracks = search_tracks(sp, queries, criteria.model_dump(), target_count=criteria.limit)
    print(f"[generator] Got {len(tracks)} tracks from Spotify")

    if not tracks:
        raise ValueError(
            "Spotify returned no tracks for these criteria. "
            "Try different genres or broader parameters."
        )

    # -------------------------------------------------------------------------
    # Step 4 — Generate playlist title and description via Claude
    # -------------------------------------------------------------------------
    title_system, title_user = build_title_generation_prompt(user_prompt, tracks)
    title, description = generate_playlist_title(title_system, title_user)
    print(f"[generator] Title: '{title}' — Description: '{description}'")

    # -------------------------------------------------------------------------
    # Step 5 — Save to DuckDB history (including full track list)
    # -------------------------------------------------------------------------
    playlist_record = save_playlist(
        PlaylistCreate(
            user_prompt=user_prompt,
            llm_params=criteria,
            title=title,
            track_count=len(tracks),
            tracks=tracks,  # persist full track list for history display
        ),
        user_id=user_id,
    )
    print(f"[generator] Saved to DuckDB — playlist ID: {playlist_record.id}")

    # -------------------------------------------------------------------------
    # Step 6 — Auto-save to Spotify (replaces manual save button flow)
    # Creates an empty playlist in the user's account immediately.
    # ADR-009: adding tracks returns 403 in Development mode — skipped.
    # -------------------------------------------------------------------------
    spotify_url = None
    spotify_playlist_id = None

    try:
        spotify_playlist = create_playlist(
            sp=sp,
            user_id=user_id,
            title=title,
            description=description,
            public=True,
        )
        spotify_playlist_id = spotify_playlist["id"]
        spotify_url = spotify_playlist["external_urls"]["spotify"]

        # Update DuckDB record with Spotify link
        update_playlist_spotify_info(
            playlist_id=playlist_record.id,
            spotify_playlist_id=spotify_playlist_id,
            spotify_url=spotify_url,
        )
        print(f"[generator] Auto-saved to Spotify: {spotify_url}")

    except Exception as e:
        # Non-fatal — playlist is still saved in DuckDB, just not in Spotify
        print(f"[generator] Auto-save to Spotify failed (non-fatal): {e}")

    # -------------------------------------------------------------------------
    # Step 7 — Return result
    # -------------------------------------------------------------------------
    return {
        "playlist_id":        playlist_record.id,
        "title":              title,
        "description":        description,
        "track_count":        len(tracks),
        "tracks":             tracks,
        "llm_params":         criteria.model_dump(),
        "spotify_url":        spotify_url,          # None if auto-save failed
        "spotify_playlist_id": spotify_playlist_id,
    }
