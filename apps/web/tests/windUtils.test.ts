import { describe, it, expect } from 'vitest';
import {
  windIconRotation,
  windIntensity,
  windClassColor,
  windClassCSSColor,
  windClassLabel,
  segmentMidpointIndex,
} from '../src/utils/windUtils';

describe('windIconRotation', () => {
  it('north wind (from 0°) icon points south (180°)', () => {
    expect(windIconRotation(0)).toBe(180);
  });

  it('east wind (from 90°) icon points west (270°)', () => {
    expect(windIconRotation(90)).toBe(270);
  });

  it('south wind (from 180°) icon points north (0°)', () => {
    expect(windIconRotation(180)).toBe(0);
  });

  it('west wind (from 270°) icon points east (90°)', () => {
    expect(windIconRotation(270)).toBe(90);
  });

  it('wraps around correctly for 350°', () => {
    expect(windIconRotation(350)).toBe(170);
  });
});

describe('windIntensity', () => {
  it('0 speed = 0 intensity', () => {
    expect(windIntensity(0)).toBe(0);
  });

  it('5 m/s = 0.5 intensity (default max 10)', () => {
    expect(windIntensity(5)).toBe(0.5);
  });

  it('10 m/s = 1.0 intensity', () => {
    expect(windIntensity(10)).toBe(1.0);
  });

  it('above max is clamped to 1.0', () => {
    expect(windIntensity(15)).toBe(1.0);
  });

  it('respects custom maxSpeed', () => {
    expect(windIntensity(5, 20)).toBe(0.25);
  });
});

describe('windClassColor', () => {
  it('headwind is red', () => {
    expect(windClassColor('headwind')).toBe(0xff4444);
  });

  it('tailwind is green', () => {
    expect(windClassColor('tailwind')).toBe(0x44ff44);
  });

  it('crosswind_left is orange', () => {
    expect(windClassColor('crosswind_left')).toBe(0xffaa00);
  });

  it('crosswind_right is orange', () => {
    expect(windClassColor('crosswind_right')).toBe(0xffaa00);
  });
});

describe('windClassCSSColor', () => {
  it('headwind returns CSS red', () => {
    expect(windClassCSSColor('headwind')).toBe('#ff4444');
  });

  it('tailwind returns CSS green', () => {
    expect(windClassCSSColor('tailwind')).toBe('#44ff44');
  });
});

describe('windClassLabel', () => {
  it('headwind label', () => {
    expect(windClassLabel('headwind')).toBe('Headwind');
  });

  it('crosswind_left label', () => {
    expect(windClassLabel('crosswind_left')).toBe('Crosswind (L)');
  });

  it('crosswind_right label', () => {
    expect(windClassLabel('crosswind_right')).toBe('Crosswind (R)');
  });

  it('tailwind label', () => {
    expect(windClassLabel('tailwind')).toBe('Tailwind');
  });
});

describe('segmentMidpointIndex', () => {
  it('computes midpoint of a segment', () => {
    expect(segmentMidpointIndex(0, 100)).toBe(50);
  });

  it('rounds down for odd ranges', () => {
    expect(segmentMidpointIndex(0, 99)).toBe(49);
  });

  it('handles same start and end', () => {
    expect(segmentMidpointIndex(50, 50)).toBe(50);
  });
});
