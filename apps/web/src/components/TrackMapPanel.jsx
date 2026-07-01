import { useEffect, useMemo, useState } from 'react';
import { CircuitMap } from './CircuitMap';
import bahrainCircuit from '../fixtures/bahrainCircuit';
import { useTrackSnapshot } from '../data/trackSnapshot';
import {
  fetchReplayFixtures,
  fetchReplayState,
  startReplay,
  stopReplay
} from '../data/replayState';

const REPLAY_SPEEDS = [1, 5, 10];

function formatReplayTime(value) {
  if (!value) {
    return '--';
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return '--';
  }

  return parsed.toISOString();
}

function clampProgress(value) {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null;
  }
  return Math.min(1, Math.max(0, value));
}

function deterministicProgressFallback(driverNumber) {
  const normalized = ((driverNumber * 37) % 100) / 100;
  return normalized;
}

function projectProgressToCircuit(progress, circuit) {
  if (!circuit || !Array.isArray(circuit.centerline) || circuit.centerline.length < 2) {
    return null;
  }

  const points = circuit.centerline;
  const segments = [];
  let totalLength = 0;

  for (let index = 0; index < points.length - 1; index += 1) {
    const start = points[index];
    const end = points[index + 1];
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.sqrt(dx * dx + dy * dy);
    segments.push({ start, end, length });
    totalLength += length;
  }

  if (totalLength <= 0) {
    return points[0] ?? null;
  }

  const targetDistance = clampProgress(progress) * totalLength;
  let traversed = 0;

  for (const segment of segments) {
    if (traversed + segment.length >= targetDistance) {
      const remaining = targetDistance - traversed;
      const ratio = segment.length > 0 ? remaining / segment.length : 0;
      return {
        x: segment.start.x + (segment.end.x - segment.start.x) * ratio,
        y: segment.start.y + (segment.end.y - segment.start.y) * ratio
      };
    }
    traversed += segment.length;
  }

  return points[points.length - 1];
}

function projectLocationToCircuit(location, bounds, circuit) {
  if (!location || !bounds || !circuit) {
    return null;
  }

  const minX = bounds.min_x;
  const maxX = bounds.max_x;
  const minY = bounds.min_y;
  const maxY = bounds.max_y;

  const xSpan = Math.max(1, maxX - minX);
  const ySpan = Math.max(1, maxY - minY);
  const mapPadding = 120;
  const mapWidth = Math.max(1, circuit.width - mapPadding * 2);
  const mapHeight = Math.max(1, circuit.height - mapPadding * 2);

  const normalizedX = (location.x - minX) / xSpan;
  const normalizedY = (location.y - minY) / ySpan;

  return {
    x: mapPadding + normalizedX * mapWidth,
    y: mapPadding + normalizedY * mapHeight
  };
}

export function TrackMapPanel({ activeLayer }) {
  const [circuit, setCircuit] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [replayState, setReplayState] = useState(null);
  const [replayFixtureId, setReplayFixtureId] = useState('bahrain-2023-race');
  const [selectedSpeed, setSelectedSpeed] = useState(1);
  const [scrubberCursor, setScrubberCursor] = useState(null);
  const [replayError, setReplayError] = useState('');
  const snapshotQuery = useTrackSnapshot();

  useEffect(() => {
    setCircuit(bahrainCircuit);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    let isCancelled = false;

    async function bootstrapReplay() {
      try {
        const fixtures = await fetchReplayFixtures();
        if (!isCancelled && fixtures.length > 0) {
          setReplayFixtureId(fixtures[0].fixture_id);
        }

        const state = await fetchReplayState();
        if (!isCancelled) {
          setReplayState(state);
          setSelectedSpeed(state.speed_multiplier || 1);
        }
      } catch {
        if (!isCancelled) {
          setReplayError('Replay service unavailable. Map playback controls are disabled.');
        }
      }
    }

    bootstrapReplay();

    return () => {
      isCancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!replayState) {
      return undefined;
    }

    const intervalMs = replayState.status === 'running' ? 250 : 1000;
    const intervalId = window.setInterval(async () => {
      try {
        const state = await fetchReplayState();
        setReplayState(state);
      } catch {
        setReplayError('Replay service unavailable. Map playback controls are disabled.');
      }
    }, intervalMs);

    return () => window.clearInterval(intervalId);
  }, [replayState?.status]);

  const effectiveCursor = scrubberCursor ?? replayState?.cursor ?? 0;
  const timelinePoint = replayState?.timeline_points?.[effectiveCursor] ?? replayState?.active_location ?? null;

  const replayMarker = useMemo(() => {
    const carMarkers = snapshotQuery.data?.car_markers;
    if (!Array.isArray(carMarkers) || carMarkers.length === 0 || !circuit) {
      return [];
    }

    const coordinateBounds = replayState?.coordinate_bounds ?? null;

    return carMarkers
      .map((marker) => {
        const driverNumber = Number(marker?.driver_number);
        if (!Number.isFinite(driverNumber)) {
          return null;
        }

        const markerX = typeof marker?.x === 'number' ? marker.x : null;
        const markerY = typeof marker?.y === 'number' ? marker.y : null;

        let projected = null;
        if (markerX != null && markerY != null && coordinateBounds) {
          projected = projectLocationToCircuit({ x: markerX, y: markerY }, coordinateBounds, circuit);
        }

        if (!projected) {
          const normalizedProgress = clampProgress(Number(marker?.normalized_progress));
          const fallbackProgress =
            normalizedProgress ?? deterministicProgressFallback(driverNumber);
          projected = projectProgressToCircuit(fallbackProgress, circuit);
        }

        if (!projected) {
          return null;
        }

        return {
          id: `driver-${driverNumber}`,
          label: `#${driverNumber}`,
          x: projected.x,
          y: projected.y,
          testId: 'replay-car-marker'
        };
      })
      .filter(Boolean);
  }, [snapshotQuery.data?.car_markers, replayState?.coordinate_bounds, circuit]);

  const handleToggleReplay = async () => {
    if (!replayState) {
      return;
    }

    try {
      if (replayState.status === 'running') {
        const nextState = await stopReplay();
        setReplayState(nextState);
        return;
      }

      setScrubberCursor(null);
      const nextState = await startReplay({
        fixtureId: replayFixtureId,
        speedMultiplier: selectedSpeed
      });
      setReplayState(nextState);
    } catch {
      setReplayError('Replay action failed. Please try again.');
    }
  };

  const handleSpeedChange = async (speed) => {
    setSelectedSpeed(speed);

    if (!replayState || replayState.status !== 'running') {
      return;
    }

    try {
      const nextState = await startReplay({
        fixtureId: replayFixtureId,
        speedMultiplier: speed
      });
      setReplayState(nextState);
    } catch {
      setReplayError('Unable to update replay speed.');
    }
  };

  if (isLoading) {
    return (
      <section className="track-map-panel" aria-label="Track map panel">
        <div className="track-map-loading">Loading track map...</div>
      </section>
    );
  }

  return (
    <section className="track-map-panel" aria-label="Track map panel">
      <header className="track-map-header">
        <h2>Track Map</h2>
        <p>Active Layer: {activeLayer}</p>
      </header>
      <p className="track-map-precision-note" data-testid="track-map-precision-note">
        Stylized Bahrain circuit. Approximate geometry only; no racing-line precision is claimed.
      </p>
      <p className="track-map-precision-note" data-testid="car-marker-approx-note">
        Car markers use measured replay locations but are displayed as approximate positions.
      </p>
      <div className="replay-controls" aria-label="Fixture replay controls">
        <p className="replay-label">Fixture replay</p>
        <div className="replay-controls-row">
          <button type="button" className="layer-button" onClick={handleToggleReplay}>
            {replayState?.status === 'running' ? 'Pause' : 'Play'}
          </button>
          <div className="replay-speed-group" role="group" aria-label="Replay speed">
            {REPLAY_SPEEDS.map((speed) => (
              <button
                key={speed}
                type="button"
                className={`layer-button ${selectedSpeed === speed ? 'is-active' : ''}`}
                onClick={() => handleSpeedChange(speed)}
              >
                {speed}x
              </button>
            ))}
          </div>
        </div>
        <label className="replay-scrubber-label" htmlFor="replay-scrubber">
          Scrubber
        </label>
        <input
          id="replay-scrubber"
          data-testid="replay-scrubber"
          type="range"
          min="0"
          max={Math.max((replayState?.total_points ?? 1) - 1, 0)}
          value={effectiveCursor}
          onChange={(event) => setScrubberCursor(Number(event.target.value))}
          disabled={(replayState?.total_points ?? 0) <= 1}
        />
        <p className="replay-meta">
          Status: <strong>{replayState?.status ?? 'idle'}</strong>
          {' | '}
          Time: <strong data-testid="replay-time">{formatReplayTime(timelinePoint?.occurred_at ?? replayState?.replay_time)}</strong>
        </p>
        {replayError && <p className="session-status-message session-status-message-error">{replayError}</p>}
      </div>
      <CircuitMap
        circuit={circuit}
        activeLayer={activeLayer}
        windDirectionDeg={snapshotQuery.data?.weather?.wind_direction_deg ?? null}
        windSpeedMs={snapshotQuery.data?.weather?.wind_speed_ms ?? null}
        carMarkers={replayMarker}
        segmentStates={snapshotQuery.data?.segment_states ?? []}
      />
    </section>
  );
}
