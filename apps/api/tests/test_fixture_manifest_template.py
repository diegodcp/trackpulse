import json
from pathlib import Path


MANIFEST_PATH = Path(__file__).resolve().parents[3] / "examples" / "fixtures" / "bahrain-2023-race" / "manifest.template.json"


def test_manifest_template_has_required_top_level_keys() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    required_keys = {"fixture_id", "seed_query", "drivers", "endpoints"}
    missing_keys = required_keys - set(manifest.keys())

    assert not missing_keys, f"manifest.template.json is missing required keys: {sorted(missing_keys)}"


def test_manifest_template_seed_values() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["fixture_id"] == "bahrain-2023-race"
    assert manifest["seed_query"] == {
        "year": 2023,
        "country_name": "Bahrain",
        "session_name": "Race",
    }
    assert manifest["drivers"] == [1, 11, 14, 16, 44]
    assert manifest["endpoints"] == [
        "sessions",
        "weather",
        "drivers",
        "location",
        "car_data",
        "laps",
        "intervals",
        "position",
        "stints",
        "pit",
        "race_control",
    ]


def test_manifest_template_sampling_targets_for_golden_and_dev() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    sampling = manifest["sampling"]["modes"]
    for mode in ["golden", "dev"]:
        assert sampling[mode]["location_hz_target"] == 1.0
        assert sampling[mode]["car_data_hz_target"] == 1.0
