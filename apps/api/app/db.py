import logging
from collections.abc import Iterator
from pathlib import Path

import psycopg
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 3
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class DatabaseStatus(BaseModel):
    reachable: bool
    pgvector_version: str | None = None


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS)


def get_connection() -> Iterator[psycopg.Connection]:
    """One connection per request, committed if the request succeeds.

    There is no pool yet; add one before this serves real traffic.
    """
    with connect(get_settings().database_url) as connection:
        yield connection


def init_schema(database_url: str) -> None:
    with connect(database_url) as connection:
        connection.execute(SCHEMA_PATH.read_text())


def check_database(database_url: str) -> DatabaseStatus:
    """Report whether Postgres answers and whether the pgvector extension is installed."""
    try:
        with connect(database_url) as connection:
            row = connection.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
    except psycopg.Error:
        logger.warning("Database check failed", exc_info=True)
        return DatabaseStatus(reachable=False)
    return DatabaseStatus(reachable=True, pgvector_version=row[0] if row else None)
