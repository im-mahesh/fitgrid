"""Upload, list, read and delete the resume and job posts.

Document text is personal data (resume) or untrusted input (job posts): it is
never logged here.
"""

from pathlib import PurePath
from typing import Annotated
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel

from app import parsing, store
from app.db import get_connection

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 50_000
MAX_TITLE_CHARS = 80

router = APIRouter(prefix="/api")

# scope="function" commits before the response is sent, so a client that
# refetches straight after an upload is guaranteed to see it.
Connection = Annotated[psycopg.Connection, Depends(get_connection, scope="function")]
UploadedFile = Annotated[UploadFile | None, File()]
PastedText = Annotated[str | None, Form()]


class DocumentList(BaseModel):
    resume: store.DocumentSummary | None
    jobs: list[store.DocumentSummary]


def _read_file(file: UploadFile) -> bytes:
    data = file.file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        limit = MAX_FILE_BYTES // (1024 * 1024)
        raise HTTPException(400, f"The file is too large. The maximum size is {limit} MB.")
    return data


def _parse(file: UploadFile | None, text: str | None) -> tuple[str | None, list[parsing.Line]]:
    """Return (filename, lines) from exactly one of an uploaded file or pasted text."""
    if (file is None) == (not (text or "").strip()):
        raise HTTPException(400, "Provide either a file or pasted text, not both.")
    if file is not None:
        filename = PurePath(file.filename or "").name
        return filename, parsing.lines_from_file(filename, _read_file(file))
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(400, f"Pasted text is limited to {MAX_TEXT_CHARS:,} characters.")
    return None, parsing.lines_from_text(text)


def _title(given: str | None, fallback: str) -> str:
    return ((given or "").strip() or fallback)[:MAX_TITLE_CHARS]


def _saved(connection: psycopg.Connection, document_id: UUID) -> store.DocumentDetail:
    return store.get_document(connection, document_id)


@router.put("/resume", response_model=store.DocumentDetail)
def upload_resume(
    connection: Connection, file: UploadedFile = None, text: PastedText = None
) -> store.DocumentDetail:
    filename, lines = _parse(file, text)
    document = store.NewDocument(
        kind="resume", title=_title(filename, "Pasted resume"), filename=filename, lines=lines
    )
    return _saved(connection, store.replace_resume(connection, document))


@router.post("/jobs", response_model=store.DocumentDetail, status_code=201)
def add_job(
    connection: Connection,
    file: UploadedFile = None,
    text: PastedText = None,
    title: PastedText = None,
) -> store.DocumentDetail:
    filename, lines = _parse(file, text)
    document = store.NewDocument(
        kind="job",
        title=_title(title, filename or lines[0].text),
        filename=filename,
        lines=lines,
    )
    return _saved(connection, store.add_job(connection, document))


@router.get("/documents", response_model=DocumentList)
def list_documents(connection: Connection) -> DocumentList:
    documents = store.list_documents(connection)
    return DocumentList(
        resume=next((d for d in documents if d.kind == "resume"), None),
        jobs=[d for d in documents if d.kind == "job"],
    )


@router.get("/documents/{document_id}", response_model=store.DocumentDetail)
def read_document(document_id: UUID, connection: Connection) -> store.DocumentDetail:
    document = store.get_document(connection, document_id)
    if document is None:
        raise HTTPException(404, "Document not found.")
    return document


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: UUID, connection: Connection) -> Response:
    if not store.delete_document(connection, document_id):
        raise HTTPException(404, "Document not found.")
    return Response(status_code=204)


@router.delete("/documents", status_code=204)
def delete_all_documents(connection: Connection) -> Response:
    store.delete_all(connection)
    return Response(status_code=204)
