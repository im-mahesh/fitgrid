import os

from pydantic import BaseModel

DEFAULT_DATABASE_URL = "postgresql://fitgrid:fitgrid@localhost:5434/fitgrid"
DEFAULT_MODEL = "claude-opus-5-5"


class Settings(BaseModel):
    database_url: str
    model: str


def get_settings() -> Settings:
    return Settings(
        database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
        model=os.environ.get("FITGRID_MODEL") or DEFAULT_MODEL,
    )
