import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useStreamingTimeline } from '../src/hooks/useStreamingTimeline';

// --- Mock Worker ---

let mockWorkerInstance: MockWorker | null = null;

class MockWorker {
  onmessage: ((e: MessageEvent) => void) | null = null;
  posted: unknown[] = [];
  terminated = false;

  postMessage(msg: unknown) {
    this.posted.push(msg);
  }

  terminate() {
    this.terminated = true;
  }

  /** Simulate a message from the worker to the main thread. */
  simulateMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage({ data } as MessageEvent);
    }
  }
}

beforeEach(() => {
  mockWorkerInstance = null;
  // Mock the Worker constructor globally
  vi.stubGlobal(
    'Worker',
    class {
      onmessage: ((e: MessageEvent) => void) | null = null;
      posted: unknown[] = [];
      terminated = false;

      constructor() {
        mockWorkerInstance = this as unknown as MockWorker;
      }

      postMessage(msg: unknown) {
        this.posted.push(msg);
      }

      terminate() {
        this.terminated = true;
      }
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function getWorker(): MockWorker {
  if (!mockWorkerInstance) throw new Error('Worker not instantiated');
  return mockWorkerInstance;
}

describe('useStreamingTimeline', () => {
  it('does not create a worker when sessionKey is null', () => {
    renderHook(() => useStreamingTimeline({ sessionKey: null }));
    expect(mockWorkerInstance).toBeNull();
  });

  it('does not create a worker when enabled is false', () => {
    renderHook(() => useStreamingTimeline({ sessionKey: 9558, enabled: false }));
    expect(mockWorkerInstance).toBeNull();
  });

  it('creates worker and sends connect message on mount', () => {
    renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558, hz: 4, speed: 2 }),
    );

    const worker = getWorker();
    expect(worker.posted).toHaveLength(1);
    expect(worker.posted[0]).toEqual({
      type: 'connect',
      payload: { sessionKey: 9558, hz: 4, speed: 2 },
    });
  });

  it('terminates worker and sends disconnect on unmount', () => {
    const { unmount } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    unmount();

    expect(worker.posted).toContainEqual({ type: 'disconnect' });
    expect(worker.terminated).toBe(true);
  });

  it('updates carsRef and currentElapsed on tick messages', () => {
    const { result } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    const cars = [
      { driver_number: 1, x: 100, y: 200, speed: 300, position: 1, lap_number: 5, isActive: true },
    ];

    act(() => {
      worker.onmessage!({ data: { type: 'tick', elapsed: 42.5, cars } } as MessageEvent);
    });

    expect(result.current.currentElapsed.current).toBe(42.5);
    expect(result.current.carsRef.current).toEqual(cars);
  });

  it('sets isConnected to true on connected message', () => {
    const { result } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    expect(result.current.isConnected).toBe(false);

    act(() => {
      worker.onmessage!({ data: { type: 'connected' } } as MessageEvent);
    });

    expect(result.current.isConnected).toBe(true);
  });

  it('sets isEnded to true on end message', () => {
    const { result } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    expect(result.current.isEnded).toBe(false);

    act(() => {
      worker.onmessage!({ data: { type: 'end' } } as MessageEvent);
    });

    expect(result.current.isEnded).toBe(true);
  });

  it('sets isConnected to false on disconnected message', () => {
    const { result } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    act(() => {
      worker.onmessage!({ data: { type: 'connected' } } as MessageEvent);
    });
    expect(result.current.isConnected).toBe(true);

    act(() => {
      worker.onmessage!({ data: { type: 'disconnected' } } as MessageEvent);
    });
    expect(result.current.isConnected).toBe(false);
  });

  it('seek() posts seek message and updates currentElapsed', () => {
    const { result } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    act(() => {
      result.current.seek(120.5);
    });

    expect(worker.posted).toContainEqual({
      type: 'seek',
      payload: { elapsed: 120.5 },
    });
    expect(result.current.currentElapsed.current).toBe(120.5);
  });

  it('setSpeed() posts speed message', () => {
    const { result } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    act(() => {
      result.current.setSpeed(5);
    });

    expect(worker.posted).toContainEqual({
      type: 'speed',
      payload: { value: 5 },
    });
  });

  it('pause() posts pause message', () => {
    const { result } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    act(() => {
      result.current.pause();
    });

    expect(worker.posted).toContainEqual({ type: 'pause' });
  });

  it('resume() posts resume message', () => {
    const { result } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    act(() => {
      result.current.resume();
    });

    expect(worker.posted).toContainEqual({ type: 'resume' });
  });

  it('disconnect() posts disconnect message', () => {
    const { result } = renderHook(() =>
      useStreamingTimeline({ sessionKey: 9558 }),
    );
    const worker = getWorker();

    act(() => {
      result.current.disconnect();
    });

    expect(worker.posted).toContainEqual({ type: 'disconnect' });
  });

  it('recreates worker when sessionKey changes', () => {
    const { rerender } = renderHook(
      ({ sessionKey }) => useStreamingTimeline({ sessionKey }),
      { initialProps: { sessionKey: 9558 as number | null } },
    );
    const firstWorker = getWorker();

    rerender({ sessionKey: 9559 });

    // First worker should be terminated
    expect(firstWorker.terminated).toBe(true);
    // New worker should have been created and sent connect
    const secondWorker = getWorker();
    expect(secondWorker).not.toBe(firstWorker);
    expect(secondWorker.posted).toContainEqual({
      type: 'connect',
      payload: { sessionKey: 9559, hz: 4, speed: 1 },
    });
  });
});
