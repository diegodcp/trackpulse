import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { usePlayback, VALID_SPEEDS } from '../src/hooks/usePlayback';

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
    const { result } = renderHook(() => usePlayback(null));
    expect(result.current.state).toBe('idle');
  });

  it('transitions to playing when timeline loads (auto-play)', () => {
    const { result, rerender } = renderHook(
      ({ timeline }) => usePlayback(timeline),
      { initialProps: { timeline: null as typeof mockTimeline | null } },
    );
    expect(result.current.state).toBe('idle');

    rerender({ timeline: mockTimeline });
    expect(result.current.state).toBe('playing');
  });

  it('shows loading state when timeline is loading', () => {
    const { result } = renderHook(() =>
      usePlayback({ isReady: false, isLoading: true, durationSeconds: 0 }),
    );
    expect(result.current.state).toBe('loading');
  });

  it('pause() transitions from playing to paused', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));
    // auto-plays
    expect(result.current.state).toBe('playing');
    act(() => result.current.pause());
    expect(result.current.state).toBe('paused');
  });

  it('play() transitions from paused to playing', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));
    act(() => result.current.pause());
    expect(result.current.state).toBe('paused');
    act(() => result.current.play());
    expect(result.current.state).toBe('playing');
  });

  it('play() does nothing in idle state', () => {
    const { result } = renderHook(() => usePlayback(null));
    act(() => result.current.play());
    expect(result.current.state).toBe('idle');
  });

  it('pause() does nothing in paused state', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));
    act(() => result.current.pause());
    act(() => result.current.pause());
    expect(result.current.state).toBe('paused');
  });

  it('seekTo clamps to [0, duration]', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));

    act(() => result.current.seekTo(-10));
    expect(result.current.currentTime).toBe(0);
    expect(result.current.currentTimeRef.current).toBe(0);

    act(() => result.current.seekTo(99999));
    expect(result.current.currentTime).toBe(mockTimeline.durationSeconds);
    expect(result.current.currentTimeRef.current).toBe(mockTimeline.durationSeconds);
  });

  it('seekTo sets time within bounds', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));

    act(() => result.current.seekTo(100));
    expect(result.current.currentTime).toBe(100);
    expect(result.current.currentTimeRef.current).toBe(100);
  });

  it('seekRelative adjusts from current time', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));

    act(() => result.current.seekTo(50));
    act(() => result.current.seekRelative(5));
    expect(result.current.currentTime).toBe(55);

    act(() => result.current.seekRelative(-10));
    expect(result.current.currentTime).toBe(45);
  });

  it('setSpeed only accepts valid speeds', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));
    act(() => result.current.setSpeed(5));
    expect(result.current.speed).toBe(5);

    act(() => result.current.setSpeed(7)); // Invalid
    expect(result.current.speed).toBe(5); // Unchanged
  });

  it('setSpeed accepts all valid speeds', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));
    for (const s of VALID_SPEEDS) {
      act(() => result.current.setSpeed(s));
      expect(result.current.speed).toBe(s);
    }
  });

  it('duration reflects timeline duration', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));
    expect(result.current.duration).toBe(5520);
  });

  it('duration is 0 when no timeline', () => {
    const { result } = renderHook(() => usePlayback(null));
    expect(result.current.duration).toBe(0);
  });

  it('advanceTime advances currentTimeRef and pauses at end', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));
    act(() => result.current.seekTo(5518));
    act(() => result.current.advanceTime(5));
    // Should be clamped to duration and paused
    expect(result.current.currentTimeRef.current).toBe(5520);
    expect(result.current.state).toBe('paused');
  });

  it('exposes refs for ticker consumption', () => {
    const { result } = renderHook(() => usePlayback(mockTimeline));
    expect(result.current.stateRef.current).toBe('playing');
    expect(result.current.speedRef.current).toBe(1);
    expect(result.current.currentTimeRef.current).toBe(0);
  });
});
