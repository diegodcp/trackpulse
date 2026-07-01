from __future__ import annotations

import pytest

from trackpulse_api.inference.wind import project_wind_projection


def test_project_wind_projection_headwind_tailwind_and_crosswind() -> None:
    headwind = project_wind_projection(
        wind_direction_deg=0.0,
        wind_speed_ms=10.0,
        segment_direction_deg=0.0,
    )
    tailwind = project_wind_projection(
        wind_direction_deg=180.0,
        wind_speed_ms=10.0,
        segment_direction_deg=0.0,
    )
    crosswind_right = project_wind_projection(
        wind_direction_deg=90.0,
        wind_speed_ms=10.0,
        segment_direction_deg=0.0,
    )
    crosswind_left = project_wind_projection(
        wind_direction_deg=270.0,
        wind_speed_ms=10.0,
        segment_direction_deg=0.0,
    )

    assert headwind.relative_angle_deg == pytest.approx(0.0)
    assert headwind.wind_class == "headwind"
    assert headwind.strength_score == pytest.approx(50.0)

    assert tailwind.relative_angle_deg == pytest.approx(-180.0)
    assert tailwind.wind_class == "tailwind"
    assert tailwind.strength_score == pytest.approx(50.0)

    assert crosswind_right.relative_angle_deg == pytest.approx(90.0)
    assert crosswind_right.wind_class == "crosswind_right"
    assert crosswind_right.strength_score == pytest.approx(0.0)

    assert crosswind_left.relative_angle_deg == pytest.approx(-90.0)
    assert crosswind_left.wind_class == "crosswind_left"
    assert crosswind_left.strength_score == pytest.approx(0.0)


def test_project_wind_projection_boundary_classes() -> None:
    boundary_headwind = project_wind_projection(
        wind_direction_deg=30.0,
        wind_speed_ms=8.0,
        segment_direction_deg=0.0,
    )
    boundary_tailwind = project_wind_projection(
        wind_direction_deg=150.0,
        wind_speed_ms=8.0,
        segment_direction_deg=0.0,
    )

    assert boundary_headwind.wind_class == "headwind"
    assert boundary_tailwind.wind_class == "tailwind"


def test_project_wind_projection_normalizes_angles() -> None:
    projected = project_wind_projection(
        wind_direction_deg=725.0,
        wind_speed_ms=12.0,
        segment_direction_deg=-10.0,
    )

    assert projected.relative_angle_deg == pytest.approx(15.0)
    assert projected.wind_class == "headwind"


@pytest.mark.parametrize(
    ("wind_direction_deg", "wind_speed_ms", "segment_direction_deg"),
    [
        (None, 10.0, 0.0),
        (180.0, None, 0.0),
        (180.0, 10.0, None),
    ],
)
def test_project_wind_projection_missing_data_returns_unknown(
    wind_direction_deg: float | None,
    wind_speed_ms: float | None,
    segment_direction_deg: float | None,
) -> None:
    projected = project_wind_projection(
        wind_direction_deg=wind_direction_deg,
        wind_speed_ms=wind_speed_ms,
        segment_direction_deg=segment_direction_deg,
    )

    assert projected.relative_angle_deg is None
    assert projected.wind_class == "unknown"
    assert projected.strength_score is None
