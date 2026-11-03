# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — LintFixHandler with real ruff subprocess.

Exercises the LintFixHandler's auto-fix pass with actual ruff running
against the sample project fixture. Only the LLM is mocked.

Uses the shared ``sample_project`` fixture for project scaffolding.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.lint_fix import LintFixHandler
from specweaver.core.flow.run_state.run_context import ModelAccess, RunContext
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(project: Path, *, llm: object = None) -> RunContext:
    """Create a RunContext from the sample project."""
    spec = project / "specs" / "calculator.md"
    return RunContext(
        project_path=project, spec_path=spec, model=ModelAccess(llm_router=FixedRouter(llm))
    )


def _make_step(target: str = "src/") -> PipelineStep:
    """Create a lint_fix step definition."""
    return PipelineStep(
        name="lint_fix",
        action=StepAction.LINT_FIX,
        target=StepTarget.CODE,
        params={"target": target, "max_reflections": 2},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLintFixAutoFix:
    """Test ruff auto-fix resolves simple errors without LLM."""

    def test_auto_fix_removes_unused_import(self, sample_project: Path) -> None:
        """Unused import → ruff auto-fix resolves it, LLM never called."""
        src = sample_project / "src" / "lint_fix_test"
        src.mkdir(parents=True, exist_ok=True)
        bad_file = src / "fixable.py"
        bad_file.write_text(
            "import os\n\n\ndef foo() -> None:\n    pass\n",
            encoding="utf-8",
        )

        mock_llm = AsyncMock()
        ctx = _make_context(sample_project, llm=mock_llm)
        step = _make_step(target=str(src))

        handler = LintFixHandler()
        result = asyncio.run(handler.execute(step, ctx))

        assert result.status == StepStatus.PASSED
        mock_llm.generate.assert_not_called()

        content = bad_file.read_text(encoding="utf-8")
        assert "import os" not in content

    def test_auto_fix_multiple_files(self, sample_project: Path) -> None:
        """Auto-fix works across multiple files in the target directory."""
        src = sample_project / "src" / "multi_fix_test"
        src.mkdir(parents=True, exist_ok=True)

        (src / "a.py").write_text(
            "import sys\n\n\ndef a() -> None:\n    pass\n",
            encoding="utf-8",
        )
        (src / "b.py").write_text(
            "import json\n\n\ndef b() -> None:\n    pass\n",
            encoding="utf-8",
        )

        mock_llm = AsyncMock()
        ctx = _make_context(sample_project, llm=mock_llm)
        step = _make_step(target=str(src))

        handler = LintFixHandler()
        result = asyncio.run(handler.execute(step, ctx))

        assert result.status == StepStatus.PASSED
        assert "import sys" not in (src / "a.py").read_text(encoding="utf-8")
        assert "import json" not in (src / "b.py").read_text(encoding="utf-8")


class TestLintFixCleanCode:
    """Clean code → handler passes immediately."""

    def test_clean_code_passes_immediately(self, sample_project: Path) -> None:
        """No lint errors on greeter module → PASSED without fixes."""
        clean_dir = sample_project / "src" / "greeter"

        mock_llm = AsyncMock()
        ctx = _make_context(sample_project, llm=mock_llm)
        step = _make_step(target=str(clean_dir))

        handler = LintFixHandler()
        result = asyncio.run(handler.execute(step, ctx))

        assert result.status == StepStatus.PASSED
        assert result.output.get("reflections_used", -1) == 0
        mock_llm.generate.assert_not_called()


class TestLintFixNoLLM:
    """Handler behavior when no LLM is configured."""

    def test_unfixable_without_llm_reports_errors(self, sample_project: Path) -> None:
        """Unfixable error + no LLM → returns remaining errors in output."""
        src = sample_project / "src" / "unfixable_test"
        src.mkdir(parents=True, exist_ok=True)
        # E741 (ambiguous variable) is not auto-fixable
        (src / "unfixable.py").write_text(
            "def foo() -> None:\n    l = [1, 2, 3]\n    print(l)\n",
            encoding="utf-8",
        )

        ctx = _make_context(sample_project, llm=None)
        step = _make_step(target=str(src))

        handler = LintFixHandler()
        result = asyncio.run(handler.execute(step, ctx))

        assert result.output.get("lint_errors_remaining", 0) > 0


class TestLintFixModelRepair:
    """The real linter, the handler and the lint repair together; only the model is scripted.

    Proves: TECH-082 FR-4. The handler hands the file's text and the real ruff errors to
    `repair_lint`, writes back what it returns, and the re-lint judges that file.
    """

    _UUID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"

    def _broken_file(self, project: Path) -> Path:
        src = project / "src" / "repair_test"
        src.mkdir(parents=True, exist_ok=True)
        path = src / "ambiguous.py"
        path.write_text(
            f"# sw-artifact: {self._UUID}\ndef foo() -> None:\n    l = [1, 2, 3]\n    print(l)\n",
            encoding="utf-8",
        )
        return path

    def test_the_model_fix_is_written_and_passes_the_relint(self, sample_project: Path) -> None:
        path = self._broken_file(sample_project)
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = SimpleNamespace(
            text="```python\ndef foo() -> None:\n    items = [1, 2, 3]\n    print(items)\n```"
        )

        result = asyncio.run(
            LintFixHandler().execute(
                _make_step(target=str(path)), _make_context(sample_project, llm=mock_llm)
            )
        )

        assert result.status == StepStatus.PASSED
        assert result.output["reflections_used"] == 1
        prompt = mock_llm.generate.call_args.args[0][-1].content
        assert "E741" in prompt
        assert path.read_text(encoding="utf-8") == (
            f"# sw-artifact: {self._UUID}\n"
            "def foo() -> None:\n    items = [1, 2, 3]\n    print(items)\n"
        )

    def test_a_model_that_fixes_nothing_exhausts_the_loop(self, sample_project: Path) -> None:
        path = self._broken_file(sample_project)
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = SimpleNamespace(text=path.read_text(encoding="utf-8"))

        result = asyncio.run(
            LintFixHandler().execute(
                _make_step(target=str(path)), _make_context(sample_project, llm=mock_llm)
            )
        )

        assert result.status == StepStatus.FAILED
        assert result.output["reflections_used"] == 2
        assert path.read_text(encoding="utf-8").count("sw-artifact") == 1
