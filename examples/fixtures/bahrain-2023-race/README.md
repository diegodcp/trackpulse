# Bahrain 2023 Race fixture

This is the first TrackPulse seed event.

Use it to build and test the fixture/replay-first vertical slice before adding more tracks or races.

## Seed query

```text
year=2023
country_name=Bahrain
session_name=Race
```

The application must discover the actual OpenF1 `session_key` through the sessions endpoint. Do not hardcode the discovered value in business logic.

## Sampling targets

The manifest template sets decimation targets for high-frequency endpoints in fixture mode:

- golden: location at 1 Hz, car_data at 1 Hz;
- dev: location at 1 Hz, car_data at 1 Hz.

## Generated files policy

Commit only:

- this README;
- `manifest.template.json`;
- a tiny golden fixture once generated and reviewed.

Do not commit:

- `.data/`;
- dev fixtures;
- full fixtures;
- raw full telemetry for all drivers;
- local credentials.

## Suggested downloader command

```bash
python -m workers.fixtures.download_openf1 \
  --fixture-id bahrain-2023-race \
  --year 2023 \
  --country-name Bahrain \
  --session-name Race \
  --drivers 1,11,14,16,44 \
  --level golden \
  --output examples/fixtures/bahrain-2023-race/golden
```

## Why this fixture exists

It gives TrackPulse a deterministic race replay target for:

- weather banner;
- wind overlay;
- approximate car markers;
- traffic density;
- corner evolution;
- rule-based insight cards;
- whole-system e2e tests.
