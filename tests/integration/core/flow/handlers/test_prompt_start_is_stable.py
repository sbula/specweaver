# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Two runs of one step send the same prompt start, so the second can read it from a cache.

Proves: C-FLOW-14 FR-3, NFR-1

Two real `RunContext`s, each building its own project metadata with its own timestamp, through the
base prompt every handler starts from.

| Bucket | Case |
|---|---|
| Happy | two runs a moment apart send the same text up to the run clock |
| Boundary | the clock still holds each run's own timestamp |
| Degradation | not applicable — the prompt is built, not sent |
| Hostile | decomposition still reads the run's timestamp from the metadata |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.handlers.base import _build_base_prompt
from specweaver.core.flow.handlers.run_context import AnalysisContext, GuidanceContent, RunContext

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _context(tmp_path: Path) -> RunContext:
    return RunContext(
        analysis=AnalysisContext(parsers={}),
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
        guidance=GuidanceContent(constitution="Always be honest.", standards="Use type hints."),
    )


async def test_two_runs_send_the_same_start(tmp_path: Path) -> None:
    first_context = _context(tmp_path)
    await asyncio.sleep(0.01)
    second_context = _context(tmp_path)

    first = (await _build_base_prompt(first_context, "Review the spec.")).build()
    second = (await _build_base_prompt(second_context, "Review the spec.")).build()

    assert first_context.project_metadata.date_iso != second_context.project_metadata.date_iso
    assert first.split("<run_clock>")[0] == second.split("<run_clock>")[0]
    assert first_context.project_metadata.date_iso in first.split("<run_clock>")[1]
    assert "<constitution>" in first.split("<run_clock>")[0]
