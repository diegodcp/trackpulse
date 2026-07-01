from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Literal, Mapping

from pydantic import BaseModel, Field

from ..inference import project_wind_projection
from .track_model import BAHRAIN_TRACK_SEGMENTS


class WeatherMeasuredState(BaseModel):
    available: bool = False
    track_temperature_c: float | None = None
    air_temperature_c: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    rainfall: bool | None = None
    wind_direction_deg: int | None = None
    wind_speed_ms: float | None = None
    truth_label: Literal["measured"] = "measured"


class CarMarkerState(BaseModel):
    driver_number: int
    x: float
    y: float
    z: float | None = None
    occurred_at: str | None = None
    truth_label: Literal["measured"] = "measured"
    location_label: Literal["approximate"] = "approximate"


class TrackSnapshot(BaseModel):
    fixture_id: str | None = None
    replay_time: str | None = None
    session_key: int | None = None
    weather: WeatherMeasuredState = Field(default_factory=WeatherMeasuredState)
    car_markers: list[CarMarkerState] = Field(default_factory=list)
    segment_states: list[dict[str, Any]] = Field(default_factory=list)
    connection_status: str = "connected"
    replay_status: str = "idle"


class TrackStateReducer:
    """Reduce replay events into a latest track snapshot."""

    def __init__(self, *, fixture_id: str | None = None) -> None:
        self._fixture_id = fixture_id
        self._replay_time: str | None = None
        self._session_key: int | None = None
        self._weather = WeatherMeasuredState()
        self._car_markers_by_driver: dict[int, CarMarkerState] = {}
        self._segment_states: list[dict[str, Any]] = self._build_segment_states()
        self._connection_status = "connected"
        self._replay_status = "idle"

    def apply_event(self, event: Mapping[str, Any]) -> TrackSnapshot:
        self._update_common_fields(event)

        event_type = event.get("event_type")
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            payload = {}

        if _is_event_type(event_type, "weather"):
            self._apply_weather(payload)
        elif _is_event_type(event_type, "location"):
            self._apply_location(event, payload)
        elif event_type in {"replay.status", "replay_status"}:
            self._apply_status(event, payload)

        return self.snapshot()

    def reduce_events(self, events: Iterable[Mapping[str, Any]]) -> TrackSnapshot:
        snapshot = self.snapshot()
        for event in events:
            snapshot = self.apply_event(event)
        return snapshot

    def snapshot(self) -> TrackSnapshot:
        return TrackSnapshot(
            fixture_id=self._fixture_id,
            replay_time=self._replay_time,
            session_key=self._session_key,
            weather=self._weather,
            car_markers=self._sorted_markers(),
            segment_states=deepcopy(self._segment_states),
            connection_status=self._connection_status,
            replay_status=self._replay_status,
        )

    def _update_common_fields(self, event: Mapping[str, Any]) -> None:
        fixture_id = event.get("fixture_id")
        if isinstance(fixture_id, str) and fixture_id:
            self._fixture_id = fixture_id

        session_key = event.get("session_key")
        if isinstance(session_key, int):
            self._session_key = session_key

        occurred_at = event.get("occurred_at")
        if isinstance(occurred_at, str) and occurred_at:
            self._replay_time = occurred_at

    def _apply_weather(self, payload: Mapping[str, Any]) -> None:
        self._weather = WeatherMeasuredState(
            available=True,
            track_temperature_c=_to_float(payload.get("track_temperature")),
            air_temperature_c=_to_float(payload.get("air_temperature")),
            humidity=_to_float(payload.get("humidity")),
            pressure=_to_float(payload.get("pressure")),
            rainfall=_to_bool(payload.get("rainfall")),
            wind_direction_deg=_to_int(payload.get("wind_direction")),
            wind_speed_ms=_to_float(payload.get("wind_speed")),
        )
        self._segment_states = self._build_segment_states()

    def _apply_location(self, event: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        driver_number = event.get("driver_number")
        if not isinstance(driver_number, int):
            driver_number = payload.get("driver_number")

        if not isinstance(driver_number, int):
            return

        x = _to_float(payload.get("x"))
        y = _to_float(payload.get("y"))
        if x is None or y is None:
            return

        occurred_at = event.get("occurred_at")
        if not isinstance(occurred_at, str) or not occurred_at:
            payload_date = payload.get("date")
            occurred_at = payload_date if isinstance(payload_date, str) and payload_date else None

        self._car_markers_by_driver[driver_number] = CarMarkerState(
            driver_number=driver_number,
            x=x,
            y=y,
            z=_to_float(payload.get("z")),
            occurred_at=occurred_at,
        )

    def _apply_status(self, event: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        status = payload.get("status")
        if not isinstance(status, str):
            status = event.get("status")
        if isinstance(status, str) and status:
            self._replay_status = status

        connection_status = payload.get("connection_status")
        if isinstance(connection_status, str) and connection_status:
            self._connection_status = connection_status

    def _sorted_markers(self) -> list[CarMarkerState]:
        return [self._car_markers_by_driver[key] for key in sorted(self._car_markers_by_driver.keys())]

    def _build_segment_states(self) -> list[dict[str, Any]]:
        segment_states: list[dict[str, Any]] = []

        for segment in BAHRAIN_TRACK_SEGMENTS:
            projection = project_wind_projection(
                wind_direction_deg=(
                    float(self._weather.wind_direction_deg)
                    if self._weather.wind_direction_deg is not None
                    else None
                ),
                wind_speed_ms=self._weather.wind_speed_ms,
                segment_direction_deg=segment.direction_deg,
            )

            segment_states.append(
                {
                    "segment_id": segment.segment_id,
                    "direction_deg": segment.direction_deg,
                    "measured": {
                        "wind_direction_deg": self._weather.wind_direction_deg,
                        "wind_speed_ms": self._weather.wind_speed_ms,
                        "truth_label": "measured",
                    },
                    "derived": {
                        "wind_relative_angle_deg": projection.relative_angle_deg,
                        "wind_class": projection.wind_class,
                        "wind_strength_score": projection.strength_score,
                        "truth_label": "derived",
                    },
                }
            )

        return segment_states


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _is_event_type(value: Any, expected: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    return value == expected or value == f"{expected}.updated"
