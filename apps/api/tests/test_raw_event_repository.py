from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from trackpulse_api.db.models import RawOpenF1Event
from trackpulse_api.db.repository import RawOpenF1EventRepository


API_ROOT = Path(__file__).resolve().parents[1]


def _upgrade_to_head(db_path: Path) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(config, "head")


@pytest.mark.asyncio
async def test_raw_insert_works(tmp_path: Path) -> None:
    db_path = tmp_path / "raw-insert.db"
    _upgrade_to_head(db_path)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = RawOpenF1EventRepository()

    async with session_factory() as session:
        event = await repository.insert_raw_event(
            session,
            topic="raw.openf1.weather.v1",
            source_id="weather-1",
            payload={"track_temperature": 43.2},
        )
        await session.commit()

        count_result = await session.execute(select(func.count()).select_from(RawOpenF1Event))
        row_count = count_result.scalar_one()

    await engine.dispose()

    assert event.id
    assert event.topic == "raw.openf1.weather.v1"
    assert row_count == 1


@pytest.mark.asyncio
async def test_duplicate_source_event_is_deterministic(tmp_path: Path) -> None:
    db_path = tmp_path / "raw-dedupe.db"
    _upgrade_to_head(db_path)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = RawOpenF1EventRepository()

    async with session_factory() as session:
        first = await repository.insert_raw_event(
            session,
            topic="raw.openf1.location.v1",
            source_id="location-100",
            payload={"x": 0.12, "y": 0.97},
        )
        await session.commit()

    async with session_factory() as session:
        duplicate = await repository.insert_raw_event(
            session,
            topic="raw.openf1.location.v1",
            source_id="location-100",
            payload={"x": 0.21, "y": 0.65},
        )
        await session.commit()

        count_result = await session.execute(select(func.count()).select_from(RawOpenF1Event))
        row_count = count_result.scalar_one()

    await engine.dispose()

    assert duplicate.id == first.id
    assert row_count == 1
