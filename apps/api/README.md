# TrackPulse API

FastAPI backend for TrackPulse health endpoints and OpenF1 proxy routes.

## Endpoints

- `GET /health/live`
- `GET /health/ready`
- `GET /version`
- `GET /api/v1/sessions/latest`
- `GET /api/v1/openf1/weather/latest`
- `GET /api/v1/openf1/location/sample`

## Development

Install the backend dependencies from `apps/api/pyproject.toml`, then run:

```bash
python -m pytest
```

The service defaults to fixture mode through `TRACKPULSE_OPENF1_MODE=fixture`.

