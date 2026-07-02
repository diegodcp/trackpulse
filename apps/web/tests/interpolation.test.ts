import { describe, it, expect } from 'vitest';
import { interpolateFrames, findFrameAtTime } from '../src/utils/interpolation';
import type { TimelineFrame } from '../src/types/timeline';

function makeCarFrame(overrides: Partial<{
  driver_number: number;
  x: number;
  y: number;
  speed: number | null;
  position: number | null;
  lap_number: number | null;
  name_acronym: string;
  team_colour: string;
}>) {
  return {
    driver_number: 1,
    x: 0,
    y: 0,
    speed: 200,
    position: 1,
    lap_number: 1,
    name_acronym: 'VER',
    team_colour: '3671C6',
    ...overrides,
  };
}

function makeFrame(
  cars: Array<Partial<{
    driver_number: number;
    x: number;
    y: number;
    speed: number | null;
    position: number | null;
    lap_number: number | null;
    name_acronym: string;
    team_colour: string;
  }>>,
  elapsedSeconds = 0,
): TimelineFrame {
  return {
    timestamp: '2023-03-05T15:00:00Z',
    elapsed_seconds: elapsedSeconds,
    cars: cars.map((c) => makeCarFrame(c)),
  };
}

function makeFrames(durationSeconds: number, hz: number): TimelineFrame[] {
  const totalFrames = Math.floor(durationSeconds * hz);
  const frames: TimelineFrame[] = [];
  for (let i = 0; i < totalFrames; i++) {
    frames.push({
      timestamp: `2023-03-05T15:00:${(i / hz).toFixed(3)}Z`,
      elapsed_seconds: i / hz,
      cars: [makeCarFrame({ driver_number: 1, x: i * 10, y: i * 5 })],
    });
  }
  return frames;
}

describe('interpolateFrames', () => {
  it('returns exact positions at t=0', () => {
    const before = makeFrame([{ driver_number: 1, x: 0, y: 0 }]);
    const after = makeFrame([{ driver_number: 1, x: 10, y: 10 }]);
    const result = interpolateFrames(before, after, 0);
    expect(result[0].x).toBe(0);
    expect(result[0].y).toBe(0);
  });

  it('returns exact positions at t=1', () => {
    const before = makeFrame([{ driver_number: 1, x: 0, y: 0 }]);
    const after = makeFrame([{ driver_number: 1, x: 10, y: 10 }]);
    const result = interpolateFrames(before, after, 1);
    expect(result[0].x).toBe(10);
    expect(result[0].y).toBe(10);
  });

  it('linearly interpolates at t=0.5', () => {
    const before = makeFrame([{ driver_number: 1, x: 0, y: 0 }]);
    const after = makeFrame([{ driver_number: 1, x: 10, y: 20 }]);
    const result = interpolateFrames(before, after, 0.5);
    expect(result[0].x).toBe(5);
    expect(result[0].y).toBe(10);
  });

  it('interpolates at arbitrary t value', () => {
    const before = makeFrame([{ driver_number: 1, x: 100, y: 200 }]);
    const after = makeFrame([{ driver_number: 1, x: 200, y: 400 }]);
    const result = interpolateFrames(before, after, 0.25);
    expect(result[0].x).toBe(125);
    expect(result[0].y).toBe(250);
  });

  it('marks DNF driver as inactive when t >= 0.5', () => {
    const before = makeFrame([{ driver_number: 1, x: 0, y: 0 }]);
    const after = makeFrame([]); // Driver gone
    const result = interpolateFrames(before, after, 0.8);
    expect(result[0].isActive).toBe(false);
  });

  it('marks DNF driver as active when t < 0.5', () => {
    const before = makeFrame([{ driver_number: 1, x: 0, y: 0 }]);
    const after = makeFrame([]); // Driver gone
    const result = interpolateFrames(before, after, 0.3);
    expect(result[0].isActive).toBe(true);
  });

  it('marks car with NaN positions as inactive', () => {
    const before = makeFrame([{ driver_number: 1, x: NaN, y: NaN }]);
    const after = makeFrame([{ driver_number: 1, x: NaN, y: NaN }]);
    const result = interpolateFrames(before, after, 0.5);
    expect(result[0].isActive).toBe(false);
  });

  it('snaps to valid position when before is invalid', () => {
    const before = makeFrame([{ driver_number: 1, x: NaN, y: NaN }]);
    const after = makeFrame([{ driver_number: 1, x: 50, y: 100 }]);
    const result = interpolateFrames(before, after, 0.5);
    expect(result[0].x).toBe(50);
    expect(result[0].y).toBe(100);
    expect(result[0].isActive).toBe(true);
  });

  it('handles 20 drivers simultaneously', () => {
    const cars = Array.from({ length: 20 }, (_, i) => ({
      driver_number: i + 1,
      x: i * 10,
      y: i * 5,
      name_acronym: `D${String(i).padStart(2, '0')}`,
    }));
    const before = makeFrame(cars);
    const after = makeFrame(cars.map((c) => ({ ...c, x: c.x + 5 })));
    const result = interpolateFrames(before, after, 0.5);
    expect(result).toHaveLength(20);
    expect(result[0].x).toBe(2.5);
    expect(result[19].x).toBe(192.5);
  });

  it('preserves metadata fields', () => {
    const before = makeFrame([{
      driver_number: 44,
      x: 0,
      y: 0,
      name_acronym: 'HAM',
      team_colour: '27F4D2',
      speed: 300,
      position: 2,
      lap_number: 15,
    }]);
    const after = makeFrame([{
      driver_number: 44,
      x: 10,
      y: 10,
      name_acronym: 'HAM',
      team_colour: '27F4D2',
      speed: 310,
      position: 1,
      lap_number: 16,
    }]);
    const result = interpolateFrames(before, after, 0.5);
    expect(result[0].name_acronym).toBe('HAM');
    expect(result[0].team_colour).toBe('27F4D2');
    expect(result[0].speed).toBe(310); // Uses latest speed
    expect(result[0].position).toBe(1); // Uses latest position
    expect(result[0].lap_number).toBe(16); // Uses latest lap
  });

  it('sets inPit to false for all cars', () => {
    const before = makeFrame([{ driver_number: 1, x: 0, y: 0 }]);
    const after = makeFrame([{ driver_number: 1, x: 10, y: 10 }]);
    const result = interpolateFrames(before, after, 0.5);
    expect(result[0].inPit).toBe(false);
  });
});

describe('findFrameAtTime', () => {
  it('returns first frame at time 0', () => {
    const frames = makeFrames(10, 4.0);
    const { frameIndex, t } = findFrameAtTime(frames, 0);
    expect(frameIndex).toBe(0);
    expect(t).toBe(0);
  });

  it('returns first frame for negative time', () => {
    const frames = makeFrames(10, 4.0);
    const { frameIndex, t } = findFrameAtTime(frames, -5);
    expect(frameIndex).toBe(0);
    expect(t).toBe(0);
  });

  it('returns last frame at time >= duration', () => {
    const frames = makeFrames(10, 4.0);
    const { frameIndex } = findFrameAtTime(frames, 15.0);
    expect(frameIndex).toBe(frames.length - 1);
  });

  it('interpolation factor is between 0 and 1', () => {
    const frames = makeFrames(10, 4.0);
    const { t } = findFrameAtTime(frames, 5.125);
    expect(t).toBeGreaterThanOrEqual(0);
    expect(t).toBeLessThanOrEqual(1);
  });

  it('binary search finds correct frame', () => {
    const frames = makeFrames(100, 4.0);
    const { frameIndex } = findFrameAtTime(frames, 50.0);
    expect(frames[frameIndex].elapsed_seconds).toBeLessThanOrEqual(50.0);
    expect(frames[frameIndex + 1].elapsed_seconds).toBeGreaterThan(50.0);
  });

  it('handles exact frame boundary', () => {
    const frames = makeFrames(10, 4.0);
    // Time exactly at a frame boundary (1.0s = frame index 4 at 4Hz)
    const { frameIndex, t } = findFrameAtTime(frames, 1.0);
    expect(frames[frameIndex].elapsed_seconds).toBeLessThanOrEqual(1.0);
    expect(t).toBeGreaterThanOrEqual(0);
    expect(t).toBeLessThanOrEqual(1);
  });

  it('handles empty frames array', () => {
    const { frameIndex, t } = findFrameAtTime([], 5.0);
    expect(frameIndex).toBe(0);
    expect(t).toBe(0);
  });

  it('handles single frame', () => {
    const frames = makeFrames(0.25, 4.0); // 1 frame
    const { frameIndex, t } = findFrameAtTime(frames, 0);
    expect(frameIndex).toBe(0);
    expect(t).toBe(0);
  });
});
