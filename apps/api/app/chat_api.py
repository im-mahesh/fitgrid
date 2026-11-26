"""POST /api/chat: a streamed, cited answer about the stored resume and jobs.

Events (one JSON object per `data:` line): "sources" first, then "token"s, then
"done", or "error". Questions and answers are not stored or logged.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from anthropic import AsyncAnthropic
from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, RootModel, StringConstraints

from app import chat, db, extraction, llm, matching, retrieval, store
from app.call_log import log_call
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

Question = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=chat.MAX_QUESTION_CHARS),
]


class ChatRequest(BaseModel):
    question: Question
    history: list[chat.ChatMessage] = Field(default=[], max_length=20)
    focus_job_id: UUID | None = None  # the job open on screen, for "this role"


class SourcesEvent(BaseModel):
    type: Literal["sources"] = "sources"
    jobs: list[int]  # the job numbers the answer is about
    sources: list[chat.Source]


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


AnyEvent = Annotated[
    SourcesEvent | TokenEvent | DoneEvent | ErrorEvent, Field(discriminator="type")
]


class ChatStreamEvent(RootModel[AnyEvent]):
    """Documents the stream's payloads in the OpenAPI schema."""


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


def _load_jobs(connection) -> list[chat.Job]:
    settings = get_settings()
    summaries = [d for d in store.list_documents(connection) if d.kind == "job"]
    return [
        chat.Job(
            number=number,  # the same order, and so the same number, as the app shows
            id=job.id,
            title=job.title,
            lines=store.get_document(connection, job.id).lines,
            requirements=store.get_requirements(
                connection, job.id, extraction.PROMPT_VERSION, settings.model
            ),
            matches=store.get_matches(connection, job.id, matching.PROMPT_VERSION, settings.model),
        )
        for number, job in enumerate(summaries, start=1)
    ]


def _retrieve(body: ChatRequest) -> tuple[SourcesEvent, list[dict]]:
    """Gather the evidence for this question and turn it into the model's messages."""
    with db.connect(get_settings().database_url) as connection:
        resume_id = store.get_resume_id(connection)
        if resume_id is None:
            raise HTTPException(409, "Add your resume first.")
        jobs = _load_jobs(connection)
        if not jobs:
            raise HTTPException(409, "Add at least one job first.")
        chosen = chat.resolve_jobs(body.question, body.history, jobs, body.focus_job_id)
        resume = store.get_document(connection, resume_id)
        query = chat.search_text(body.question, body.history)

        found = retrieval.search(connection, [resume_id], query, chat.RESUME_HITS)
        cited = {n for job in chosen for m in job.matches or [] for n in m.line_numbers}
        resume_lines = retrieval.with_neighbours({n for _, n in found} | cited, resume.lines)

        found = retrieval.search(connection, [j.id for j in chosen], query, chat.JOB_HITS)
        job_lines = {
            job.id: retrieval.with_neighbours({n for d, n in found if d == job.id}, job.lines)
            for job in chosen
        }

    context = chat.build_context(chosen, resume_lines, job_lines, date.today())
    event = SourcesEvent(
        jobs=[job.number for job in chosen],
        sources=chat.build_sources(chosen, resume_id, resume_lines, job_lines),
    )
    return event, chat.build_messages(body.question, body.history, context)


def _sse(event: BaseModel) -> str:
    return f"data: {event.model_dump_json()}\n\n"


async def _events(
    http_request: Request, client: AsyncAnthropic, sources: SourcesEvent, messages: list[dict]
) -> AsyncIterator[str]:
    yield _sse(sources)
    tokens = llm.stream_text(
        client,
        model=get_settings().model,
        system=chat.SYSTEM_PROMPT,
        messages=messages,
        stage="chat",
        prompt_version=chat.PROMPT_VERSION,
        on_record=log_call,
    )
    try:
        async with aclosing(tokens):
            async for text in tokens:
                if await http_request.is_disconnected():
                    return
                yield _sse(TokenEvent(text=text))
    except llm.LLMError as exc:
        yield _sse(ErrorEvent(message=str(exc)))
        return
    except Exception:
        # The response has started, so report the failure as an event, not a 500.
        logger.exception("Unexpected error while streaming an answer")
        yield _sse(ErrorEvent(message="Something went wrong while answering."))
        return
    yield _sse(DoneEvent())


@router.post(
    "/chat",
    response_class=EventStreamResponse,
    responses={200: {"model": ChatStreamEvent, "description": "Server-sent events"}},
)
async def ask(body: ChatRequest, http_request: Request) -> EventStreamResponse:
    client = llm.get_async_client()  # fail with 503 before doing any work
    sources, messages = await run_in_threadpool(_retrieve, body)
    return EventStreamResponse(
        _events(http_request, client, sources, messages),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
