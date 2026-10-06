"""Apply Alembic migrations at startup, waiting for the database if it is still booting."""

import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.logging import get_logger
from app.database.session import engine

logger = get_logger("database")

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CONNECT_ATTEMPTS = 30
CONNECT_DELAY_SECONDS = 2


def wait_for_database() -> None:
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except OperationalError:
            if attempt == CONNECT_ATTEMPTS:
                raise
            logger.warning(
                "Database not reachable yet (attempt %d/%d)", attempt, CONNECT_ATTEMPTS
            )
            time.sleep(CONNECT_DELAY_SECONDS)


def run_migrations() -> None:
    wait_for_database()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")
    logger.info("Database schema is up to date")
