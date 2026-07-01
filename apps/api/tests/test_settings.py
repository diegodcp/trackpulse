from trackpulse_api.settings import get_settings


def test_settings_load_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TRACKPULSE_APP_NAME", "TrackPulse Backend")
    monkeypatch.setenv("TRACKPULSE_APP_VERSION", "2026.06.30")
    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_OPENF1_BASE_URL", "https://mock.openf1.local")
    monkeypatch.setenv("TRACKPULSE_OPENF1_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("TRACKPULSE_OPENF1_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("TRACKPULSE_OPENF1_MAX_RETRIES", "4")
    monkeypatch.setenv("TRACKPULSE_CORS_ALLOW_ORIGINS", "https://app.example.com,https://admin.example.com")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "TrackPulse Backend"
    assert settings.app_version == "2026.06.30"
    assert settings.openf1_mode == "fixture"
    assert settings.openf1_base_url == "https://mock.openf1.local"
    assert settings.openf1_bearer_token == "test-token"
    assert settings.openf1_timeout_seconds == 3.5
    assert settings.openf1_max_retries == 4
    assert settings.cors_allow_origins == "https://app.example.com,https://admin.example.com"
    assert settings.cors_allow_origins_list == ["https://app.example.com", "https://admin.example.com"]
