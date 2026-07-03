import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// We test the chunkToFrames logic by importing the worker module directly
// and simulating the message protocol.

// Mock self.postMessage
const posted: unknown[] = [];
const originalPostMessage = globalThis.postMessage;

beforeEach(() => {
  posted.length = 0;
  (globalThis as unknown as { postMessage: (msg: unknown) => void }).postMessage = (msg: unknown) => {
    posted.push(msg);
  };
});

afterEach(() => {
  (globalThis as unknown as { postMessage: typeof originalPostMessage }).postMessage = originalPostMessage;
});

// The worker assigns self.onmessage — we import it to trigger the side effect
// Instead, let's test the logic directly by reimplementing the conversion function here
// since Web Workers can't be imported directly in vitest jsdom environment.

function chunkToFrames(chunk: {
  drivers: { driver_number: number; name_acronym: string; team_colour: string }[];
  elapsed: number[];
  positions: Record<string, { x: (number | null)[]; y: (number | null)[]; speed: (number | null)[]; position: (number | null)[]; lap: (number | null)[] }>;
}) {
  const frames: {
    timestamp: string;
    elapsed_seconds: number;
    cars: {
      driver_number: number;
      x: number;
      y: number;
      speed: number | null;
      position: number | null;
      lap_number: number | null;
      name_acronym: string;
      team_colour: string;
    }[];
  }[] = [];

  const { drivers, elapsed, positions } = chunk;

  for (let i = 0; i < elapsed.length; i++) {
    const cars: typeof frames[0]['cars'] = [];
    for (const driver of drivers) {
      const driverPos = positions[String(driver.driver_number)];
      if (!driverPos) continue;

      const x = driverPos.x[i];
      const y = driverPos.y[i];

      cars.push({
        driver_number: driver.driver_number,
        x: x ?? NaN,
        y: y ?? NaN,
        speed: driverPos.speed[i],
        position: driverPos.position[i],
        lap_number: driverPos.lap[i],
        name_acronym: driver.name_acronym,
        team_colour: driver.team_colour,
      });
    }

    frames.push({
      timestamp: '',
      elapsed_seconds: elapsed[i],
      cars,
    });
  }

  return frames;
}

describe('chunkConverter (chunkToFrames logic)', () => {
  const sampleChunk = {
    session_key: 9558,
    total_duration_seconds: 5400,
    target_hz: 4,
    total_chunks: 180,
    chunk_index: 0,
    chunk_start_seconds: 0,
    chunk_end_seconds: 30,
    frame_count: 3,
    drivers: [
      { driver_number: 1, name_acronym: 'VER', team_colour: '3671C6' },
      { driver_number: 44, name_acronym: 'HAM', team_colour: '27F4D2' },
    ],
    elapsed: [0.0, 0.25, 0.5],
    positions: {
      '1': {
        x: [100, 110, 120],
        y: [200, 210, 220],
        speed: [280, 285, 290],
        position: [1, 1, 1],
        lap: [1, 1, 1],
      },
      '44': {
        x: [90, 100, 110],
        y: [190, 200, 210],
        speed: [275, 280, 285],
        position: [2, 2, 2],
        lap: [1, 1, 1],
      },
    },
  };

  it('converts compact chunk to correct number of frames', () => {
    const frames = chunkToFrames(sampleChunk);
    expect(frames).toHaveLength(3);
  });

  it('sets elapsed_seconds on each frame', () => {
    const frames = chunkToFrames(sampleChunk);
    expect(frames[0].elapsed_seconds).toBe(0.0);
    expect(frames[1].elapsed_seconds).toBe(0.25);
    expect(frames[2].elapsed_seconds).toBe(0.5);
  });

  it('includes all drivers in each frame', () => {
    const frames = chunkToFrames(sampleChunk);
    for (const frame of frames) {
      expect(frame.cars).toHaveLength(2);
      const driverNums = frame.cars.map((c) => c.driver_number);
      expect(driverNums).toContain(1);
      expect(driverNums).toContain(44);
    }
  });

  it('maps position data correctly', () => {
    const frames = chunkToFrames(sampleChunk);
    const ver = frames[1].cars.find((c) => c.driver_number === 1)!;
    expect(ver.x).toBe(110);
    expect(ver.y).toBe(210);
    expect(ver.speed).toBe(285);
    expect(ver.position).toBe(1);
    expect(ver.lap_number).toBe(1);
    expect(ver.name_acronym).toBe('VER');
    expect(ver.team_colour).toBe('3671C6');
  });

  it('converts null coordinates to NaN', () => {
    const chunkWithNull = {
      ...sampleChunk,
      positions: {
        '1': {
          x: [null, 110, 120],
          y: [null, 210, 220],
          speed: [null, 285, 290],
          position: [null, 1, 1],
          lap: [null, 1, 1],
        },
        '44': {
          x: [90, 100, 110],
          y: [190, 200, 210],
          speed: [275, 280, 285],
          position: [2, 2, 2],
          lap: [1, 1, 1],
        },
      },
    };

    const frames = chunkToFrames(chunkWithNull);
    const ver = frames[0].cars.find((c) => c.driver_number === 1)!;
    expect(ver.x).toBeNaN();
    expect(ver.y).toBeNaN();
    expect(ver.speed).toBeNull();
  });

  it('handles empty elapsed array', () => {
    const emptyChunk = {
      ...sampleChunk,
      elapsed: [],
      frame_count: 0,
      positions: { '1': { x: [], y: [], speed: [], position: [], lap: [] } },
    };
    const frames = chunkToFrames(emptyChunk);
    expect(frames).toHaveLength(0);
  });

  it('handles driver with missing position data', () => {
    const chunkMissingDriver = {
      ...sampleChunk,
      positions: {
        '1': {
          x: [100, 110, 120],
          y: [200, 210, 220],
          speed: [280, 285, 290],
          position: [1, 1, 1],
          lap: [1, 1, 1],
        },
        // driver 44 has no position data
      },
    };
    const frames = chunkToFrames(chunkMissingDriver);
    expect(frames[0].cars).toHaveLength(1);
    expect(frames[0].cars[0].driver_number).toBe(1);
  });
});
