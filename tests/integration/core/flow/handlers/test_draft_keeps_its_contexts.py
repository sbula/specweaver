# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Drafting hands the drafter the related modules the run setup found.

Proves: TECH-088 FR-2

Drafting is the one reader of the topology slot that worked before `TECH-088`: it took the list the
run setup stored. This pins that path through the real run setup, so moving the reader to its own
field cannot lose it. Only the drafter is doubled; it records what it was given.

| Bucket | Case |
|---|---|
| Happy | a spec for `billing` is drafted with `payments` as its one related context |
| Boundary | a module no `context.yaml` names is drafted with no contexts |
| Degradation | — the drafter double cannot fail; the handler's own failures are tested in its unit tests |
| Hostile | — the contexts come from the run setup, not from input the test controls |
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.draft import DraftSpecHandler
from specweaver.interfaces.run_setup.builder import build_run_sync
from tests.fixtures.module_graph_project import module_graph_project, run_request
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


class _RecordingDrafters:
    """Builds drafters that write the spec and remember the contexts they were handed."""

    def __init__(self) -> None:
        self.seen: dict[str, Any] = {}

    def spec(self, **_kw: Any) -> Any:
        recorder = self

        class _Drafter:
            async def draft(self, name: str, specs_dir: Path, **kwargs: Any) -> Path:
                recorder.seen.update(kwargs)
                path = specs_dir / f"{name}_spec.md"
                path.write_text(f"# {name}\n", encoding="utf-8")
                return path

        return _Drafter()

    def feature(self, **_kw: Any) -> Any:
        raise AssertionError("a spec draft built a feature drafter")


async def _draft(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module: str) -> dict[str, Any]:
    db, root = module_graph_project(tmp_path, monkeypatch)
    (root / "specs" / f"{module}_spec.md").unlink()
    with doubled_llm(MagicMock()):
        context = build_run_sync(run_request(db, root, module, StepAction.DRAFT))
        drafters = _RecordingDrafters()
        context.model = context.model.model_copy(update={"drafters": drafters})
        context.context_provider = MagicMock()
        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        result = await DraftSpecHandler().execute(step, context)
    assert result.status == StepStatus.PASSED, result.error_message
    return drafters.seen


async def test_the_drafter_gets_the_related_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = await _draft(tmp_path, monkeypatch, "billing")

    assert [c.name for c in seen["topology_contexts"]] == ["payments"]


async def test_an_unnamed_module_is_drafted_without_contexts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = await _draft(tmp_path, monkeypatch, "orphan")

    assert seen["topology_contexts"] is None
