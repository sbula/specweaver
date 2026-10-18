# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run's timestamp stands at the end of the prompt, so everything before it is the same each run.

Proves: C-FLOW-14 FR-3, NFR-1

| Bucket | Case |
|---|---|
| Happy | the metadata carries no date; the prompt ends with the run clock holding it |
| Boundary | two prompts a moment apart are equal up to the clock |
| Degradation | no metadata: no clock either |
| Hostile | every profile with metadata ends with the clock; one without has none |
"""

from __future__ import annotations

import pytest

from specweaver.core.flow.handlers._profiles import ARBITER, FULL, INTERACTIVE, MINIMAL
from specweaver.infrastructure.llm.models import ProjectMetadata, PromptSafeConfig
from specweaver.infrastructure.llm.prompt.profiles import PromptSlot, RenderProfile
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder


def _meta(date_iso: str) -> ProjectMetadata:
    return ProjectMetadata(
        project_name="demo",
        archetype="generic",
        language_target="Python 3.14",
        date_iso=date_iso,
        safe_config=PromptSafeConfig(llm_provider="fake", llm_model="fake"),
    )


def _prompt(date_iso: str, profile: RenderProfile | None = None) -> str:
    builder = PromptBuilder(profile=profile) if profile else PromptBuilder()
    builder.add_instructions("Review the spec.")
    builder.add_project_metadata(_meta(date_iso))
    builder.add_constitution("Always be honest.")
    return builder.build()


def test_the_metadata_has_no_date_and_the_prompt_ends_with_it() -> None:
    prompt = _prompt("2026-10-18T09:01:02.123456+00:00")

    metadata = prompt.split("<project_metadata>")[1].split("</project_metadata>")[0]
    assert "2026-10-18" not in metadata
    assert prompt.rstrip().endswith("</run_clock>")
    assert "2026-10-18T09:01:02.123456+00:00" in prompt.split("<run_clock>")[1]


@pytest.mark.parametrize(
    "profile", [None, FULL, MINIMAL, INTERACTIVE], ids=["default", "full", "minimal", "interactive"]
)
def test_two_runs_are_equal_up_to_the_clock(profile: RenderProfile | None) -> None:
    first = _prompt("2026-10-18T09:01:02.000001+00:00", profile)
    second = _prompt("2026-10-18T09:07:44.999999+00:00", profile)

    assert first != second
    assert first.split("<run_clock>")[0] == second.split("<run_clock>")[0]


def test_no_metadata_no_clock() -> None:
    prompt = PromptBuilder().add_instructions("x").add_project_metadata(None).build()

    assert "<run_clock>" not in prompt


@pytest.mark.parametrize("profile", [FULL, MINIMAL, INTERACTIVE], ids=lambda p: p.name)
def test_every_profile_with_metadata_ends_with_the_clock(profile: RenderProfile) -> None:
    assert profile.order[-1] == PromptSlot.RUN_CLOCK


def test_a_profile_without_metadata_has_no_clock() -> None:
    assert PromptSlot.RUN_CLOCK not in ARBITER.active_slots
