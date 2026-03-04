# core/prompts.py
# LLM prompt templates.
# All prompts live here so they can be versioned, tested, and improved independently.
# Prompts are built dynamically from user profile data stored in DuckDB.

from db.models import UserProfile


def build_criteria_extraction_prompt(
    user_prompt: str,
    profile: UserProfile | None
) -> tuple[str, str]:
    """
    Build the system and user messages for the first LLM call.
    Claude will extract structured Spotify parameters from the user's free text input.

    Returns a tuple: (system_message, user_message)

    The system prompt is enriched with the user's musical profile when available,
    so Claude can personalize recommendations and fill in gaps in the user's request.
    """

    # ---------------------------------------------------------------------------
    # Profile context block — injected into the system prompt when available.
    # This is the "RAG-like" personalization described in the CDC.
    # ---------------------------------------------------------------------------

    if profile:
        # Extract top artist names (max 20 for prompt brevity)
        top_artist_names = [a["name"] for a in profile.top_artists[:20]]

        # Extract top track names with their first artist (max 20)
        top_track_names = [
            f"{t['name']} — {t['artists'][0]}" if t.get('artists') else t['name']
            for t in profile.top_tracks[:20]
        ]

        profile_context = f"""
## User's Musical Profile

The user's top artists (most listened to first):
{", ".join(top_artist_names) if top_artist_names else "Not available"}

The user's top tracks (most listened to first):
{", ".join(top_track_names) if top_track_names else "Not available"}

Use this profile to:
- Infer the user's preferred genres and musical universe
- Fill in missing parameters when the user's request is vague
- Suggest seed_artists from their top artists when relevant
- Calibrate energy/valence/tempo to match their usual listening habits
"""
    else:
        profile_context = "\n## User's Musical Profile\nNo profile available — use only the explicit criteria from the request.\n"

    # ---------------------------------------------------------------------------
    # System prompt
    # ---------------------------------------------------------------------------

    system_message = f"""You are a music expert and Spotify playlist curator.
Your job is to interpret a user's natural language playlist request and extract structured parameters for the Spotify Recommendations API.

{profile_context}

## Your task

Analyze the user's request and return a JSON object with the following fields:

```json
{{
  "seed_genres": [],        // list of Spotify genre strings (e.g. "post-rock", "shoegaze")
  "seed_artists": [],       // list of Spotify artist URIs (e.g. "spotify:artist:xxxx") — only use URIs you are certain about
  "year_min": null,         // integer or null
  "year_max": null,         // integer or null
  "target_energy": null,    // float 0.0-1.0 or null (0=calm, 1=intense)
  "target_valence": null,   // float 0.0-1.0 or null (0=sad/dark, 1=happy/euphoric)
  "target_tempo": null,     // float in BPM or null
  "target_danceability": null, // float 0.0-1.0 or null
  "target_acousticness": null, // float 0.0-1.0 or null
  "market": "FR",           // ISO 3166-1 alpha-2 country code
  "limit": 30               // number of tracks, between 1 and 100
}}
```

## Critical constraints

1. `seed_genres` + `seed_artists` combined must not exceed 5 items total (Spotify API hard limit)
2. Prioritize `seed_genres` over `seed_artists` unless the user explicitly names artists
3. Only include `seed_artists` URIs you are 100% certain about — wrong URIs will break the API call
4. If unsure about an artist URI, omit it and compensate with more genres
5. Return ONLY the JSON object — no explanation, no markdown, no preamble

## Genre vocabulary

Use Spotify's genre taxonomy. Common examples:
acoustic, afrobeat, alt-rock, ambient, black-metal, blues, bossanova, classical,
death-metal, deep-house, drum-and-bass, electronic, emo, folk, funk, garage,
hardcore, hardstyle, heavy-metal, hip-hop, house, indie, indie-pop, jazz,
k-pop, latin, metal, new-wave, opera, piano, pop, post-rock, punk, r-n-b,
reggae, rock, sad, shoegaze, singer-songwriter, soul, synthpop, techno, trance,
trip-hop, world-music"""

    # ---------------------------------------------------------------------------
    # User message
    # ---------------------------------------------------------------------------

    user_message = f"Generate a playlist: {user_prompt}"

    return system_message, user_message


def build_search_queries_prompt(
    criteria: dict,
    profile: "UserProfile | None"
) -> tuple[str, str]:
    """
    Build messages for an intermediate LLM call that converts extracted criteria
    into concrete Spotify search queries.

    Why a separate call? The /search endpoint needs specific query strings
    (e.g. 'genre:post-rock year:2010-2024'), not abstract parameters.
    Claude is better at building these than a hardcoded template.

    Returns a tuple: (system_message, user_message)
    """
    # Include top artist names for context so Claude can suggest similar artists
    top_artist_names = []
    if profile:
        top_artist_names = [a["name"] for a in profile.top_artists[:15]]

    artist_context = ""
    if top_artist_names:
        artist_context = f"""
## User's top artists (for context)
{', '.join(top_artist_names)}
You can suggest artists similar to these in your search queries.
"""

    system_message = f"""You are a Spotify search expert.
Your job is to convert playlist criteria into effective Spotify search queries.
{artist_context}
Return ONLY a JSON array of 4 to 6 search query strings.
Each query will be sent directly to the Spotify search API (track search).

Effective query formats:
- "genre:post-rock year:2010-2024"
- "artist:Mogwai genre:post-rock"
- "genre:shoegaze genre:ambient"
- "post-rock instrumental japan"

Rules:
- Vary the queries to maximize track diversity
- Mix genre-based and artist-based queries
- Keep each query under 100 characters
- Return ONLY the JSON array, no explanation, no markdown

Example output:
["genre:post-rock year:2010-2024", "genre:math-rock instrumental", "artist:Toe genre:post-rock"]`"""

    user_message = f"""Criteria: {criteria}

Generate search queries to find matching tracks."""

    return system_message, user_message


def build_title_generation_prompt(
    user_prompt: str,
    tracks: list[dict]
) -> tuple[str, str]:
    """
    Build the messages for the second LLM call.
    Claude generates an evocative title and short description for the playlist,
    based on the original user request and the actual tracks selected.

    Returns a tuple: (system_message, user_message)
    """

    # Build a readable track list for context (max 10 tracks)
    track_list = "\n".join([
        f"- {t.get('name', 'Unknown')} — {', '.join(t.get('artists', ['Unknown']))}"
        for t in tracks[:10]
    ])

    system_message = """You are a creative music curator.
Your job is to generate an evocative playlist title and a short description.

Return ONLY a JSON object with this exact structure:
{
  "title": "...",       // short, evocative title (max 50 characters)
  "description": "..."  // one sentence description (max 120 characters)
}

No explanation, no markdown, no preamble — just the JSON."""

    user_message = f"""Original request: "{user_prompt}"

Tracks selected:
{track_list}

Generate a title and description for this playlist."""

    return system_message, user_message
