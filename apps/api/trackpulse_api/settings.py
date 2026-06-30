from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_cors_allow_origins() -> list[str]:
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRACKPULSE_", extra="ignore")

    app_name: str = "TrackPulse API"
    app_version: str = "0.1.0"
    openf1_mode: Literal["fixture", "historical", "live"] = "fixture"
    log_level: str = "INFO"
    cors_allow_origins: str = Field(
        default=",".join(_default_cors_allow_origins()),
        description="Comma-separated CORS allowlist",
    )

    @property
    def cors_allow_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
