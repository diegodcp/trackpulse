from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

import trackpulse_api.main as main_module
from trackpulse_api.settings import AppSettings, get_settings


@pytest.fixture(autouse=True)
def force_fixture_mode_settings_override(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()

    def _test_settings() -> AppSettings:
        return AppSettings(openf1_mode="fixture")

    monkeypatch.setattr(main_module, "get_settings", _test_settings)
    yield
    get_settings.cache_clear()
