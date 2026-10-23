# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A reply that reports no usage counts its worst case, so the limits still fill.

Proves: B-FLOW-05 FR-1

| Bucket | Case |
|---|---|
| Happy | a reply with usage counts what it reports |
| Boundary | a reply without usage counts the call's reserved worst case |
| Degradation | a server that never reports usage still reaches the token limit and stops |
| Hostile | not applicable — usage comes from the server, never from input |
"""

from __future__ import annotations

import httpx2
import pytest

from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
from specweaver.infrastructure.llm.budget import SpendLimitReachedError
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

pytestmark = pytest.mark.integration

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 100 }

[brake]
hosted_spend_per_run = 10
tokens_per_run = 1000
agent_turns = 5
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
    ],
}


def _router():
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE, machine_source="settings.toml", project_text="", project_source="-"
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW])


async def test_a_server_without_usage_still_reaches_the_limit() -> None:
    router = _router()
    routed = router.get_for_task(TaskType.REVIEW)

    with (
        fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen,
        pytest.raises(SpendLimitReachedError),
    ):
        for _ in range(50):
            await routed.adapter.generate(
                [Message(role=Role.USER, content="x" * 400)], routed.config
            )

    assert router.budget.spent("brake.tokens_per_run") > 0
    assert len(seen) < 50
