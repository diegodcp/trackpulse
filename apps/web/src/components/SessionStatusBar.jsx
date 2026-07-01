import { useLatestWeatherQuery } from '../data/weatherLatest';

function formatTemperature(value) {
  return `${value.toFixed(1)} C`;
}

function formatWind(speed, direction) {
  return `${speed.toFixed(1)} m/s @ ${Math.round(direction)} deg`;
}

function formatRainfall(value) {
  return value ? 'Rain detected' : 'No rain detected'; 
  //return `${value.toFixed(1)} mm`;
}

export function SessionStatusBar() {
  const weatherQuery = useLatestWeatherQuery();

  return (
    <section className="session-status" aria-label="Session status">
      <h2>Session Status</h2>
      <div className="session-status-grid">
        <p><span>Session</span>Bahrain 2023 Race</p>
        <p><span>Source</span>Fixture replay</p>
        <p><span>Backend</span>Awaiting live link</p>
        {weatherQuery.isPending && (
          <p><span>Weather</span>Loading measured weather...</p>
        )}

        {weatherQuery.isError && (
          <p role="alert" className="session-status-message session-status-message-error">
            Measured weather unavailable. Please try again shortly.
          </p>
        )}

        {weatherQuery.isSuccess && !weatherQuery.data && (
          <p className="session-status-message">No measured weather available.</p>
        )}

        {weatherQuery.isSuccess && weatherQuery.data && (
          <>
            <p><span>Track Temp</span>{formatTemperature(weatherQuery.data.track_temperature)}</p>
            <p><span>Air Temp</span>{formatTemperature(weatherQuery.data.air_temperature)}</p>
            <p><span>Wind</span>{formatWind(weatherQuery.data.wind_speed, weatherQuery.data.wind_direction)}</p>
            <p><span>Rainfall</span>{formatRainfall(weatherQuery.data.rainfall)}</p>
            <p><span>Truth</span>Measured</p>
          </>
        )}
      </div>
    </section>
  );
}
