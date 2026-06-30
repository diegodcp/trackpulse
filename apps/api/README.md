# TrackPulse API

FastAPI backend for TrackPulse health, readiness, and version endpoints.

## Endpoints

- `GET /health/live`
- `GET /health/ready`
- `GET /version`

## Development

Install the backend dependencies from `apps/api/pyproject.toml`, then run:

```bash
python -m pytest
```

The service defaults to fixture mode through `TRACKPULSE_OPENF1_MODE=fixture`.

