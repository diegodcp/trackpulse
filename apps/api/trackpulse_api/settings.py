from functools import lru_cache
from fastapi import Request
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_cors_allow_origins() -> list[str]:
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


def _default_openf1_fixture_data_dir() -> str:
    repo_root = Path(__file__).resolve().parents[3]
    return str(repo_root / "examples" / "fixtures" / "bahrain-2023-race" / "golden")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRACKPULSE_", extra="ignore")

    app_name: str = "TrackPulse API"
    app_version: str = "0.1.0"
    openf1_mode: Literal["fixture", "historical", "live"] = "fixture"
    openf1_base_url: str = "https://api.openf1.org"
    openf1_bearer_token: str | None = None
    openf1_fixture_data_dir: str = _default_openf1_fixture_data_dir()
    openf1_timeout_seconds: float = 10.0
    openf1_max_retries: int = 2
    openf1_seed_year: int = 2023
    openf1_seed_country_name: str = "Bahrain"
    openf1_seed_session_name: str = "Race"
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


def get_app_settings(request: Request) -> AppSettings:
    return request.app.state.settings
