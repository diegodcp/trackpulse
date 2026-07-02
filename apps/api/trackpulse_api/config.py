from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "TRACKPULSE_"}

    app_name: str = "TrackPulse API"
    debug: bool = False
    cors_allow_origins: str = "http://localhost:5173"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/trackpulse"
    openf1_base_url: str = "https://api.openf1.org/v1"
