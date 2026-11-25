"""A job's requirements judged against the resume: read what is stored, or run it.

Matching sends the resume to Anthropic and costs money, so it only happens on an
explicit POST.
"""

from datetime import date
from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db, extraction, llm, matching, store
from app.call_log import log_call
from app.config import get_settings

router = APIRouter(prefix="/api")


class MatchResponse(BaseModel):
    matched: bool
    model: str | None = None
    results: list[matching.Match] = []


class _Inputs(BaseModel):
    requirements: list[extraction.Requirement] | None
    resume: store.DocumentDetail | None
    stored: list[matching.Match] | None


def _load(job_id: UUID) -> _Inputs:
    settings = get_settings()
    with db.connect(settings.database_url) as connection:
        job = store.get_document(connection, job_id)
        if job is None or job.kind != "job":
            raise HTTPException(404, "Job not found.")
        resume_id = store.get_resume_id(connection)
        return _Inputs(
            requirements=store.get_requirements(
                connection, job_id, extraction.PROMPT_VERSION, settings.model
            ),
            resume=store.get_document(connection, resume_id) if resume_id else None,
            stored=store.get_matches(connection, job_id, matching.PROMPT_VERSION, settings.model),
        )


def _response(results: list[matching.Match] | None) -> MatchResponse:
    if results is None:
        return MatchResponse(matched=False)
    return MatchResponse(matched=True, model=get_settings().model, results=results)


@router.get("/jobs/{job_id}/match", response_model=MatchResponse)
def read_match(job_id: UUID) -> MatchResponse:
    return _response(_load(job_id).stored)


@router.post("/jobs/{job_id}/match", response_model=MatchResponse)
def match_job(job_id: UUID) -> MatchResponse:
    inputs = _load(job_id)
    if inputs.stored is not None:
        return _response(inputs.stored)
    if inputs.resume is None:
        raise HTTPException(409, "Add your resume first.")
    if inputs.requirements is None:
        raise HTTPException(409, "Extract this job's requirements first.")
    if not inputs.requirements:
        raise HTTPException(409, "This job has no requirements to compare against.")

    settings = get_settings()
    client = llm.get_client()
    try:
        results, record = matching.match_requirements(
            client, settings.model, inputs.requirements, inputs.resume.lines, date.today()
        )
    except llm.LLMError as exc:
        if exc.record:
            log_call(exc.record)
        raise
    log_call(record)
    try:
        with db.connect(settings.database_url) as connection:
            store.save_matches(
                connection,
                job_id,
                inputs.resume.id,
                matching.PROMPT_VERSION,
                settings.model,
                results,
            )
    except psycopg.errors.ForeignKeyViolation as exc:
        raise HTTPException(409, "Your resume or this job changed. Try again.") from exc
    return _response(results)
