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
}

export const VALID_SPEEDS = [1, 2, 5, 10, 20, 50];

interface TimelineInfo {
  isReady: boolean;
  isLoading: boolean;
  durationSeconds: number;
}

export function usePlayback(
  timeline: TimelineInfo | null,
  onTimeUpdate: (elapsedSeconds: number) => void,
): PlaybackControls {
  const [state, setState] = useState<PlaybackState>('idle');
  const [speed, setSpeedState] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [currentLap, setCurrentLap] = useState<number | null>(null);
  const currentTimeRef = useRef(0);
  const onTimeUpdateRef = useRef(onTimeUpdate);
  onTimeUpdateRef.current = onTimeUpdate;

  const duration = timeline?.durationSeconds ?? 0;

  // Transition states based on timeline availability
  useEffect(() => {
    if (!timeline || (!timeline.isReady && !timeline.isLoading)) {
      setState('idle');
    } else if (timeline.isLoading && !timeline.isReady) {
      setState('loading');
    } else if (timeline.isReady && (state === 'idle' || state === 'loading')) {
      setState('paused');
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
      const clamped = Math.max(0, Math.min(seconds, duration));
      currentTimeRef.current = clamped;
      setCurrentTime(clamped);
      onTimeUpdateRef.current(clamped);
    },
    [duration],
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

  // Animation loop
  useEffect(() => {
    if (state !== 'playing') return;

    let rafId: number;
    let lastTimestamp: number | null = null;

    function tick(timestamp: number) {
      if (lastTimestamp !== null) {
        const deltaSec = ((timestamp - lastTimestamp) / 1000) * speed;
        const newTime = currentTimeRef.current + deltaSec;

        if (newTime >= duration) {
          // Reached end — pause at end
          currentTimeRef.current = duration;
          setCurrentTime(duration);
          onTimeUpdateRef.current(duration);
          setState('paused');
          return;
        }

        currentTimeRef.current = newTime;
        setCurrentTime(newTime);
        onTimeUpdateRef.current(newTime);
      }
      lastTimestamp = timestamp;
      rafId = requestAnimationFrame(tick);
    }

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [state, speed, duration]);

  // Update current lap from external source
  const updateLap = useCallback((lap: number | null) => {
    setCurrentLap(lap);
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
  };
}
