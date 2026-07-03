import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { WeatherSection } from '../src/components/WeatherSection';
import type { WeatherState } from '../src/types/timeline';

const mockWeather: WeatherState = {
  air_temperature: 27.5,
  track_temperature: 48.3,
  humidity: 42,
  wind_speed: 3.8,
  wind_direction: 225,
  rainfall: false,
};

describe('WeatherSection', () => {
  it('displays all weather values', () => {
    render(<WeatherSection weather={mockWeather} />);
    expect(screen.getByText('27.5°C')).toBeInTheDocument();
    expect(screen.getByText('48.3°C')).toBeInTheDocument();
    expect(screen.getByText(/3.8 m\/s/)).toBeInTheDocument();
    expect(screen.getByText('42%')).toBeInTheDocument();
  });

  it('shows sunny indicator when no rain', () => {
    render(<WeatherSection weather={mockWeather} />);
    expect(screen.getByText(/☀️ No/)).toBeInTheDocument();
  });

  it('shows rain indicator when rainfall is true', () => {
    render(<WeatherSection weather={{ ...mockWeather, rainfall: true }} />);
    expect(screen.getByText(/🌧️ Yes/)).toBeInTheDocument();
  });

  it('shows placeholder when no weather data', () => {
    render(<WeatherSection weather={null} />);
    expect(screen.getByText('No weather data')).toBeInTheDocument();
  });

  it('wind arrow has correct rotation', () => {
    render(<WeatherSection weather={mockWeather} />);
    const arrow = screen.getByLabelText(/Wind from 225/);
    expect(arrow).toHaveStyle({ transform: 'rotate(225deg)' });
  });

  it('has accessible label', () => {
    render(<WeatherSection weather={mockWeather} />);
    expect(screen.getByRole('status', { name: /weather conditions/i })).toBeInTheDocument();
  });

  it('formats temperature to one decimal place', () => {
    render(<WeatherSection weather={{ ...mockWeather, air_temperature: 30.0 }} />);
    expect(screen.getByText('30.0°C')).toBeInTheDocument();
  });

  it('formats humidity as integer', () => {
    render(<WeatherSection weather={{ ...mockWeather, humidity: 65.7 }} />);
    expect(screen.getByText('66%')).toBeInTheDocument();
  });
});
