/**
 * TP-BH-0022 — Whole-system e2e: Bahrain fixture replay vertical slice
 *
 * Prerequisites (must be running before this suite executes):
 *   - Backend:  cd apps/api && TRACKPULSE_OPENF1_MODE=fixture fastapi dev
 *               (or: uvicorn trackpulse_api.main:app --host 127.0.0.1 --port 8000)
 *   - Frontend: managed automatically by Playwright via webServer in playwright.config.js
 *
 * Routing assumption:
 *   The frontend is a single-page app currently served at '/'.
 *   There is no '/replay/bahrain-2023-race' client-side route yet.
 *   This test navigates to '/' and exercises the full replay stack.
 *   When URL routing for fixture sessions is added, update the goto() call
 *   to use the canonical path (e.g. '/replay/bahrain-2023-race').
 *
 * Run locally:
 *   cd apps/web && npm run test:e2e -- --grep "Bahrain fixture replay"
 *
 * Run in CI: see .github/workflows/ci.yml (job: e2e)
 */

import { expect, test } from '@playwright/test';

const BACKEND_URL = process.env.TRACKPULSE_E2E_BACKEND_URL ?? 'http://127.0.0.1:8000';
const FIXTURE_ID = 'bahrain-2023-race';

test.describe('TP-BH-0022 — Bahrain fixture replay vertical slice', () => {
  test.afterEach(async ({ request }) => {
    // Best-effort teardown: stop any running replay so tests don't leak state.
    try {
      await request.post(
        `${BACKEND_URL}/api/v1/replay/${encodeURIComponent(FIXTURE_ID)}/stop`,
      );
    } catch {
      // Ignore — backend may not have started or replay was already idle.
    }
  });

  test(
    'page loads, health ready, weather banner visible, circuit map renders, ' +
      'replay starts, car markers appear, insight cards appear, layer toggles work, ' +
      'no console errors',
    async ({ page, request }) => {
      // Collect application-level console errors (ignore browser noise like missing favicon).
      const consoleErrors = [];
      page.on('console', (msg) => {
        if (msg.type() !== 'error') return;
        const text = msg.text();
        if (/favicon/i.test(text)) return;
        consoleErrors.push(text);
      });

      // ── 1. Backend health ──────────────────────────────────────────────────
      const readyResponse = await request.get(`${BACKEND_URL}/health/ready`);
      expect(readyResponse.ok(), 'health/ready should return HTTP 200').toBeTruthy();

      const readyPayload = await readyResponse.json();
      expect(readyPayload.ready, 'backend should report ready=true').toBeTruthy();
      expect(readyPayload.status, 'backend status should be "ready"').toBe('ready');
      expect(
        readyPayload.dependencies?.openf1?.mode,
        'backend should be in fixture mode for deterministic replay',
      ).toBe('fixture');

      // ── 2. Page loads ──────────────────────────────────────────────────────
      // NOTE: navigates to / because there is no /replay/:id client route yet.
      await page.goto('/');

      await expect(page.getByRole('heading', { name: 'TrackPulse' })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Track Map' })).toBeVisible();

      // ── 3. Circuit map renders ─────────────────────────────────────────────
      await expect(
        page.getByRole('img', { name: /Circuit map with \d+ segments/i }),
      ).toBeVisible();

      // ── 4. Weather banner (Session Status section) is visible ──────────────
      // The section renders immediately; weather data loads once the first
      // track-state snapshot arrives from the backend (fixture mode, always present).
      const sessionStatus = page.getByRole('region', { name: 'Session status' });
      await expect(sessionStatus).toBeVisible();
      await expect(sessionStatus.getByText('Track Temp'), {
        message: 'weather banner should show Track Temp once snapshot loads',
      }).toBeVisible({ timeout: 10_000 });

      // ── 5. Fixture replay controls are present ─────────────────────────────
      const replayControls = page.getByLabel('Fixture replay controls');
      await expect(replayControls).toBeVisible();

      // ── 6. Start replay ────────────────────────────────────────────────────
      const startBtn = replayControls.getByTestId('replay-start-btn');
      await expect(startBtn, 'Start button should be enabled before replay').toBeEnabled({
        timeout: 5_000,
      });
      await startBtn.click();

      await expect(replayControls.getByTestId('replay-status')).toContainText('running', {
        timeout: 8_000,
      });

      // ── 7. At least one car marker appears ────────────────────────────────
      // Car markers are driven by the track-state snapshot (car_markers field).
      // After the replay starts, the backend begins advancing through the timeline
      // and the frontend polls /api/v1/track-state/latest every ~2 s.
      await expect(page.getByTestId('replay-car-marker').first()).toBeVisible({
        timeout: 20_000,
      });

      // ── 8. At least one insight card appears ──────────────────────────────
      // Insights are generated by the rule engine as replay events are processed.
      // The golden fixture includes a high-wind weather entry (≥ 8 m/s) that
      // guarantees at least one wind insight fires in the rule engine.
      const insightCards = page.locator('section[aria-label="Insights"] article');
      await expect
        .poll(async () => insightCards.count(), {
          message: 'expected at least one insight card to appear',
          intervals: [500, 1_000, 2_000],
          timeout: 20_000,
        })
        .toBeGreaterThan(0);
      await expect(insightCards.first()).toBeVisible();

      // ── 9. Layer toggles work ─────────────────────────────────────────────
      // The toolbar is scoped to avoid collision with map segment path buttons
      // that also have role=button (see repo memory note on Wind button collision).
      const layerToolbar = page.getByRole('toolbar', { name: 'Track data layers' });

      await layerToolbar.getByRole('button', { name: 'Wind' }).click();
      await expect(page.getByText('Active Layer: Wind')).toBeVisible();

      await layerToolbar.getByRole('button', { name: 'Traffic' }).click();
      await expect(page.getByText('Active Layer: Traffic')).toBeVisible();

      // Return to a known-neutral layer.
      await layerToolbar.getByRole('button', { name: 'Track Temp' }).click();
      await expect(page.getByText('Active Layer: Track Temp')).toBeVisible();

      // ── 10. No application console errors ────────────────────────────────
      expect(consoleErrors, 'no browser console errors during the test').toEqual([]);
    },
  );
});
