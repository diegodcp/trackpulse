# TrackPulse API

FastAPI backend for TrackPulse health endpoints and OpenF1 proxy routes.

## Endpoints

- `GET /health/live`
- `GET /health/ready`
- `GET /version`
- `GET /api/v1/sessions/latest`
- `GET /api/v1/openf1/weather/latest`
- `GET /api/v1/openf1/location/sample`
- `GET /api/v1/replay/fixtures`
- `POST /api/v1/replay/start`
- `POST /api/v1/replay/stop`
- `GET /api/v1/replay/state`

## Development

Install the backend dependencies from `apps/api/pyproject.toml`, then run:

```bash
python -m pytest
```

The service defaults to fixture mode through `TRACKPULSE_OPENF1_MODE=fixture`.

## Running against real OpenF1 data

Use historical mode to fetch public 2023 data from OpenF1.
No bearer token is required for this workflow.

1. Copy the local template:

	```bash
	cp .env.local.example .env.local
	```

2. Start the API with the env file:

	```bash
	fastapi dev trackpulse_api/main.py --env-file .env.local
	```

3. Verify it is using historical mode:

	```bash
	curl http://127.0.0.1:8000/api/v1/openf1/weather/latest
	```

Minimum required setting:

```env
TRACKPULSE_OPENF1_MODE=historical
```

The provided `apps/api/.env.local.example` includes optional `TRACKPULSE_OPENF1_*`
seed and timeout overrides you can tune for local development.

