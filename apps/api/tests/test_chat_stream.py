"""llm.stream_text: what is recorded when a reader leaves early."""

import asyncio

from app import llm
from fake_claude import FakeStreamingClaude


def test_leaving_early_closes_the_stream_and_records_a_cancellation() -> None:
    client = FakeStreamingClaude(chunks=("one ", "two ", "three"))
    records: list[llm.CallRecord] = []

    async def read_one() -> str:
        tokens = llm.stream_text(
            client,
            model="claude-sonnet-5-5",
            system="s",
            messages=[],
            stage="chat",
            prompt_version="chat-v1",
            on_record=records.append,
        )
        first = await anext(tokens)
        await tokens.aclose()
        return first

    assert asyncio.run(read_one()) == "one "
    assert client.closed
    assert [r.outcome for r in records] == ["cancelled"]
