"""One structured call to Claude, with its outcome, tokens, time and cost recorded.

Prompts and replies contain personal or untrusted text, so neither is logged.
"""

import logging
import os
import time
from collections.abc import AsyncIterator, Callable
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

MAX_TOKENS = 16000  # thinking counts towards this, so leave room
TIMEOUT_SECONDS = 150  # matching 40 requirements can take over a minute
MAX_RETRIES = 1
EFFORT = "medium"
CHAT_EFFORT = "low"  # conversational answers: favour a quick first token
# Lets the API retry a request on another model if a safety classifier declines it.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
PRICE_PER_MILLION_TOKENS = {  # (input, output) in USD
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
}

Outcome = Literal["ok", "refusal", "truncated", "invalid_output", "api_error", "cancelled"]


class CallRecord(BaseModel):
    stage: str
    model: str
    prompt_version: str
    duration_ms: int
    outcome: Outcome
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    rejected_items: int = 0
    cost_usd: float | None = None


class LLMError(Exception):
    """A call failed; the message is safe to show the user."""

    def __init__(self, message: str, status_code: int = 502, record: CallRecord | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.record = record


def _require_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise LLMError("ANTHROPIC_API_KEY is not set. Add it to .env and restart the API.", 503)


def get_client() -> anthropic.Anthropic:
    _require_key()
    return anthropic.Anthropic(timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)


def get_async_client() -> anthropic.AsyncAnthropic:
    _require_key()
    return anthropic.AsyncAnthropic(timeout=TIMEOUT_SECONDS, max_retries=MAX_RETRIES)


def structured_call[T: BaseModel](
    client: anthropic.Anthropic,
    *,
    model: str,
    system: str,
    user: str,
    output_type: type[T],
    stage: str,
    prompt_version: str,
) -> tuple[T, CallRecord]:
    """Ask for JSON matching `output_type`. Raises LLMError, carrying the record, on failure."""
    started = time.monotonic()

    def record(outcome: Outcome, response: object = None) -> CallRecord:
        entry = _record(response, model, stage, prompt_version, outcome, started)
        logger.info("llm_call %s", entry.model_dump_json())
        return entry

    try:
        response = client.beta.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": EFFORT,
                "format": {
                    "type": "json_schema",
                    "schema": anthropic.transform_schema(output_type),
                },
            },
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.APIError as exc:
        message, status = _describe(exc)
        raise LLMError(message, status, record("api_error")) from exc

    if response.stop_reason == "refusal":
        raise LLMError("The model declined to process this.", record=record("refusal", response))
    if response.stop_reason == "max_tokens":
        raise LLMError("The model's reply was cut off.", record=record("truncated", response))
    try:
        parsed = output_type.model_validate_json(_reply_text(response))
    except ValidationError as exc:
        entry = record("invalid_output", response)
        raise LLMError("The model returned an unusable reply.", record=entry) from exc
    return parsed, record("ok", response)


async def stream_text(
    client: anthropic.AsyncAnthropic,
    *,
    model: str,
    system: str,
    messages: list[dict],
    stage: str,
    prompt_version: str,
    on_record: Callable[[CallRecord], None],
) -> AsyncIterator[str]:
    """Yield the reply's text as it arrives; `on_record` gets the call's record however it ends.

    Closing the iterator early (the reader went away) closes the connection,
    which stops generation, and records the call as cancelled.
    """
    started = time.monotonic()
    outcome: Outcome = "cancelled"
    final = None
    produced = False
    try:
        async with client.beta.messages.stream(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=messages,
            output_config={"effort": CHAT_EFFORT},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        ) as stream:
            async for text in stream.text_stream:
                produced = produced or bool(text.strip())
                yield text
            final = await stream.get_final_message()
        if final.stop_reason == "refusal":
            outcome = "refusal"
            raise LLMError("The model declined to answer this.")
        if final.stop_reason == "max_tokens":
            outcome = "truncated"
            raise LLMError("The answer was cut off.")
        if not produced:
            outcome = "invalid_output"
            raise LLMError("The model returned an empty answer.")
        outcome = "ok"
    except anthropic.APIError as exc:
        outcome = "api_error"
        message, status = _describe(exc)
        raise LLMError(message, status) from exc
    finally:
        record = _record(final, model, stage, prompt_version, outcome, started)
        logger.info("llm_call %s", record.model_dump_json())
        on_record(record)


def _reply_text(response: object) -> str:
    """The text of the model that finished the reply (the one after any fallback marker)."""
    blocks = response.content
    start = max((i + 1 for i, b in enumerate(blocks) if b.type == "fallback"), default=0)
    return "".join(b.text for b in blocks[start:] if b.type == "text")


def _record(
    response: object,
    model: str,
    stage: str,
    prompt_version: str,
    outcome: Outcome,
    started: float,
) -> CallRecord:
    entry = CallRecord(
        stage=stage,
        model=getattr(response, "model", None) or model,
        prompt_version=prompt_version,
        outcome=outcome,
        duration_ms=int((time.monotonic() - started) * 1000),
        request_id=getattr(response, "_request_id", None),
    )
    usage = getattr(response, "usage", None)
    if usage:
        entry.input_tokens, entry.output_tokens = usage.input_tokens, usage.output_tokens
        entry.cost_usd = _cost(entry.model, usage.input_tokens, usage.output_tokens)
    return entry


def _cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = PRICE_PER_MILLION_TOKENS.get(model)
    if price is None:
        return None  # unknown model: better no figure than a wrong one
    return (input_tokens * price[0] + output_tokens * price[1]) / 1_000_000


def _describe(exc: anthropic.APIError) -> tuple[str, int]:
    logger.warning("Anthropic API error: %s", type(exc).__name__)
    if isinstance(exc, anthropic.RateLimitError):
        return "Anthropic's rate limit was reached. Try again shortly.", 429
    if isinstance(exc, anthropic.APITimeoutError):
        return "The request to Anthropic timed out.", 504
    if isinstance(exc, anthropic.APIConnectionError):
        return "Could not reach Anthropic.", 503
    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return "Anthropic rejected the server's API key.", 502
    return "Anthropic returned an error.", 502
