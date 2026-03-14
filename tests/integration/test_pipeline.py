# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests — end-to-end flows through the CLI.

These tests exercise full command sequences, mocking only the LLM
adapter to avoid real API calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.cli import app
from specweaver.llm.models import LLMResponse

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all pipeline tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli.get_db", lambda: db)
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
# sw init → sw check flow
# ---------------------------------------------------------------------------


class TestInitCheckFlow:
    """Test init + check sequence."""

    def test_init_then_check_good_spec(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Init a project, then check a good spec — should pass."""
        # Step 1: Init
        result = runner.invoke(app, ["init", "testapp", "--path", str(tmp_path)])
        assert result.exit_code == 0
        assert "initialized" in result.output.lower()

        # Step 2: Copy good spec
        good_spec = tmp_path / "specs" / "greeter_spec.md"
        fixture = (
            "# Greeter — Component Spec\n\n"
            "> **Status**: DRAFT\n\n---\n\n"
            "## 1. Purpose\n\nGreets users.\n\n---\n\n"
            "## 2. Contract\n\n```python\n"
            "def greet(name: str) -> str:\n"
            '    return f"Hello {name}"\n```\n\n---\n\n'
            "## 3. Protocol\n\n"
            "1. Validate name is not empty.\n"
            "2. Return greeting.\n\n---\n\n"
            "## 4. Policy\n\n"
            "| Error | Behavior |\n|:---|:---|\n"
            "| Empty name | Raise ValueError |\n\n---\n\n"
            "## 5. Boundaries\n\n"
            "| Concern | Owned By |\n|:---|:---|\n"
            "| Auth | AuthService |\n\n---\n\n"
            "## Done Definition\n\n"
            "- [ ] Unit tests pass\n"
            "- [ ] Coverage >= 70%\n"
        )
        good_spec.write_text(fixture, encoding="utf-8")

        # Step 3: Check spec
        result = runner.invoke(
            app,
            ["check", "--level", "component", str(good_spec)],
        )
        assert "S01" in result.output
        # Should not hard-fail on a well-formed spec
        assert "ALL PASSED" in result.output or "warnings" in result.output

    def test_init_then_check_bad_spec(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Init, then check a bad spec — should fail."""
        runner.invoke(app, ["init", "badspec", "--path", str(tmp_path)])

        bad_spec = tmp_path / "specs" / "bad_spec.md"
        bad_spec.write_text("This is not a proper spec.", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "component", str(bad_spec)],
        )
        assert result.exit_code == 1
        assert "FAIL" in result.output


# ---------------------------------------------------------------------------
# sw implement flow
# ---------------------------------------------------------------------------


class TestImplementFlow:
    """Test sw implement command."""

    @patch("specweaver.cli._require_llm_adapter")
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
            "def greet(name: str) -> str:\n"
            '    return f"Hello {name}!"\n',
        )
        mock_require.return_value = (
            MagicMock(),
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

    @patch("specweaver.cli._require_llm_adapter")
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
        mock_require.return_value = (
            MagicMock(),
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
# sw check --level=code on generated code
# ---------------------------------------------------------------------------


class TestCheckCodeFlow:
    """Test running code checks on Python files."""

    def test_check_clean_code_passes(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Clean Python code should pass syntax and type hint checks."""
        code = tmp_path / "clean.py"
        code.write_text(
            "def greet(name: str) -> str:\n"
            '    return f"Hello {name}!"\n',
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(code)],
        )
        assert "C01" in result.output
        assert "PASS" in result.output

    def test_check_broken_code_fails(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Code with syntax errors should fail C01."""
        broken = tmp_path / "broken.py"
        broken.write_text("def foo(\n", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(broken)],
        )
        assert result.exit_code == 1
        assert "FAIL" in result.output

    def test_check_code_with_bare_except(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Code with bare excepts should trigger C06 warning."""
        code = tmp_path / "bare.py"
        code.write_text(
            "def foo() -> None:\n"
            "    try:\n"
            "        pass\n"
            "    except:\n"
            "        pass\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(code)],
        )
        # C06 should show up
        assert "C06" in result.output

    def test_check_code_with_todos(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Code with TODOs should trigger C07 warning."""
        code = tmp_path / "todos.py"
        code.write_text(
            "# TODO: implement this\n"
            "def foo() -> None:\n"
            "    pass\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(code)],
        )
        # C07 should show up
        assert "C07" in result.output

    def test_check_code_missing_type_hints(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Code missing type hints should trigger C08."""
        code = tmp_path / "nohints.py"
        code.write_text(
            "def foo():\n"
            "    return 42\n"
            "def bar():\n"
            "    return 'hi'\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(code)],
        )
        assert "C08" in result.output


# ---------------------------------------------------------------------------
# Full end-to-end: init → check spec → implement → check code
# ---------------------------------------------------------------------------


class TestFullPipeline:
    """Test the full SpecWeaver pipeline end-to-end."""

    @patch("specweaver.cli._require_llm_adapter")
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
            "def add(a: int, b: int) -> int:\n"
            '    """Add two integers."""\n'
            "    return a + b\n"
        )
        mock_adapter = _make_mock_adapter(generated_code)
        mock_require.return_value = (
            MagicMock(),
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


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_check_nonexistent_file(self) -> None:
        """Check with a non-existent file should fail."""
        result = runner.invoke(
            app,
            ["check", "--level", "component", "does_not_exist.md"],
        )
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_check_invalid_level(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Check with invalid level should fail."""
        f = tmp_path / "test.md"
        f.write_text("content", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "invalid", str(f)],
        )
        assert result.exit_code == 1
        assert "unknown level" in result.output.lower()

    def test_check_empty_spec(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Empty spec file should trigger failures."""
        empty = tmp_path / "empty.md"
        empty.write_text("", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "component", str(empty)],
        )
        # Should produce results (mostly WARN/FAIL)
        assert "S01" in result.output

    def test_check_empty_code(
        self,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        """Empty code file should still produce results."""
        empty = tmp_path / "empty.py"
        empty.write_text("", encoding="utf-8")

        result = runner.invoke(
            app,
            ["check", "--level", "code", str(empty)],
        )
        assert "C01" in result.output
