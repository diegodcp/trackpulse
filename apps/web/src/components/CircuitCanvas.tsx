import { Application } from 'pixi.js';
import { useRef, useEffect, useState, useCallback } from 'react';
import { useCircuitGeometry } from '../hooks/useCircuitGeometry';
import { useCarTimeline } from '../hooks/useCarTimeline';
import { useAppContext } from '../context/AppContext';
import { computeTransform, type Transform } from '../utils/coordinates';
import { drawTrack } from './TrackLayer';
import { drawStartFinish } from './StartFinishMarker';
import { useCarLayer } from './CarLayer';
import { interpolateFrames, findFrameAtTime, type InterpolatedCar } from '../utils/interpolation';
import type { CircuitGeometry } from '../types/circuit';

export function CircuitCanvas() {
  const canvasRef = useRef<HTMLDivElement>(null);
  const appRef = useRef<Application | null>(null);
  const geometryRef = useRef<CircuitGeometry | undefined>(undefined);
  const transformRef = useRef<Transform | null>(null);
  const currentTimeRef = useRef(0);
  const { selectedSessionKey } = useAppContext();
  const { data: geometry, isLoading, error } = useCircuitGeometry(selectedSessionKey);
  const timeline = useCarTimeline(selectedSessionKey);

  const [isPlaying, setIsPlaying] = useState(true);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [interpolatedCars, setInterpolatedCars] = useState<InterpolatedCar[]>([]);
  const [currentTransform, setCurrentTransform] = useState<Transform | null>(null);

  // Keep geometry ref in sync
  geometryRef.current = geometry;

  // Car layer management
  useCarLayer({
    app: appRef.current,
    cars: interpolatedCars,
    transform: currentTransform,
  });

  function redraw() {
    const app = appRef.current;
    const geo = geometryRef.current;
    if (!app || !geo) return;
    const transform = renderCircuit(app, geo);
    transformRef.current = transform;
    setCurrentTransform(transform);
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

  // Animation ticker for car interpolation (chunked)
  useEffect(() => {
    const app = appRef.current;
    if (!app || !timeline.isReady) return;

    const tickerCallback = (deltaTime: { deltaMS: number }) => {
      if (isPlaying) {
        const deltaSec = (deltaTime.deltaMS / 1000) * playbackSpeed;
        currentTimeRef.current += deltaSec;

        // Loop back to start if past end
        if (currentTimeRef.current > timeline.durationSeconds) {
          currentTimeRef.current = 0;
        }
      }

      const result = timeline.getFramesForTime(currentTimeRef.current);
      if (!result || result.frames.length === 0) return;

      const { frames } = result;
      const { frameIndex, t } = findFrameAtTime(frames, currentTimeRef.current);
      const nextIndex = Math.min(frameIndex + 1, frames.length - 1);
      const interpolated = interpolateFrames(
        frames[frameIndex],
        frames[nextIndex],
        t,
      );
      setInterpolatedCars(interpolated);
    };

    app.ticker.add(tickerCallback);
    return () => {
      app.ticker.remove(tickerCallback);
    };
  }, [timeline.isReady, timeline.durationSeconds, isPlaying, playbackSpeed]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset time when session changes
  useEffect(() => {
    currentTimeRef.current = 0;
    setInterpolatedCars([]);
  }, [selectedSessionKey]);

  return (
    <div ref={canvasRef} className="circuit-canvas">
      {isLoading && <div className="circuit-loading">Loading circuit...</div>}
      {error && <div className="circuit-error">Failed to load circuit</div>}
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
