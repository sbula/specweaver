# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The ceilings come from configuration, and a default install already has them.

Proves: B-FLOW-05 FR-5, B-FLOW-05 NFR-2

A breaker that ships disabled protects nobody, and the queue entry's premise is that nothing
currently caps spend at all. So the default is finite rather than `None`: generous enough that an
ordinary run never reaches it, small enough that a runaway loop stops at a number the operator
would not have chosen to pay.

Both ceilings are settable, and both can be turned off deliberately by writing `null`.
"""

from __future__ import annotations

from unittest.mock import patch

from specweaver.core.config.settings import LLMSettings


def test_a_default_install_has_a_spend_ceiling() -> None:
    """The control that makes the rest of this capability worth having."""
    assert LLMSettings().max_spend_usd is not None


def test_a_default_install_has_a_token_ceiling() -> None:
    """The ceiling that still applies when a model is missing from the cost table."""
    assert LLMSettings().max_tokens_per_run is not None


def test_the_spend_ceiling_is_configurable() -> None:
    assert LLMSettings(max_spend_usd=3.5).max_spend_usd == 3.5


def test_the_token_ceiling_is_configurable() -> None:
    assert LLMSettings(max_tokens_per_run=42).max_tokens_per_run == 42


def test_each_ceiling_can_be_disabled_deliberately() -> None:
    settings = LLMSettings(max_spend_usd=None, max_tokens_per_run=None)

    assert settings.max_spend_usd is None
    assert settings.max_tokens_per_run is None


def test_a_telemetry_adapter_carries_the_configured_ceilings() -> None:
    """The seam. Settings nothing reads are a comment.

    `command_router` is where a command's settings meet the resolver that builds every
    `TelemetryCollector`, so it is the only place the configured limit can reach the breaker.
    """
    from specweaver.core.config.llm_settings import LlmSettingsFiles
    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.infrastructure.llm.interfaces.command import command_router
    from specweaver.infrastructure.llm.models import TaskType

    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE, machine_source="-", project_text="", project_source="-"
    )
    settings = SpecWeaverSettings(llm=LLMSettings(max_spend_usd=7.5))

    with patch("specweaver.interfaces.cli._core.load_active_llm_settings", return_value=files):
        router = command_router("proj", settings, [TaskType.REVIEW])

    assert router.get_for_task(TaskType.REVIEW).adapter.budget.limit_usd == 7.5


_MACHINE = """\
[servers.local]
kind = "openai-compatible"
base_url = "http://localhost:8000/v1"
private = true
max_parallel = 1

[roles]
default = { model = "m@local", max_output_tokens = 1024 }
"""
