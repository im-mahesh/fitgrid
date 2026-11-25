"""A stand-in for the Anthropic client: records requests and returns canned replies."""

import json
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
        model: str = "claude-opus-5-5",
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
