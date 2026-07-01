import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';

const weatherSchema = z.object({
  track_temperature: z.coerce.number(),
  air_temperature: z.coerce.number(),
  wind_speed: z.coerce.number(),
  wind_direction: z.coerce.number(),
  rainfall: z.coerce.number()
});

function pickLatestWeatherPayload(payload) {
  if (Array.isArray(payload)) {
    return payload[0] ?? null;
  }

  if (payload && typeof payload === 'object') {
    if (payload.weather && typeof payload.weather === 'object') {
      return payload.weather;
    }

    if (Array.isArray(payload.data)) {
      return payload.data[0] ?? null;
    }

    if (payload.data && typeof payload.data === 'object') {
      return payload.data;
    }

    return payload;
  }

  return null;
}

async function fetchLatestWeather() {
  const response = await fetch('/api/v1/openf1/weather/latest');

  if (!response.ok) {
    throw new Error('Failed to fetch latest weather');
  }

  const payload = await response.json();
  const latestWeather = pickLatestWeatherPayload(payload);

  if (!latestWeather) {
    return null;
  }

  return weatherSchema.parse(latestWeather);
}

export function useLatestWeatherQuery() {
  return useQuery({
    queryKey: ['openf1', 'weather', 'latest'],
    queryFn: fetchLatestWeather,
    staleTime: 30_000,
    retry: false
  });
}
