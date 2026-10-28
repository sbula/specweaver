# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The draft handlers draft through the drafters the run was given; they import no drafting code.

Proves: TECH-081 FR-13

| Bucket | Case |
|---|---|
| Happy | spec and feature drafting call `context.drafters.spec` / `.feature` with the run's LLM |
| Boundary | a run with no drafters parks for the user, like a run with no provider |
| Degradation | a drafter that raises gives an error result, not a crash |
| Hostile | the handler module names no `workflows.drafting` import |
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers import draft as draft_module
from specweaver.core.flow.handlers.draft import DraftFeatureHandler, DraftSpecHandler
from specweaver.core.flow.handlers.run_context import RunContext
from tests.scripted_llm import FixedRouter


class _Drafters:
    """Records what each drafter was built with; each drafter writes its target file."""

    def __init__(self, *, fail: bool = False) -> None:
        self.built: list[tuple[str, dict[str, Any]]] = []
        self._fail = fail

    def _drafter(self, kind: str, kw: dict[str, Any]) -> Any:
        self.built.append((kind, kw))
        fail = self._fail

        async def draft(name: str, specs_dir: Path, **_: Any) -> Path:
            if fail:
                raise RuntimeError("model went away")
            suffix = "_spec.md" if kind == "spec" else "_feature_spec.md"
            path = specs_dir / f"{name}{suffix}"
            path.write_text("# drafted\n", encoding="utf-8")
            return path

        return MagicMock(draft=draft)

    def spec(self, **kw: Any) -> Any:
        return self._drafter("spec", kw)

    def feature(self, **kw: Any) -> Any:
        return self._drafter("feature", kw)


def _context(spec: Path, drafters: _Drafters | None) -> RunContext:
    ctx = RunContext(project_path=spec.parent, spec_path=spec, db=MagicMock())
    ctx.model = ctx.model.model_copy(
        update={"llm_router": FixedRouter(AsyncMock()), "drafters": drafters}
    )
    ctx.context_provider = AsyncMock()
    return ctx


def _step(target: StepTarget) -> PipelineStep:
    return PipelineStep(name="draft", action=StepAction.DRAFT, target=target)


@pytest.mark.asyncio
@patch("specweaver.core.flow.store.FlowRepository")
async def test_spec_drafting_goes_through_the_given_drafters(_repo: Any, tmp_path: Path) -> None:
    drafters = _Drafters()
    ctx = _context(tmp_path / "orders_spec.md", drafters)

    result = await DraftSpecHandler().execute(_step(StepTarget.SPEC), ctx)

    assert result.status == StepStatus.PASSED
    assert [kind for kind, _ in drafters.built] == ["spec"]
    assert drafters.built[0][1]["context_provider"] is ctx.context_provider


@pytest.mark.asyncio
@patch("specweaver.core.flow.store.FlowRepository")
async def test_feature_drafting_goes_through_the_given_drafters(_repo: Any, tmp_path: Path) -> None:
    drafters = _Drafters()
    ctx = _context(tmp_path / "orders_feature_spec.md", drafters)

    result = await DraftFeatureHandler().execute(_step(StepTarget.FEATURE), ctx)

    assert result.status == StepStatus.PASSED
    assert [kind for kind, _ in drafters.built] == ["feature"]


@pytest.mark.asyncio
async def test_a_run_without_drafters_parks(tmp_path: Path) -> None:
    ctx = _context(tmp_path / "orders_spec.md", None)

    result = await DraftSpecHandler().execute(_step(StepTarget.SPEC), ctx)

    assert result.status == StepStatus.WAITING_FOR_INPUT


@pytest.mark.asyncio
async def test_a_failing_drafter_gives_an_error_result(tmp_path: Path) -> None:
    ctx = _context(tmp_path / "orders_spec.md", _Drafters(fail=True))

    result = await DraftSpecHandler().execute(_step(StepTarget.SPEC), ctx)

    assert result.status == StepStatus.ERROR
    assert "model went away" in result.error_message


def test_the_handler_imports_no_drafting_code() -> None:
    tree = ast.parse(Path(draft_module.__file__).read_text(encoding="utf-8"))
    modules = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)] + [
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
    ]

    assert [m for m in modules if m.startswith("specweaver.workflows.drafting")] == []
