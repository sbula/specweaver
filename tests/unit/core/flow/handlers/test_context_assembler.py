# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from specweaver.core.flow.handlers.context_assembler import evaluate_and_fetch_skeleton_context
from specweaver.core.flow.handlers.run_context import RunContext


@pytest.fixture(autouse=True)
def _stop_leaked_patches():
    """Every test below starts a patch without stopping it, so the mock leaks into the next test.

    That matters here specifically: the containment test needs the REAL `CodeStructureAtom`, and a
    leaked mock would hand it a fake one — the test would pass while proving nothing.
    """
    yield
    patch.stopall()


def test_evaluate_and_fetch_skeleton_context_empty() -> None:
    """Story 1: Assembly bypasses execution trivially when target list is empty."""
    ctx = RunContext(project_path=Path("."), spec_path=Path("."))
    res = evaluate_and_fetch_skeleton_context(ctx, [])
    assert res == {}


def test_evaluate_and_fetch_skeleton_context_success(tmp_path: Path) -> None:
    """Story 2: Component successfully delegates payload mappings natively."""
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "foo.md")
    target = tmp_path / "test.py"

    mock_atom_class = patch(
        "specweaver.core.flow.handlers.context_assembler.CodeStructureAtom"
    ).start()
    mock_atom_instance = mock_atom_class.return_value
    mock_atom_instance.run.return_value.status.value = "SUCCESS"
    # `CodeStructureAtom` exports under "structure". This mock said "skeleton" until 2026-08-14,
    # matching the assembler's bug rather than the atom's contract — so the pair agreed with each
    # other and disagreed with production, where the function returned {} for every caller.
    mock_atom_instance.run.return_value.exports = {"structure": "def fake(): pass"}

    res = evaluate_and_fetch_skeleton_context(ctx, [target])

    assert str(target) in res
    assert res[str(target)] == "def fake(): pass"
    mock_atom_instance.run.assert_called_once_with({"intent": "skeletonize", "path": str(target)})


def test_evaluate_and_fetch_skeleton_context_swallows_exception(tmp_path: Path) -> None:
    """Story 3: Extractor safely suppresses underlying architectural exceptions without faulting pipeline runners."""
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "foo.md")
    target = tmp_path / "test.py"

    mock_atom_class = patch(
        "specweaver.core.flow.handlers.context_assembler.CodeStructureAtom"
    ).start()
    mock_atom_instance = mock_atom_class.return_value
    mock_atom_instance.run.side_effect = Exception("Native C-Binding Crash!")

    # Should not raise
    res = evaluate_and_fetch_skeleton_context(ctx, [target])
    assert res == {}


@pytest.mark.asyncio
async def test_evaluate_and_fetch_skeleton_context_concurrency(tmp_path: Path) -> None:
    """Story 11: Context assembler securely manages multi-threaded execution from the pipeline."""
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "foo.md")
    targets = [tmp_path / f"test_{i}.py" for i in range(10)]

    mock_atom_class = patch(
        "specweaver.core.flow.handlers.context_assembler.CodeStructureAtom"
    ).start()
    mock_atom_instance = mock_atom_class.return_value
    mock_atom_instance.run.return_value.status.value = "SUCCESS"
    mock_atom_instance.run.return_value.exports = {"structure": "def concurrent(): pass"}

    def sync_call():
        return evaluate_and_fetch_skeleton_context(ctx, targets)

    res = await asyncio.to_thread(sync_call)
    assert len(res) == 10
    assert mock_atom_instance.run.call_count == 10


def test_skeletonization_is_bounded_to_the_project_root(tmp_path: Path) -> None:
    """[Hostile/containment] the extractor reads inside the project root and refuses outside it.

    `INT-US-05` claims the AST extractor resolves *"without hallucinatory paths"* — a bounded read.
    Nothing verified the bound. Measured 2026-08-14 with `scripts/_mutate_campaign.py`: widening the
    containment root to `context.project_path.parent` **survived all 6853 tests**.

    Chasing that survivor found the reason, and it was worse than a coverage gap: the assembler read
    `res.exports["skeleton"]` while the atom exports `"structure"`, so it returned `{}` for every
    caller and the containment root never mattered. Every other test in this module mocks
    `CodeStructureAtom` and hands back `{"skeleton": ...}`, so they passed against a dead function.

    **Both halves are asserted on purpose.** The first attempt checked only that the outside file was
    absent — which an empty result satisfies, so it passed while proving nothing. Asserting the
    inside file IS returned is what stops this test going vacuous if the feature dies again.

    `TECH-017` SF-02.
    """
    project = tmp_path / "proj"
    project.mkdir()
    (project / "inside.py").write_text("def visible():\n    return 1\n", encoding="utf-8")
    (tmp_path / "outside.py").write_text("def out_of_bounds():\n    return 2\n", encoding="utf-8")

    ctx = RunContext(project_path=project, spec_path=project / "spec.md")
    res = evaluate_and_fetch_skeleton_context(ctx, ["inside.py", "../outside.py"])

    assert "inside.py" in res, (
        "the extractor returned nothing for a file inside the project root — the assembler is "
        f"dead again, and any containment assertion below would be vacuous: {sorted(res)}"
    )
    assert "../outside.py" not in res, (
        "the extractor read outside the project root — the containment root is not bound to "
        f"project_path: {sorted(res)}"
    )
