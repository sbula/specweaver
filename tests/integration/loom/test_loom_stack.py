# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests — loom cross-layer stack with real ruff subprocess.

Tests the full commons → atom → tool stack WITHOUT mocking subprocesses.
Uses real ruff to lint/fix/check-complexity on the sample project fixture.

Uses the shared ``sample_project`` fixture for clean/broken modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.loom.commons.test_runner.interface import (
    ComplexityRunResult,
    LintRunResult,
)
from specweaver.loom.commons.test_runner.python import PythonTestRunner

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_py(tmp_path: Path, name: str, content: str) -> Path:
    """Write a Python file and return its parent directory."""
    target = tmp_path / name
    target.write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# PythonTestRunner — real ruff subprocess
# ---------------------------------------------------------------------------


class TestRealLinting:
    """Lint real files with actual ruff subprocess."""

    def test_clean_module_no_errors(self, sample_project: Path) -> None:
        """Clean greeter module → zero lint errors."""
        clean_dir = sample_project / "src" / "greeter"

        runner = PythonTestRunner(cwd=sample_project)
        result = runner.run_linter(target=str(clean_dir))

        assert isinstance(result, LintRunResult)
        assert result.error_count == 0

    def test_broken_module_has_lint_errors(self, sample_project: Path) -> None:
        """Broken module with unused imports → lint detects errors."""
        # Write a broken file without noqa (the fixture file has noqa)
        broken_dir = sample_project / "src" / "lint_test"
        broken_dir.mkdir(parents=True, exist_ok=True)
        (broken_dir / "bad.py").write_text(
            "import os\nimport sys\n\n\ndef foo() -> None:\n    pass\n",
            encoding="utf-8",
        )

        runner = PythonTestRunner(cwd=sample_project)
        result = runner.run_linter(target=str(broken_dir))

        assert isinstance(result, LintRunResult)
        assert result.error_count > 0
        codes = [e.code for e in result.errors]
        assert any(c.startswith("F") for c in codes)  # F401 = unused import

    def test_auto_fix_removes_unused_import(self, sample_project: Path) -> None:
        """Ruff auto-fix removes unused import from a temp file."""
        fixable_dir = sample_project / "src" / "fixable"
        fixable_dir.mkdir(parents=True, exist_ok=True)
        bad_file = fixable_dir / "fixable.py"
        bad_file.write_text(
            "import os\n\n\ndef foo() -> None:\n    pass\n",
            encoding="utf-8",
        )

        runner = PythonTestRunner(cwd=sample_project)

        before = runner.run_linter(target=str(fixable_dir))
        assert before.error_count > 0

        runner.run_linter(target=str(fixable_dir), fix=True)

        after = runner.run_linter(target=str(fixable_dir))
        assert after.error_count == 0

        content = bad_file.read_text(encoding="utf-8")
        assert "import os" not in content


class TestRealComplexity:
    """Complexity checks on real files with actual ruff C901."""

    def test_simple_function_no_violations(self, sample_project: Path) -> None:
        """Clean greeter module → no complexity violations."""
        clean_dir = sample_project / "src" / "greeter"

        runner = PythonTestRunner(cwd=sample_project)
        result = runner.run_complexity(target=str(clean_dir))

        assert isinstance(result, ComplexityRunResult)
        assert result.violation_count == 0
        assert len(result.violations) == 0

    def test_complex_function_detected(self, sample_project: Path) -> None:
        """Complex function → violation detected."""
        # Write a complex file without noqa so ruff detects it
        complex_dir = sample_project / "src" / "complex_test"
        complex_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            '"""Complex module."""\n',
            "\n\n",
            "def complex_func(x: int) -> str:\n",
            '    """Handle many cases."""\n',
        ]
        for i in range(12):
            if i == 0:
                lines.append(f"    if x == {i}:\n")
            else:
                lines.append(f"    elif x == {i}:\n")
            lines.append(f'        return "case_{i}"\n')
        lines.append('    return "default"\n')
        (complex_dir / "complex.py").write_text("".join(lines), encoding="utf-8")

        runner = PythonTestRunner(cwd=sample_project)
        result = runner.run_complexity(target=str(complex_dir))

        assert isinstance(result, ComplexityRunResult)
        assert result.violation_count > 0
        assert len(result.violations) > 0
        assert result.violations[0].function == "complex_func"

    def test_custom_threshold(self, sample_project: Path) -> None:
        """Custom low threshold catches moderately complex functions."""
        moderate_dir = sample_project / "src" / "moderate_test"
        moderate_dir.mkdir(parents=True, exist_ok=True)
        (moderate_dir / "moderate.py").write_text(
            '"""Moderate module."""\n'
            "\n\n"
            "def categorize(x: int) -> str:\n"
            '    """Categorize a number."""\n'
            "    if x < 0:\n"
            '        return "negative"\n'
            "    elif x == 0:\n"
            '        return "zero"\n'
            "    elif x < 10:\n"
            '        return "small"\n'
            '    return "large"\n',
            encoding="utf-8",
        )

        runner = PythonTestRunner(cwd=sample_project)

        result_default = runner.run_complexity(target=str(moderate_dir))
        assert result_default.violation_count == 0

        result_low = runner.run_complexity(target=str(moderate_dir), max_complexity=2)
        assert result_low.violation_count > 0


# ---------------------------------------------------------------------------
# Atom → Tool full stack
# ---------------------------------------------------------------------------


class TestAtomToolStack:
    """Test the atom → tool wiring with real execution."""

    def test_atom_lint_intent_with_real_ruff(self, sample_project: Path) -> None:
        """TestRunnerAtom handles run_linter intent via real PythonTestRunner."""
        # Write a broken file without noqa
        lint_dir = sample_project / "src" / "atom_lint_test"
        lint_dir.mkdir(parents=True, exist_ok=True)
        (lint_dir / "lintme.py").write_text(
            "import os\n\n\ndef bar() -> None:\n    pass\n",
            encoding="utf-8",
        )

        from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom

        atom = TestRunnerAtom(cwd=sample_project)
        result = atom.run(
            {
                "intent": "run_linter",
                "target": str(lint_dir),
            }
        )

        assert result.status.value == "FAILED"
        assert result.exports.get("error_count", 0) > 0

    def test_atom_complexity_intent_clean(self, sample_project: Path) -> None:
        """TestRunnerAtom handles run_complexity intent — clean code."""
        clean_dir = sample_project / "src" / "greeter"

        from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom

        atom = TestRunnerAtom(cwd=sample_project)
        result = atom.run(
            {
                "intent": "run_complexity",
                "target": str(clean_dir),
            }
        )

        assert result.status.value == "SUCCESS"

    def test_tool_role_gating_blocks_reviewer_fix(self, sample_project: Path) -> None:
        """TestRunnerTool blocks reviewer from using fix=True."""
        from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom
        from specweaver.loom.tools.test_runner.tool import (
            TestRunnerTool,
            TestRunnerToolError,
        )

        atom = TestRunnerAtom(cwd=sample_project)
        tool = TestRunnerTool(atom, role="reviewer")
        with pytest.raises(TestRunnerToolError, match="not allowed"):
            tool.run_linter(target=".", fix=True)

    def test_tool_implementer_can_lint_fix(self, sample_project: Path) -> None:
        """TestRunnerTool allows implementer to use fix=True."""
        fix_dir = sample_project / "src" / "tool_fix_test"
        fix_dir.mkdir(parents=True, exist_ok=True)
        bad_file = fix_dir / "fixable.py"
        bad_file.write_text(
            "import os\n\n\ndef foo() -> None:\n    pass\n",
            encoding="utf-8",
        )

        from specweaver.loom.atoms.test_runner.atom import TestRunnerAtom
        from specweaver.loom.tools.test_runner.tool import TestRunnerTool

        atom = TestRunnerAtom(cwd=sample_project)
        tool = TestRunnerTool(atom, role="implementer")
        tool.run_linter(target=str(fix_dir), fix=True)

        content = bad_file.read_text(encoding="utf-8")
        assert "import os" not in content


# ---------------------------------------------------------------------------
# Compiler and Debugger Real Executions
# ---------------------------------------------------------------------------


class TestPythonRunnerExecution:
    """Validate python debugger execution integration."""

    def test_run_compiler_stub(self, sample_project: Path) -> None:
        """Python compiler just returns a 0 error stub organically."""
        runner = PythonTestRunner(cwd=sample_project)
        result = runner.run_compiler(target=".")
        assert result.error_count == 0

    def test_run_debugger_streams(self, sample_project: Path) -> None:
        """Python debugger runs the process natively parsing stdout."""
        target_dir = sample_project / "src" / "debug_test"
        target_dir.mkdir(parents=True, exist_ok=True)
        py_file = target_dir / "app.py"
        py_file.write_text(
            'import sys\nprint("STDOUT_LINE")\nprint("STDERR_LINE", file=sys.stderr)',
            encoding="utf-8",
        )

        runner = PythonTestRunner(cwd=sample_project)
        result = runner.run_debugger(target=str(target_dir), entrypoint=str(py_file))
        assert result.exit_code == 0
        outputs = [e.output for e in result.events]
        assert "STDOUT_LINE" in outputs
        assert "STDERR_LINE" in outputs


class TestTypeScriptRunnerRealTooling:
    """Validate real npx tsc / ts-node logic integration constraints."""

    def test_tsc_compiler_regex_parsing(self, sample_project: Path) -> None:
        """Create a broken typescript file and invoke real tsc compiler."""
        import shutil
        import subprocess

        from specweaver.loom.commons.test_runner.typescript import TypeScriptRunner

        target_dir = sample_project / "src" / "ts_compile"
        target_dir.mkdir(parents=True, exist_ok=True)
        ts_file = target_dir / "index.ts"
        # Type error TS2322: Type number is not assignable to type string.
        ts_file.write_text("let x: string = 5;", encoding="utf-8")

        # Create localized tsconfig to compile everything in src
        (sample_project / "tsconfig.json").write_text(
            '{"compilerOptions": {"noEmit": true}, "include": ["src/**/*"]}', encoding="utf-8"
        )

        npm_bin = shutil.which("npm") or "npm"
        subprocess.run(
            [npm_bin, "install", "typescript", "ts-node"],
            cwd=sample_project,
            check=False,
            capture_output=True,
        )

        runner = TypeScriptRunner(cwd=sample_project)
        result = runner.run_compiler(target=".")
        assert result.error_count > 0
        assert result.errors[0].code == "TS2322"
        assert result.errors[0].line == 1

    def test_ts_node_debugger_execution(self, sample_project: Path) -> None:
        """Execute a typescript file natively through ts-node."""
        import shutil
        import subprocess

        from specweaver.loom.commons.test_runner.typescript import TypeScriptRunner

        target_dir = sample_project / "src" / "ts_debug"
        target_dir.mkdir(parents=True, exist_ok=True)
        ts_file = target_dir / "app.ts"
        ts_file.write_text('console.log("HELLO_TSNODE");', encoding="utf-8")

        npm_bin = shutil.which("npm") or "npm"
        subprocess.run(
            [npm_bin, "install", "typescript", "ts-node", "@types/node"],
            cwd=sample_project,
            check=False,
            capture_output=True,
        )

        runner = TypeScriptRunner(cwd=sample_project)
        result = runner.run_debugger(target=str(target_dir), entrypoint=str(ts_file))
        assert result.exit_code == 0
        outputs = [e.output for e in result.events]
        assert "HELLO_TSNODE" in outputs
