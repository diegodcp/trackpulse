from __future__ import annotations

from dataclasses import dataclass
from math import isnan

INFERRED_LABEL = "inferred"


@dataclass(frozen=True)
class RainInfluenceInput:
    """Minimal signal set for TP-INF-05 rain influence scoring."""

    measured_rainfall: bool
    track_temp_drop_celsius: float | None
    cross_driver_variance_kmh: float | None
    high_speed_corner_speed_loss_kmh: float | None
    anomalous_driver_count: int
    external_radar_confirmed: bool = False


@dataclass(frozen=True)
class RainInfluenceResult:
    label: str
    rain_influence_probability: float
    confidence: float
    is_rain_influence_likely: bool
    local_rainfall_claimed: bool
    evidence: dict[str, float | int | bool | None]


def _valid_number(value: float | None) -> bool:
    return value is not None and not isnan(value)


def _bounded_non_negative(value: float | None) -> float:
    if not _valid_number(value):
        return 0.0

    return max(0.0, float(value))


def score_rain_influence(rain_input: RainInfluenceInput) -> RainInfluenceResult:
    """Infer rain influence probability from measured and behavioral signals.

    TP-INF-05 assumptions for v1:
    - measured_rainfall reflects track-level measured rainfall only;
    - local rainfall is never claimed without an external radar confirmation;
    - cross-driver confirmation is required to allow high confidence.
    """
    track_temp_drop = _bounded_non_negative(rain_input.track_temp_drop_celsius)
    cross_driver_variance = _bounded_non_negative(rain_input.cross_driver_variance_kmh)
    high_speed_corner_speed_loss = _bounded_non_negative(rain_input.high_speed_corner_speed_loss_kmh)
    anomalous_driver_count = max(0, rain_input.anomalous_driver_count)

    cross_driver_confirmed = anomalous_driver_count >= 2

    probability = 0.0
    if rain_input.measured_rainfall:
        probability += 0.55

    if track_temp_drop >= 3.0:
        probability += 0.15
    elif track_temp_drop >= 1.5:
        probability += 0.08

    if cross_driver_variance >= 4.0:
        probability += 0.15
    elif cross_driver_variance >= 2.5:
        probability += 0.08

    if high_speed_corner_speed_loss >= 6.0:
        probability += 0.2
    elif high_speed_corner_speed_loss >= 3.0:
        probability += 0.1

    if cross_driver_confirmed:
        probability += 0.1

    bounded_probability = round(min(1.0, probability), 2)

    confidence = 0.35
    if rain_input.measured_rainfall:
        confidence += 0.35

    if track_temp_drop >= 2.0:
        confidence += 0.05
    if cross_driver_variance >= 3.0:
        confidence += 0.05
    if high_speed_corner_speed_loss >= 4.0:
        confidence += 0.05

    if cross_driver_confirmed:
        confidence += 0.3
    elif anomalous_driver_count == 1:
        confidence += 0.05

    if not cross_driver_confirmed:
        confidence = min(confidence, 0.65)

    bounded_confidence = round(min(1.0, confidence), 2)
    likely = bounded_probability >= 0.6

    return RainInfluenceResult(
        label=INFERRED_LABEL,
        rain_influence_probability=bounded_probability,
        confidence=bounded_confidence,
        is_rain_influence_likely=likely,
        local_rainfall_claimed=(rain_input.measured_rainfall and rain_input.external_radar_confirmed),
        evidence={
            "measuredRainfall": rain_input.measured_rainfall,
            "trackTempDropCelsius": round(track_temp_drop, 2),
            "crossDriverVarianceKmh": round(cross_driver_variance, 2),
            "highSpeedCornerSpeedLossKmh": round(high_speed_corner_speed_loss, 2),
            "anomalousDriverCount": anomalous_driver_count,
            "crossDriverConfirmed": cross_driver_confirmed,
            "externalRadarConfirmed": rain_input.external_radar_confirmed,
        },
    )