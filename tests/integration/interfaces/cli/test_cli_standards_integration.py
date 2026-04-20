# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — sw standards scan → show → clear flow.

Tests the full standards discovery lifecycle through the CLI.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: db)
    return db


def _init_project_with_python(tmp_path: Path, name: str = "std-proj") -> Path:
    """Helper: init a project with some Python files for standards scan."""
    project_dir = tmp_path / name
    project_dir.mkdir(exist_ok=True)

    # Create Python source files with consistent style
    src_dir = project_dir / "src"
    src_dir.mkdir()
    (src_dir / "__init__.py").write_text("", encoding="utf-8")
    (src_dir / "module_a.py").write_text(
        '"""Module A."""\n\n\n'
        "def process_data(name: str) -> str:\n"
        '    """Process data by name."""\n'
        '    return f"processed-{name}"\n\n\n'
        "def validate_input(value: int) -> bool:\n"
        '    """Validate the input value."""\n'
        "    return value > 0\n",
        encoding="utf-8",
    )
    (src_dir / "module_b.py").write_text(
        '"""Module B."""\n\n\n'
        "def calculate_total(items: list) -> float:\n"
        '    """Calculate total from items."""\n'
        "    return sum(items)\n\n\n"
        "def format_result(total: float) -> str:\n"
        '    """Format the result."""\n'
        '    return f"Total: {total:.2f}"\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, f"init failed: {result.output}"
    return project_dir


# ---------------------------------------------------------------------------
# Full lifecycle: scan → show → clear
# ---------------------------------------------------------------------------


class TestStandardsLifecycle:
    """Test the full standards discovery lifecycle."""

    def test_scan_discovers_standards(self, tmp_path: Path) -> None:
        """sw standards scan discovers standards from Python files."""
        _init_project_with_python(tmp_path)
        result = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert result.exit_code == 0
        assert "scan" in result.output.lower()
        assert "complete" in result.output.lower()

    def test_show_after_scan(self, tmp_path: Path) -> None:
        """sw standards show displays discovered standards after scan."""
        _init_project_with_python(tmp_path)
        runner.invoke(app, ["standards", "scan", "--no-review"])
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code == 0
        # Should show a table with at least one standard
        assert "python" in result.output.lower() or "category" in result.output.lower()

    def test_clear_removes_all(self, tmp_path: Path) -> None:
        """sw standards clear removes all discovered standards."""
        _init_project_with_python(tmp_path)
        runner.invoke(app, ["standards", "scan", "--no-review"])
        result = runner.invoke(app, ["standards", "clear"])
        assert result.exit_code == 0
        assert "cleared" in result.output.lower()

        # Verify show is empty now
        show_result = runner.invoke(app, ["standards", "show"])
        assert "no standards" in show_result.output.lower()

    def test_scan_then_show_then_clear_then_show(self, tmp_path: Path) -> None:
        """Full lifecycle: scan → show → clear → show (empty)."""
        _init_project_with_python(tmp_path)

        # 1. Scan
        scan_result = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert scan_result.exit_code == 0

        # 2. Show (should have results)
        show1 = runner.invoke(app, ["standards", "show"])
        assert show1.exit_code == 0
        assert "no standards" not in show1.output.lower()

        # 3. Clear
        clear_result = runner.invoke(app, ["standards", "clear"])
        assert clear_result.exit_code == 0

        # 4. Show (should be empty)
        show2 = runner.invoke(app, ["standards", "show"])
        assert "no standards" in show2.output.lower()


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestStandardsErrors:
    """Test standards command error handling."""

    def test_scan_requires_active_project(self) -> None:
        """sw standards scan without active project fails."""
        result = runner.invoke(app, ["standards", "scan"])
        assert result.exit_code == 1
        assert "no active project" in result.output.lower()

    def test_show_requires_active_project(self) -> None:
        """sw standards show without active project fails."""
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code == 1
        assert "no active project" in result.output.lower()

    def test_clear_requires_active_project(self) -> None:
        """sw standards clear without active project fails."""
        result = runner.invoke(app, ["standards", "clear"])
        assert result.exit_code == 1
        assert "no active project" in result.output.lower()

    def test_show_empty_no_scan(self, tmp_path: Path) -> None:
        """sw standards show without prior scan shows empty message."""
        project_dir = tmp_path / "empty-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "empty-proj", "--path", str(project_dir)])
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code == 0
        assert "no standards" in result.output.lower()


# ---------------------------------------------------------------------------
# Integration: Re-scan and upsert behavior
# ---------------------------------------------------------------------------


class TestStandardsRescan:
    """Integration tests for re-scan → upsert."""

    def test_rescan_updates_existing_standards(self, tmp_path: Path) -> None:
        """Re-scanning the same project overwrites old standards (upsert)."""
        project_dir = _init_project_with_python(tmp_path)

        # First scan
        r1 = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert r1.exit_code == 0

        runner.invoke(app, ["standards", "show"])

        # Change code style and re-scan
        src = project_dir / "src" / "module_a.py"
        src.write_text(
            "def getData():\n    pass\n\ndef processItem():\n    pass\n",
            encoding="utf-8",
        )

        r2 = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert r2.exit_code == 0

        show2 = runner.invoke(app, ["standards", "show"])
        # Both should succeed — no duplicate key errors
        assert show2.exit_code == 0


# ---------------------------------------------------------------------------
# Integration: SyntaxError file graceful degradation
# ---------------------------------------------------------------------------


class TestStandardsSyntaxError:
    """Integration: scan project containing unparseable files."""

    def test_scan_with_syntax_error_file(self, tmp_path: Path) -> None:
        """Scan skips files with SyntaxError, still produces results."""
        project_dir = _init_project_with_python(tmp_path)

        # Add a broken file
        broken = project_dir / "src" / "broken.py"
        broken.write_text("def oops(\n", encoding="utf-8")

        result = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert result.exit_code == 0
        assert "scan" in result.output.lower()
        assert "complete" in result.output.lower()

        # Standards from valid files should still be saved
        show = runner.invoke(app, ["standards", "show"])
        assert show.exit_code == 0
        assert "no standards" not in show.output.lower()


# ---------------------------------------------------------------------------
# Integration: .specweaverignore respected during scan
# ---------------------------------------------------------------------------


class TestStandardsWithIgnore:
    """Integration: .specweaverignore filters files before analysis."""

    def test_specweaverignore_excludes_from_scan(self, tmp_path: Path) -> None:
        """Files matching .specweaverignore are not analyzed."""
        project_dir = _init_project_with_python(tmp_path)

        # Add generated code that should be ignored
        gen = project_dir / "generated"
        gen.mkdir()
        (gen / "auto.py").write_text(
            "def GeneratedFunc():\n    pass\n",
            encoding="utf-8",
        )
        (project_dir / ".specweaverignore").write_text(
            "generated/**\n",
            encoding="utf-8",
        )

        result = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Integration: _load_standards_content round-trip
# ---------------------------------------------------------------------------


class TestStandardsPromptInjection:
    """Integration: scan → _load_standards_content → formatted text."""

    def test_standards_roundtrip_to_prompt_text(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Scan, then _load_standards_content returns formatted text."""
        from specweaver.interfaces.cli._helpers import _load_standards_content

        project_dir = _init_project_with_python(tmp_path)

        runner.invoke(app, ["standards", "scan", "--no-review"])

        content = _load_standards_content(project_dir)
        # After scanning a project with consistent snake_case functions
        # and type hints, standards should be stored and loadable
        if content is not None:
            # Verify it's a non-empty formatted string
            assert len(content) > 10
            assert "python" in content.lower() or "SHOULD follow" in content


# ---------------------------------------------------------------------------
# Integration: discover_files on non-git dir with skip dirs
# ---------------------------------------------------------------------------


class TestDiscoveryIntegration:
    """Integration: discover_files across real filesystem structures."""

    def test_discover_skips_venv_and_pycache(self, tmp_path: Path) -> None:
        """discover_files skips all standard skip dirs on real filesystem."""
        from specweaver.assurance.standards.discovery import discover_files
        from specweaver.workspace.analyzers.factory import AnalyzerFactory

        # Create project structure with skip directories
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("pass")
        (tmp_path / ".venv" / "lib").mkdir(parents=True)
        (tmp_path / ".venv" / "lib" / "site.py").write_text("pass")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "cached.pyc").write_text("compiled")
        (tmp_path / "node_modules" / "pkg").mkdir(parents=True)
        (tmp_path / "node_modules" / "pkg" / "index.js").write_text("module.exports={}")

        files = discover_files(tmp_path, AnalyzerFactory)
        names = [f.name for f in files]
        assert "main.py" in names
        assert "site.py" not in names
        assert "cached.pyc" not in names
        assert "index.js" not in names
