import hashlib
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import class_row
from pydantic import BaseModel

from app.extraction import Requirement
from app.llm import CallRecord
from app.parsing import Line

MAX_JOBS = 5

DocumentKind = Literal["resume", "job"]


class JobLimitError(Exception):
    def __init__(self) -> None:
        super().__init__(f"You can compare up to {MAX_JOBS} jobs. Remove one to add another.")


class NewDocument(BaseModel):
    kind: DocumentKind
    title: str
    filename: str | None = None
    lines: list[Line]


class DocumentSummary(BaseModel):
    id: UUID
    kind: DocumentKind
    title: str
    filename: str | None
    line_count: int
    created_at: datetime


class DocumentDetail(DocumentSummary):
    lines: list[Line]


_SUMMARY_QUERY = """
    SELECT d.id, d.kind, d.title, d.filename, d.created_at, count(l.line_no) AS line_count
    FROM documents d LEFT JOIN document_lines l ON l.document_id = d.id
"""


def _content_hash(lines: list[Line]) -> str:
    return hashlib.sha256("\n".join(line.text for line in lines).encode()).hexdigest()


def _insert(connection: psycopg.Connection, document: NewDocument) -> UUID:
    document_id = uuid4()
    connection.execute(
        "INSERT INTO documents (id, kind, title, filename, content_hash) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            document_id,
            document.kind,
            document.title,
            document.filename,
            _content_hash(document.lines),
        ),
    )
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO document_lines (document_id, line_no, section, text) "
            "VALUES (%s, %s, %s, %s)",
            [(document_id, line.number, line.section, line.text) for line in document.lines],
        )
    return document_id


def _lock(connection: psycopg.Connection, name: str) -> None:
    """Serialise concurrent writers until this transaction ends."""
    connection.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (name,))


def replace_resume(connection: psycopg.Connection, document: NewDocument) -> UUID:
    _lock(connection, "resume")
    connection.execute("DELETE FROM documents WHERE kind = 'resume'")
    return _insert(connection, document)


def add_job(connection: psycopg.Connection, document: NewDocument) -> UUID:
    _lock(connection, "jobs")  # so two uploads can't both take the last place
    (count,) = connection.execute("SELECT count(*) FROM documents WHERE kind = 'job'").fetchone()
    if count >= MAX_JOBS:
        raise JobLimitError()
    return _insert(connection, document)


def list_documents(connection: psycopg.Connection) -> list[DocumentSummary]:
    with connection.cursor(row_factory=class_row(DocumentSummary)) as cursor:
        cursor.execute(_SUMMARY_QUERY + " GROUP BY d.id ORDER BY d.created_at, d.id")
        return cursor.fetchall()


def get_document(connection: psycopg.Connection, document_id: UUID) -> DocumentDetail | None:
    with connection.cursor(row_factory=class_row(DocumentSummary)) as cursor:
        cursor.execute(_SUMMARY_QUERY + " WHERE d.id = %s GROUP BY d.id", (document_id,))
        summary = cursor.fetchone()
    if summary is None:
        return None
    rows = connection.execute(
        "SELECT line_no, section, text FROM document_lines WHERE document_id = %s ORDER BY line_no",
        (document_id,),
    ).fetchall()
    lines = [Line(number=number, section=section, text=text) for number, section, text in rows]
    return DocumentDetail(**summary.model_dump(), lines=lines)


def delete_document(connection: psycopg.Connection, document_id: UUID) -> bool:
    cursor = connection.execute("DELETE FROM documents WHERE id = %s", (document_id,))
    return cursor.rowcount > 0


def delete_all(connection: psycopg.Connection) -> None:
    connection.execute("DELETE FROM documents")


def get_requirements(
    connection: psycopg.Connection, document_id: UUID, prompt_version: str, model: str
) -> list[Requirement] | None:
    """The stored extraction for this prompt and model, or None if there isn't one."""
    found = connection.execute(
        "SELECT 1 FROM extractions WHERE document_id = %s AND prompt_version = %s AND model = %s",
        (document_id, prompt_version, model),
    ).fetchone()
    if not found:
        return None
    with connection.cursor(row_factory=class_row(Requirement)) as cursor:
        cursor.execute(
            "SELECT position, text, importance, category, line_numbers "
            "FROM requirements WHERE document_id = %s ORDER BY position",
            (document_id,),
        )
        return cursor.fetchall()


def save_requirements(
    connection: psycopg.Connection,
    document_id: UUID,
    prompt_version: str,
    model: str,
    requirements: list[Requirement],
) -> None:
    _lock(connection, f"extraction:{document_id}")
    connection.execute("DELETE FROM extractions WHERE document_id = %s", (document_id,))
    connection.execute(
        "INSERT INTO extractions (document_id, prompt_version, model) VALUES (%s, %s, %s)",
        (document_id, prompt_version, model),
    )
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO requirements "
            "(document_id, position, text, importance, category, line_numbers) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            [
                (document_id, r.position, r.text, r.importance, r.category, r.line_numbers)
                for r in requirements
            ],
        )


def record_llm_call(connection: psycopg.Connection, call: CallRecord) -> None:
    values = call.model_dump()
    columns = ", ".join(values)  # field names of CallRecord, not user input
    placeholders = ", ".join(f"%({name})s" for name in values)
    connection.execute(f"INSERT INTO llm_calls ({columns}) VALUES ({placeholders})", values)
