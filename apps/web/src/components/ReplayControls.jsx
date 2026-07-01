import { useEffect, useState } from 'react';
import {
  startFixtureReplay,
  pauseFixtureReplay,
  stopFixtureReplay,
  fetchReplayStatus
} from '../data/replayState';

const REPLAY_SPEEDS = [1, 5, 20, 100];

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

export function ReplayControls({ fixtureId, sessionName }) {
  const [status, setStatus] = useState('idle');
  const [speedMultiplier, setSpeedMultiplier] = useState(1);
  const [replayTime, setReplayTime] = useState(null);
  const [error, setError] = useState('');
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function pollStatus() {
      try {
        const state = await fetchReplayStatus();
        if (!cancelled) {
          setStatus(state.status);
          setSpeedMultiplier(state.speed_multiplier);
          setReplayTime(state.replay_time ?? null);
        }
      } catch {
        // ignore polling errors silently — controls will remain in current state
      }
    }

    pollStatus();

    const intervalMs = status === 'running' ? 500 : 2000;
    const id = window.setInterval(pollStatus, intervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [status]);

  const handleStart = async () => {
    setIsBusy(true);
    setError('');
    try {
      const state = await startFixtureReplay(fixtureId, speedMultiplier);
      setStatus(state.status);
      setReplayTime(state.replay_time ?? null);
    } catch {
      setError('Failed to start replay. Please try again.');
    } finally {
      setIsBusy(false);
    }
  };

  const handlePause = async () => {
    setIsBusy(true);
    setError('');
    try {
      const state = await pauseFixtureReplay(fixtureId);
      setStatus(state.status);
      setReplayTime(state.replay_time ?? null);
    } catch {
      setError('Failed to pause replay. Please try again.');
    } finally {
      setIsBusy(false);
    }
  };

  const handleStop = async () => {
    setIsBusy(true);
    setError('');
    try {
      const state = await stopFixtureReplay(fixtureId);
      setStatus(state.status);
      setReplayTime(state.replay_time ?? null);
    } catch {
      setError('Failed to stop replay. Please try again.');
    } finally {
      setIsBusy(false);
    }
  };

  const handleSpeedChange = async (speed) => {
    setSpeedMultiplier(speed);
    if (status === 'running') {
      setIsBusy(true);
      try {
        const state = await startFixtureReplay(fixtureId, speed);
        setStatus(state.status);
      } catch {
        setError('Failed to update replay speed. Please try again.');
      } finally {
        setIsBusy(false);
      }
    }
  };

  const isRunning = status === 'running';
  const isPaused = status === 'paused';
  const isIdle = !isRunning && !isPaused;

  const canStart = (isIdle || isPaused) && !isBusy;
  const canPause = isRunning && !isBusy;
  const canStop = (isRunning || isPaused) && !isBusy;

  const statusClass =
    isRunning
      ? 'replay-status-running'
      : isPaused
        ? 'replay-status-paused'
        : 'replay-status-idle';

  return (
    <div className="replay-controls" aria-label="Fixture replay controls">
      <p className="replay-label">Fixture Replay</p>
      <p className="replay-meta" data-testid="replay-fixture-info">
        <span>{fixtureId}</span>
        {sessionName ? (
          <>
            {' \u2014 '}
            <span>{sessionName}</span>
          </>
        ) : null}
      </p>
      <div className="replay-controls-row">
        <button
          type="button"
          className="layer-button"
          onClick={handleStart}
          disabled={!canStart}
          aria-disabled={!canStart}
          data-testid="replay-start-btn"
        >
          {isPaused ? 'Resume' : 'Start'}
        </button>
        <button
          type="button"
          className="layer-button"
          onClick={handlePause}
          disabled={!canPause}
          aria-disabled={!canPause}
          data-testid="replay-pause-btn"
        >
          Pause
        </button>
        <button
          type="button"
          className="layer-button"
          onClick={handleStop}
          disabled={!canStop}
          aria-disabled={!canStop}
          data-testid="replay-stop-btn"
        >
          Stop
        </button>
        <div className="replay-speed-group" role="group" aria-label="Replay speed">
          {REPLAY_SPEEDS.map((speed) => (
            <button
              key={speed}
              type="button"
              className={`layer-button${speedMultiplier === speed ? ' is-active' : ''}`}
              onClick={() => handleSpeedChange(speed)}
              data-testid={`replay-speed-${speed}x`}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>
      <p className="replay-meta">
        Status:{' '}
        <strong
          className={statusClass}
          data-testid="replay-status"
          aria-live="polite"
        >
          {status}
        </strong>
        {' | '}
        Time:{' '}
        <strong data-testid="replay-time">
          {formatReplayTime(replayTime)}
        </strong>
      </p>
      {error && (
        <p
          className="session-status-message session-status-message-error"
          role="alert"
          data-testid="replay-error"
        >
          {error}
        </p>
      )}
    </div>
  );
}
