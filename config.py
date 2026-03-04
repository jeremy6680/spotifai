# config.py
# Loads and validates all environment variables using pydantic-settings.
# Every other module imports settings from here — never from os.environ directly.

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings loaded from the .env file.
    pydantic-settings automatically reads the .env file and validates types.
    """

    # Spotify OAuth credentials
    spotify_client_id: str = Field(..., env="SPOTIFY_CLIENT_ID")
    spotify_client_secret: str = Field(..., env="SPOTIFY_CLIENT_SECRET")
    spotify_redirect_uri: str = Field(..., env="SPOTIFY_REDIRECT_URI")

    # Anthropic / Claude API key
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")

    # FastAPI session secret (used to sign session cookies)
    secret_key: str = Field(..., env="SECRET_KEY")

    # Path to the DuckDB database file
    duckdb_path: str = Field("./data/spotifai.duckdb", env="DUCKDB_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton instance — import this in every module that needs settings
settings = Settings()
