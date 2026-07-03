import { Application } from 'pixi.js';
import { useRef, useEffect } from 'react';
import { useCircuitGeometry } from '../hooks/useCircuitGeometry';
import { useCarTimeline } from '../hooks/useCarTimeline';
import { usePlayback } from '../hooks/usePlayback';
import { useStreamingTimeline } from '../hooks/useStreamingTimeline';
import { useAppContext } from '../context/AppContext';
import { computeTransform, worldToScreen, type Transform } from '../utils/coordinates';
import { drawTrack } from './TrackLayer';
import { drawStartFinish } from './StartFinishMarker';
import { PlaybackControlsBar } from './PlaybackControls';
import { CarMarkerSprite } from './CarMarker';
import { interpolateFrames, findFrameAtTime } from '../utils/interpolation';
import type { CircuitGeometry } from '../types/circuit';
import type { InterpolatedCar } from '../workers/types';

const USE_STREAMING = import.meta.env.VITE_USE_STREAMING === 'true';

export function CircuitCanvas() {
  const canvasRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const geometryRef = useRef<CircuitGeometry | undefined>(undefined);
  const transformRef = useRef<Transform | null>(null);
  const markersRef = useRef<Map<number, CarMarkerSprite>>(new Map());
  const driverMetaRef = useRef<Map<number, { name_acronym: string; team_colour: string }>>(new Map());
  const { selectedSessionKey } = useAppContext();
  const { data: geometry, isLoading, error } = useCircuitGeometry(selectedSessionKey);
  const timeline = useCarTimeline(selectedSessionKey);

  // Streaming timeline (WebSocket via Web Worker)
  const streaming = useStreamingTimeline({
    sessionKey: selectedSessionKey,
    hz: 4,
    speed: 1,
    enabled: USE_STREAMING,
  });

  // Playback controls — ticker-driven, no per-frame React state
  const playback = usePlayback(timeline);

  // Build driver metadata map from timeline for marker creation
  useEffect(() => {
    if (timeline.drivers.length > 0) {
      const map = new Map<number, { name_acronym: string; team_colour: string }>();
      for (const d of timeline.drivers) {
        map.set(d.driver_number, { name_acronym: d.name_acronym, team_colour: d.team_colour });
      }
      driverMetaRef.current = map;
    }
  }, [timeline.drivers]);

  // Sync playback state → streaming worker (seek, speed, pause/resume)
  const prevPlaybackStateRef = useRef(playback.state);
  useEffect(() => {
    if (!USE_STREAMING) return;
    const prev = prevPlaybackStateRef.current;
    const curr = playback.state;
    prevPlaybackStateRef.current = curr;

    if (prev === 'playing' && curr === 'paused') {
      streaming.pause();
    } else if (prev === 'paused' && curr === 'playing') {
      streaming.resume();
    }
  }, [playback.state]); // eslint-disable-line react-hooks/exhaustive-deps

  // Relay speed changes to streaming worker
  useEffect(() => {
    if (!USE_STREAMING) return;
    streaming.setSpeed(playback.speed);
  }, [playback.speed]); // eslint-disable-line react-hooks/exhaustive-deps

  // Wrap seekTo to also relay to streaming worker
  const originalSeekTo = playback.seekTo;
  const wrappedSeekTo = useRef(originalSeekTo);
  useEffect(() => {
    if (!USE_STREAMING) {
      wrappedSeekTo.current = originalSeekTo;
      return;
    }
    wrappedSeekTo.current = (seconds: number) => {
      originalSeekTo(seconds);
      streaming.seek(seconds);
    };
  }, [originalSeekTo]); // eslint-disable-line react-hooks/exhaustive-deps

  // Update playback currentTime from streaming elapsed (for UI display)
  useEffect(() => {
    if (!USE_STREAMING) return;
    const interval = setInterval(() => {
      const elapsed = streaming.currentElapsed.current;
      if (elapsed !== playback.currentTimeRef.current) {
        playback.seekTo(elapsed);
      }
    }, 100);
    return () => clearInterval(interval);
  }, [streaming.isConnected]); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep geometry ref in sync
  geometryRef.current = geometry;

  function redraw() {
    const app = appRef.current;
    const geo = geometryRef.current;
    if (!app || !geo) return;
    const transform = renderCircuit(app, geo);
    transformRef.current = transform;
  }

  useEffect(() => {
    if (!canvasRef.current) return;

    const container = canvasRef.current;
    let app: Application | null = null;
    let destroyed = false;

    const { width, height } = container.getBoundingClientRect();

    async function initApp() {
      const instance = new Application();
      await instance.init({
        width: width || 800,
        height: height || 600,
        background: 0x1a1a2e,
        antialias: true,
      });

      if (destroyed) {
        instance.destroy(true, { children: true });
        return;
      }

      app = instance;
      container.appendChild(instance.canvas);
      appRef.current = instance;
      redraw();
    }

    initApp();

    return () => {
      destroyed = true;
      appRef.current = null;
      if (app) {
        try {
          app.destroy(true, { children: true });
        } catch {
          // Pixi cleanup edge cases
        }
        app = null;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Redraw when geometry changes
  useEffect(() => {
    redraw();
  }, [geometry]); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle resize
  useEffect(() => {
    if (!canvasRef.current) return;
    const container = canvasRef.current;

    let resizeTimeout: ReturnType<typeof setTimeout>;
    const observer = new ResizeObserver((entries) => {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(() => {
        const app = appRef.current;
        if (!app) return;
        const { width, height } = entries[0].contentRect;
        if (width > 0 && height > 0) {
          app.renderer.resize(width, height);
          redraw();
        }
      }, 100);
    });

    observer.observe(container);
    return () => {
      observer.disconnect();
      clearTimeout(resizeTimeout);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Pixi ticker drives animation — updates sprites directly via refs (no React re-renders)
  useEffect(() => {
    const app = appRef.current;
    if (!app || !timeline.isReady) return;

    const tickerCallback = (ticker: { deltaMS: number }) => {
      const transform = transformRef.current;
      if (!transform) return;

      let cars: InterpolatedCar[] | null = null;

      if (USE_STREAMING) {
        // Streaming mode: worker already interpolated — just read the ref
        cars = streaming.carsRef.current;
      } else {
        // Chunk-based mode: advance time and compute interpolation on main thread
        const state = playback.stateRef.current;
        const speed = playback.speedRef.current;

        if (state === 'playing') {
          const deltaSec = (ticker.deltaMS / 1000) * speed;
          playback.advanceTime(deltaSec);
        }

        const elapsedSeconds = playback.currentTimeRef.current;
        const result = timeline.getFramesForTime(elapsedSeconds);
        if (!result || result.frames.length === 0) return;

        const { frames } = result;
        const { frameIndex, t } = findFrameAtTime(frames, elapsedSeconds);
        const nextIndex = Math.min(frameIndex + 1, frames.length - 1);
        const interpolated = interpolateFrames(frames[frameIndex], frames[nextIndex], t);
        cars = interpolated;
      }

      if (!cars || cars.length === 0) return;

      // Update sprites directly — no React state
      const currentDrivers = new Set<number>();
      for (const car of cars) {
        currentDrivers.add(car.driver_number);
        let marker = markersRef.current.get(car.driver_number);

        if (!marker) {
          // Look up driver metadata for marker creation
          const meta = driverMetaRef.current.get(car.driver_number);
          const teamColour = ('team_colour' in car ? (car as { team_colour: string }).team_colour : null)
            ?? meta?.team_colour ?? 'ffffff';
          const nameAcronym = ('name_acronym' in car ? (car as { name_acronym: string }).name_acronym : null)
            ?? meta?.name_acronym ?? String(car.driver_number);
          marker = new CarMarkerSprite(teamColour, nameAcronym);
          app.stage.addChild(marker.container);
          markersRef.current.set(car.driver_number, marker);
        }

        const { screenX, screenY } = worldToScreen(car.x, car.y, transform);
        marker.updatePosition(screenX, screenY);

        if ('inPit' in car && (car as { inPit: boolean }).inPit) {
          marker.setInPit(true);
        } else {
          marker.setActive(car.isActive);
        }
      }

      // Remove stale markers
      for (const [driverNum, marker] of markersRef.current) {
        if (!currentDrivers.has(driverNum)) {
          marker.destroy();
          markersRef.current.delete(driverNum);
        }
      }

      // Update current lap from first active car
      const firstCar = cars.find((c) => c.isActive && c.lap_number !== null);
      if (firstCar) {
        playback.setCurrentLap(firstCar.lap_number);
      }
    };

    app.ticker.add(tickerCallback);
    return () => {
      app.ticker.remove(tickerCallback);
    };
  }, [timeline.isReady]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup markers and reset when session changes
  useEffect(() => {
    for (const marker of markersRef.current.values()) {
      marker.destroy();
    }
    markersRef.current.clear();
  }, [selectedSessionKey]);

  return (
    <div className="circuit-canvas-wrapper">
      <div ref={canvasRef} className="circuit-canvas">
        {isLoading && <div className="circuit-loading">Loading circuit...</div>}
        {error && <div className="circuit-error">Failed to load circuit</div>}
      </div>
      <PlaybackControlsBar
        playback={playback}
        disabled={!timeline.isReady}
      />
    </div>
  );
}

function renderCircuit(app: Application, geometry: CircuitGeometry): Transform {
  app.stage.removeChildren();

  const viewport = { width: app.screen.width, height: app.screen.height };
  const transform = computeTransform(geometry.bounds, viewport);

  // Draw track segments
  const trackGraphics = drawTrack(geometry, transform);
  for (const g of trackGraphics) {
    app.stage.addChild(g);
  }

  // Draw start/finish marker
  if (geometry.points.length > 0) {
    const marker = drawStartFinish(geometry.points[0], transform);
    app.stage.addChild(marker);
  }

  return transform;
}
