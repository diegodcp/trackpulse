/**
 * Wind visualization utilities — pure functions for rendering wind overlays.
 */

import type { CircuitGeometry } from '../types/circuit';

export type WindClass = 'headwind' | 'tailwind' | 'crosswind_left' | 'crosswind_right';

export interface SegmentWind {
  segment_id: number;
  wind_class: WindClass;
  effective_speed: number;
  headwind_component: number;
  crosswind_component: number;
}

/**
 * Get wind icon rotation angle for visual display.
 * Wind icon points in the direction wind is GOING (opposite of meteorological "from").
 *
 * @param windFromDegrees - Meteorological wind direction (where wind comes FROM, 0-359°)
 * @returns Rotation angle in degrees for the wind icon
 */
export function windIconRotation(windFromDegrees: number): number {
  return (windFromDegrees + 180) % 360;
}

/**
 * Map wind effective speed to visual intensity (0-1).
 * Used for scaling icon size and opacity.
 *
 * @param effectiveSpeed - Wind component magnitude in m/s
 * @param maxSpeed - Speed that maps to 1.0 intensity (default 10 m/s)
 * @returns Normalized intensity between 0 and 1
 */
export function windIntensity(effectiveSpeed: number, maxSpeed: number = 10): number {
  return Math.min(effectiveSpeed / maxSpeed, 1.0);
}

/**
 * Map wind class to display color (hex number for Pixi.js).
 */
export function windClassColor(windClass: WindClass): number {
  switch (windClass) {
    case 'headwind':
      return 0xff4444; // Red (opposing — performance penalty)
    case 'tailwind':
      return 0x44ff44; // Green (assisting — DRS-like benefit)
    case 'crosswind_left':
      return 0xffaa00; // Orange (lateral — instability risk)
    case 'crosswind_right':
      return 0xffaa00; // Orange
    default:
      return 0x888888;
  }
}

/**
 * Map wind class to CSS color string.
 */
export function windClassCSSColor(windClass: WindClass): string {
  switch (windClass) {
    case 'headwind':
      return '#ff4444';
    case 'tailwind':
      return '#44ff44';
    case 'crosswind_left':
      return '#ffaa00';
    case 'crosswind_right':
      return '#ffaa00';
    default:
      return '#888888';
  }
}

/**
 * Get human-readable label for a wind class.
 */
export function windClassLabel(windClass: WindClass): string {
  switch (windClass) {
    case 'headwind':
      return 'Headwind';
    case 'tailwind':
      return 'Tailwind';
    case 'crosswind_left':
      return 'Crosswind (L)';
    case 'crosswind_right':
      return 'Crosswind (R)';
    default:
      return 'Unknown';
  }
}

/**
 * Compute the midpoint index for a segment in the circuit points array.
 */
export function segmentMidpointIndex(startIdx: number, endIdx: number): number {
  return Math.floor((startIdx + endIdx) / 2);
}

// --- Client-side wind derivation (mirrors backend pure function) ---

/**
 * Compute signed angle difference normalized to [-180, 180].
 */
function angleDifference(fromDeg: number, toDeg: number): number {
  return ((fromDeg - toDeg + 180) % 360 + 360) % 360 - 180;
}

/**
 * Compute track heading at a given point index.
 * Returns heading in degrees (0-360, 0=North, 90=East).
 */
function computeTrackHeading(
  points: { x: number; y: number }[],
  idx: number,
  lookahead: number = 5,
): number {
  let nextIdx = Math.min(idx + lookahead, points.length - 1);
  let dx: number;
  let dy: number;

  if (nextIdx === idx) {
    const prevIdx = Math.max(idx - lookahead, 0);
    dx = points[idx].x - points[prevIdx].x;
    dy = points[idx].y - points[prevIdx].y;
  } else {
    dx = points[nextIdx].x - points[idx].x;
    dy = points[nextIdx].y - points[idx].y;
  }

  // atan2(dx, dy) gives angle from North (Y-axis), clockwise positive
  const angleRad = Math.atan2(dx, dy);
  return ((angleRad * 180) / Math.PI + 360) % 360;
}

/**
 * Derive per-segment wind characteristics from global wind + circuit geometry.
 * This is the client-side equivalent of the backend `derive_segment_wind()`.
 *
 * Used as fallback when the backend doesn't include segment_wind in responses
 * (e.g. when circuit geometry isn't stored in the DB yet).
 */
export function deriveSegmentWind(
  windSpeed: number,
  windDirection: number,
  geometry: CircuitGeometry,
): SegmentWind[] {
  const results: SegmentWind[] = [];

  for (const segment of geometry.segments) {
    const midIdx = Math.floor((segment.start_idx + segment.end_idx) / 2);
    const heading = computeTrackHeading(geometry.points, midIdx);

    // Relative angle: wind_from - track_heading
    const relative = angleDifference(windDirection, heading);

    // Decompose into head/cross components
    const relRad = (relative * Math.PI) / 180;
    const headwind = windSpeed * Math.cos(relRad);
    const crosswind = windSpeed * Math.sin(relRad);

    // Classify
    const absRelative = Math.abs(relative);
    let windClass: WindClass;
    if (absRelative <= 45) {
      windClass = 'headwind';
    } else if (absRelative >= 135) {
      windClass = 'tailwind';
    } else if (relative > 0) {
      windClass = 'crosswind_right';
    } else {
      windClass = 'crosswind_left';
    }

    const effectiveSpeed =
      absRelative <= 45 || absRelative >= 135
        ? Math.abs(headwind)
        : Math.abs(crosswind);

    results.push({
      segment_id: segment.id,
      wind_class: windClass,
      effective_speed: Math.round(effectiveSpeed * 1000) / 1000,
      headwind_component: Math.round(headwind * 1000) / 1000,
      crosswind_component: Math.round(crosswind * 1000) / 1000,
    });
  }

  return results;
}
