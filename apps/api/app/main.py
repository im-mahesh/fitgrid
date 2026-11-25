from typing import Literal

from fastapi import FastAPI, Response
from pydantic import BaseModel

from app import db
from app.config import get_settings

app = FastAPI(title="FitGrid API", docs_url="/api/docs", openapi_url="/api/openapi.json")


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
