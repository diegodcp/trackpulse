from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

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


@dataclass(frozen=True)
class SessionRef:
    session_key: int
    meeting_key: int | None


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
    session = await _discover_session(args)

    if args.dry_run:
        plan = build_dry_run_plan(args, session)
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    print(
        "download execution is not implemented yet; use --dry-run to inspect the deterministic request plan"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_run_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
