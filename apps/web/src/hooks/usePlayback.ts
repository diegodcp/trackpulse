import { useState, useCallback, useEffect, useRef } from 'react';

export type PlaybackState = 'idle' | 'loading' | 'playing' | 'paused';

export interface PlaybackControls {
  state: PlaybackState;
  currentTime: number;
  duration: number;
  speed: number;
  currentLap: number | null;

  play: () => void;
  pause: () => void;
  setSpeed: (speed: number) => void;
  seekTo: (seconds: number) => void;
  seekRelative: (deltaSec: number) => void;

  /** Ref for high-frequency reads (Pixi ticker). Avoid React re-renders. */
  currentTimeRef: React.RefObject<number>;
  /** Ref for speed (Pixi ticker reads). */
  speedRef: React.RefObject<number>;
  /** Ref for state (Pixi ticker reads). */
  stateRef: React.RefObject<PlaybackState>;
  /** Write current time from ticker (throttled UI update). */
  advanceTime: (deltaSec: number) => void;
  /** Set current lap from external source. */
  setCurrentLap: (lap: number | null) => void;
}

export const VALID_SPEEDS = [1, 2, 5, 10, 20, 50];

interface TimelineInfo {
  isReady: boolean;
  isLoading: boolean;
  durationSeconds: number;
}

const UI_UPDATE_INTERVAL = 100; // ms between React state updates for time display

export function usePlayback(
  timeline: TimelineInfo | null,
  onTimeUpdate?: (elapsedSeconds: number) => void,
): PlaybackControls {
  const [state, setState] = useState<PlaybackState>('idle');
  const [speed, setSpeedState] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [currentLap, setCurrentLapState] = useState<number | null>(null);

  const currentTimeRef = useRef(0);
  const speedRef = useRef(1);
  const stateRef = useRef<PlaybackState>('idle');
  const lastUiUpdateRef = useRef(0);
  const onTimeUpdateRef = useRef(onTimeUpdate);
  onTimeUpdateRef.current = onTimeUpdate;

  const duration = timeline?.durationSeconds ?? 0;
  const durationRef = useRef(duration);
  durationRef.current = duration;

  // Keep refs in sync with state
  useEffect(() => {
    stateRef.current = state;
  }, [state]);
  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  // Transition states based on timeline availability
  useEffect(() => {
    if (!timeline || (!timeline.isReady && !timeline.isLoading)) {
      setState('idle');
    } else if (timeline.isLoading && !timeline.isReady) {
      setState('loading');
    } else if (timeline.isReady && (stateRef.current === 'idle' || stateRef.current === 'loading')) {
      setState('playing'); // Auto-play when timeline is ready
    }
  }, [timeline?.isReady, timeline?.isLoading]); // eslint-disable-line react-hooks/exhaustive-deps

  const play = useCallback(() => {
    setState((s) => (s === 'paused' ? 'playing' : s));
  }, []);

  const pause = useCallback(() => {
    setState((s) => (s === 'playing' ? 'paused' : s));
  }, []);

  const seekTo = useCallback(
    (seconds: number) => {
      const clamped = Math.max(0, Math.min(seconds, durationRef.current));
      currentTimeRef.current = clamped;
      setCurrentTime(clamped);
      onTimeUpdateRef.current?.(clamped);
    },
    [],
  );

  const seekRelative = useCallback(
    (delta: number) => {
      seekTo(currentTimeRef.current + delta);
    },
    [seekTo],
  );

  const setSpeed = useCallback((newSpeed: number) => {
    if (VALID_SPEEDS.includes(newSpeed)) {
      setSpeedState(newSpeed);
    }
  }, []);

  // Called by Pixi ticker every frame — advances time without causing React re-renders
  const advanceTime = useCallback((deltaSec: number) => {
    const dur = durationRef.current;
    let newTime = currentTimeRef.current + deltaSec;

    if (newTime >= dur) {
      newTime = dur;
      currentTimeRef.current = newTime;
      setState('paused');
    } else {
      currentTimeRef.current = newTime;
    }

    // Throttle React state updates for the time display
    const now = performance.now();
    if (now - lastUiUpdateRef.current >= UI_UPDATE_INTERVAL) {
      lastUiUpdateRef.current = now;
      setCurrentTime(currentTimeRef.current);
    }
  }, []);

  const setCurrentLap = useCallback((lap: number | null) => {
    setCurrentLapState(lap);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLSelectElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (e.code) {
        case 'Space':
          e.preventDefault();
          setState((s) => {
            if (s === 'playing') return 'paused';
            if (s === 'paused') return 'playing';
            return s;
          });
          break;
        case 'ArrowLeft':
          e.preventDefault();
          seekRelative(-5);
          break;
        case 'ArrowRight':
          e.preventDefault();
          seekRelative(5);
          break;
        case 'Minus':
        case 'NumpadSubtract': {
          e.preventDefault();
          setSpeedState((curr) => {
            const idx = VALID_SPEEDS.indexOf(curr);
            return VALID_SPEEDS[Math.max(0, idx - 1)];
          });
          break;
        }
        case 'Equal':
        case 'NumpadAdd': {
          e.preventDefault();
          setSpeedState((curr) => {
            const idx = VALID_SPEEDS.indexOf(curr);
            return VALID_SPEEDS[Math.min(VALID_SPEEDS.length - 1, idx + 1)];
          });
          break;
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [seekRelative]);

  return {
    state,
    currentTime,
    duration,
    speed,
    currentLap,
    play,
    pause,
    setSpeed,
    seekTo,
    seekRelative,
    currentTimeRef,
    speedRef,
    stateRef,
    advanceTime,
    setCurrentLap,
  };
}
