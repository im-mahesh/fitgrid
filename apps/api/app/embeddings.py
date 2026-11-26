"""Local sentence embeddings: no document text leaves the machine to be embedded."""

import os
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastembed import TextEmbedding

MODEL = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384  # must match the vector column in schema.sql


@lru_cache(maxsize=1)
def _model() -> "TextEmbedding":
    """Loaded once. The cache directory comes from FASTEMBED_CACHE_PATH."""
    # ONNX Runtime reports usage to Microsoft by default; this must be set before it loads.
    os.environ.setdefault("ORT_DISABLE_TELEMETRY", "1")
    from fastembed import TextEmbedding

    return TextEmbedding(MODEL)


def embed_passages(texts: list[str]) -> list[list[float]]:
    return [vector.tolist() for vector in _model().embed(texts)]


def embed_query(text: str) -> list[float]:
    return next(iter(_model().query_embed(text))).tolist()
