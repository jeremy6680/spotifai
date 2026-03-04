# core/generator.py
# Orchestrates the full playlist generation pipeline.
# This is the heart of the application — it wires together LLM, Spotify, and DuckDB.

# Pipeline:
# 1. Load user profile from DuckDB
# 2. Call Claude API to extract Spotify parameters from user text input
# 3. Call Spotify /recommendations with extracted parameters
# 4. Call Claude API again to generate title + description
# 5. (Optional) Create playlist in user's Spotify account
# 6. Save playlist to DuckDB history
# 7. Return result to the route handler

# TODO: implement generate_playlist(user_id, user_prompt, spotify_client)
