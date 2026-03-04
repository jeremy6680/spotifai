# core/prompts.py
# LLM prompt templates.
# All prompts live here so they can be versioned, tested, and improved independently.

# TODO: build_criteria_extraction_prompt(user_prompt, user_profile)
#       → returns the system + user messages for the first LLM call
#       → system prompt includes dynamic user profile context (top genres, audio features)

# TODO: build_title_generation_prompt(user_prompt, tracks)
#       → returns the messages for the second LLM call
#       → generates an evocative playlist title and short description
