"""Requirements of a job post: read what is stored, or extract it with Claude.

Extraction costs money, so it only happens on an explicit POST and the result is
reused until the prompt or model changes.
"""

import logging
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db, extraction, llm, store
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


class RequirementsResponse(BaseModel):
    extracted: bool
    model: str | None = None
    requirements: list[extraction.Requirement] = []


def _stored(job_id: UUID) -> tuple[store.DocumentDetail, RequirementsResponse]:
    settings = get_settings()
    with db.connect(settings.database_url) as connection:
        job = store.get_document(connection, job_id)
        if job is None or job.kind != "job":
            raise HTTPException(404, "Job not found.")
        requirements = store.get_requirements(
            connection, job_id, extraction.PROMPT_VERSION, settings.model
        )
    if requirements is None:
        return job, RequirementsResponse(extracted=False)
    return job, RequirementsResponse(
        extracted=True, model=settings.model, requirements=requirements
    )


def _log_call(record: llm.CallRecord) -> None:
    """Losing a metrics row must not fail a request that has already been paid for."""
    try:
        with db.connect(get_settings().database_url) as connection:
            store.record_llm_call(connection, record)
    except psycopg.Error:
        logger.warning("Could not record an LLM call", exc_info=True)


@router.get("/jobs/{job_id}/requirements", response_model=RequirementsResponse)
def read_requirements(job_id: UUID) -> RequirementsResponse:
    return _stored(job_id)[1]


@router.post("/jobs/{job_id}/requirements", response_model=RequirementsResponse)
def extract_job_requirements(job_id: UUID) -> RequirementsResponse:
    # No database connection is held open while waiting for the model.
    job, current = _stored(job_id)
    if current.extracted:
        return current
    settings = get_settings()
    client = llm.get_client()
    try:
        requirements, record = extraction.extract_requirements(client, settings.model, job.lines)
    except llm.LLMError as exc:
        if exc.record:
            _log_call(exc.record)
        raise
    _log_call(record)
    try:
        with db.connect(settings.database_url) as connection:
            store.save_requirements(
                connection, job_id, extraction.PROMPT_VERSION, settings.model, requirements
            )
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(404, "The job was deleted while it was being read.") from exc
    return RequirementsResponse(extracted=True, model=settings.model, requirements=requirements)
