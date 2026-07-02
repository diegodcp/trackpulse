from functools import lru_cache

from trackpulse_api.config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()
