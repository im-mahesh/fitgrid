"""Everything the fit grid shows, in one read. It never calls the model."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from app import db, extraction, matching, store
from app.config import get_settings

router = APIRouter(prefix="/api")


class JobOverview(BaseModel):
    job: store.DocumentSummary
    # None means "not done yet", which is different from an empty list.
    requirements: list[extraction.Requirement] | None
    matches: list[matching.Match] | None


class Overview(BaseModel):
    resume_id: UUID | None
    jobs: list[JobOverview]


@router.get("/overview", response_model=Overview)
def read_overview() -> Overview:
    settings = get_settings()
    with db.connect(settings.database_url) as connection:
        jobs = [d for d in store.list_documents(connection) if d.kind == "job"]
        return Overview(
            resume_id=store.get_resume_id(connection),
            jobs=[
                JobOverview(
                    job=job,
                    requirements=store.get_requirements(
                        connection, job.id, extraction.PROMPT_VERSION, settings.model
                    ),
                    matches=store.get_matches(
                        connection, job.id, matching.PROMPT_VERSION, settings.model
                    ),
                )
                for job in jobs
            ],
        )
