import os

from pydantic import BaseModel

DEFAULT_DATABASE_URL = "postgresql://fitgrid:fitgrid@localhost:5434/fitgrid"


class Settings(BaseModel):
    database_url: str


def get_settings() -> Settings:
    return Settings(database_url=os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
