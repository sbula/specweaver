# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — sw implement CLI flows.

Tests the `sw implement` command: file generation, suffix stripping,
missing spec handling, and the full init → check → implement → check pipeline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.database import Database
    from specweaver.core.config.db_bootstrap import bootstrap_database

    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    db_path = str(data_dir / "specweaver.db")
    bootstrap_database(db_path)
    db = Database(db_path)
    return db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_adapter(response_text: str = "pass\n") -> MagicMock:
    """Create a mock LLM adapter that returns fixed text."""
    adapter = MagicMock()
    adapter.available.return_value = True
    adapter.generate = AsyncMock(
        return_value=LLMResponse(
            text=response_text,
            model="test-model",
        ),
    )
    return adapter


def _scaffold_project(tmp_path: object) -> object:
    """Create a minimal scaffolded project for testing."""
    result = runner.invoke(app, ["init", "test_proj", "--path", str(tmp_path)])
    assert result.exit_code == 0
    return tmp_path


# ---------------------------------------------------------------------------
# QA stubbing — INT-US-03 SF-01 appended run_tests + validate_code steps to the
# implement pipeline. CLI-tier tests stub the QA handlers' execute() (the real
# pytest/rule execution is proven by the SF-03 e2e). This keeps these tests
# deterministic and fast, and is the correct mocking boundary for a CLI test.
# ---------------------------------------------------------------------------


def _qa_result(*, passed: bool, output: dict) -> object:
    from specweaver.core.flow.engine.state import StepResult, StepStatus

    return StepResult(
        status=StepStatus.PASSED if passed else StepStatus.FAILED,
        output=output,
        error_message="" if passed else "stubbed QA failure",
        started_at="t0",
        completed_at="t1",
    )


def _patch_qa(*, tests_pass: bool = True, code_pass: bool = True):
    """Context managers patching both QA handlers' execute()."""
    tests_out = (
        {"passed": 2, "failed": 0, "total": 2, "coverage_pct": 95}
        if tests_pass
        else {"passed": 0, "failed": 1, "total": 1, "coverage_pct": 0}
    )
    code_out = (
        {"passed": 8, "failed": 0, "total": 8, "results": []}
        if code_pass
        else {
            "passed": 6,
            "failed": 2,
            "total": 8,
            "results": [
                {"rule_id": "C04", "status": "FAIL", "message": "coverage"},
                {"rule_id": "C05", "status": "FAIL", "message": "type hints"},
            ],
        }
    )
    tests_patch = patch(
        "specweaver.core.flow.handlers.validation.ValidateTestsHandler.execute",
        new=AsyncMock(return_value=_qa_result(passed=tests_pass, output=tests_out)),
    )
    code_patch = patch(
        "specweaver.core.flow.handlers.validation.ValidateCodeHandler.execute",
        new=AsyncMock(return_value=_qa_result(passed=code_pass, output=code_out)),
    )
    return tests_patch, code_patch


# ---------------------------------------------------------------------------
# INT-US-03 SF-01: generation → QA loop
# ---------------------------------------------------------------------------


class TestImplementQALoop:
    """sw implement runs tests + code validation in-pipeline and reports outcomes."""

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    def test_qa_pass_reports_and_exits_zero(self, mock_require, tmp_path) -> None:
        project = _scaffold_project(tmp_path)
        spec = project / "specs" / "greeter_spec.md"
        spec.write_text("# Greeter\n## 1. Purpose\nGreets.", encoding="utf-8")
        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_require.return_value = (
            mock_settings,
            _make_mock_adapter("def greet(n):\n    return n\n"),
            MagicMock(temperature=0.2),
        )

        tp, cp = _patch_qa(tests_pass=True, code_pass=True)
        with tp, cp:
            result = runner.invoke(app, ["implement", str(spec), "--project", str(project)])

        assert result.exit_code == 0, result.output
        assert "Implementation complete" in result.output
        assert "2 passed" in result.output
        assert "95" in result.output  # coverage surfaced

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    def test_failing_tests_exit_nonzero(self, mock_require, tmp_path) -> None:
        project = _scaffold_project(tmp_path)
        spec = project / "specs" / "greeter_spec.md"
        spec.write_text("# Greeter\n## 1. Purpose\nGreets.", encoding="utf-8")
        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_require.return_value = (
            mock_settings,
            _make_mock_adapter("def greet(n):\n    return n\n"),
            MagicMock(temperature=0.2),
        )

        tp, cp = _patch_qa(tests_pass=False, code_pass=True)
        with tp, cp:
            result = runner.invoke(app, ["implement", str(spec), "--project", str(project)])

        # run_tests fails → loop-back exhausts → run not completed → exit 1
        assert result.exit_code == 1, result.output
        assert "fail" in result.output.lower()

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    def test_validate_code_failure_is_report_only(self, mock_require, tmp_path) -> None:
        project = _scaffold_project(tmp_path)
        spec = project / "specs" / "greeter_spec.md"
        spec.write_text("# Greeter\n## 1. Purpose\nGreets.", encoding="utf-8")
        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_require.return_value = (
            mock_settings,
            _make_mock_adapter("def greet(n):\n    return n\n"),
            MagicMock(temperature=0.2),
        )

        tp, cp = _patch_qa(tests_pass=True, code_pass=False)
        with tp, cp:
            result = runner.invoke(app, ["implement", str(spec), "--project", str(project)])

        # validate_code gate is CONTINUE → run completes → exit 0, failure reported
        assert result.exit_code == 0, result.output
        assert "Implementation complete" in result.output
        assert "C04" in result.output  # failed rule surfaced


# ---------------------------------------------------------------------------
# sw implement flow
# ---------------------------------------------------------------------------


class TestImplementFlow:
    """Test sw implement command."""

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    def test_implement_generates_files(
        self,
        mock_require,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Implement should create code and test files."""
        project = _scaffold_project(tmp_path)

        # Create spec
        spec = project / "specs" / "greeter_spec.md"
        spec.write_text("# Greeter Spec\n## 1. Purpose\nGreets.", encoding="utf-8")

        # Mock LLM
        mock_adapter = _make_mock_adapter(
            'def greet(name: str) -> str:\n    return f"Hello {name}!"\n',
        )
        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_require.return_value = (
            mock_settings,
            mock_adapter,
            MagicMock(temperature=0.7),
        )

        tp, cp = _patch_qa()  # SF-01: stub the appended QA steps (real exec = SF-03 e2e)
        with tp, cp:
            result = runner.invoke(
                app,
                ["implement", str(spec), "--project", str(project)],
            )

        assert result.exit_code == 0
        assert "Implementation complete" in result.output

        # Check files were created
        code_path = project / "src" / "greeter.py"
        test_path = project / "tests" / "test_greeter.py"
        assert code_path.exists()
        assert test_path.exists()

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    def test_implement_spec_suffix_removal(
        self,
        mock_require,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """The _spec suffix should be stripped from output filenames."""
        project = _scaffold_project(tmp_path)

        # Spec with _spec suffix
        spec = project / "specs" / "auth_service_spec.md"
        spec.write_text("# Auth Spec\n## 1. Purpose\nAuth.", encoding="utf-8")

        mock_adapter = _make_mock_adapter("pass\n")
        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_require.return_value = (
            mock_settings,
            mock_adapter,
            MagicMock(temperature=0.7),
        )

        tp, cp = _patch_qa()  # SF-01: stub the appended QA steps
        with tp, cp:
            result = runner.invoke(
                app,
                ["implement", str(spec), "--project", str(project)],
            )

        assert result.exit_code == 0
        # Should be auth_service.py, not auth_service_spec.py
        assert (project / "src" / "auth_service.py").exists()
        assert (project / "tests" / "test_auth_service.py").exists()

    def test_implement_missing_spec(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Implement with non-existent spec should fail."""
        result = runner.invoke(
            app,
            ["implement", "nonexistent.md", "--project", str(tmp_path)],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# Full end-to-end: init → check spec → implement → check code
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Test the full SpecWeaver pipeline end-to-end."""

    @patch("specweaver.infrastructure.llm.factory.create_llm_adapter")
    def test_full_pipeline(
        self,
        mock_require,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Run the complete pipeline: init → check → implement → check."""
        # 1. Init
        result = runner.invoke(app, ["init", "calcapp", "--path", str(tmp_path)])
        assert result.exit_code == 0

        # 2. Create and check a spec
        spec = tmp_path / "specs" / "calc_spec.md"
        spec.write_text(
            "# Calculator — Component Spec\n\n"
            "> **Status**: DRAFT\n\n---\n\n"
            "## 1. Purpose\n\nPerforms basic arithmetic.\n\n---\n\n"
            "## 2. Contract\n\n```python\n"
            "def add(a: int, b: int) -> int:\n"
            "    return a + b\n```\n\n---\n\n"
            "## 3. Protocol\n\n1. Validate inputs.\n"
            "2. Perform operation.\n3. Return result.\n\n---\n\n"
            "## 4. Policy\n\n"
            "| Error | Behavior |\n|:---|:---|\n"
            "| Overflow | Raise OverflowError |\n\n---\n\n"
            "## 5. Boundaries\n\n"
            "| Concern | Owned By |\n|:---|:---|\n"
            "| Logging | Logger |\n\n---\n\n"
            "## Done Definition\n\n"
            "- [ ] All tests pass\n"
            "- [ ] Coverage >= 70%\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "component", str(spec)],
        )
        # Spec should pass or warn (not hard fail)
        assert "S01" in result.output

        # 3. Mock LLM and implement
        generated_code = (
            'def add(a: int, b: int) -> int:\n    """Add two integers."""\n    return a + b\n'
        )
        mock_adapter = _make_mock_adapter(generated_code)
        mock_settings = MagicMock()
        mock_settings.llm.model = "test-model"
        mock_require.return_value = (
            mock_settings,
            mock_adapter,
            MagicMock(temperature=0.7),
        )

        tp, cp = _patch_qa()  # SF-01: stub the appended QA steps (real exec = SF-03 e2e)
        with tp, cp:
            result = runner.invoke(
                app,
                ["implement", str(spec), "--project", str(tmp_path)],
            )
        assert result.exit_code == 0
        assert "Implementation complete" in result.output

        # 4. Check generated code
        code_path = tmp_path / "src" / "calc.py"
        assert code_path.exists()

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(code_path)],
        )
        # C01 syntax should pass on valid generated code
        assert "C01" in result.output
        assert "PASS" in result.output
