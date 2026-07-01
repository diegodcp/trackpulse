from pathlib import Path


def test_env_local_example_contains_required_historical_mode_settings() -> None:
    env_example = Path(__file__).resolve().parents[1] / ".env.local.example"

    content = env_example.read_text(encoding="utf-8")

    assert "TRACKPULSE_OPENF1_MODE=historical" in content
    assert "TRACKPULSE_OPENF1_SEED_YEAR=2023" in content
    assert "TRACKPULSE_OPENF1_SEED_COUNTRY_NAME=Bahrain" in content
    assert "TRACKPULSE_OPENF1_SEED_SESSION_NAME=Race" in content
    assert "does not require credentials for 2023 data" in content