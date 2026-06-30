from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

try:
    from trackpulse_api.openf1 import OpenF1HistoricalClient, SessionDiscoveryQuery
except Exception:  # pragma: no cover - fallback when backend package is unavailable
    from dataclasses import dataclass
    from urllib.parse import urlencode
    from urllib.request import urlopen

    @dataclass(frozen=True)
    class SessionDiscoveryQuery:
        year: int
        country_name: str
        session_name: str

    @dataclass(frozen=True)
    class _FallbackSession:
        session_key: int
        meeting_key: int | None = None

    class OpenF1HistoricalClient:
        def __init__(self, *, base_url: str = "https://api.openf1.org") -> None:
            self._base_url = base_url.rstrip("/")

        async def discover_session(self, query: SessionDiscoveryQuery) -> _FallbackSession:
            params = urlencode(
                {
                    "year": query.year,
                    "country_name": query.country_name,
                    "session_name": query.session_name,
                }
            )
            with urlopen(f"{self._base_url}/v1/sessions?{params}") as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))

            if not payload:
                raise LookupError("No OpenF1 session found for query")

            selected = min(payload, key=lambda item: item.get("session_key", 0))
            return _FallbackSession(
                session_key=int(selected["session_key"]),
                meeting_key=selected.get("meeting_key"),
            )


logger = logging.getLogger(__name__)

VALID_LEVELS = ("golden", "dev", "full")
DEFAULT_HIGH_FREQUENCY_ENDPOINTS = ("location", "car_data")
DEFAULT_ENDPOINTS = (
    "weather",
    "drivers",
    "location",
    "car_data",
    "laps",
    "intervals",
    "position",
    "stints",
    "pit",
    "race_control",
)

# Low-frequency endpoints downloaded in TP-BH-0004.
# High-frequency endpoints (location, car_data) are handled separately in TP-BH-0005.
LOW_FREQUENCY_ENDPOINTS = (
    "sessions",
    "drivers",
    "weather",
    "laps",
    "intervals",
    "position",
    "stints",
    "pit",
    "race_control",
)

# Mandatory endpoints: their failure stops the downloader.
# Assumption: sessions, drivers, and laps are the minimal required set for a usable fixture.
# All other low-frequency endpoints are optional (empty is reported but allowed).
MANDATORY_ENDPOINTS: frozenset[str] = frozenset({"sessions", "drivers", "laps"})

OPENF1_BASE_URL = "https://api.openf1.org"
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 3
DEFAULT_DECIMATION_SAMPLE_RATE_HZ = 1


@dataclass(frozen=True)
class SessionRef:
    session_key: int
    meeting_key: int | None


@dataclass
class EndpointResult:
    endpoint: str
    records: list[dict[str, Any]]
    mandatory: bool
    error: str | None = None

    @property
    def count(self) -> int:
        return len(self.records)

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class DriverEndpointResult:
    endpoint: str
    driver_number: int
    records_before: list[dict[str, Any]]
    records_after: list[dict[str, Any]]
    error: str | None = None

    @property
    def count_before(self) -> int:
        return len(self.records_before)

    @property
    def count_after(self) -> int:
        return len(self.records_after)

    @property
    def ok(self) -> bool:
        return self.error is None


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    path: str,
    params: dict[str, Any],
    *,
    max_retries: int = MAX_RETRIES,
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    """Fetch an OpenF1 endpoint with exponential backoff on 429/5xx."""
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        if attempt > 0:
            wait = 2.0 ** (attempt - 1)  # 1s, 2s, 4s
            logger.debug("Retry %d/%d for %s — waiting %.1fs", attempt, max_retries, path, wait)
            await asyncio.sleep(wait)

        try:
            response = await client.get(path, params=params, timeout=timeout_seconds)

            if response.status_code == 429 or response.status_code >= 500:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )
                logger.warning(
                    "Retryable HTTP %d from %s (attempt %d/%d)",
                    response.status_code,
                    path,
                    attempt + 1,
                    max_retries + 1,
                )
                continue

            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list):
                raise ValueError(f"Expected list from {path}, got {type(payload).__name__}")
            return payload

        except httpx.TimeoutException as exc:
            last_exc = exc
            logger.warning("Timeout fetching %s (attempt %d/%d)", path, attempt + 1, max_retries + 1)

    raise RuntimeError(
        f"Failed to fetch {path} after {max_retries + 1} attempts"
    ) from last_exc


async def _download_low_frequency(
    session: SessionRef,
    *,
    base_url: str = OPENF1_BASE_URL,
    http_client: httpx.AsyncClient | None = None,
) -> list[EndpointResult]:
    """Download all low-frequency endpoints for a discovered session."""
    results: list[EndpointResult] = []

    async def _run(client: httpx.AsyncClient) -> None:
        for endpoint in LOW_FREQUENCY_ENDPOINTS:
            # sessions endpoint accepts session_key as a filter;
            # all other low-frequency endpoints use session_key directly.
            params: dict[str, Any] = {"session_key": session.session_key}

            try:
                records = await _fetch_with_retry(client, f"/v1/{endpoint}", params)
                results.append(
                    EndpointResult(
                        endpoint=endpoint,
                        records=records,
                        mandatory=endpoint in MANDATORY_ENDPOINTS,
                    )
                )
                if records:
                    logger.info("Downloaded %d records from /%s", len(records), endpoint)
                else:
                    logger.warning("Empty response from /%s (optional=%s)", endpoint, endpoint not in MANDATORY_ENDPOINTS)

            except Exception as exc:  # noqa: BLE001
                results.append(
                    EndpointResult(
                        endpoint=endpoint,
                        records=[],
                        mandatory=endpoint in MANDATORY_ENDPOINTS,
                        error=str(exc),
                    )
                )
                logger.error("Failed to download /%s: %s", endpoint, exc)

    if http_client is not None:
        await _run(http_client)
    else:
        async with httpx.AsyncClient(base_url=base_url) as client:
            await _run(client)

    return results


def _parse_openf1_timestamp(value: Any) -> float | None:
    """Parse OpenF1 ISO date values to epoch seconds."""
    if not isinstance(value, str) or not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _decimate_timestamped_records(
    records: list[dict[str, Any]],
    *,
    sample_rate_hz: int,
) -> list[dict[str, Any]]:
    """Deterministically down-sample records by timestamp bucket."""
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be greater than 0")

    if len(records) <= 1:
        return list(records)

    sorted_rows: list[tuple[float, int, dict[str, Any]]] = []
    unparsable: list[tuple[int, dict[str, Any]]] = []

    for idx, record in enumerate(records):
        ts = _parse_openf1_timestamp(record.get("date"))
        if ts is None:
            unparsable.append((idx, record))
            continue
        sorted_rows.append((ts, idx, record))

    # Keep ordering deterministic even if source payload order varies.
    sorted_rows.sort(key=lambda row: (row[0], row[1]))

    selected: list[tuple[float, int, dict[str, Any]]] = []
    seen_buckets: set[int] = set()
    for ts, idx, record in sorted_rows:
        bucket = int(ts * sample_rate_hz)
        if bucket in seen_buckets:
            continue
        seen_buckets.add(bucket)
        selected.append((ts, idx, record))

    # Append unparsable rows in original order instead of dropping unknown data.
    selected.extend((float("inf"), idx, record) for idx, record in unparsable)
    selected.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in selected]


async def _download_high_frequency(
    session: SessionRef,
    drivers: list[int],
    *,
    level: str,
    base_url: str = OPENF1_BASE_URL,
    sample_rate_hz: int = DEFAULT_DECIMATION_SAMPLE_RATE_HZ,
    http_client: httpx.AsyncClient | None = None,
) -> list[DriverEndpointResult]:
    """Download and optionally decimate location/car_data for each selected driver."""
    results: list[DriverEndpointResult] = []
    should_decimate = level in {"golden", "dev"}

    async def _run(client: httpx.AsyncClient) -> None:
        for driver_number in drivers:
            for endpoint in DEFAULT_HIGH_FREQUENCY_ENDPOINTS:
                params = {
                    "session_key": session.session_key,
                    "driver_number": driver_number,
                }
                try:
                    records_before = await _fetch_with_retry(client, f"/v1/{endpoint}", params)
                    records_after = (
                        _decimate_timestamped_records(records_before, sample_rate_hz=sample_rate_hz)
                        if should_decimate
                        else list(records_before)
                    )
                    results.append(
                        DriverEndpointResult(
                            endpoint=endpoint,
                            driver_number=driver_number,
                            records_before=records_before,
                            records_after=records_after,
                        )
                    )
                    if not records_before:
                        logger.warning(
                            "No %s records for driver %d in session %d",
                            endpoint,
                            driver_number,
                            session.session_key,
                        )
                    else:
                        logger.info(
                            "Downloaded %d %s records for driver %d (%d after decimation)",
                            len(records_before),
                            endpoint,
                            driver_number,
                            len(records_after),
                        )
                except Exception as exc:  # noqa: BLE001
                    results.append(
                        DriverEndpointResult(
                            endpoint=endpoint,
                            driver_number=driver_number,
                            records_before=[],
                            records_after=[],
                            error=str(exc),
                        )
                    )
                    logger.error(
                        "Failed to download /%s for driver %d: %s",
                        endpoint,
                        driver_number,
                        exc,
                    )

    if http_client is not None:
        await _run(http_client)
    else:
        async with httpx.AsyncClient(base_url=base_url) as client:
            await _run(client)

    return results


def _write_raw_files(output_dir: Path, results: list[EndpointResult]) -> None:
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        if result.ok:
            dest = raw_dir / f"{result.endpoint}.json"
            dest.write_text(json.dumps(result.records, indent=2), encoding="utf-8")
            logger.info("Wrote %s (%d records)", dest, result.count)


def _write_driver_raw_files(output_dir: Path, driver_results: list[DriverEndpointResult]) -> None:
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for result in driver_results:
        if not result.ok:
            continue
        dest = raw_dir / f"{result.endpoint}.driver_{result.driver_number}.json"
        dest.write_text(json.dumps(result.records_after, indent=2), encoding="utf-8")
        logger.info("Wrote %s (%d records)", dest, result.count_after)


def _build_summary(
    fixture_id: str,
    session: SessionRef,
    results: list[EndpointResult],
    driver_results: list[DriverEndpointResult] | None = None,
) -> dict[str, Any]:
    endpoint_counts: dict[str, Any] = {}
    for result in results:
        if result.ok:
            endpoint_counts[result.endpoint] = result.count
        else:
            endpoint_counts[result.endpoint] = {"error": result.error}

    summary: dict[str, Any] = {
        "fixture_id": fixture_id,
        "session_key": session.session_key,
        "meeting_key": session.meeting_key,
        "endpoints": endpoint_counts,
    }

    if driver_results:
        per_driver: dict[str, dict[str, Any]] = {}
        for result in driver_results:
            driver_key = str(result.driver_number)
            driver_entry = per_driver.setdefault(driver_key, {})
            if result.ok:
                driver_entry[result.endpoint] = {
                    "before": result.count_before,
                    "after": result.count_after,
                }
            else:
                driver_entry[result.endpoint] = {
                    "error": result.error,
                }
        summary["high_frequency"] = {
            "drivers": per_driver,
        }

    return summary


def _write_summary(output_dir: Path, summary: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / "summary.json"
    dest.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Wrote fixture summary to %s", dest)


def _parse_drivers(raw: str) -> list[int]:
    if not raw.strip():
        return []

    parsed: list[int] = []
    for token in raw.split(","):
        value = token.strip()
        if not value:
            continue
        if not value.isdigit():
            raise argparse.ArgumentTypeError(
                "--drivers must be a comma-separated list of numeric driver numbers"
            )
        parsed.append(int(value))

    return sorted(set(parsed))


def _default_output(fixture_id: str, level: str) -> str:
    if level == "golden":
        return str(Path("examples") / "fixtures" / fixture_id / "golden")
    return str(Path(".data") / "openf1" / fixture_id / level)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m workers.fixtures.download_openf1",
        description="Download OpenF1 historical fixture data (skeleton).",
    )
    parser.add_argument("--fixture-id", required=True, help="Fixture identifier, e.g. bahrain-2023-race")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--country-name", required=True)
    parser.add_argument("--session-name", required=True)
    parser.add_argument(
        "--drivers",
        default="",
        type=_parse_drivers,
        help="Comma-separated driver numbers, e.g. 1,11,14",
    )
    parser.add_argument(
        "--level",
        default="dev",
        choices=VALID_LEVELS,
        help="Fixture level to plan/download",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output directory. Defaults to examples/fixtures/... for golden and .data/openf1/... for dev/full.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print request plan without downloading payloads")
    return parser


async def _discover_session(args: argparse.Namespace) -> SessionRef:
    client = OpenF1HistoricalClient()
    session = await client.discover_session(
        SessionDiscoveryQuery(
            year=args.year,
            country_name=args.country_name,
            session_name=args.session_name,
        )
    )
    return SessionRef(session_key=int(session.session_key), meeting_key=session.meeting_key)


def _request(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "endpoint": f"/v1/{endpoint}",
        "params": params,
    }


def build_dry_run_plan(args: argparse.Namespace, session: SessionRef) -> dict[str, Any]:
    output = args.output or _default_output(args.fixture_id, args.level)
    requests: list[dict[str, Any]] = [
        _request(
            "sessions",
            {
                "year": args.year,
                "country_name": args.country_name,
                "session_name": args.session_name,
            },
        )
    ]

    for endpoint in DEFAULT_ENDPOINTS:
        if endpoint in DEFAULT_HIGH_FREQUENCY_ENDPOINTS and args.drivers:
            for driver_number in args.drivers:
                requests.append(
                    _request(
                        endpoint,
                        {
                            "session_key": session.session_key,
                            "driver_number": driver_number,
                        },
                    )
                )
            continue

        requests.append(_request(endpoint, {"session_key": session.session_key}))

    return {
        "dry_run": True,
        "fixture_id": args.fixture_id,
        "level": args.level,
        "output": output,
        "session": asdict(session),
        "drivers": args.drivers,
        "requests": requests,
    }


async def _run_async(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    session = await _discover_session(args)

    if args.dry_run:
        plan = build_dry_run_plan(args, session)
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    output_dir = Path(args.output or _default_output(args.fixture_id, args.level))
    logger.info(
        "Downloading low-frequency endpoints for fixture '%s' (session_key=%d) → %s",
        args.fixture_id,
        session.session_key,
        output_dir,
    )

    results = await _download_low_frequency(session)

    # Check mandatory endpoints first — stop if any failed.
    failed_mandatory = [r for r in results if r.mandatory and not r.ok]
    if failed_mandatory:
        for r in failed_mandatory:
            logger.error("Mandatory endpoint '%s' failed: %s", r.endpoint, r.error)
        logger.error("Download aborted: mandatory endpoint(s) failed: %s", [r.endpoint for r in failed_mandatory])
        return 1

    # Report empty optional endpoints.
    for r in results:
        if r.ok and not r.mandatory and r.count == 0:
            logger.warning("Optional endpoint '%s' returned no records.", r.endpoint)

    _write_raw_files(output_dir, results)

    driver_results: list[DriverEndpointResult] = []
    if args.drivers:
        logger.info(
            "Downloading high-frequency endpoints for drivers %s at level '%s'",
            args.drivers,
            args.level,
        )
        driver_results = await _download_high_frequency(
            session,
            args.drivers,
            level=args.level,
        )

        # Driver-level failures are tolerated unless all selected drivers fail.
        failed_drivers: set[int] = set()
        successful_drivers: set[int] = set()
        by_driver: dict[int, list[DriverEndpointResult]] = {}
        for result in driver_results:
            by_driver.setdefault(result.driver_number, []).append(result)

        for driver, entries in by_driver.items():
            if entries and all(not entry.ok for entry in entries):
                failed_drivers.add(driver)
            else:
                successful_drivers.add(driver)

        if failed_drivers and not successful_drivers:
            logger.error(
                "Download aborted: all selected drivers failed in high-frequency download: %s",
                sorted(failed_drivers),
            )
            return 1

        if failed_drivers:
            logger.warning(
                "High-frequency download failed for drivers %s, continuing with successful drivers.",
                sorted(failed_drivers),
            )

        _write_driver_raw_files(output_dir, driver_results)

    summary = _build_summary(args.fixture_id, session, results, driver_results)
    _write_summary(output_dir, summary)

    print(json.dumps(summary, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
