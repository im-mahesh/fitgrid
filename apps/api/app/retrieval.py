"""Find the lines of the resume and job posts that bear on a question (pgvector).

Lines are embedded the first time they are searched, so uploading stays instant
and documents stored before this existed are covered too.
"""

from uuid import UUID

import psycopg

from app import embeddings
from app.parsing import Line

NEIGHBOURS = 1  # lines either side of a hit: a bullet means little without its heading or employer


def _vector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def _passage(section: str | None, text: str) -> str:
    return f"{section}: {text}" if section and section != text else text


def ensure_embeddings(connection: psycopg.Connection, document_ids: list[UUID]) -> None:
    rows = connection.execute(
        """
        SELECT l.document_id, l.line_no, l.section, l.text
        FROM document_lines l
        LEFT JOIN line_embeddings e
          ON e.document_id = l.document_id AND e.line_no = l.line_no AND e.model = %s
        WHERE l.document_id = ANY(%s) AND e.document_id IS NULL
        ORDER BY l.document_id, l.line_no
        """,
        (embeddings.MODEL, document_ids),
    ).fetchall()
    if not rows:
        return
    vectors = embeddings.embed_passages([_passage(section, text) for *_, section, text in rows])
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO line_embeddings (document_id, line_no, model, embedding) "
            "VALUES (%s, %s, %s, %s::vector) "
            "ON CONFLICT (document_id, line_no) DO UPDATE "
            "SET model = EXCLUDED.model, embedding = EXCLUDED.embedding",
            [
                (document_id, line_no, embeddings.MODEL, _vector(vector))
                for (document_id, line_no, *_), vector in zip(rows, vectors, strict=True)
            ],
        )


def search(
    connection: psycopg.Connection, document_ids: list[UUID], question: str, limit: int
) -> list[tuple[UUID, int]]:
    """The (document, line number) pairs closest to the question, best first.

    An exact scan: with a few hundred lines an approximate index would add
    complexity and lose accuracy for no gain.
    """
    ensure_embeddings(connection, document_ids)
    return connection.execute(
        "SELECT document_id, line_no FROM line_embeddings "
        "WHERE document_id = ANY(%s) AND model = %s "
        "ORDER BY embedding <=> %s::vector, document_id, line_no LIMIT %s",
        (document_ids, embeddings.MODEL, _vector(embeddings.embed_query(question)), limit),
    ).fetchall()


def with_neighbours(hits: set[int], lines: list[Line]) -> list[Line]:
    """The chosen lines plus the ones around them, in document order."""
    wanted = {n + offset for n in hits for offset in range(-NEIGHBOURS, NEIGHBOURS + 1)}
    return [line for line in lines if line.number in wanted]
