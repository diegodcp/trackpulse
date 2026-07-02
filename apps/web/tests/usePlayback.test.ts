import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlayback, VALID_SPEEDS } from '../src/hooks/usePlayback';

// Mock requestAnimationFrame for controlled testing
beforeEach(() => {
  vi.restoreAllMocks();
});

const mockTimeline = {
  isReady: true,
  isLoading: false,
  durationSeconds: 5520,
};

describe('usePlayback', () => {
  it('starts in idle state with no timeline', () => {
    const { result } = renderHook(() => usePlayback(null, vi.fn()));
    expect(result.current.state).toBe('idle');
  });

  it('transitions to paused when timeline loads', () => {
    const { result, rerender } = renderHook(
      ({ timeline }) => usePlayback(timeline, vi.fn()),
      { initialProps: { timeline: null as typeof mockTimeline | null } },
    );
    expect(result.current.state).toBe('idle');

    rerender({ timeline: mockTimeline });
    expect(result.current.state).toBe('paused');
  });

  it('shows loading state when timeline is loading', () => {
    const { result } = renderHook(() =>
      usePlayback({ isReady: false, isLoading: true, durationSeconds: 0 }, vi.fn()),
    );
    expect(result.current.state).toBe('loading');
  });

  it('play() transitions from paused to playing', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline, vi.fn()));
    act(() => result.current.play());
    expect(result.current.state).toBe('playing');
  });

  it('pause() transitions from playing to paused', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline, vi.fn()));
    act(() => result.current.play());
    act(() => result.current.pause());
    expect(result.current.state).toBe('paused');
  });

  it('play() does nothing in idle state', () => {
    const { result } = renderHook(() => usePlayback(null, vi.fn()));
    act(() => result.current.play());
    expect(result.current.state).toBe('idle');
  });

  it('pause() does nothing in paused state', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline, vi.fn()));
    act(() => result.current.pause());
    expect(result.current.state).toBe('paused');
  });

  it('seekTo clamps to [0, duration]', () => {
    const onUpdate = vi.fn();
    const { result } = renderHook(() => usePlayback(mockTimeline, onUpdate));

    act(() => result.current.seekTo(-10));
    expect(onUpdate).toHaveBeenCalledWith(0);
    expect(result.current.currentTime).toBe(0);

    act(() => result.current.seekTo(99999));
    expect(onUpdate).toHaveBeenCalledWith(mockTimeline.durationSeconds);
    expect(result.current.currentTime).toBe(mockTimeline.durationSeconds);
  });

  it('seekTo sets time within bounds', () => {
    const onUpdate = vi.fn();
    const { result } = renderHook(() => usePlayback(mockTimeline, onUpdate));

    act(() => result.current.seekTo(100));
    expect(onUpdate).toHaveBeenCalledWith(100);
    expect(result.current.currentTime).toBe(100);
  });

  it('seekRelative adjusts from current time', () => {
    const onUpdate = vi.fn();
    const { result } = renderHook(() => usePlayback(mockTimeline, onUpdate));

    act(() => result.current.seekTo(50));
    act(() => result.current.seekRelative(5));
    expect(result.current.currentTime).toBe(55);

    act(() => result.current.seekRelative(-10));
    expect(result.current.currentTime).toBe(45);
  });

  it('setSpeed only accepts valid speeds', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline, vi.fn()));
    act(() => result.current.setSpeed(5));
    expect(result.current.speed).toBe(5);

    act(() => result.current.setSpeed(7)); // Invalid
    expect(result.current.speed).toBe(5); // Unchanged
  });

  it('setSpeed accepts all valid speeds', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline, vi.fn()));
    for (const s of VALID_SPEEDS) {
      act(() => result.current.setSpeed(s));
      expect(result.current.speed).toBe(s);
    }
  });

  it('duration reflects timeline duration', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline, vi.fn()));
    expect(result.current.duration).toBe(5520);
  });

  it('duration is 0 when no timeline', () => {
    const { result } = renderHook(() => usePlayback(null, vi.fn()));
    expect(result.current.duration).toBe(0);
  });
});
