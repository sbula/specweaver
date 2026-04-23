import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.context_assembler import evaluate_and_fetch_skeleton_context


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
    mock_atom_instance.run.return_value.exports = {"skeleton": "def fake(): pass"}

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
    mock_atom_instance.run.return_value.exports = {"skeleton": "def concurrent(): pass"}

    def sync_call():
        return evaluate_and_fetch_skeleton_context(ctx, targets)

    res = await asyncio.to_thread(sync_call)
    assert len(res) == 10
    assert mock_atom_instance.run.call_count == 10
