const COLD_TEMP_C = 20;
const MID_TEMP_C = 40;
const HOT_TEMP_C = 60;

const COLD_RGB = [0, 102, 255];
const MID_RGB = [255, 255, 0];
const HOT_RGB = [255, 0, 0];
const UNKNOWN_TRACK_TEMP_COLOR = '#7d8797';

function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

function normalizeNumber(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null;
  }

  return value;
}

function lerp(start, end, progress) {
  return start + (end - start) * progress;
}

function interpolateRgb(startRgb, endRgb, progress) {
  const safeProgress = clamp01(progress);

  return [
    Math.round(lerp(startRgb[0], endRgb[0], safeProgress)),
    Math.round(lerp(startRgb[1], endRgb[1], safeProgress)),
    Math.round(lerp(startRgb[2], endRgb[2], safeProgress))
  ];
}

function componentToHex(component) {
  return component.toString(16).padStart(2, '0');
}

function rgbToHex(rgb) {
  return `#${componentToHex(rgb[0])}${componentToHex(rgb[1])}${componentToHex(rgb[2])}`;
}

export function resolveTrackTemperatureC(segmentState, globalTrackTemperatureC) {
  const measuredTrackTempC = normalizeNumber(segmentState?.measured?.track_temperature_c);
  if (measuredTrackTempC != null) {
    return {
      valueC: measuredTrackTempC,
      source: 'measured_segment'
    };
  }

  const fallbackTrackTempC = normalizeNumber(globalTrackTemperatureC);
  if (fallbackTrackTempC != null) {
    return {
      valueC: fallbackTrackTempC,
      source: 'fallback_weather'
    };
  }

  return {
    valueC: null,
    source: 'unknown'
  };
}

export function getTrackTemperatureColor(trackTemperatureC) {
  const normalizedTrackTemperatureC = normalizeNumber(trackTemperatureC);
  if (normalizedTrackTemperatureC == null) {
    return UNKNOWN_TRACK_TEMP_COLOR;
  }

  if (normalizedTrackTemperatureC <= COLD_TEMP_C) {
    return rgbToHex(COLD_RGB);
  }

  if (normalizedTrackTemperatureC >= HOT_TEMP_C) {
    return rgbToHex(HOT_RGB);
  }

  if (normalizedTrackTemperatureC <= MID_TEMP_C) {
    const progress = (normalizedTrackTemperatureC - COLD_TEMP_C) / (MID_TEMP_C - COLD_TEMP_C);
    return rgbToHex(interpolateRgb(COLD_RGB, MID_RGB, progress));
  }

  const progress = (normalizedTrackTemperatureC - MID_TEMP_C) / (HOT_TEMP_C - MID_TEMP_C);
  return rgbToHex(interpolateRgb(MID_RGB, HOT_RGB, progress));
}

export function formatTrackTempTooltip(trackTemperatureC) {
  const normalizedTrackTemperatureC = normalizeNumber(trackTemperatureC);
  if (normalizedTrackTemperatureC == null) {
    return 'Track Temp: -- \u00B0C (measured)';
  }

  return `Track Temp: ${normalizedTrackTemperatureC.toFixed(1)} \u00B0C (measured)`;
}

export function TrackTempLayer({
  activeLayer,
  segments,
  segmentStateById,
  globalTrackTemperatureC,
  baseStrokeUnit
}) {
  if (activeLayer !== 'Track Temp') {
    return null;
  }

  const overlayStrokeWidth = Number((baseStrokeUnit * 1.1).toFixed(2));

  return (
    <g className="track-temp-overlay" aria-label="Track temperature layer (measured)">
      {segments.map((segment) => {
        const segmentState = segmentStateById.get(segment.segmentId);
        const trackTemp = resolveTrackTemperatureC(segmentState, globalTrackTemperatureC);
        const segmentPath = segment.path
          .map((point, idx) => `${idx === 0 ? 'M' : 'L'} ${point.x} ${point.y}`)
          .join(' ');

        return (
          <path
            key={`track-temp-${segment.segmentId}`}
            d={segmentPath}
            className="track-temp-path"
            fill="none"
            strokeLinecap="round"
            style={{
              stroke: getTrackTemperatureColor(trackTemp.valueC),
              strokeWidth: overlayStrokeWidth,
              opacity: trackTemp.valueC == null ? 0.35 : 0.9
            }}
            data-segment-id={segment.segmentId}
            data-track-temp-c={trackTemp.valueC == null ? 'unknown' : trackTemp.valueC.toFixed(1)}
            data-track-temp-source={trackTemp.source}
            aria-label={formatTrackTempTooltip(trackTemp.valueC)}
          />
        );
      })}
    </g>
  );
}