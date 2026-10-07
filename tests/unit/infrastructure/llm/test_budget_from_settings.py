# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The ceilings come from `[brake]` in the machine `settings.toml`, and nowhere else.

Proves: B-FLOW-05 FR-5, B-FLOW-05 NFR-2

No limit has a value in code. A command that calls a model refuses until `[brake]` sets every
limit, naming the key it is missing — a breaker that silently ran with no ceiling would protect
nobody, and one that ran with a built-in number would spend money nobody chose.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from specweaver.core.config.llm_settings import LlmSettingsFiles, SettingsFileError
from specweaver.infrastructure.llm.models import TaskType
from specweaver.infrastructure.llm.router import build_router

_MACHINE = """\
[servers.local]
kind = "openai-compatible"
base_url = "http://localhost:8000/v1"
private = true
max_parallel = 1

[roles]
default = { model = "m@local", max_output_tokens = 1024 }
"""

_BRAKE = """
[brake]
hosted_spend_per_run = 7.5
tokens_per_run = 42
agent_turns = 10
"""


def _files(machine_text: str) -> LlmSettingsFiles:
    return LlmSettingsFiles.from_texts(
        machine_text=machine_text, machine_source="-", project_text="", project_source="-"
    )


def _limits(machine_text: str) -> dict[str, float]:
    """Each limit a review call counts against, by key."""
    router = build_router(_files(machine_text), project="proj", roles=[TaskType.REVIEW])
    routed = router.get_for_task(TaskType.REVIEW)
    return {limit.key: limit.value for limit in routed.adapter.scope(routed.config).limits}


_HOSTED = _MACHINE.replace("private = true", "private = false") + (
    '\n[models."m"]\nusd_per_million_input = 1.0\nusd_per_million_output = 1.0\n'
    "thinking_in_output_cap = true\n"
)


def test_the_spend_ceiling_comes_from_the_brake_table() -> None:
    assert _limits(_HOSTED + _BRAKE) == {"brake.hosted_spend_per_run": 7.5}


def test_the_token_ceiling_comes_from_the_brake_table() -> None:
    assert _limits(_MACHINE + _BRAKE) == {"brake.tokens_per_run": 42}


def test_the_spend_ceiling_is_given_in_the_configured_currency() -> None:
    currency = '[currency]\ncode = "CHF"\nper_usd = 0.80\nrate_date = 2026-09-26\n\n'

    limits = _limits(currency + _HOSTED + _BRAKE)
    assert limits["brake.hosted_spend_per_run"] == pytest.approx(7.5 / 0.80)


@pytest.mark.parametrize("key", ["hosted_spend_per_run", "tokens_per_run", "agent_turns"])
def test_an_unset_ceiling_refuses_naming_its_key(key: str) -> None:
    brake = "\n".join(line for line in _BRAKE.splitlines() if not line.startswith(key))

    with pytest.raises(SettingsFileError) as caught:
        _limits(_MACHINE + brake)

    assert caught.value.key == f"brake.{key}"


def test_a_telemetry_adapter_carries_the_configured_ceilings() -> None:
    """The seam. Settings nothing reads are a comment.

    `command_router` is where a command's settings files meet the resolver that builds every
    `TelemetryCollector`, so it is the only place the configured limit can reach the breaker.
    """
    from specweaver.infrastructure.llm.interfaces.command import command_router

    files = _files(_HOSTED + _BRAKE)

    with patch("specweaver.interfaces.cli._core.load_active_llm_settings", return_value=files):
        router = command_router("proj", [TaskType.REVIEW])

    routed = router.get_for_task(TaskType.REVIEW)
    (limit,) = routed.adapter.scope(routed.config).limits
    assert (limit.key, limit.value) == ("brake.hosted_spend_per_run", 7.5)
