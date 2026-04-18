# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the LintFixHandler — lint-fix reflection loop.

Call sequence through the atom:
  1. Initial lint (read-only)
  2. Auto-fix lint (fix=True)  — Phase 1
  3. Re-lint (read-only)       — check what remains after auto-fix
  4+. [LLM fix → re-lint]*     — Phase 2 (up to max_reflections)
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.core.flow.handlers import LintFixHandler, RunContext
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.loom.atoms.base import AtomResult, AtomStatus

if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(tmp_path: Path, *, llm: MagicMock | None = None) -> RunContext:
    """Build a RunContext for testing."""
    output_dir = tmp_path / "output"
    output_dir.mkdir(exist_ok=True)
    return RunContext(
        project_path=tmp_path,
        spec_path=tmp_path / "spec.md",
        llm=llm,
        output_dir=output_dir,
    )


def _make_step(max_reflections: int = 3, target: str = "src/") -> PipelineStep:
    return PipelineStep(
        name="lint_fix",
        action=StepAction.LINT_FIX,
        target=StepTarget.CODE,
        params={"max_reflections": max_reflections, "target": target},
    )


def _clean() -> AtomResult:
    return AtomResult(
        status=AtomStatus.SUCCESS,
        message="No lint errors.",
        exports={"error_count": 0, "fixable_count": 0, "fixed_count": 0, "errors": []},
    )


def _dirty(errors: int = 3) -> AtomResult:
    return AtomResult(
        status=AtomStatus.FAILED,
        message=f"{errors} lint error(s) found.",
        exports={
            "error_count": errors,
            "fixable_count": 0,
            "fixed_count": 0,
            "errors": [
                {"file": "src/foo.py", "line": 10, "code": "E501", "message": f"err {i}"}
                for i in range(errors)
            ],
        },
    )


def _handler(atom_mock: MagicMock) -> LintFixHandler:
    handler = LintFixHandler()
    handler._get_atom = lambda ctx: atom_mock  # type: ignore[method-assign]
    return handler


def _setup_code(tmp_path: Path) -> None:
    """Create a .py file in the output dir."""
    out = tmp_path / "output"
    out.mkdir(exist_ok=True)
    (out / "foo.py").write_text("bad code", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLintFixCleanCode:
    """When initial lint is already clean."""

    @pytest.mark.asyncio
    async def test_clean_lint_passes_immediately(self, tmp_path: Path) -> None:
        """Clean code → PASSED, auto_fixed=False, 0 reflections."""
        mock_atom = MagicMock()
        mock_atom.run.return_value = _clean()

        result = await _handler(mock_atom).execute(_make_step(), _make_context(tmp_path))

        assert result.status == StepStatus.PASSED
        assert result.output["reflections_used"] == 0
        assert result.output["auto_fixed"] is False
        # Only the initial lint call
        assert mock_atom.run.call_count == 1


class TestLintFixAutoFix:
    """Phase 1: ruff auto-fix resolves all errors ⇒ no LLM needed."""

    @pytest.mark.asyncio
    async def test_auto_fix_resolves_all(self, tmp_path: Path) -> None:
        """Dirty → auto-fix → clean. No LLM calls."""
        mock_atom = MagicMock()
        # 1=initial_lint(dirty), 2=auto_fix(accepted), 3=re_lint(clean)
        mock_atom.run.side_effect = [_dirty(), _dirty(), _clean()]

        result = await _handler(mock_atom).execute(_make_step(), _make_context(tmp_path))

        assert result.status == StepStatus.PASSED
        assert result.output["auto_fixed"] is True
        assert result.output["reflections_used"] == 0
        assert mock_atom.run.call_count == 3


class TestLintFixReflectionLoop:
    """Phase 2: auto-fix doesn't resolve all, LLM reflection loop kicks in."""

    @pytest.mark.asyncio
    async def test_fix_succeeds_after_one_reflection(self, tmp_path: Path) -> None:
        """Auto-fix partial → LLM fixes remainder → clean."""
        mock_atom = MagicMock()
        # 1=initial(dirty), 2=auto_fix(partial), 3=re_lint(still dirty),
        # 4=re_lint_after_LLM(clean)
        mock_atom.run.side_effect = [
            _dirty(3),
            _dirty(1),
            _dirty(1),  # initial + autofix + relint
            _clean(),  # after LLM fix
        ]

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="fixed code"))
        _setup_code(tmp_path)

        ctx = _make_context(tmp_path, llm=mock_llm)
        result = await _handler(mock_atom).execute(_make_step(max_reflections=3), ctx)

        assert result.status == StepStatus.PASSED
        assert result.output["reflections_used"] == 1
        assert mock_llm.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_reflections_exhausted(self, tmp_path: Path) -> None:
        """Auto-fix doesn't help, LLM can't fix either → FAILED."""
        mock_atom = MagicMock()
        # All calls return dirty (return_value, not side_effect)
        mock_atom.run.return_value = _dirty()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="still broken"))
        _setup_code(tmp_path)

        ctx = _make_context(tmp_path, llm=mock_llm)
        result = await _handler(mock_atom).execute(_make_step(max_reflections=2), ctx)

        assert result.status == StepStatus.FAILED
        assert result.output["reflections_used"] == 2
        assert result.output["lint_errors_remaining"] > 0
        assert mock_llm.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_fix_on_second_reflection(self, tmp_path: Path) -> None:
        """Auto-fix partial → 2 LLM rounds → clean on 2nd."""
        mock_atom = MagicMock()
        # 1=initial(dirty), 2=auto_fix, 3=re_lint(still dirty),
        # 4=after_LLM1(still dirty), 5=after_LLM2(clean)
        mock_atom.run.side_effect = [
            _dirty(5),
            _dirty(3),
            _dirty(3),  # initial + autofix + relint
            _dirty(1),  # after LLM fix #1
            _clean(),  # after LLM fix #2
        ]

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="fixed"))
        _setup_code(tmp_path)

        ctx = _make_context(tmp_path, llm=mock_llm)
        result = await _handler(mock_atom).execute(_make_step(max_reflections=3), ctx)

        assert result.status == StepStatus.PASSED
        assert result.output["reflections_used"] == 2
        assert mock_llm.generate.call_count == 2


class TestLintFixEdgeCases:
    """Edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_no_llm_configured(self, tmp_path: Path) -> None:
        """Lint fails, auto-fix doesn't resolve, no LLM → FAILED."""
        mock_atom = MagicMock()
        mock_atom.run.return_value = _dirty()

        result = await _handler(mock_atom).execute(
            _make_step(),
            _make_context(tmp_path, llm=None),
        )

        assert result.status == StepStatus.FAILED
        assert "no llm" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_zero_max_reflections(self, tmp_path: Path) -> None:
        """max_reflections=0 → auto-fix only, no LLM attempts."""
        mock_atom = MagicMock()
        mock_atom.run.return_value = _dirty()

        result = await _handler(mock_atom).execute(
            _make_step(max_reflections=0),
            _make_context(tmp_path),
        )

        assert result.status == StepStatus.FAILED
        assert result.output["reflections_used"] == 0

    @pytest.mark.asyncio
    async def test_llm_error_propagates(self, tmp_path: Path) -> None:
        """LLM raises → handler returns ERROR."""
        mock_atom = MagicMock()
        mock_atom.run.return_value = _dirty()

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(side_effect=RuntimeError("LLM kaput"))
        _setup_code(tmp_path)

        result = await _handler(mock_atom).execute(
            _make_step(),
            _make_context(tmp_path, llm=mock_llm),
        )

        assert result.status == StepStatus.ERROR
        assert "LLM kaput" in result.error_message

    @pytest.mark.asyncio
    async def test_no_code_files_found(self, tmp_path: Path) -> None:
        """No .py files in output_dir → FAILED."""
        mock_atom = MagicMock()
        mock_atom.run.return_value = _dirty()

        # Don't create any .py files — output dir is empty
        result = await _handler(mock_atom).execute(
            _make_step(),
            _make_context(tmp_path),
        )

        assert result.status == StepStatus.FAILED


class TestLintFixInterface:
    """Verify standard interface: generate(messages, config)."""

    @pytest.mark.asyncio
    async def test_llm_fix_uses_generate_with_messages_config(self, tmp_path: Path) -> None:
        """LintFixHandler must use the (messages, config) signature."""
        mock_atom = MagicMock()
        mock_atom.run.side_effect = [_dirty(1), _dirty(1), _dirty(1), _clean()]

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="fixed"))
        _setup_code(tmp_path)

        result = await _handler(mock_atom).execute(
            _make_step(), _make_context(tmp_path, llm=mock_llm)
        )

        assert result.status == StepStatus.PASSED
        mock_llm.generate.assert_called_once()
        args, _kwargs = mock_llm.generate.call_args
        # First arg should be a list of Messages
        messages = args[0]
        assert len(messages) == 1
        assert messages[0].role == "user"

        # Second arg should be GenerationConfig
        config = args[1]
        assert config.task_type == "check"
        assert config.temperature == 0.1


class TestLintFixArtifactLineage:
    """Verify artifact lineage tagging and logging during fix loops."""

    @pytest.mark.asyncio
    async def test_lint_fix_extracts_and_injects_uuid(self, tmp_path: Path) -> None:
        """Handler must extract an existing file tag and inject instruction to preserve it."""
        mock_atom = MagicMock()
        mock_atom.run.side_effect = [_dirty(1), _dirty(1), _dirty(1), _clean()]

        out = tmp_path / "output"
        out.mkdir(exist_ok=True)
        py_file = out / "foo.py"
        valid_uuid = "11111111-2222-3333-4444-999999999999"
        py_file.write_text(f"# sw-artifact: {valid_uuid}\ndef bad(): pass\n", encoding="utf-8")

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="fixed"))

        ctx = _make_context(tmp_path, llm=mock_llm)
        result = await _handler(mock_atom).execute(_make_step(), ctx)

        assert result.status == StepStatus.PASSED
        mock_llm.generate.assert_called_once()
        args, _kwargs = mock_llm.generate.call_args
        prompt = args[0][0].content

        # Verify the UUID injection rule is physically present in the LLM prompt
        assert valid_uuid in prompt
        assert "physically at the very top" in prompt

    @pytest.mark.asyncio
    async def test_lint_fix_logs_events_to_db(self, tmp_path: Path) -> None:
        """Handler must log a lint_fixed event to context.db if an artifact_uuid is present."""
        mock_atom = MagicMock()
        mock_atom.run.side_effect = [_dirty(1), _dirty(1), _dirty(1), _clean()]

        out = tmp_path / "output"
        out.mkdir(exist_ok=True)
        py_file = out / "foo.py"
        valid_uuid = "22222222-2222-3333-4444-999999999999"
        py_file.write_text(f"# sw-artifact: {valid_uuid}\ndef bad(): pass\n", encoding="utf-8")

        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="fixed"))

        ctx = _make_context(tmp_path, llm=mock_llm)
        ctx.db = MagicMock()
        ctx.run_id = "test-run-1"

        result = await _handler(mock_atom).execute(_make_step(), ctx)

        assert result.status == StepStatus.PASSED

        # Verify DB logging was called
        assert ctx.db.log_artifact_event.call_count == 1
        ctx.db.log_artifact_event.assert_called_with(
            artifact_id=valid_uuid,
            parent_id=None,
            run_id="test-run-1",
            event_type="lint_fixed",
            model_id="gemini-3-flash-preview",
        )
