# core/profile.py
# Business logic for syncing and building the user's musical profile.
# Coordinates between api/spotify.py (data fetching) and db/queries.py (persistence).

# TODO: implement sync_user_profile(user_id, spotify_client)
#       → fetches top tracks, artists, recently played
#       → computes average audio features
#       → saves everything to DuckDB via db/queries.py

# TODO: implement compute_audio_features_avg(tracks)
#       → takes a list of tracks with audio features
#       → returns dict with mean energy, valence, tempo, danceability, acousticness
