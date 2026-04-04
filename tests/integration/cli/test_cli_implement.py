# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests — sw implement CLI flows.

Tests the `sw implement` command: file generation, suffix stripping,
missing spec handling, and the full init → check → implement → check pipeline.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.cli.main import app
from specweaver.llm.models import LLMResponse

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
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
    sw_dir = tmp_path / ".specweaver"
    sw_dir.mkdir()
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# sw implement flow
# ---------------------------------------------------------------------------


class TestImplementFlow:
    """Test sw implement command."""

    @patch("specweaver.cli._helpers._require_llm_adapter")
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

    @patch("specweaver.cli._helpers._require_llm_adapter")
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

    @patch("specweaver.cli._helpers._require_llm_adapter")
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
