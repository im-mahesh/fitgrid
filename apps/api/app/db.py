import logging

import psycopg
from pydantic import BaseModel

logger = logging.getLogger(__name__)

CONNECT_TIMEOUT_SECONDS = 3


class DatabaseStatus(BaseModel):
    reachable: bool
    pgvector_version: str | None = None


def check_database(database_url: str) -> DatabaseStatus:
    """Report whether Postgres answers and whether the pgvector extension is installed."""
    try:
        with psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS) as connection:
            row = connection.execute(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
    except psycopg.Error:
        logger.warning("Database check failed", exc_info=True)
        return DatabaseStatus(reachable=False)
    return DatabaseStatus(reachable=True, pgvector_version=row[0] if row else None)
