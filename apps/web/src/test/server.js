import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

export const weatherFixture = {
  track_temperature: 43.2,
  air_temperature: 29.1,
  wind_speed: 2.7,
  wind_direction: 310,
  rainfall: false
};

export const server = setupServer(
  http.get('/api/v1/openf1/weather/latest', () =>
    HttpResponse.json({
      data: weatherFixture,
      meta: { request_id: 'test-request-id' }
    })
  )
);
