"""Keyword-count vectors: texts sharing a keyword are close, with no model to load."""

from app.embeddings import DIMENSIONS

KEYWORDS = ("python", "kubernetes", "postgres", "docker", "react", "leadership")


def embed(text: str) -> list[float]:
    lowered = text.lower()
    counts = [float(lowered.count(word)) for word in KEYWORDS]
    # A small constant keeps the vector non-zero, which cosine distance needs.
    return [*counts, 0.1] + [0.0] * (DIMENSIONS - len(KEYWORDS) - 1)
