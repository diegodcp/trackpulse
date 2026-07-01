from __future__ import annotations

import pytest

from trackpulse_api.inference.rain import INFERRED_LABEL, RainInfluenceInput, score_rain_influence


def test_measured_rainfall_sets_high_probability() -> None:
    result = score_rain_influence(
        RainInfluenceInput(
            measured_rainfall=True,
            track_temp_drop_celsius=2.8,
            cross_driver_variance_kmh=3.1,
            high_speed_corner_speed_loss_kmh=4.8,
            anomalous_driver_count=3,
            external_radar_confirmed=False,
        )
    )

    assert result.label == INFERRED_LABEL
    assert result.rain_influence_probability >= 0.6
    assert result.is_rain_influence_likely is True
    assert result.confidence >= 0.8
    assert result.local_rainfall_claimed is False
    assert result.evidence["measuredRainfall"] is True


def test_no_rainfall_and_no_anomaly_returns_low_probability() -> None:
    result = score_rain_influence(
        RainInfluenceInput(
            measured_rainfall=False,
            track_temp_drop_celsius=0.2,
            cross_driver_variance_kmh=0.6,
            high_speed_corner_speed_loss_kmh=0.8,
            anomalous_driver_count=0,
        )
    )

    assert result.rain_influence_probability == pytest.approx(0.0)
    assert result.is_rain_influence_likely is False
    assert result.confidence <= 0.5
    assert result.evidence["crossDriverConfirmed"] is False


def test_one_driver_anomaly_is_low_confidence() -> None:
    result = score_rain_influence(
        RainInfluenceInput(
            measured_rainfall=False,
            track_temp_drop_celsius=3.5,
            cross_driver_variance_kmh=3.8,
            high_speed_corner_speed_loss_kmh=6.2,
            anomalous_driver_count=1,
        )
    )

    assert result.rain_influence_probability > 0.0
    assert result.confidence <= 0.65
    assert result.evidence["crossDriverConfirmed"] is False


def test_multi_driver_variance_allows_high_confidence() -> None:
    result = score_rain_influence(
        RainInfluenceInput(
            measured_rainfall=False,
            track_temp_drop_celsius=3.5,
            cross_driver_variance_kmh=4.3,
            high_speed_corner_speed_loss_kmh=6.2,
            anomalous_driver_count=4,
        )
    )

    assert result.rain_influence_probability >= 0.6
    assert result.confidence >= 0.8
    assert result.evidence["crossDriverConfirmed"] is True