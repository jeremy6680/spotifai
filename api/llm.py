# api/llm.py
# Claude API wrapper.
# Handles prompt construction, API calls, JSON extraction from responses,
# and retry logic for malformed outputs.

# TODO: implement extract_criteria() — parse user text input into Spotify params JSON
# TODO: implement generate_playlist_title() — generate title + description from tracks
# TODO: implement retry logic for invalid JSON responses (max 2 retries)
