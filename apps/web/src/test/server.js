import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

export const weatherFixture = {
  track_temperature: 43.2,
  air_temperature: 29.1,
  wind_speed: 2.7,
  wind_direction: 310,
  rainfall: false
};

export const trackSnapshotFixture = {
  snapshot: {
    fixture_id: 'bahrain-2023-race',
    replay_time: '2023-03-05T15:00:00+00:00',
    session_key: 9149,
    weather: {
      available: true,
      track_temperature_c: 43.2,
      air_temperature_c: 29.1,
      humidity: 32,
      pressure: 1012,
      rainfall: false,
      wind_direction_deg: 310,
      wind_speed_ms: 2.7,
      truth_label: 'measured'
    },
    car_markers: [
      {
        driver_number: 1,
        x: 10,
        y: 20,
        truth_label: 'measured',
        location_label: 'approximate',
        occurred_at: '2023-03-05T15:00:00+00:00'
      }
    ],
    segment_states: [],
    connection_status: 'connected',
    replay_status: 'paused'
  }
};

export const replayStateFixture = {
  fixture_id: 'bahrain-2023-race',
  status: 'paused',
  speed_multiplier: 1,
  cursor: 0,
  total_points: 2,
  progress_pct: 50,
  replay_time: '2023-03-05T15:00:00+00:00',
  active_location: {
    occurred_at: '2023-03-05T15:00:00+00:00',
    driver_number: 1,
    x: 10,
    y: 20
  },
  coordinate_bounds: {
    min_x: 10,
    max_x: 11,
    min_y: 20,
    max_y: 21
  },
  timeline_points: [
    {
      occurred_at: '2023-03-05T15:00:00+00:00',
      driver_number: 1,
      x: 10,
      y: 20
    },
    {
      occurred_at: '2023-03-05T15:00:01+00:00',
      driver_number: 11,
      x: 11,
      y: 21
    }
  ]
};

export const server = setupServer(
  http.get('/api/v1/openf1/weather/latest', () => HttpResponse.json({ data: weatherFixture })),
  http.get('/api/v1/track-state/latest', () => HttpResponse.json(trackSnapshotFixture)),
  http.get('/api/v1/replay/fixtures', () =>
    HttpResponse.json({
      fixtures: [
        {
          fixture_id: 'bahrain-2023-race',
          display_name: 'Bahrain 2023 Race',
          source_mode: 'fixture',
          supported_speeds: [1, 5, 10]
        }
      ]
    })
  ),
  http.get('/api/v1/replay/state', () => HttpResponse.json(replayStateFixture)),
  http.post('/api/v1/replay/start', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({
      ...replayStateFixture,
      status: 'running',
      speed_multiplier: body.speed_multiplier ?? 1
    });
  }),
  http.post('/api/v1/replay/stop', () =>
    HttpResponse.json({
      ...replayStateFixture,
      status: 'paused'
    })
  )
);
