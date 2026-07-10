# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for PythonQARunner DAL-aware architecture checking.

Tests the two-phase architecture check:
  Phase 1: context.yaml forbids (AST import scanning)
  Phase 2: tach boundary check (existing behavior)
"""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from specweaver.sandbox.language.core.python.runner import PythonQARunner
from specweaver.sandbox.qa_runner.core.interface import (
    ArchitectureRunResult,
    ArchitectureViolation,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def runner(tmp_path: Path) -> PythonQARunner:
    """Create a PythonQARunner rooted at tmp_path."""
    return PythonQARunner(cwd=tmp_path)


def _write_py(tmp_path: Path, rel_path: str, content: str) -> Path:
    """Write a Python file at rel_path inside tmp_path."""
    p = tmp_path / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


def _write_context_yaml(tmp_path: Path, rel_dir: str, forbids: list[str]) -> Path:
    """Write a context.yaml with the given forbids list."""
    import yaml

    ctx_path = tmp_path / rel_dir / "context.yaml"
    ctx_path.parent.mkdir(parents=True, exist_ok=True)
    ctx_path.write_text(
        yaml.dump({"archetype": "pure-logic", "forbids": forbids}),
        encoding="utf-8",
    )
    return ctx_path


_EMPTY_TACH = ArchitectureRunResult(violation_count=0, violations=[])


class TestForbidsChecking:
    """Phase 1: context.yaml forbids AST import scanning."""

    def test_forbids_violation_detected(self, runner: PythonQARunner, tmp_path: Path) -> None:
        """A forbidden import produces a ForbiddenImport violation."""
        _write_py(
            tmp_path,
            "src/module.py",
            """\
            from specweaver.sandbox.base import Atom
            """,
        )
        _write_context_yaml(tmp_path, "src", ["specweaver/sandbox/*"])

        with patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH):
            result = runner.run_architecture_check(target="src/module.py")

        assert result.violation_count >= 1
        codes = [v.code for v in result.violations]
        assert "ForbiddenImport" in codes

    def test_no_forbids_violation_when_clean(
        self, runner: PythonQARunner, tmp_path: Path
    ) -> None:
        """Clean imports produce zero forbids violations."""
        _write_py(
            tmp_path,
            "src/module.py",
            """\
            import os
            from pathlib import Path
            """,
        )
        _write_context_yaml(tmp_path, "src", ["specweaver/sandbox/*"])

        with patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH):
            result = runner.run_architecture_check(target="src/module.py")

        assert result.violation_count == 0

    def test_no_context_yaml_skips_forbids_check(
        self, runner: PythonQARunner, tmp_path: Path
    ) -> None:
        """Without context.yaml, only tach results are returned."""
        _write_py(
            tmp_path,
            "src/module.py",
            """\
            from specweaver.sandbox.base import Atom
            """,
        )
        # No context.yaml written

        with patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH):
            result = runner.run_architecture_check(target="src/module.py")

        # No forbids violations — only tach would matter
        assert result.violation_count == 0

    def test_forbids_pattern_glob_matching(
        self, runner: PythonQARunner, tmp_path: Path
    ) -> None:
        """Glob pattern 'specweaver/sandbox/*' matches deep imports but not others."""
        _write_py(
            tmp_path,
            "src/module.py",
            """\
            from specweaver.sandbox.anything.deep import Foo
            from specweaver.core.config import Settings
            """,
        )
        _write_context_yaml(tmp_path, "src", ["specweaver/sandbox/*"])

        with patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH):
            result = runner.run_architecture_check(target="src/module.py")

        # Only the sandbox import should be flagged, not core.config
        assert result.violation_count == 1
        assert "specweaver.sandbox.anything.deep" in result.violations[0].message

    def test_forbids_exact_match(self, runner: PythonQARunner, tmp_path: Path) -> None:
        """Exact pattern 'specweaver/llm' matches specweaver.llm but not specweaver.llm_tools."""
        _write_py(
            tmp_path,
            "src/module.py",
            """\
            from specweaver.llm import Client
            from specweaver.llm_tools import Helper
            """,
        )
        _write_context_yaml(tmp_path, "src", ["specweaver/llm"])

        with patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH):
            result = runner.run_architecture_check(target="src/module.py")

        # Only specweaver.llm should match, not specweaver.llm_tools
        assert result.violation_count == 1
        assert "specweaver.llm" in result.violations[0].message
        assert "llm_tools" not in result.violations[0].message

    def test_tach_and_forbids_merged(
        self, runner: PythonQARunner, tmp_path: Path
    ) -> None:
        """Both forbids and tach violations are merged in the result."""
        _write_py(
            tmp_path,
            "src/module.py",
            """\
            from specweaver.sandbox.base import Atom
            """,
        )
        _write_context_yaml(tmp_path, "src", ["specweaver/sandbox/*"])

        tach_violation = ArchitectureViolation(
            file="src/other.py",
            code="UndeclaredDependency",
            message="tach violation",
        )
        tach_result = ArchitectureRunResult(
            violation_count=1, violations=[tach_violation]
        )

        with patch.object(runner, "_run_tach_check", return_value=tach_result):
            result = runner.run_architecture_check(target="src/module.py")

        # 1 forbids + 1 tach = 2
        assert result.violation_count == 2
        codes = [v.code for v in result.violations]
        assert "ForbiddenImport" in codes
        assert "UndeclaredDependency" in codes

    def test_dal_level_logged(
        self, runner: PythonQARunner, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """dal_level appears in debug log output."""
        from specweaver.commons.enums.dal import DALLevel

        _write_py(tmp_path, "src/module.py", "import os\n")

        with (
            caplog.at_level("DEBUG", logger="specweaver.sandbox.language.core.python.runner"),
            patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH),
        ):
            runner.run_architecture_check(target="src/module.py", dal_level=DALLevel.DAL_A)

        assert "DAL_A" in caplog.text

    def test_non_python_file_skips_forbids(
        self, runner: PythonQARunner, tmp_path: Path
    ) -> None:
        """Non-Python files skip the forbids phase."""
        txt_file = tmp_path / "src" / "readme.txt"
        txt_file.parent.mkdir(parents=True, exist_ok=True)
        txt_file.write_text("hello", encoding="utf-8")
        _write_context_yaml(tmp_path, "src", ["specweaver/sandbox/*"])

        with patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH):
            result = runner.run_architecture_check(target="src/readme.txt")

        # Only tach, no forbids
        assert result.violation_count == 0

    def test_directory_target_skips_forbids(
        self, runner: PythonQARunner, tmp_path: Path
    ) -> None:
        """Directory targets skip the forbids phase."""
        (tmp_path / "src").mkdir(parents=True, exist_ok=True)
        _write_context_yaml(tmp_path, "src", ["specweaver/sandbox/*"])

        with patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH):
            result = runner.run_architecture_check(target="src")

        assert result.violation_count == 0

    def test_syntax_error_in_target_skips_forbids(
        self, runner: PythonQARunner, tmp_path: Path
    ) -> None:
        """Python file with syntax errors skips forbids gracefully."""
        _write_py(
            tmp_path,
            "src/broken.py",
            """\
            def foo(
                # Missing closing paren
            """,
        )
        _write_context_yaml(tmp_path, "src", ["specweaver/sandbox/*"])

        with patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH):
            # Should not crash
            result = runner.run_architecture_check(target="src/broken.py")

        # Only tach, no crash
        assert result.violation_count == 0

    def test_type_checking_import_not_flagged(
        self, runner: PythonQARunner, tmp_path: Path
    ) -> None:
        """Imports inside if TYPE_CHECKING: blocks must NOT be flagged (RED-5)."""
        _write_py(
            tmp_path,
            "src/module.py",
            """\
            from __future__ import annotations
            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                from specweaver.sandbox.base import Atom

            import os
            """,
        )
        _write_context_yaml(tmp_path, "src", ["specweaver/sandbox/*"])

        with patch.object(runner, "_run_tach_check", return_value=_EMPTY_TACH):
            result = runner.run_architecture_check(target="src/module.py")

        # TYPE_CHECKING imports must be excluded
        assert result.violation_count == 0
