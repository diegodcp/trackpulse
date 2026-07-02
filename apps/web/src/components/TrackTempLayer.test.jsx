import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  TrackTempLayer,
  formatTrackTempTooltip,
  getTrackTemperatureColor,
  resolveTrackTemperatureC
} from './TrackTempLayer';

describe('MVP-0301 TrackTempLayer', () => {
  it('interpolates heat-map colors across the configured temperature scale', () => {
    expect(getTrackTemperatureColor(15)).toBe('#0066ff');
    expect(getTrackTemperatureColor(20)).toBe('#0066ff');
    expect(getTrackTemperatureColor(30)).toBe('#80b380');
    expect(getTrackTemperatureColor(40)).toBe('#ffff00');
    expect(getTrackTemperatureColor(50)).toBe('#ff8000');
    expect(getTrackTemperatureColor(60)).toBe('#ff0000');
    expect(getTrackTemperatureColor(70)).toBe('#ff0000');
  });

  it('falls back to global measured weather track temperature when segment measured value is missing', () => {
    expect(resolveTrackTemperatureC({}, 37.4)).toEqual({
      valueC: 37.4,
      source: 'fallback_weather'
    });
  });

  it('prefers measured segment track temperature over global weather fallback', () => {
    expect(
      resolveTrackTemperatureC(
        {
          measured: {
            track_temperature_c: 44.2
          }
        },
        32.1
      )
    ).toEqual({
      valueC: 44.2,
      source: 'measured_segment'
    });
  });

  it('formats tooltip text with measured truth label', () => {
    expect(formatTrackTempTooltip(39.94)).toBe('Track Temp: 39.9 \u00B0C (measured)');
    expect(formatTrackTempTooltip(null)).toBe('Track Temp: -- \u00B0C (measured)');
  });

  it('renders fallback temperature metadata per segment while Track Temp layer is active', () => {
    const segments = [
      {
        segmentId: 'bh-s01',
        path: [
          { x: 10, y: 10 },
          { x: 20, y: 20 }
        ]
      }
    ];

    const { container } = render(
      <svg>
        <TrackTempLayer
          activeLayer="Track Temp"
          segments={segments}
          segmentStateById={new Map()}
          globalTrackTemperatureC={38.2}
          baseStrokeUnit={10}
        />
      </svg>
    );

    const overlayPath = container.querySelector('.track-temp-path');
    expect(overlayPath).toHaveAttribute('data-track-temp-c', '38.2');
    expect(overlayPath).toHaveAttribute('data-track-temp-source', 'fallback_weather');
    expect(overlayPath).toHaveAttribute('aria-label', 'Track Temp: 38.2 \u00B0C (measured)');
  });
});