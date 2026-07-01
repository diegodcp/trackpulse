# apps/web

TrackPulse web frontend.

## TP-FE-01 UI shell

Implemented components:

- `AppShell`
- `SessionStatusBar`
- `TrackMapPanel`
- `LayerToggleBar`
- `InsightPanel`
- `InsightCard`
- `TruthLabelBadge`

## Commands

- `npm install`
- `npm run dev`
- `npm run test`
- `npm run test:e2e`

During local development, Vite proxies `/api/*` requests to the FastAPI backend at `http://127.0.0.1:8000`.

## Running e2e tests

### Locally

The e2e suite requires both the backend and the frontend dev server to be running.

**1. Start the backend** (fixture mode, no credentials needed):

```bash
cd apps/api
TRACKPULSE_OPENF1_MODE=fixture fastapi dev
# or: uvicorn trackpulse_api.main:app --host 127.0.0.1 --port 8000
```

**2. Run Playwright** (frontend dev server is started automatically):

```bash
cd apps/web
npm run test:e2e
```

To run only the Bahrain replay slice:

```bash
npx playwright test --grep "Bahrain fixture replay"
```

To run with a visible browser (headed mode):

```bash
npx playwright test --headed
```

To view the HTML report after a run:

```bash
npx playwright show-report
```

### In CI

The GitHub Actions workflow (`.github/workflows/ci.yml`, job `e2e`) starts the backend automatically in fixture mode and runs all Playwright tests. On failure, screenshots, traces, and the HTML report are uploaded as a `playwright-report` artefact (retained for 14 days).

### Failure artefacts

Playwright is configured to capture on failure:

- **Screenshot** — full-page PNG of the browser at the moment of failure.
- **Trace** — Playwright trace file (`.zip`); open with `npx playwright show-trace <file>`.
- **Video** — screen recording of the failing test.

All artefacts are written to `test-results/` locally and uploaded to CI artefacts.

### Golden fixture

The e2e suite uses the committed golden fixture at
`examples/fixtures/bahrain-2023-race/golden/`. This fixture is small and
deterministic. Do **not** replace it with generated `dev/` or `full/` fixture
data — those directories are git-ignored and must never be committed.

