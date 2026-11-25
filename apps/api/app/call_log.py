"""Write one metrics row per model call."""

import logging

import psycopg

from app import db, store
from app.config import get_settings
from app.llm import CallRecord

logger = logging.getLogger(__name__)


def log_call(record: CallRecord) -> None:
    """Losing a metrics row must not fail a request that has already been paid for."""
    try:
        with db.connect(get_settings().database_url) as connection:
            store.record_llm_call(connection, record)
    except psycopg.Error:
        logger.warning("Could not record an LLM call", exc_info=True)
