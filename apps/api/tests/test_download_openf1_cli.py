from __future__ import annotations

import json

import pytest

from workers.fixtures import download_openf1


def test_cli_help_includes_required_options() -> None:
    help_text = download_openf1.build_parser().format_help()

    assert "--fixture-id" in help_text
    assert "--year" in help_text
    assert "--country-name" in help_text
    assert "--session-name" in help_text
    assert "--drivers" in help_text
    assert "--level" in help_text
    assert "--output" in help_text
    assert "--dry-run" in help_text


def test_invalid_fixture_level_fails_with_useful_message(capsys: pytest.CaptureFixture[str]) -> None:
    parser = download_openf1.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "--fixture-id",
                "bahrain-2023-race",
                "--year",
                "2023",
                "--country-name",
                "Bahrain",
                "--session-name",
                "Race",
                "--level",
                "invalid",
            ]
        )

    stderr = capsys.readouterr().err
    assert "invalid choice" in stderr
    assert "golden" in stderr
    assert "dev" in stderr
    assert "full" in stderr


def test_dry_run_outputs_deterministic_plan(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    async def fake_discover_session(_args: object) -> download_openf1.SessionRef:
        return download_openf1.SessionRef(session_key=1001, meeting_key=55)

    monkeypatch.setattr(download_openf1, "_discover_session", fake_discover_session)

    exit_code = download_openf1.main(
        [
            "--fixture-id",
            "bahrain-2023-race",
            "--year",
            "2023",
            "--country-name",
            "Bahrain",
            "--session-name",
            "Race",
            "--drivers",
            "14,1,14,11",
            "--level",
            "golden",
            "--output",
            "examples/fixtures/bahrain-2023-race/golden",
            "--dry-run",
        ]
    )

    assert exit_code == 0

    stdout = capsys.readouterr().out
    plan = json.loads(stdout)

    assert plan["dry_run"] is True
    assert plan["fixture_id"] == "bahrain-2023-race"
    assert plan["level"] == "golden"
    assert plan["drivers"] == [1, 11, 14]
    assert plan["session"] == {"meeting_key": 55, "session_key": 1001}

    assert plan["requests"][0] == {
        "endpoint": "/v1/sessions",
        "params": {
            "country_name": "Bahrain",
            "session_name": "Race",
            "year": 2023,
        },
    }

    location_requests = [
        request for request in plan["requests"] if request["endpoint"] == "/v1/location"
    ]
    assert location_requests == [
        {"endpoint": "/v1/location", "params": {"driver_number": 1, "session_key": 1001}},
        {"endpoint": "/v1/location", "params": {"driver_number": 11, "session_key": 1001}},
        {"endpoint": "/v1/location", "params": {"driver_number": 14, "session_key": 1001}},
    ]
