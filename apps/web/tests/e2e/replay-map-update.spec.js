import { expect, test } from '@playwright/test';

test('fixture replay updates map marker time', async ({ page }) => {
  let replayCursor = 0;
  let replayStatus = 'paused';
  const timeline = [
    {
      occurred_at: '2023-03-05T15:00:00+00:00',
      driver_number: 1,
      x: 10,
      y: 20
    },
    {
      occurred_at: '2023-03-05T15:00:01+00:00',
      driver_number: 11,
      x: 15,
      y: 24
    },
    {
      occurred_at: '2023-03-05T15:00:02+00:00',
      driver_number: 16,
      x: 19,
      y: 28
    }
  ];

  const buildState = () => {
    if (replayStatus === 'running') {
      replayCursor = Math.min(replayCursor + 1, timeline.length - 1);
    }

    return {
      fixture_id: 'bahrain-2023-race',
      status: replayStatus,
      speed_multiplier: 1,
      cursor: replayCursor,
      total_points: timeline.length,
      progress_pct: Number((((replayCursor + 1) / timeline.length) * 100).toFixed(1)),
      replay_time: timeline[replayCursor].occurred_at,
      active_location: timeline[replayCursor],
      coordinate_bounds: {
        min_x: 10,
        max_x: 19,
        min_y: 20,
        max_y: 28
      },
      timeline_points: timeline
    };
  };

  await page.route('**/api/v1/openf1/weather/latest', async (route) => {
    await route.fulfill({
      json: {
        data: {
          track_temperature: 43.2,
          air_temperature: 29.1,
          wind_speed: 2.7,
          wind_direction: 310,
          rainfall: false
        },
        meta: { request_id: 'pw-e2e' }
      }
    });
  });

  await page.route('**/api/v1/replay/fixtures', async (route) => {
    await route.fulfill({
      json: {
        fixtures: [
          {
            fixture_id: 'bahrain-2023-race',
            display_name: 'Bahrain 2023 Race',
            source_mode: 'fixture',
            supported_speeds: [1, 5, 10]
          }
        ]
      }
    });
  });

  await page.route('**/api/v1/replay/state', async (route) => {
    await route.fulfill({ json: buildState() });
  });

  await page.route('**/api/v1/replay/start', async (route) => {
    replayStatus = 'running';
    await route.fulfill({ json: buildState() });
  });

  await page.route('**/api/v1/replay/stop', async (route) => {
    replayStatus = 'paused';
    await route.fulfill({ json: buildState() });
  });

  await page.goto('/');

  await expect(page.getByLabel('Fixture replay controls')).toBeVisible();
  await expect(page.getByTestId('replay-time')).toContainText('2023-03-05T15:00:00');

  await page.getByRole('button', { name: 'Play' }).click();

  await expect.poll(async () => page.getByTestId('replay-time').textContent()).toContain('2023-03-05T15:00:02');
  await expect(page.getByTestId('replay-car-marker')).toBeVisible();
});
