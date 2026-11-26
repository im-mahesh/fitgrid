"""A stand-in for the Anthropic client: records requests and returns canned replies."""

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import httpx2
from anthropic import APIConnectionError, APIStatusError, RateLimitError


def requirement(text: str, lines: list[int], importance: str = "must") -> dict[str, Any]:
    return {"text": text, "importance": importance, "category": "skill", "line_numbers": lines}


def reply(*requirements: dict[str, Any]) -> str:
    return json.dumps({"requirements": list(requirements)})


class FakeClaude:
    def __init__(
        self,
        text: str = "",
        stop_reason: str = "end_turn",
        error: Exception | None = None,
        model: str = "claude-sonnet-5-5",
        blocks: list[SimpleNamespace] | None = None,
    ):
        self.requests: list[dict[str, Any]] = []
        self.error = error
        self.response = SimpleNamespace(
            content=blocks or [SimpleNamespace(type="text", text=text or reply())],
            stop_reason=stop_reason,
            model=model,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500),
            _request_id="req_test",
        )
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **request: Any) -> SimpleNamespace:
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.response


_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(kind: type[APIStatusError], status: int) -> APIStatusError:
    return kind("boom", response=httpx2.Response(status, request=_REQUEST), body=None)


def rate_limited() -> RateLimitError:
    return status_error(RateLimitError, 429)


def unreachable() -> APIConnectionError:
    return APIConnectionError(request=_REQUEST)


def verdict(
    requirement: int, verdict: str, lines: list[int], reason: str = "Your resume says so."
) -> dict[str, Any]:
    return {"requirement": requirement, "verdict": verdict, "reason": reason, "resume_lines": lines}


def match_reply(*results: dict[str, Any]) -> str:
    return json.dumps({"results": list(results)})


class FakeStreamingClaude:
    """The async client's `beta.messages.stream`, replying with canned chunks."""

    def __init__(
        self,
        chunks: tuple[str, ...] = ("Your resume shows ", "Python [R2]."),
        stop_reason: str = "end_turn",
        error: Exception | None = None,
    ):
        self.requests: list[dict[str, Any]] = []
        self.closed = False
        self.chunks = chunks
        self.error = error
        self.final = SimpleNamespace(
            stop_reason=stop_reason,
            model="claude-sonnet-5-5",
            usage=SimpleNamespace(input_tokens=2000, output_tokens=100),
        )
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **request: Any) -> "FakeStreamingClaude":
        self.requests.append(request)
        return self

    async def __aenter__(self) -> "FakeStreamingClaude":
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed = True

    @property
    def text_stream(self) -> AsyncIterator[str]:
        return self._text()

    async def _text(self) -> AsyncIterator[str]:
        for chunk in self.chunks:
            yield chunk
        if self.error:
            raise self.error  # the connection drops after some text

    async def get_final_message(self) -> SimpleNamespace:
        return self.final
