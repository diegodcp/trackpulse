import { describe, it, expect, beforeEach } from 'vitest';
import { RingBuffer } from '../src/workers/ringBuffer';

interface TestFrame {
  elapsed: number;
  value: number;
}

describe('RingBuffer', () => {
  let buffer: RingBuffer<TestFrame>;

  beforeEach(() => {
    buffer = new RingBuffer<TestFrame>(5);
  });

  it('starts empty', () => {
    expect(buffer.size).toBe(0);
    expect(buffer.latest()).toBeNull();
    expect(buffer.toSortedArray()).toEqual([]);
  });

  it('push increases size up to capacity', () => {
    buffer.push({ elapsed: 0, value: 1 });
    expect(buffer.size).toBe(1);

    buffer.push({ elapsed: 1, value: 2 });
    buffer.push({ elapsed: 2, value: 3 });
    buffer.push({ elapsed: 3, value: 4 });
    buffer.push({ elapsed: 4, value: 5 });
    expect(buffer.size).toBe(5);

    // Overflow — size stays at capacity
    buffer.push({ elapsed: 5, value: 6 });
    expect(buffer.size).toBe(5);
  });

  it('overwrites oldest items when full', () => {
    for (let i = 0; i < 7; i++) {
      buffer.push({ elapsed: i, value: i * 10 });
    }

    const sorted = buffer.toSortedArray();
    expect(sorted.length).toBe(5);
    // Should contain frames 2-6 (oldest 0,1 overwritten)
    expect(sorted[0].elapsed).toBe(2);
    expect(sorted[4].elapsed).toBe(6);
  });

  it('latest returns the most recently pushed item', () => {
    buffer.push({ elapsed: 0, value: 100 });
    buffer.push({ elapsed: 1, value: 200 });
    buffer.push({ elapsed: 2, value: 300 });

    expect(buffer.latest()).toEqual({ elapsed: 2, value: 300 });
  });

  it('clear resets the buffer', () => {
    buffer.push({ elapsed: 0, value: 1 });
    buffer.push({ elapsed: 1, value: 2 });

    buffer.clear();
    expect(buffer.size).toBe(0);
    expect(buffer.latest()).toBeNull();
    expect(buffer.toSortedArray()).toEqual([]);
  });

  it('toSortedArray returns items in elapsed order', () => {
    // Push out of order (ring wrapping can cause this)
    buffer.push({ elapsed: 3, value: 30 });
    buffer.push({ elapsed: 1, value: 10 });
    buffer.push({ elapsed: 2, value: 20 });

    const sorted = buffer.toSortedArray();
    expect(sorted.map((f) => f.elapsed)).toEqual([1, 2, 3]);
  });

  describe('findSurrounding', () => {
    it('returns nulls for empty buffer', () => {
      const result = buffer.findSurrounding(5.0);
      expect(result.before).toBeNull();
      expect(result.after).toBeNull();
      expect(result.t).toBe(0);
    });

    it('finds exact match frame', () => {
      buffer.push({ elapsed: 0, value: 1 });
      buffer.push({ elapsed: 1, value: 2 });
      buffer.push({ elapsed: 2, value: 3 });

      const result = buffer.findSurrounding(1.0);
      expect(result.before!.elapsed).toBe(1);
      expect(result.after!.elapsed).toBe(2);
      expect(result.t).toBe(0);
    });

    it('interpolates between frames', () => {
      buffer.push({ elapsed: 0, value: 1 });
      buffer.push({ elapsed: 2, value: 2 });

      const result = buffer.findSurrounding(1.0);
      expect(result.before!.elapsed).toBe(0);
      expect(result.after!.elapsed).toBe(2);
      expect(result.t).toBeCloseTo(0.5);
    });

    it('returns before=null when elapsed is before all frames', () => {
      buffer.push({ elapsed: 5, value: 1 });
      buffer.push({ elapsed: 10, value: 2 });

      const result = buffer.findSurrounding(2.0);
      expect(result.before).toBeNull();
      expect(result.after!.elapsed).toBe(5);
      expect(result.t).toBe(0);
    });

    it('returns after=null when elapsed is past all frames', () => {
      buffer.push({ elapsed: 0, value: 1 });
      buffer.push({ elapsed: 1, value: 2 });

      const result = buffer.findSurrounding(5.0);
      expect(result.before!.elapsed).toBe(1);
      expect(result.after).toBeNull();
      expect(result.t).toBe(0);
    });

    it('computes correct t factor', () => {
      buffer.push({ elapsed: 10, value: 100 });
      buffer.push({ elapsed: 20, value: 200 });

      const result = buffer.findSurrounding(15.0);
      expect(result.t).toBeCloseTo(0.5);

      const result2 = buffer.findSurrounding(12.0);
      expect(result2.t).toBeCloseTo(0.2);
    });
  });
});
