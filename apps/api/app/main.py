import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

import psycopg
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app import db, documents, llm, parsing, requirements, store
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    db.init_schema(get_settings().database_url)
    yield


app = FastAPI(
    title="FitGrid API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
app.include_router(documents.router)
app.include_router(requirements.router)


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"detail": message}, status_code=status)


@app.exception_handler(parsing.ParsingError)
def unreadable_document(_: Request, exc: parsing.ParsingError) -> JSONResponse:
    return _error(400, str(exc))


@app.exception_handler(store.JobLimitError)
def too_many_jobs(_: Request, exc: store.JobLimitError) -> JSONResponse:
    return _error(409, str(exc))


@app.exception_handler(llm.LLMError)
def model_failed(_: Request, exc: llm.LLMError) -> JSONResponse:
    return _error(exc.status_code, str(exc))


@app.exception_handler(psycopg.OperationalError)
def database_unavailable(_: Request, exc: psycopg.OperationalError) -> JSONResponse:
    logger.error("Database unavailable: %s", type(exc).__name__)
    return _error(503, "The database is unavailable. Try again shortly.")


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: db.DatabaseStatus


@app.get("/api/health", response_model=HealthResponse)
def health(response: Response) -> HealthResponse:
    database = db.check_database(get_settings().database_url)
    healthy = database.reachable and database.pgvector_version is not None
    if not healthy:
        response.status_code = 503
    return HealthResponse(status="ok" if healthy else "degraded", database=database)
