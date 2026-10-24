# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Generation and the merge allow-list name the same module for a spec with `_spec` inside its name.

Proves: D-INTL-08 FR-1

`my_spec_tool_spec.md` was `my_tool` to generation and the merge, and `my_spec_tool` to
`sw implement`'s QA targets (`TECH-073`).

| Bucket | Case |
|---|---|
| Happy | the generated file is the one the merge allow-list names |
| Boundary | the spec's name holds `_spec` twice |
| Degradation | not applicable — names only |
| Hostile | not applicable — names only |
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.isolation import derive_allowed_paths
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.models import LLMResponse
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


class _Model:
    def available(self) -> bool:
        return True

    async def generate(self, *_a: Any, **_k: Any) -> LLMResponse:
        return LLMResponse(text="def tool() -> int:\n    return 1\n", model="test-model")


def test_generation_writes_the_file_the_merge_allows(tmp_path: Path) -> None:
    spec = tmp_path / "specs" / "my_spec_tool_spec.md"
    spec.parent.mkdir()
    spec.write_text("# Tool\n## 1. Purpose\nCounts.\n", encoding="utf-8")
    context = RunContext(
        project_path=tmp_path,
        spec_path=spec,
        model=ModelAccess(config=MagicMock(), llm_router=FixedRouter(_Model())),
    )
    step = PipelineStep(name="code", action=StepAction.GENERATE, target=StepTarget.CODE)
    pipeline = PipelineDefinition(name="p", steps=[step])

    asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())

    allowed = derive_allowed_paths(spec)
    assert allowed[0] == "src/my_spec_tool.py"
    assert (tmp_path / allowed[0]).is_file()


def test_sw_implement_targets_the_same_module(tmp_path: Path) -> None:
    """The implement pipeline names no file; its steps find the task's, the module the session
    policy allows."""
    from pathlib import Path as _Path

    from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
    from specweaver.core.flow.handlers.lint_fix import _lint_target
    from specweaver.core.flow.handlers.qa_targets import default_test_target

    spec = _Path("specs/my_spec_tool_spec.md")
    (tmp_path / "specs").mkdir()
    (tmp_path / spec).write_text("# Tool\n")
    context = RunContext(
        project_path=tmp_path, spec_path=tmp_path / spec, output_dir=tmp_path / "src"
    )
    step = PipelineStep(name="lint_fix", action=StepAction.LINT_FIX, target=StepTarget.CODE)

    assert _lint_target(step, context) == derive_allowed_paths(spec)[0]
    assert default_test_target(context, "unit") == derive_allowed_paths(spec)[1]
