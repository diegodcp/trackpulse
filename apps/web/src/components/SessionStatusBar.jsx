import { useTrackSnapshot } from '../data/trackSnapshot';

function formatTemperature(value) {
  if (typeof value !== 'number') {
    return '--';
  }
  return `${value.toFixed(1)} C`;
}

function formatWind(speed, direction) {
  if (typeof speed !== 'number' || typeof direction !== 'number') {
    return '--';
  }
  return `${speed.toFixed(1)} m/s @ ${Math.round(direction)} deg`;
}

function formatRainfall(value) {
  if (typeof value !== 'boolean') {
    return '--';
  }
  return value ? 'Rain detected' : 'No rain detected'; 
  //return `${value.toFixed(1)} mm`;
}

export function SessionStatusBar() {
  const snapshotQuery = useTrackSnapshot();
  const snapshot = snapshotQuery.data;
  const weather = snapshot?.weather;
  const hasMeasuredWeather = Boolean(snapshot && weather?.available);
  const trackTemperature = weather?.track_temperature_c;
  const replayStatus = snapshot?.replay_status ?? 'idle';
  const connectionStatus = snapshot?.connection_status ?? 'disconnected';

  return (
    <section className="session-status" aria-label="Session status">
      <h2>Session Status</h2>
      <div className="session-status-grid">
        <p><span>Session</span>Bahrain 2023 Race</p>
        <p><span>Source</span>Fixture replay</p>
        <p><span>Connection</span>{connectionStatus}</p>
        <p><span>Replay</span>{replayStatus}</p>
        {snapshotQuery.isPending && (
          <p><span>Weather</span>Loading measured weather...</p>
        )}

        {snapshotQuery.isError && (
          <p role="alert" className="session-status-message session-status-message-error">
            Track snapshot unavailable. Please try again shortly.
          </p>
        )}

        {snapshotQuery.isSuccess && !snapshot && (
          <p className="session-status-message">No track snapshot available.</p>
        )}

        {snapshotQuery.isSuccess && snapshot && !hasMeasuredWeather && (
          <p className="session-status-message">No measured weather available.</p>
        )}

        {snapshotQuery.isSuccess && hasMeasuredWeather && (
          <>
            <p className="session-status-badge">
              <span>Track Temp Badge</span>
              {trackTemperature === null ? '--' : formatTemperature(trackTemperature)}
            </p>
            <p><span>Track Temp</span>{formatTemperature(weather.track_temperature_c)}</p>
            <p><span>Air Temp</span>{formatTemperature(weather.air_temperature_c)}</p>
            <p><span>Wind</span>{formatWind(weather.wind_speed_ms, weather.wind_direction_deg)}</p>
            <p><span>Rainfall</span>{formatRainfall(weather.rainfall)}</p>
            <p><span>Truth</span>{weather.truth_label}</p>
          </>
        )}
      </div>
    </section>
  );
}
