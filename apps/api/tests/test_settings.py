from trackpulse_api.settings import get_settings


def test_settings_load_from_env(monkeypatch) -> None:
    monkeypatch.setenv("TRACKPULSE_APP_NAME", "TrackPulse Backend")
    monkeypatch.setenv("TRACKPULSE_APP_VERSION", "2026.06.30")
    monkeypatch.setenv("TRACKPULSE_OPENF1_MODE", "fixture")
    monkeypatch.setenv("TRACKPULSE_OPENF1_BASE_URL", "https://mock.openf1.local")
    monkeypatch.setenv("TRACKPULSE_OPENF1_BEARER_TOKEN", "test-token")
    monkeypatch.setenv("TRACKPULSE_OPENF1_FIXTURE_DATA_DIR", "/tmp/openf1-fixtures")
    monkeypatch.setenv("TRACKPULSE_OPENF1_TIMEOUT_SECONDS", "3.5")
    monkeypatch.setenv("TRACKPULSE_OPENF1_MAX_RETRIES", "4")
    monkeypatch.setenv("TRACKPULSE_OPENF1_SEED_YEAR", "2025")
    monkeypatch.setenv("TRACKPULSE_OPENF1_SEED_COUNTRY_NAME", "Australia")
    monkeypatch.setenv("TRACKPULSE_OPENF1_SEED_SESSION_NAME", "Qualifying")
    monkeypatch.setenv("TRACKPULSE_DB_ENABLED", "true")
    monkeypatch.setenv("TRACKPULSE_DB_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/trackpulse_test")
    monkeypatch.setenv("TRACKPULSE_CORS_ALLOW_ORIGINS", "https://app.example.com,https://admin.example.com")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.app_name == "TrackPulse Backend"
    assert settings.app_version == "2026.06.30"
    assert settings.openf1_mode == "fixture"
    assert settings.openf1_base_url == "https://mock.openf1.local"
    assert settings.openf1_bearer_token == "test-token"
    assert settings.openf1_fixture_data_dir == "/tmp/openf1-fixtures"
    assert settings.openf1_timeout_seconds == 3.5
    assert settings.openf1_max_retries == 4
    assert settings.openf1_seed_year == 2025
    assert settings.openf1_seed_country_name == "Australia"
    assert settings.openf1_seed_session_name == "Qualifying"
    assert settings.db_enabled is True
    assert settings.db_url == "postgresql+asyncpg://postgres:postgres@localhost:5432/trackpulse_test"
    assert settings.cors_allow_origins == "https://app.example.com,https://admin.example.com"
    assert settings.cors_allow_origins_list == ["https://app.example.com", "https://admin.example.com"]
