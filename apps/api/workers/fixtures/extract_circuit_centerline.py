from __future__ import annotations

import argparse
import json
import math
from bisect import bisect_left
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_CIRCUIT_KEY = "bahrain-2023-real"
DEFAULT_SOURCE = "openf1-location-telemetry"
DEFAULT_DRIVER_NUMBER = 1
DEFAULT_LAP = 5
DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 700
DEFAULT_PADDING = 80
DEFAULT_SEGMENT_COUNT = 16
DEFAULT_DEDUP_DISTANCE_METERS = 3.0
DEFAULT_SMOOTH_WINDOW = 5


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _default_location_path() -> Path:
    return _repo_root() / "examples" / "fixtures" / "bahrain-2023-race" / "golden" / "location.json"


def _default_laps_path() -> Path:
    return _repo_root() / "examples" / "fixtures" / "bahrain-2023-race" / "golden" / "laps.json"


def _default_output_path() -> Path:
    return _repo_root() / "examples" / "fixtures" / "bahrain-2023-race" / "circuit-centerline.json"


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError(f"Expected array payload in {path}")

    rows: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp is missing or invalid")

    normalized = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _to_float(value: Any, *, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid numeric value for {field_name}: {value!r}") from exc


def _lap_window(
    laps: list[dict[str, Any]],
    *,
    driver_number: int,
    lap_number: int,
) -> tuple[datetime, datetime, int | None]:
    candidates = [
        row
        for row in laps
        if int(row.get("driver_number", -1)) == driver_number
        and int(row.get("lap_number", -1)) == lap_number
    ]
    if not candidates:
        raise ValueError(
            f"No lap record found for driver_number={driver_number}, lap_number={lap_number}"
        )

    lap = candidates[0]
    start = _parse_timestamp(lap.get("date_start"))

    end: datetime | None = None
    if lap.get("date_end"):
        end = _parse_timestamp(lap.get("date_end"))
    elif lap.get("lap_duration") is not None:
        end = start + timedelta(seconds=_to_float(lap.get("lap_duration"), field_name="lap_duration"))

    if end is None:
        raise ValueError(
            "Lap boundary detection requires date_end or lap_duration in laps fixture"
        )
    if end <= start:
        raise ValueError("Lap end timestamp must be after lap start timestamp")

    session_key = lap.get("session_key")
    if session_key is not None:
        session_key = int(session_key)

    return start, end, session_key


def _driver_lap_points(
    location_rows: list[dict[str, Any]],
    *,
    driver_number: int,
    start: datetime,
    end: datetime,
) -> tuple[list[float], list[float], int | None]:
    selected_rows: list[tuple[datetime, dict[str, Any]]] = []
    for row in location_rows:
        if int(row.get("driver_number", -1)) != driver_number:
            continue
        ts = _parse_timestamp(row.get("date"))
        if start <= ts <= end:
            selected_rows.append((ts, row))

    selected_rows.sort(key=lambda item: item[0])

    x: list[float] = []
    y: list[float] = []
    session_key: int | None = None

    for _, row in selected_rows:
        x.append(_to_float(row.get("x"), field_name="x"))
        y.append(_to_float(row.get("y"), field_name="y"))
        if session_key is None and row.get("session_key") is not None:
            session_key = int(row["session_key"])

    return x, y, session_key


def _deduplicate_points(x: list[float], y: list[float], *, min_distance: float) -> tuple[list[float], list[float]]:
    if not x:
        return [], []

    out_x: list[float] = [x[0]]
    out_y: list[float] = [y[0]]

    for idx in range(1, len(x)):
        dx = x[idx] - out_x[-1]
        dy = y[idx] - out_y[-1]
        if math.hypot(dx, dy) < min_distance:
            continue
        out_x.append(x[idx])
        out_y.append(y[idx])

    return out_x, out_y


def _smooth(values: list[float], *, window: int) -> list[float]:
    if not values:
        return []

    if window <= 1:
        return list(values)

    radius = window // 2
    smoothed: list[float] = []
    for idx in range(len(values)):
        start = max(0, idx - radius)
        end = min(len(values), idx + radius + 1)
        segment = values[start:end]
        smoothed.append(sum(segment) / len(segment))
    return smoothed


def _gradient(values: list[float]) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [0.0]

    grad = [0.0] * len(values)
    grad[0] = values[1] - values[0]
    grad[-1] = values[-1] - values[-2]
    for idx in range(1, len(values) - 1):
        grad[idx] = (values[idx + 1] - values[idx - 1]) / 2.0
    return grad


def _track_normals(x: list[float], y: list[float]) -> tuple[list[float], list[float], list[float], list[float]]:
    dx = _gradient(x)
    dy = _gradient(y)

    ndx: list[float] = []
    ndy: list[float] = []
    nx: list[float] = []
    ny: list[float] = []
    for gx, gy in zip(dx, dy, strict=True):
        norm = math.sqrt(gx**2 + gy**2)
        if norm == 0.0:
            norm = 1.0
        ux = gx / norm
        uy = gy / norm
        ndx.append(ux)
        ndy.append(uy)
        nx.append(-uy)
        ny.append(ux)

    return ndx, ndy, nx, ny


def _normalize_points(
    x: list[float],
    y: list[float],
    *,
    width: int,
    height: int,
    padding: int,
) -> tuple[list[float], list[float]]:
    min_x = min(x)
    max_x = max(x)
    min_y = min(y)
    max_y = max(y)

    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    target_w = max(float(width - 2 * padding), 1.0)
    target_h = max(float(height - 2 * padding), 1.0)
    scale = min(target_w / span_x, target_h / span_y)

    nx = [padding + (value - min_x) * scale for value in x]
    ny = [padding + (value - min_y) * scale for value in y]
    return nx, ny


def _cumulative_arc_lengths(x: list[float], y: list[float]) -> list[float]:
    if not x:
        return []

    arc = [0.0]
    for idx in range(1, len(x)):
        dist = math.hypot(x[idx] - x[idx - 1], y[idx] - y[idx - 1])
        arc.append(arc[-1] + dist)
    return arc


def _direction_deg(start: tuple[float, float], end: tuple[float, float]) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    raw = math.degrees(math.atan2(dy, dx))
    return (raw + 360.0) % 360.0


def _build_segments(
    x: list[float],
    y: list[float],
    *,
    segment_count: int,
) -> list[dict[str, Any]]:
    if len(x) < 2:
        raise ValueError("Need at least 2 centerline points to build segments")

    arc = _cumulative_arc_lengths(x, y)
    total = arc[-1]
    if total <= 0.0:
        raise ValueError("Cannot build segments from zero-length centerline")

    segments: list[dict[str, Any]] = []
    previous_end = 0
    for idx in range(segment_count):
        start_target = total * (idx / segment_count)
        end_target = total * ((idx + 1) / segment_count)

        start_index = max(previous_end, bisect_left(arc, start_target))
        end_index = max(start_index + 1, bisect_left(arc, end_target))
        end_index = min(end_index, len(x) - 1)

        if end_index <= start_index:
            if start_index < len(x) - 1:
                end_index = start_index + 1
            else:
                start_index = len(x) - 2
                end_index = len(x) - 1

        start_point = (x[start_index], y[start_index])
        end_point = (x[end_index], y[end_index])

        segments.append(
            {
                "segment_id": f"bh-s{idx + 1:02d}",
                "arc_start_index": start_index,
                "arc_end_index": end_index,
                "start_point": {"x": round(start_point[0], 3), "y": round(start_point[1], 3)},
                "end_point": {"x": round(end_point[0], 3), "y": round(end_point[1], 3)},
                "direction_deg": round(_direction_deg(start_point, end_point), 3),
            }
        )
        previous_end = end_index

    return segments


def extract_circuit_centerline(
    *,
    location_path: Path,
    laps_path: Path,
    lap_number: int = DEFAULT_LAP,
    driver_number: int = DEFAULT_DRIVER_NUMBER,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    padding: int = DEFAULT_PADDING,
    segment_count: int = DEFAULT_SEGMENT_COUNT,
    dedup_distance_meters: float = DEFAULT_DEDUP_DISTANCE_METERS,
    smooth_window: int = DEFAULT_SMOOTH_WINDOW,
) -> dict[str, Any]:
    location_rows = _load_json_array(location_path)
    laps_rows = _load_json_array(laps_path)

    start, end, lap_session_key = _lap_window(
        laps_rows,
        driver_number=driver_number,
        lap_number=lap_number,
    )

    x, y, location_session_key = _driver_lap_points(
        location_rows,
        driver_number=driver_number,
        start=start,
        end=end,
    )
    if len(x) < 2:
        raise ValueError(
            "Not enough location points after lap filtering; expected at least 2 points"
        )

    x, y = _deduplicate_points(x, y, min_distance=dedup_distance_meters)
    x = _smooth(x, window=smooth_window)
    y = _smooth(y, window=smooth_window)

    if len(x) < 2:
        raise ValueError("Not enough centerline points after deduplication and smoothing")

    # Compute gradients/normals to preserve track geometry behavior.
    _track_normals(x, y)

    normalized_x, normalized_y = _normalize_points(
        x,
        y,
        width=width,
        height=height,
        padding=padding,
    )
    segments = _build_segments(normalized_x, normalized_y, segment_count=segment_count)

    points = [
        {"x": round(px, 3), "y": round(py, 3)}
        for px, py in zip(normalized_x, normalized_y, strict=True)
    ]

    session_key = location_session_key if location_session_key is not None else lap_session_key

    return {
        "circuitKey": DEFAULT_CIRCUIT_KEY,
        "source": DEFAULT_SOURCE,
        "session_key": session_key,
        "lap": lap_number,
        "driver_number": driver_number,
        "width": width,
        "height": height,
        "points": points,
        "segments": segments,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract TrackPulse Bahrain circuit centerline from OpenF1 location fixture"
    )
    parser.add_argument("--location-path", type=Path, default=_default_location_path())
    parser.add_argument("--laps-path", type=Path, default=_default_laps_path())
    parser.add_argument("--output-path", type=Path, default=_default_output_path())
    parser.add_argument("--lap", type=int, default=DEFAULT_LAP)
    parser.add_argument("--driver-number", type=int, default=DEFAULT_DRIVER_NUMBER)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--padding", type=int, default=DEFAULT_PADDING)
    parser.add_argument("--segments", type=int, default=DEFAULT_SEGMENT_COUNT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    result = extract_circuit_centerline(
        location_path=args.location_path,
        laps_path=args.laps_path,
        lap_number=args.lap,
        driver_number=args.driver_number,
        width=args.width,
        height=args.height,
        padding=args.padding,
        segment_count=args.segments,
    )

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    with args.output_path.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")

    print(
        json.dumps(
            {
                "output_path": str(args.output_path),
                "points": len(result["points"]),
                "segments": len(result["segments"]),
                "lap": result["lap"],
                "driver_number": result["driver_number"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())