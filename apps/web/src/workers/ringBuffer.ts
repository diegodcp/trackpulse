/**
 * Ring buffer for frame windowing — stores a fixed-capacity rolling window
 * of time-stamped frames. Used by the timeline worker to hold recent frames
 * for interpolation without accumulating unbounded memory.
 */

export interface Timestamped {
  elapsed: number;
}

export class RingBuffer<T extends Timestamped> {
  private buffer: (T | null)[];
  private head = 0;
  private _size = 0;

  constructor(private capacity: number) {
    this.buffer = new Array<T | null>(capacity).fill(null);
  }

  /** Number of items currently in the buffer. */
  get size(): number {
    return this._size;
  }

  /** Push an item into the ring buffer, overwriting the oldest if full. */
  push(item: T): void {
    this.buffer[this.head] = item;
    this.head = (this.head + 1) % this.capacity;
    this._size = Math.min(this._size + 1, this.capacity);
  }

  /** Clear all items from the buffer. */
  clear(): void {
    this.buffer.fill(null);
    this.head = 0;
    this._size = 0;
  }

  /**
   * Find the two frames surrounding a given elapsed time.
   * Returns the frame before, frame after, and interpolation factor t ∈ [0, 1].
   */
  findSurrounding(elapsed: number): { before: T | null; after: T | null; t: number } {
    const sorted = this.toSortedArray();
    if (sorted.length === 0) {
      return { before: null, after: null, t: 0 };
    }

    // Binary search for insertion point
    let lo = 0;
    let hi = sorted.length - 1;

    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (sorted[mid].elapsed <= elapsed) {
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }

    const before = hi >= 0 ? sorted[hi] : null;
    const after = lo < sorted.length ? sorted[lo] : null;

    if (!before || !after) {
      return { before, after, t: 0 };
    }

    const range = after.elapsed - before.elapsed;
    const t = range > 0 ? (elapsed - before.elapsed) / range : 0;
    return { before, after, t };
  }

  /** Get the most recently pushed item. */
  latest(): T | null {
    if (this._size === 0) return null;
    const idx = (this.head - 1 + this.capacity) % this.capacity;
    return this.buffer[idx];
  }

  /** Return all non-null items sorted by elapsed time. */
  toSortedArray(): T[] {
    const items: T[] = [];
    for (let i = 0; i < this._size; i++) {
      const idx = (this.head - this._size + i + this.capacity) % this.capacity;
      const item = this.buffer[idx];
      if (item !== null) {
        items.push(item);
      }
    }
    return items.sort((a, b) => a.elapsed - b.elapsed);
  }
}
