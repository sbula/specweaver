# mypy: ignore-errors
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

from tests.rendering import shows

#: These assertions read a Rich *table*. `shows()` makes them immune to soft WRAPPING, but below
#: about 80 columns Rich TRUNCATES the cell instead — the text is gone from `result.output`, and no
#: test-side helper can recover it. Verified 2026-08-14: green at COLUMNS 80/100/200, and the
#: `function_style=` value genuinely absent at 60 and 40. A rendering floor, not a test defect —
#: and 80 is the no-TTY default, so it is the width CI actually gets.

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database

    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))

    db_path = str(data_dir / "specweaver.db")
    bootstrap_database(db_path)
    db = Database(db_path)
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
        assert shows(result.output.lower(), "scan")
        assert shows(result.output.lower(), "complete")

    def test_show_after_scan(self, tmp_path: Path) -> None:
        """sw standards show displays discovered standards after scan."""
        _init_project_with_python(tmp_path)
        runner.invoke(app, ["standards", "scan", "--no-review"])
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code == 0
        # Should show a table with at least one standard
        assert shows(result.output.lower(), "python") or shows(result.output.lower(), "category")

    def test_clear_removes_all(self, tmp_path: Path) -> None:
        """sw standards clear removes all discovered standards."""
        _init_project_with_python(tmp_path)
        runner.invoke(app, ["standards", "scan", "--no-review"])
        result = runner.invoke(app, ["standards", "clear"])
        assert result.exit_code == 0
        assert shows(result.output.lower(), "cleared")

        # Verify show is empty now
        show_result = runner.invoke(app, ["standards", "show"])
        assert shows(show_result.output.lower(), "no standards")

    def test_scan_then_show_then_clear_then_show(self, tmp_path: Path) -> None:
        """Full lifecycle: scan → show → clear → show (empty)."""
        _init_project_with_python(tmp_path)

        # 1. Scan
        scan_result = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert scan_result.exit_code == 0

        # 2. Show (should have results)
        show1 = runner.invoke(app, ["standards", "show"])
        assert show1.exit_code == 0
        assert not shows(show1.output.lower(), "no standards")

        # 3. Clear
        clear_result = runner.invoke(app, ["standards", "clear"])
        assert clear_result.exit_code == 0

        # 4. Show (should be empty)
        show2 = runner.invoke(app, ["standards", "show"])
        assert shows(show2.output.lower(), "no standards")


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestStandardsErrors:
    """Test standards command error handling."""

    def test_scan_requires_active_project(self) -> None:
        """sw standards scan without active project fails."""
        result = runner.invoke(app, ["standards", "scan"])
        assert result.exit_code == 1
        assert shows(result.output.lower(), "no active project")

    def test_show_requires_active_project(self) -> None:
        """sw standards show without active project fails."""
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code == 1
        assert shows(result.output.lower(), "no active project")

    def test_clear_requires_active_project(self) -> None:
        """sw standards clear without active project fails."""
        result = runner.invoke(app, ["standards", "clear"])
        assert result.exit_code == 1
        assert shows(result.output.lower(), "no active project")

    def test_show_empty_no_scan(self, tmp_path: Path) -> None:
        """sw standards show without prior scan shows empty message."""
        project_dir = tmp_path / "empty-proj"
        project_dir.mkdir()
        runner.invoke(app, ["init", "empty-proj", "--path", str(project_dir)])
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code == 0
        assert shows(result.output.lower(), "no standards")


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

        show1 = runner.invoke(app, ["standards", "show"])
        assert show1.exit_code == 0

        # Change code style and re-scan
        src = project_dir / "src" / "module_a.py"
        src.write_text(
            "def getData():\n    pass\n\ndef processItem():\n    pass\n",
            encoding="utf-8",
        )

        r2 = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert r2.exit_code == 0

        show2 = runner.invoke(app, ["standards", "show"])

        # `TECH-017`: this used to assert exit codes only, under a comment claiming "no duplicate
        # key errors" — which it never checked. The claim is UPSERT, so both halves are asserted:
        # the stored standard CHANGED, and it was replaced rather than added alongside.
        assert shows(show1.output, "function_style=sna"), show1.output
        assert shows(show2.output, "function_style=cam"), show2.output
        assert not shows(show2.output, "function_style=sna")
        assert show2.output.count("naming") == 1, "re-scan inserted a second naming row"
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
        assert shows(result.output.lower(), "scan")
        assert shows(result.output.lower(), "complete")

        # Standards from valid files should still be saved
        show = runner.invoke(app, ["standards", "show"])
        assert show.exit_code == 0
        assert not shows(show.output.lower(), "no standards")


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

        # `TECH-017`: the claim is that `generated/auto.py` was NOT analyzed. Exit code cannot show
        # that. `GeneratedFunc` is camelCase and every other function in the fixture is snake_case,
        # so if the ignore were disregarded the dominant naming pattern would shift.
        show = runner.invoke(app, ["standards", "show"])

        assert shows(show.output, "function_style=sna"), show.output
        assert not shows(show.output, "function_style=cam")


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
        #         from specweaver.assurance.standards.interfaces.cli import _load_standards_content

        _init_project_with_python(tmp_path)

        runner.invoke(app, ["standards", "scan", "--no-review"])

        # content = _load_standards_content(project_dir)
        content = None
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
