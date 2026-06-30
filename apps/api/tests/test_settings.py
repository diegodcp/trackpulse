from trackpulse_api.settings import get_settings


def test_settings_load_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TRACKPULSE_APP_NAME", "TrackPulse Backend")
    monkeypatch.setenv("TRACKPULSE_APP_VERSION", "2026.06.30")
    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_CORS_ALLOW_ORIGINS", "https://app.example.com,https://admin.example.com")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "TrackPulse Backend"
    assert settings.app_version == "2026.06.30"
    assert settings.openf1_mode == "fixture"
    assert settings.cors_allow_origins == "https://app.example.com,https://admin.example.com"
    assert settings.cors_allow_origins_list == ["https://app.example.com", "https://admin.example.com"]
