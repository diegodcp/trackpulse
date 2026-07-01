from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

from workers.fixtures.extract_circuit_centerline import extract_circuit_centerline


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_extract_circuit_centerline_with_synthetic_fixture(tmp_path: Path) -> None:
    start = datetime(2023, 3, 5, 15, 0, tzinfo=timezone.utc)
    point_count = 200

    location_rows: list[dict[str, object]] = []
    for idx in range(point_count):
        theta = 2.0 * math.pi * (idx / point_count)
        x = 1500.0 + 450.0 * math.cos(theta)
        y = 800.0 + 250.0 * math.sin(theta)

        # Inject near-duplicate points periodically to validate distance-based deduplication.
        if idx % 17 == 0 and idx > 0:
            x += 0.6
            y += 0.4

        location_rows.append(
            {
                "date": _iso(start + timedelta(milliseconds=200 * idx)),
                "driver_number": 1,
                "session_key": 9149,
                "meeting_key": 1210,
                "x": x,
                "y": y,
                "z": 0.0,
            }
        )

    laps_rows = [
        {
            "driver_number": 1,
            "lap_number": 5,
            "session_key": 9149,
            "date_start": _iso(start),
            "lap_duration": 39.8,
        }
    ]

    location_path = tmp_path / "location.json"
    laps_path = tmp_path / "laps.json"
    _write_json(location_path, location_rows)
    _write_json(laps_path, laps_rows)

    output = extract_circuit_centerline(
        location_path=location_path,
        laps_path=laps_path,
        lap_number=5,
        driver_number=1,
    )

    assert output["circuitKey"] == "bahrain-2023-real"
    assert output["source"] == "openf1-location-telemetry"
    assert output["session_key"] == 9149
    assert output["lap"] == 5
    assert output["driver_number"] == 1
    assert output["width"] == 1200
    assert output["height"] == 700

    points = output["points"]
    segments = output["segments"]

    assert isinstance(points, list)
    assert len(points) >= 100
    assert isinstance(segments, list)
    assert len(segments) == 16

    previous_end = 0
    for segment in segments:
        start_point = segment["start_point"]
        end_point = segment["end_point"]

        assert (start_point["x"], start_point["y"]) != (end_point["x"], end_point["y"])

        direction_deg = segment["direction_deg"]
        assert 0.0 <= direction_deg < 360.0

        start_index = segment["arc_start_index"]
        end_index = segment["arc_end_index"]
        assert start_index >= previous_end
        assert end_index > start_index
        previous_end = end_index
