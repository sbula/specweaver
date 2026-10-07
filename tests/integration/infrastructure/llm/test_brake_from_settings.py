# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run's limits come from the settings file and stop a real call before it is sent.

Proves: C-FLOW-13 FR-17, B-FLOW-05 FR-5

Settings file → `build_router` → a real adapter → its collector → the brake. Only HTTP is faked.

| Bucket | Case |
|---|---|
| Happy | a GB10 call counts its tokens on the run's, the model's and the role's token limits, and no money |
| Boundary | a hosted call counts money only, the CHF limit converted once to USD |
| Degradation | a `[brake]` value missing → the router refuses before any adapter is built, naming the key |
| Hostile | a role limit below the model's stops the call first, and nothing is sent |
"""

from __future__ import annotations

import httpx2
import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles, SettingsFileError
from specweaver.infrastructure.llm.budget import SpendLimitReachedError
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

_GB10 = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 1000, tokens_per_run = 5000 }

[models."qwen3-coder-next"]
tokens_per_run = 1000000
"""

_HOSTED = """\
[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 4

[roles]
default = { model = "big-model@hosted", max_output_tokens = 1000 }

[models."big-model"]
usd_per_million_input = 1000.0
usd_per_million_output = 1000.0
thinking_in_output_cap = true
"""

_BRAKE = """
[brake]
hosted_spend_per_run = 16
tokens_per_run = 2000000
agent_turns = 30
"""

_CHF = """
[currency]
code = "CHF"
per_usd = 0.8
rate_date = 2026-09-26
"""

_REPLY = {
    "id": "c1",
    "object": "chat.completion",
    "created": 1,
    "model": "m",
    "choices": [
        {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
    ],
    "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
}

_PROMPT = [Message(role=Role.USER, content="hello")]


def _router(machine: str):
    files = LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="settings.toml", project_text="", project_source="-"
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW])


async def _call(router) -> tuple[list[httpx2.Request], object]:
    routed = router.get_for_task(TaskType.REVIEW)
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_REPLY)) as seen:
        await routed.adapter.generate(_PROMPT, routed.config)
    return seen, routed.adapter.budget


class TestALimitedCall:
    async def test_a_gb10_call_counts_tokens_on_every_token_limit_and_no_money(self) -> None:
        seen, budget = await _call(_router(_GB10 + _BRAKE))

        assert len(seen) == 1
        assert budget.spent("brake.tokens_per_run") == 30
        assert budget.spent('models."qwen3-coder-next".tokens_per_run') == 30
        assert budget.spent("roles.default.tokens_per_run") == 30
        assert budget.spent("brake.hosted_spend_per_run") == 0

    async def test_a_hosted_call_counts_money_against_the_converted_limit(self) -> None:
        router = _router(_HOSTED + _BRAKE + _CHF)
        routed = router.get_for_task(TaskType.REVIEW)
        (limit,) = [x for x in routed.adapter.scope(routed.config).limits]

        _seen, budget = await _call(router)

        assert (limit.key, limit.unit) == ("brake.hosted_spend_per_run", "usd")
        assert limit.value == pytest.approx(20.0)  # CHF 16 at 0.8 CHF per USD
        assert budget.spent("brake.hosted_spend_per_run") == pytest.approx(0.03)  # 30 tokens
        assert budget.spent("brake.tokens_per_run") == 0

    def test_a_models_and_a_roles_money_limit_are_converted_too(self) -> None:
        machine = (
            _HOSTED.replace(
                'default = { model = "big-model@hosted", max_output_tokens = 1000 }',
                'default = { model = "big-model@hosted", max_output_tokens = 1000, spend_per_run = 4 }',
            )
            + "spend_per_run = 8\n"
            + _BRAKE
            + _CHF
        )
        router = _router(machine)
        routed = router.get_for_task(TaskType.REVIEW)

        values = {x.key: x.value for x in routed.adapter.scope(routed.config).limits}

        assert values == pytest.approx(
            {
                "brake.hosted_spend_per_run": 20.0,
                'models."big-model".spend_per_run': 10.0,
                "roles.default.spend_per_run": 5.0,
            }
        )

    async def test_a_role_limit_below_the_worst_case_stops_the_call_before_it_is_sent(
        self,
    ) -> None:
        machine = (_GB10 + _BRAKE).replace("tokens_per_run = 5000", "tokens_per_run = 900")

        with pytest.raises(SpendLimitReachedError) as caught:
            await _call(_router(machine))

        assert caught.value.limit.key == "roles.default.tokens_per_run"

    def test_agent_turns_is_every_roles_round_limit(self) -> None:
        router = _router(_GB10 + _BRAKE)

        assert router.get_for_task(TaskType.REVIEW).config.max_tool_rounds == 30
        assert router.get_for_task(TaskType.IMPLEMENT).config.max_tool_rounds == 30


class TestBrakeValueMissing:
    @pytest.mark.parametrize("key", ["hosted_spend_per_run", "tokens_per_run", "agent_turns"])
    def test_the_router_refuses_naming_the_key(self, key: str) -> None:
        brake = "\n".join(line for line in _BRAKE.splitlines() if not line.startswith(key))

        with pytest.raises(SettingsFileError) as caught:
            _router(_GB10 + brake)
        assert caught.value.key == f"brake.{key}"
        assert caught.value.source == "settings.toml"

    def test_no_brake_section_at_all(self) -> None:
        with pytest.raises(SettingsFileError, match=r"brake\.hosted_spend_per_run"):
            _router(_GB10)
