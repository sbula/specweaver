# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The ceilings come from configuration, and a default install already has them.

Proves: B-FLOW-05 FR-5

A breaker that ships disabled protects nobody, and the queue entry's premise is that nothing
currently caps spend at all. So the default is finite rather than `None`: generous enough that an
ordinary run never reaches it, small enough that a runaway loop stops at a number the operator
would not have chosen to pay.

Both ceilings are settable, and both can be turned off deliberately by writing `null`.
"""

from __future__ import annotations

from specweaver.core.config.settings import LLMSettings


def test_a_default_install_has_a_spend_ceiling() -> None:
    """The control that makes the rest of this capability worth having."""
    assert LLMSettings(model="m").max_spend_usd is not None


def test_a_default_install_has_a_token_ceiling() -> None:
    """The ceiling that still applies when a model is missing from the cost table."""
    assert LLMSettings(model="m").max_tokens_per_run is not None


def test_the_spend_ceiling_is_configurable() -> None:
    assert LLMSettings(model="m", max_spend_usd=3.5).max_spend_usd == 3.5


def test_the_token_ceiling_is_configurable() -> None:
    assert LLMSettings(model="m", max_tokens_per_run=42).max_tokens_per_run == 42


def test_each_ceiling_can_be_disabled_deliberately() -> None:
    settings = LLMSettings(model="m", max_spend_usd=None, max_tokens_per_run=None)

    assert settings.max_spend_usd is None
    assert settings.max_tokens_per_run is None


def test_a_telemetry_adapter_carries_the_configured_ceilings() -> None:
    """The seam. Settings nothing reads are a comment.

    `create_llm_adapter` is the only place a `TelemetryCollector` is built, so it is the only
    place the configured limit can reach the breaker.
    """
    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.infrastructure.llm.factory import create_llm_adapter

    settings = SpecWeaverSettings(
        llm=LLMSettings(model="gemini-3-flash-preview", api_key="k", max_spend_usd=7.5)
    )

    _, adapter, _ = create_llm_adapter(settings, telemetry_project="proj")

    assert adapter.budget.limit_usd == 7.5
