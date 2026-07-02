import type { CarFrame, TimelineFrame } from '../types/timeline';

export interface InterpolatedCar {
  driver_number: number;
  x: number;
  y: number;
  speed: number | null;
  position: number | null;
  lap_number: number | null;
  name_acronym: string;
  team_colour: string;
  isActive: boolean;
  inPit: boolean;
}

/**
 * Linearly interpolate car positions between two timeline frames.
 *
 * @param frameBefore - The frame at or before current time
 * @param frameAfter - The frame at or after current time
 * @param t - Interpolation factor [0.0, 1.0] where 0 = frameBefore, 1 = frameAfter
 * @returns Array of interpolated car positions
 */
export function interpolateFrames(
  frameBefore: TimelineFrame,
  frameAfter: TimelineFrame,
  t: number,
): InterpolatedCar[] {
  const result: InterpolatedCar[] = [];

  for (const carBefore of frameBefore.cars) {
    const carAfter = frameAfter.cars.find(
      (c) => c.driver_number === carBefore.driver_number,
    );

    if (!carAfter) {
      // Driver not in next frame (DNF between frames)
      result.push({
        ...carBefore,
        speed: carBefore.speed,
        position: carBefore.position,
        lap_number: carBefore.lap_number,
        isActive: t < 0.5,
        inPit: false,
      });
      continue;
    }

    // Check for NaN/Infinity (invalid positions)
    const beforeValid = isFinite(carBefore.x) && isFinite(carBefore.y);
    const afterValid = isFinite(carAfter.x) && isFinite(carAfter.y);

    if (!beforeValid && !afterValid) {
      result.push({
        driver_number: carBefore.driver_number,
        x: carBefore.x,
        y: carBefore.y,
        speed: carBefore.speed,
        position: carBefore.position,
        lap_number: carBefore.lap_number,
        name_acronym: carBefore.name_acronym,
        team_colour: carBefore.team_colour,
        isActive: false,
        inPit: false,
      });
      continue;
    }

    // If only one is valid, snap to the valid position
    if (!beforeValid) {
      result.push({
        driver_number: carAfter.driver_number,
        x: carAfter.x,
        y: carAfter.y,
        speed: carAfter.speed,
        position: carAfter.position,
        lap_number: carAfter.lap_number,
        name_acronym: carAfter.name_acronym,
        team_colour: carAfter.team_colour,
        isActive: true,
        inPit: false,
      });
      continue;
    }

    if (!afterValid) {
      result.push({
        driver_number: carBefore.driver_number,
        x: carBefore.x,
        y: carBefore.y,
        speed: carBefore.speed,
        position: carBefore.position,
        lap_number: carBefore.lap_number,
        name_acronym: carBefore.name_acronym,
        team_colour: carBefore.team_colour,
        isActive: t < 0.5,
        inPit: false,
      });
      continue;
    }

    // Linear interpolation
    const x = lerp(carBefore.x, carAfter.x, t);
    const y = lerp(carBefore.y, carAfter.y, t);

    result.push({
      driver_number: carBefore.driver_number,
      x,
      y,
      speed: carAfter.speed,
      position: carAfter.position,
      lap_number: carAfter.lap_number,
      name_acronym: carBefore.name_acronym,
      team_colour: carBefore.team_colour,
      isActive: true,
      inPit: false,
    });
  }

  return result;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Find the two frames surrounding a given elapsed time.
 * Returns the index of the frame before and the interpolation factor.
 */
export function findFrameAtTime(
  frames: TimelineFrame[],
  elapsedSeconds: number,
): { frameIndex: number; t: number } {
  if (frames.length === 0) return { frameIndex: 0, t: 0 };
  if (elapsedSeconds <= 0) return { frameIndex: 0, t: 0 };
  if (elapsedSeconds >= frames[frames.length - 1].elapsed_seconds) {
    return { frameIndex: frames.length - 1, t: 0 };
  }

  // Binary search for the frame before current time
  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi - 1) {
    const mid = Math.floor((lo + hi) / 2);
    if (frames[mid].elapsed_seconds <= elapsedSeconds) lo = mid;
    else hi = mid;
  }

  const frameDuration =
    frames[hi].elapsed_seconds - frames[lo].elapsed_seconds;
  const t =
    frameDuration > 0
      ? (elapsedSeconds - frames[lo].elapsed_seconds) / frameDuration
      : 0;

  return { frameIndex: lo, t };
}
