import { type PlaybackControls, VALID_SPEEDS } from '../hooks/usePlayback';
import { formatTime } from '../utils/formatTime';

interface PlaybackControlsProps {
  playback: PlaybackControls;
  disabled: boolean;
  raceStartElapsedSeconds?: number | null;
}

export function PlaybackControlsBar({ playback, disabled, raceStartElapsedSeconds }: PlaybackControlsProps) {
  const { state, currentTime, duration, speed, play, pause, setSpeed, seekTo } =
    playback;

  const isFormationLap = raceStartElapsedSeconds != null && currentTime < raceStartElapsedSeconds;

  return (
    <div className="playback-controls" role="toolbar" aria-label="Playback controls">
      <button
        className="playback-controls__play-btn"
        onClick={state === 'playing' ? pause : play}
        disabled={disabled || state === 'idle' || state === 'loading'}
        aria-label={state === 'playing' ? 'Pause' : 'Play'}
      >
        {state === 'playing' ? '⏸' : '▶'}
      </button>

      <select
        className="playback-controls__speed"
        value={speed}
        onChange={(e) => setSpeed(Number(e.target.value))}
        disabled={disabled || state === 'idle' || state === 'loading'}
        aria-label="Playback speed"
      >
        {VALID_SPEEDS.map((s) => (
          <option key={s} value={s}>
            {s}x
          </option>
        ))}
      </select>

      <input
        className="playback-controls__scrubber"
        type="range"
        min={0}
        max={duration}
        step={0.25}
        value={currentTime}
        onChange={(e) => seekTo(Number(e.target.value))}
        disabled={disabled || state === 'idle' || state === 'loading'}
        aria-label="Timeline"
      />

      <span className="playback-controls__time">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>

      {isFormationLap && (
        <span className="playback-controls__lap playback-controls__lap--formation">Formation Lap</span>
      )}

      {!isFormationLap && playback.currentLap !== null && (
        <span className="playback-controls__lap">Lap {playback.currentLap}</span>
      )}
    </div>
  );
}
