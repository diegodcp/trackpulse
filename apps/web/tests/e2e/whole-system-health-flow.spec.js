import { expect, test } from '@playwright/test';

const BACKEND_URL = process.env.TRACKPULSE_E2E_BACKEND_URL ?? 'http://127.0.0.1:8000';

test('whole-system fixture-mode health flow', async ({ page, request }) => {
  const criticalConsoleErrors = [];

  page.on('console', (message) => {
    if (message.type() !== 'error') {
      return;
    }

    const text = message.text();
    if (/favicon/i.test(text)) {
      return;
    }

    criticalConsoleErrors.push(text);
  });

  const readyResponse = await request.get(`${BACKEND_URL}/health/ready`);
  expect(readyResponse.ok()).toBeTruthy();

  const readyPayload = await readyResponse.json();
  expect(readyPayload.ready).toBeTruthy();
  expect(readyPayload.status).toBe('ready');
  expect(readyPayload.dependencies?.openf1?.mode).toBe('fixture');

  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'TrackPulse' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Track Map' })).toBeVisible();
  await expect(page.getByRole('img', { name: /Circuit map with \d+ segments/i })).toBeVisible();

  const layerToolbar = page.getByRole('toolbar', { name: 'Track data layers' });

  await layerToolbar.getByRole('button', { name: 'Track Temp' }).click();
  await expect(page.getByText(/^Track Temp\d+\.\d C$/)).toBeVisible();

  await layerToolbar.getByRole('button', { name: 'Wind' }).click();
  await expect(page.getByText('Active Layer: Wind')).toBeVisible();

  const insightCards = page.locator('section[aria-label="Insights"] article');
  await expect(insightCards.first()).toBeVisible();
  await expect.poll(async () => insightCards.count()).toBeGreaterThan(0);

  expect(criticalConsoleErrors).toEqual([]);
});