from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable, Literal, Mapping

from pydantic import BaseModel, Field

from ..inference import (
    CORNER_EVOLUTION_IMPROVING,
    CornerSpeedSample,
    DirtyZoneInsightInput,
    DirtyZoneInput,
    InsightEngineInput,
    InsightEngineState,
    LiveInsight,
    SegmentTrendInsightInput,
    TrafficInsightInput,
    WindInsightInput,
    generate_rule_based_insights,
    infer_dirty_zone_probability,
    project_wind_projection,
    score_corner_evolution,
)
from ..inference.traffic import CarSegmentState, compute_traffic_scores
from .track_model import BAHRAIN_SECTOR_SEGMENTS, BAHRAIN_TRACK_SEGMENTS


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
    segment_id: str | None = None
    truth_label: Literal["measured"] = "measured"
    location_label: Literal["approximate"] = "approximate"


class TrackSnapshot(BaseModel):
    fixture_id: str | None = None
    replay_time: str | None = None
    session_key: int | None = None
    weather: WeatherMeasuredState = Field(default_factory=WeatherMeasuredState)
    car_markers: list[CarMarkerState] = Field(default_factory=list)
    segment_states: list[dict[str, Any]] = Field(default_factory=list)
    live_insights: list[LiveInsight] = Field(default_factory=list)
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
        self._segment_order = [segment.segment_id for segment in BAHRAIN_TRACK_SEGMENTS]
        self._segment_set = set(self._segment_order)
        self._segment_models = {segment.segment_id: segment for segment in BAHRAIN_TRACK_SEGMENTS}
        self._segment_states: list[dict[str, Any]] = self._build_segment_states()
        self._traffic_persistence_counts = {segment_id: 0 for segment_id in self._segment_order}
        self._corner_samples_by_segment: dict[str, list[CornerSpeedSample]] = {}
        self._corner_trend_by_segment: dict[str, SegmentTrendInsightInput] = {}
        self._dirty_zone_inputs: list[DirtyZoneInput] = []
        self._insight_engine_state = InsightEngineState()
        self._active_insights_by_id: dict[str, LiveInsight] = {}
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
        elif _is_event_type(event_type, "car_data"):
            self._apply_car_data(event, payload)
        elif _is_event_type(event_type, "race_control"):
            self._apply_race_control(event, payload)
        elif event_type in {"replay.status", "replay_status"}:
            self._apply_status(event, payload)

        self._refresh_live_insights(event, payload)
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
            segment_states=self._segment_states_with_traffic(),
            live_insights=self._sorted_live_insights(),
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

        resolved_segment_id = self._resolve_segment_id(driver_number, payload)

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
            segment_id=resolved_segment_id,
        )

    def _apply_car_data(self, event: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        speed_kmh = _to_float(payload.get("speed"))
        if speed_kmh is None:
            return

        driver_number = event.get("driver_number")
        if not isinstance(driver_number, int):
            driver_number = payload.get("driver_number")

        segment_id = payload.get("segment_id")
        if not isinstance(segment_id, str) or segment_id not in self._segment_set:
            if isinstance(driver_number, int):
                marker = self._car_markers_by_driver.get(driver_number)
                segment_id = marker.segment_id if marker is not None else None

        if not isinstance(segment_id, str) or segment_id not in self._segment_set:
            return

        samples = self._corner_samples_by_segment.setdefault(segment_id, [])
        samples.append(CornerSpeedSample(segment_id=segment_id, speed_kmh=speed_kmh))
        if len(samples) > 12:
            del samples[:-12]

        result = score_corner_evolution(samples)
        if result.evolution == CORNER_EVOLUTION_IMPROVING:
            self._corner_trend_by_segment[segment_id] = SegmentTrendInsightInput(
                segment_id=segment_id,
                avg_speed_delta_kmh=result.avg_speed_delta_kmh,
                confidence=result.confidence,
                clean_sample_count=int(result.evidence.get("cleanSampleCount", 0)),
            )
        else:
            self._corner_trend_by_segment.pop(segment_id, None)

    def _apply_race_control(self, event: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        event_time = _event_time(event, payload)
        if event_time is None:
            return

        self._dirty_zone_inputs.append(
            DirtyZoneInput(
                event_time=event_time,
                sector=_to_int(payload.get("sector")),
                flag=payload.get("flag") if isinstance(payload.get("flag"), str) else None,
                category=payload.get("category") if isinstance(payload.get("category"), str) else None,
                message=payload.get("message") if isinstance(payload.get("message"), str) else None,
            )
        )
        if len(self._dirty_zone_inputs) > 5:
            del self._dirty_zone_inputs[:-5]

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

    def _sorted_live_insights(self) -> list[LiveInsight]:
        severity_order = {"warning": 0, "info": 1}
        return sorted(
            self._active_insights_by_id.values(),
            key=lambda item: (severity_order.get(item.severity, 9), item.expires_at, item.insight_id),
        )

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

    def _resolve_segment_id(self, driver_number: int, payload: Mapping[str, Any]) -> str | None:
        payload_segment_id = payload.get("segment_id")
        if isinstance(payload_segment_id, str) and payload_segment_id in self._segment_set:
            return payload_segment_id

        normalized_progress = _to_float(payload.get("normalized_progress"))
        if normalized_progress is not None:
            return self._segment_from_progress(normalized_progress)

        fallback_progress = ((driver_number * 37) % 100) / 100
        return self._segment_from_progress(fallback_progress)

    def _segment_from_progress(self, progress: float) -> str | None:
        if not self._segment_order:
            return None

        clamped = min(1.0, max(0.0, progress))
        segment_count = len(self._segment_order)
        index = min(segment_count - 1, int(clamped * segment_count))
        return self._segment_order[index]

    def _segment_states_with_traffic(self) -> list[dict[str, Any]]:
        segment_states = deepcopy(self._segment_states)
        traffic_scores = self._traffic_scores()

        for segment_state in segment_states:
            segment_id = segment_state.get("segment_id")
            derived = segment_state.setdefault("derived", {})
            derived["traffic_score"] = round(float(traffic_scores.get(segment_id, 0.0)), 1)
            derived["traffic_truth_label"] = "derived"

        return segment_states

    def _traffic_scores(self) -> dict[str, float]:
        return compute_traffic_scores(
            car_states=[
                CarSegmentState(segment_id=marker.segment_id)
                for marker in self._car_markers_by_driver.values()
                if isinstance(marker.segment_id, str) and marker.segment_id in self._segment_set
            ],
            segment_order=self._segment_order,
        )

    def _refresh_live_insights(self, event: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        now = _event_time(event, payload)
        if now is None:
            return

        event_type = event.get("event_type")

        self._active_insights_by_id = {
            key: insight
            for key, insight in self._active_insights_by_id.items()
            if insight.expires_at > now
        }

        traffic_scores = self._traffic_scores()
        if _is_event_type(event_type, "location"):
            for segment_id in self._segment_order:
                if traffic_scores.get(segment_id, 0.0) >= 20.0:
                    self._traffic_persistence_counts[segment_id] += 1
                else:
                    self._traffic_persistence_counts[segment_id] = 0

        dirty_zone_inputs: list[DirtyZoneInsightInput] = []
        for dirty_input in self._dirty_zone_inputs:
            result = infer_dirty_zone_probability(dirty_input, BAHRAIN_SECTOR_SEGMENTS, now=now)
            if not result.segments:
                continue

            dirty_zone_inputs.append(
                DirtyZoneInsightInput(
                    segment_ids=tuple(segment.segment_id for segment in result.segments),
                    probability=max(segment.probability for segment in result.segments),
                    confidence=max(segment.confidence for segment in result.segments),
                    trigger=result.trigger,
                )
            )

        insight_input = InsightEngineInput(
            wind=tuple(self._wind_insight_inputs()),
            traffic=tuple(
                TrafficInsightInput(
                    segment_id=segment_id,
                    traffic_score=score,
                    consecutive_updates=self._traffic_persistence_counts.get(segment_id, 0),
                )
                for segment_id, score in traffic_scores.items()
            ),
            segment_trend=tuple(self._corner_trend_by_segment.values()),
            dirty_zone=tuple(dirty_zone_inputs),
        )
        new_insights, self._insight_engine_state = generate_rule_based_insights(
            insight_input,
            now=now,
            state=self._insight_engine_state,
        )
        for insight in new_insights:
            self._active_insights_by_id[insight.insight_id] = insight

    def _wind_insight_inputs(self) -> list[WindInsightInput]:
        inputs: list[WindInsightInput] = []
        for segment_state in self._segment_states:
            segment_id = segment_state.get("segment_id")
            if not isinstance(segment_id, str):
                continue

            model = self._segment_models.get(segment_id)
            if model is None:
                continue

            measured = segment_state.get("measured", {})
            derived = segment_state.get("derived", {})
            inputs.append(
                WindInsightInput(
                    segment_id=segment_id,
                    wind_speed_ms=_to_float(measured.get("wind_speed_ms")),
                    wind_class=derived.get("wind_class") if isinstance(derived.get("wind_class"), str) else None,
                    wind_strength_score=_to_float(derived.get("wind_strength_score")),
                    is_braking_zone=model.is_braking_zone,
                    is_fast_corner=model.is_fast_corner,
                )
            )
        return inputs


def _parse_datetime(value: str) -> datetime | None:
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _event_time(event: Mapping[str, Any], payload: Mapping[str, Any]) -> datetime | None:
    occurred_at = event.get("occurred_at")
    if isinstance(occurred_at, str):
        parsed = _parse_datetime(occurred_at)
        if parsed is not None:
            return parsed

    payload_date = payload.get("date")
    if isinstance(payload_date, str):
        return _parse_datetime(payload_date)

    return None


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
