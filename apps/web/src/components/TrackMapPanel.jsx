import { useEffect, useMemo, useState } from 'react';
import { CircuitMap } from './CircuitMap';
import { ReplayControls } from './ReplayControls';
import { TruthLabelBadge } from './TruthLabelBadge';
import bahrainCircuit from '../fixtures/bahrainCircuit';
import { useTrackSnapshot } from '../data/trackSnapshot';
import {
  fetchReplayFixtures,
  fetchReplayState
} from '../data/replayState';

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
  const [fixtureDisplayName, setFixtureDisplayName] = useState('');
  const [scrubberCursor, setScrubberCursor] = useState(null);
  const [replayError, setReplayError] = useState('');
  const [isSnapshotErrorVisible, setIsSnapshotErrorVisible] = useState(true);
  const snapshotQuery = useTrackSnapshot();

  useEffect(() => {
    if (snapshotQuery.isError) {
      setIsSnapshotErrorVisible(true);
    }
  }, [snapshotQuery.isError]);

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
          setFixtureDisplayName(fixtures[0].display_name ?? '');
        }

        const state = await fetchReplayState();
        if (!isCancelled) {
          setReplayState(state);
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
      {activeLayer === 'Traffic' && (
        <p className="track-map-precision-note" data-testid="traffic-derived-note">
          Traffic density overlay is <TruthLabelBadge label="derived" /> from segment occupancy and adjacency. This is not a dirty-air precision model.
        </p>
      )}
      {activeLayer === 'Corner Evolution' && (
        <p className="track-map-precision-note" data-testid="corner-evolution-inferred-note">
          Corner evolution overlay is <TruthLabelBadge label="inferred" /> from replay segment speed deltas. Missing samples are shown as neutral.
        </p>
      )}
      <ReplayControls
        fixtureId={replayFixtureId}
        sessionName={fixtureDisplayName}
        isSnapshotLoading={snapshotQuery.isLoading}
      />
      <div className="replay-controls">
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
        {replayError && <p className="session-status-message session-status-message-error">{replayError}</p>}
      </div>
      {snapshotQuery.isError && isSnapshotErrorVisible ? (
        <div className="track-map-error-banner" role="alert">
          <p>Connection error. Unable to load latest track snapshot.</p>
          <button
            type="button"
            className="layer-button"
            onClick={() => setIsSnapshotErrorVisible(false)}
            aria-label="Dismiss track map error"
          >
            Dismiss
          </button>
        </div>
      ) : null}
      <div className="track-map-canvas">
        <CircuitMap
          circuit={circuit}
          activeLayer={activeLayer}
          windDirectionDeg={snapshotQuery.data?.weather?.wind_direction_deg ?? null}
          windSpeedMs={snapshotQuery.data?.weather?.wind_speed_ms ?? null}
          globalTrackTemperatureC={snapshotQuery.data?.weather?.track_temperature_c ?? null}
          carMarkers={replayMarker}
          segmentStates={snapshotQuery.data?.segment_states ?? []}
        />
        {snapshotQuery.isLoading ? (
          <div className="track-map-overlay" role="status" aria-live="polite">
            <span className="status-spinner" aria-hidden="true" />
            Loading map snapshot...
          </div>
        ) : null}
      </div>
    </section>
  );
}
