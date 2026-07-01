import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';

const weatherSchema = z.object({
  available: z.boolean(),
  track_temperature_c: z.coerce.number().nullable(),
  air_temperature_c: z.coerce.number().nullable(),
  humidity: z.coerce.number().nullable().optional(),
  pressure: z.coerce.number().nullable().optional(),
  rainfall: z.boolean().nullable(),
  wind_direction_deg: z.coerce.number().nullable(),
  wind_speed_ms: z.coerce.number().nullable(),
  truth_label: z.literal('measured')
});

const snapshotSchema = z.object({
  fixture_id: z.string().nullable(),
  replay_time: z.string().nullable(),
  session_key: z.number().nullable(),
  weather: weatherSchema,
  car_markers: z.array(z.unknown()),
  segment_states: z.array(z.unknown()),
  connection_status: z.string(),
  replay_status: z.string()
});

const responseSchema = z.object({
  snapshot: snapshotSchema
});

async function fetchTrackSnapshot() {
  const response = await fetch('/api/v1/track-state/latest');

  if (!response.ok) {
    throw new Error('Failed to fetch latest track snapshot');
  }

  const payload = await response.json();
  if (!payload || typeof payload !== 'object' || !payload.snapshot) {
    return null;
  }

  return responseSchema.parse(payload).snapshot;
}

export function useTrackSnapshot() {
  return useQuery({
    queryKey: ['track-state', 'latest'],
    queryFn: fetchTrackSnapshot,
    staleTime: 2_000,
    retry: false,
    refetchInterval: 2_000
  });
}
