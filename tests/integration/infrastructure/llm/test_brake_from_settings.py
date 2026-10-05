# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run's brake takes its numbers from `[brake]` in the machine file, and nowhere else.

Proves: C-FLOW-13 FR-17

The seam: `core.config` parses the values, `infrastructure.llm` builds the run's budget and round
limit from them. Nothing below is doubled except the HTTP the adapters never reach.

| Bucket | Case |
|---|---|
| Happy | `hosted_spend_per_run` in CHF becomes the budget's USD limit; `agent_turns` becomes every role's round limit |
| Boundary | no `[currency]` → the value is already USD |
| Degradation | a `[brake]` value missing → the router refuses before any adapter is built, naming the key |
| Hostile | a spent run's error names the `[brake]` key to raise, in the user's currency |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles, SettingsFileError
from specweaver.infrastructure.llm.budget import BudgetExceededError
from specweaver.infrastructure.llm.models import TaskType
from specweaver.infrastructure.llm.router import build_router

_SERVERS = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 4096 }
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


def _router(machine: str):
    files = LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="settings.toml", project_text="", project_source="-"
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW])


def _budget(router):
    (collector,) = router.collectors()
    return collector._budget


class TestBrakeReachesTheRun:
    def test_the_spend_limit_is_converted_from_the_users_currency(self) -> None:
        router = _router(_SERVERS + _BRAKE + _CHF)
        router.get_for_task(TaskType.REVIEW)

        budget = _budget(router)
        assert budget.limit_usd == pytest.approx(20.0)  # CHF 16 at 0.8 CHF per USD
        assert budget.token_limit == 2_000_000

    def test_without_a_currency_the_value_is_usd(self) -> None:
        router = _router(_SERVERS + _BRAKE)
        router.get_for_task(TaskType.REVIEW)

        assert _budget(router).limit_usd == 16

    def test_agent_turns_is_every_roles_round_limit(self) -> None:
        router = _router(_SERVERS + _BRAKE)

        assert router.get_for_task(TaskType.REVIEW).config.max_tool_rounds == 30
        assert router.get_for_task(TaskType.IMPLEMENT).config.max_tool_rounds == 30


class TestBrakeValueMissing:
    @pytest.mark.parametrize("key", ["hosted_spend_per_run", "tokens_per_run", "agent_turns"])
    def test_the_router_refuses_naming_the_key(self, key: str) -> None:
        brake = "\n".join(line for line in _BRAKE.splitlines() if not line.startswith(key))

        with pytest.raises(SettingsFileError) as caught:
            _router(_SERVERS + brake)
        assert caught.value.key == f"brake.{key}"
        assert caught.value.source == "settings.toml"

    def test_no_brake_section_at_all(self) -> None:
        with pytest.raises(SettingsFileError, match=r"brake\.hosted_spend_per_run"):
            _router(_SERVERS)


class TestSpentRunNamesTheKey:
    def test_the_error_names_the_brake_key_and_the_users_currency(self) -> None:
        router = _router(_SERVERS + _BRAKE + _CHF)
        router.get_for_task(TaskType.REVIEW)
        budget = _budget(router)
        budget.record(cost_usd=25.0)

        with pytest.raises(BudgetExceededError) as caught:
            budget.check()
        message = str(caught.value)
        assert "brake.hosted_spend_per_run" in message
        assert "CHF 20.00" in message  # USD 25 shown in CHF
        assert "CHF 16.00" in message


@pytest.mark.xfail(
    strict=True,
    reason="blocked on B-FLOW-05: the brake does not apply model and role limits yet",
)
class TestModelAndRoleLimitsApplied:
    def test_the_lower_of_a_models_and_a_roles_limit_stops_the_run(self) -> None:
        machine = (
            _SERVERS.replace(
                'default = { model = "qwen3-coder-next@gb10", max_output_tokens = 4096 }',
                'default = { model = "qwen3-coder-next@gb10", max_output_tokens = 4096, '
                "tokens_per_run = 100 }",
            )
            + _BRAKE
            + '\n[models."qwen3-coder-next"]\ntokens_per_run = 1000\n'
        )
        router = _router(machine)
        router.get_for_task(TaskType.REVIEW)
        budget = _budget(router)
        budget.record(cost_usd=0.0, tokens=150)

        with pytest.raises(BudgetExceededError):
            budget.check()
