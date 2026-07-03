import { describe, it, expect } from 'vitest';
import { lerpFrames } from '../src/workers/timeline.worker';
import type { StreamFrame } from '../src/workers/types';

describe('lerpFrames', () => {
  const frameBefore: StreamFrame = {
    type: 'frame',
    elapsed: 0,
    cars: {
      '1': { x: 0, y: 0, s: 200, p: 1, l: 5 },
      '44': { x: 10, y: 20, s: 180, p: 2, l: 5 },
    },
  };

  const frameAfter: StreamFrame = {
    type: 'frame',
    elapsed: 1,
    cars: {
      '1': { x: 100, y: 50, s: 220, p: 1, l: 5 },
      '44': { x: 110, y: 70, s: 190, p: 2, l: 5 },
    },
  };

  it('at t=0 returns before positions', () => {
    const cars = lerpFrames(frameBefore, frameAfter, 0);
    const car1 = cars.find((c) => c.driver_number === 1)!;
    expect(car1.x).toBe(0);
    expect(car1.y).toBe(0);
  });

  it('at t=1 returns after positions', () => {
    const cars = lerpFrames(frameBefore, frameAfter, 1);
    const car1 = cars.find((c) => c.driver_number === 1)!;
    expect(car1.x).toBe(100);
    expect(car1.y).toBe(50);
  });

  it('at t=0.5 returns midpoint positions', () => {
    const cars = lerpFrames(frameBefore, frameAfter, 0.5);
    const car1 = cars.find((c) => c.driver_number === 1)!;
    expect(car1.x).toBeCloseTo(50);
    expect(car1.y).toBeCloseTo(25);

    const car44 = cars.find((c) => c.driver_number === 44)!;
    expect(car44.x).toBeCloseTo(60);
    expect(car44.y).toBeCloseTo(45);
  });

  it('forward-fills discrete values from before frame', () => {
    const cars = lerpFrames(frameBefore, frameAfter, 0.5);
    const car1 = cars.find((c) => c.driver_number === 1)!;
    expect(car1.speed).toBe(200);
    expect(car1.position).toBe(1);
    expect(car1.lap_number).toBe(5);
  });

  it('handles driver appearing only in before frame', () => {
    const before: StreamFrame = {
      type: 'frame',
      elapsed: 0,
      cars: { '1': { x: 0, y: 0, s: 200, p: 1, l: 5 } },
    };
    const after: StreamFrame = {
      type: 'frame',
      elapsed: 1,
      cars: {},
    };

    const cars = lerpFrames(before, after, 0.5);
    expect(cars.length).toBe(1);
    expect(cars[0].driver_number).toBe(1);
    expect(cars[0].x).toBe(0);
  });

  it('handles driver appearing only in after frame', () => {
    const before: StreamFrame = {
      type: 'frame',
      elapsed: 0,
      cars: {},
    };
    const after: StreamFrame = {
      type: 'frame',
      elapsed: 1,
      cars: { '1': { x: 100, y: 50, s: 220, p: 1, l: 5 } },
    };

    const cars = lerpFrames(before, after, 0.5);
    expect(cars.length).toBe(1);
    expect(cars[0].driver_number).toBe(1);
    expect(cars[0].x).toBe(100);
  });

  it('marks all cars as active', () => {
    const cars = lerpFrames(frameBefore, frameAfter, 0.5);
    expect(cars.every((c) => c.isActive)).toBe(true);
  });
});
