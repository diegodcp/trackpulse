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
