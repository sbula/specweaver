# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — LintFixHandler with real ruff subprocess.

Exercises the LintFixHandler's auto-fix pass with actual ruff running
against the sample project fixture. Only the LLM is mocked.

Uses the shared ``sample_project`` fixture for project scaffolding.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from specweaver.core.flow.handlers import LintFixHandler, RunContext
from specweaver.core.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.state import StepStatus

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_context(project: Path, *, llm: object = None) -> RunContext:
    """Create a RunContext from the sample project."""
    spec = project / "specs" / "calculator.md"
    return RunContext(project_path=project, spec_path=spec, llm=llm)


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
