import type { WeatherState } from '../types/timeline';

interface WeatherSectionProps {
  weather: WeatherState | null;
}

export function WeatherSection({ weather }: WeatherSectionProps) {
  if (!weather) {
    return <div className="weather-section weather-section--empty">No weather data</div>;
  }

  return (
    <div className="weather-section" role="status" aria-label="Current weather conditions">
      <div className="weather-item">
        <span className="weather-label">Air</span>
        <span className="weather-value">{weather.air_temperature.toFixed(1)}°C</span>
      </div>

      <div className="weather-item">
        <span className="weather-label">Track</span>
        <span className="weather-value">{weather.track_temperature.toFixed(1)}°C</span>
      </div>

      <div className="weather-item">
        <span className="weather-label">Wind</span>
        <span className="weather-value">
          {weather.wind_speed.toFixed(1)} m/s
          <WindArrow direction={weather.wind_direction} />
        </span>
      </div>

      <div className="weather-item">
        <span className="weather-label">Humidity</span>
        <span className="weather-value">{weather.humidity.toFixed(0)}%</span>
      </div>

      <div className={`weather-item ${weather.rainfall ? 'weather-item--rain' : ''}`}>
        <span className="weather-label">Rain</span>
        <span className="weather-value">
          {weather.rainfall ? '🌧️ Yes' : '☀️ No'}
        </span>
      </div>
    </div>
  );
}

/**
 * Rotated arrow indicating wind direction.
 * 0° = wind from North (arrow points down), 180° = wind from South (arrow points up).
 */
function WindArrow({ direction }: { direction: number }) {
  return (
    <span
      className="wind-arrow"
      style={{ transform: `rotate(${direction}deg)`, display: 'inline-block' }}
      aria-label={`Wind from ${direction}°`}
    >
      ↓
    </span>
  );
}
