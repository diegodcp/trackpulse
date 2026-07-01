from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


API_ROOT = Path(__file__).resolve().parents[1]


def _upgrade_to_head(db_path: Path) -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path.as_posix()}")
    command.upgrade(config, "head")


def test_migration_applies_and_creates_expected_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "migration-test.db"
    _upgrade_to_head(db_path)

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    inspector = inspect(engine)

    table_names = set(inspector.get_table_names())
    assert "raw_openf1_events" in table_names
    assert "track_segment_states" in table_names
    assert "live_insights" in table_names
