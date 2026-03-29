# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for CLI standards commands and _load_standards_content helper.

Covers:
- _load_standards_content() edge cases (item 1)
- sw standards scan (item 2)
- sw standards show (item 3)
- sw standards clear (item 4)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all standards tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


def _init_project(db, name: str, root_path: str) -> None:
    """Register and activate a project in the test DB."""
    runner.invoke(app, ["init", name, "--path", root_path])
    runner.invoke(app, ["use", name])


def _seed_standards(db, name: str, count: int = 2) -> None:
    """Insert sample standards into the DB."""
    db.save_standard(
        project_name=name,
        scope=".",
        language="python",
        category="naming",
        data={"style": "snake_case", "classes": "PascalCase"},
        confidence=0.85,
    )
    if count >= 2:
        db.save_standard(
            project_name=name,
            scope=".",
            language="python",
            category="docstrings",
            data={"style": "google"},
            confidence=0.72,
        )


# ---------------------------------------------------------------------------
# Item 1: _load_standards_content()
# ---------------------------------------------------------------------------


class TestLoadStandardsContent:
    """Unit tests for the _load_standards_content helper."""

    def test_no_active_project_returns_none(self, _mock_db) -> None:
        """No active project → returns None."""
        from pathlib import Path

        from specweaver.cli import _load_standards_content

        assert _load_standards_content(Path(".")) is None

    def test_active_project_no_standards_returns_none(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Active project but no standards → returns None."""
        from specweaver.cli import _load_standards_content

        _init_project(_mock_db, "empty_proj", str(tmp_path))
        assert _load_standards_content(tmp_path) is None

    def test_returns_formatted_string(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """With standards in DB, returns formatted multi-line string."""
        from specweaver.cli import _load_standards_content

        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj", count=1)

        result = _load_standards_content(tmp_path)
        assert result is not None
        assert "snake_case" in result
        assert "naming" in result
        assert "SHOULD follow" in result

    def test_multiple_standards_all_rendered(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Multiple standards are all included in output."""
        from specweaver.cli import _load_standards_content

        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj", count=2)

        result = _load_standards_content(tmp_path)
        assert result is not None
        assert "naming" in result
        assert "docstrings" in result

    def test_data_as_json_string(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Handles data stored as JSON string (not dict)."""
        from specweaver.cli import _load_standards_content

        _init_project(_mock_db, "proj", str(tmp_path))
        # save_standard serialises data internally, but let's verify the
        # formatter handles both possibilities by roundtripping.
        _mock_db.save_standard(
            project_name="proj",
            scope=".",
            language="python",
            category="imports",
            data={"style": "grouped"},
            confidence=0.9,
        )

        result = _load_standards_content(tmp_path)
        assert result is not None
        assert "grouped" in result

    def test_confidence_formatted_as_percent(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Confidence is formatted as percentage (e.g. 85%)."""
        from specweaver.cli import _load_standards_content

        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj", count=1)

        result = _load_standards_content(tmp_path)
        assert result is not None
        assert "85%" in result

    def test_empty_data_dict(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Standard with empty data dict doesn't crash."""
        from specweaver.cli import _load_standards_content

        _init_project(_mock_db, "proj", str(tmp_path))
        _mock_db.save_standard(
            project_name="proj",
            scope=".",
            language="python",
            category="empty_cat",
            data={},
            confidence=0.5,
        )

        result = _load_standards_content(tmp_path)
        assert result is not None
        assert "empty_cat" in result


# ---------------------------------------------------------------------------
# Item 2: sw standards scan
# ---------------------------------------------------------------------------


class TestStandardsScan:
    """CLI tests for sw standards scan."""

    def test_scan_no_active_project(self) -> None:
        """Scan without active project → error."""
        result = runner.invoke(app, ["standards", "scan"])
        assert result.exit_code != 0

    def test_scan_nonexistent_root(
        self,
        tmp_path: Path,
        _mock_db,
        monkeypatch,
    ) -> None:
        """Scan with non-existent root path → error."""
        _init_project(_mock_db, "ghost", str(tmp_path))
        # Monkeypatch get_project to return a non-existent path
        monkeypatch.setattr(
            _mock_db,
            "get_project",
            lambda name: {"name": name, "root_path": "/nonexistent/path"},
        )
        result = runner.invoke(app, ["standards", "scan"])
        assert result.exit_code != 0
        assert "Error" in result.output or "does not exist" in result.output

    def test_scan_no_python_files(
        self,
        tmp_path: Path,
        _mock_db,
        monkeypatch,
    ) -> None:
        """Scan with no Python files → shows message, exit 0."""
        _init_project(_mock_db, "nopy", str(tmp_path))
        # Mock discover_files to return no .py files
        monkeypatch.setattr(
            "specweaver.standards.discovery.discover_files",
            lambda p: [],
        )
        result = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert result.exit_code == 0
        assert "No standards discovered" in result.output or "No Python files" in result.output

    def test_scan_saves_high_confidence(
        self,
        tmp_path: Path,
        _mock_db,
        monkeypatch,
    ) -> None:
        """Scan saves categories with confidence >= 0.3."""

        _init_project(_mock_db, "myproj", str(tmp_path))
        # Create a real .py file
        py_file = tmp_path / "hello.py"
        py_file.write_text("def hello():\n    pass\n", encoding="utf-8")

        monkeypatch.setattr(
            "specweaver.standards.discovery.discover_files",
            lambda p: [py_file],
        )

        result = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert result.exit_code == 0
        assert "Scan complete" in result.output

    def test_scan_skips_low_confidence(
        self,
        tmp_path: Path,
        _mock_db,
        monkeypatch,
    ) -> None:
        """Scan skips categories with confidence < 0.3."""
        from specweaver.standards.analyzer import CategoryResult

        _init_project(_mock_db, "lowconf", str(tmp_path))
        py_file = tmp_path / "tiny.py"
        py_file.write_text("x = 1\n", encoding="utf-8")

        # Mock scan to always return low confidence
        def mock_scan(self, files, hld):
            return [
                CategoryResult(
                    category="test",
                    dominant={"style": "none"},
                    confidence=0.1,
                    sample_size=1,
                    language="python",
                )
            ]

        monkeypatch.setattr(
            "specweaver.standards.discovery.discover_files",
            lambda p: [py_file],
        )
        monkeypatch.setattr(
            "specweaver.standards.scanner.StandardsScanner.scan",
            mock_scan,
        )

        result = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert result.exit_code == 0
        assert "No standards discovered" in result.output or "0 standards saved" in result.output

    def test_scan_help(self) -> None:
        """sw standards scan --help works."""
        result = runner.invoke(app, ["standards", "scan", "--help"])
        assert result.exit_code == 0
        assert "Scan" in result.output or "scan" in result.output


# ---------------------------------------------------------------------------
# Item 3: sw standards show
# ---------------------------------------------------------------------------


class TestStandardsShow:
    """CLI tests for sw standards show."""

    def test_show_no_active_project(self) -> None:
        """Show without active project → error."""
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code != 0

    def test_show_no_standards(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Show with no standards in DB → friendly message."""
        _init_project(_mock_db, "empty", str(tmp_path))
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code == 0
        assert "No standards found" in result.output

    def test_show_displays_table(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Show with standards → renders table including data."""
        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj", count=2)
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code == 0
        assert "naming" in result.output
        assert "docstrings" in result.output
        assert "snake_case" in result.output

    def test_show_scope_filter(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Show with --scope filter."""
        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj")
        # Add a standard with a different scope (short category name
        # to avoid Rich table truncation in narrow terminal)
        _mock_db.save_standard(
            project_name="proj",
            scope="backend",
            language="python",
            category="errors",
            data={"style": "exceptions"},
            confidence=0.8,
        )
        result = runner.invoke(app, ["standards", "show", "--scope", "backend"])
        assert result.exit_code == 0
        assert "backend" in result.output
        assert "errors" in result.output

    def test_show_scope_filter_no_match(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Show with --scope that matches nothing → friendly message."""
        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj")
        result = runner.invoke(app, ["standards", "show", "--scope", "nonexistent"])
        assert result.exit_code == 0
        assert "No standards found" in result.output

    def test_show_language_filter(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Show with --language filter returns only matching."""
        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj")
        result = runner.invoke(
            app,
            ["standards", "show", "--language", "python"],
        )
        assert result.exit_code == 0
        assert "naming" in result.output

    def test_show_help(self) -> None:
        """sw standards show --help works."""
        result = runner.invoke(app, ["standards", "show", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Edge cases — boundary conditions
# ---------------------------------------------------------------------------


class TestStandardsEdgeCases:
    """Edge-case scenarios for standards CLI."""

    def test_scan_confidence_exactly_at_boundary(
        self,
        tmp_path: Path,
        _mock_db,
        monkeypatch,
    ) -> None:
        """Scan with confidence exactly 0.3 → saved (< 0.3 is the skip)."""
        from specweaver.standards.analyzer import CategoryResult

        _init_project(_mock_db, "boundary", str(tmp_path))
        py_file = tmp_path / "code.py"
        py_file.write_text("def hello():\n    pass\n", encoding="utf-8")

        call_count = 0

        def mock_scan(self, files, hld):
            nonlocal call_count
            call_count += 1
            # First: 0.3 (saved), rest: 0.29 (skipped)
            conf = 0.3 if call_count == 1 else 0.29
            return [
                CategoryResult(
                    category="test_cat",
                    dominant={"style": "test"},
                    confidence=conf,
                    sample_size=1,
                    language="python",
                )
            ]

        monkeypatch.setattr(
            "specweaver.standards.discovery.discover_files",
            lambda p: [py_file],
        )
        monkeypatch.setattr(
            "specweaver.standards.scanner.StandardsScanner.scan",
            mock_scan,
        )

        result = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert result.exit_code == 0
        standards = _mock_db.get_standards("boundary")
        assert len(standards) >= 1

    def test_scan_rescan_overwrites_existing(
        self,
        tmp_path: Path,
        _mock_db,
        monkeypatch,
    ) -> None:
        """Re-scanning overwrites existing standards (upsert)."""
        _init_project(_mock_db, "rescan", str(tmp_path))
        py_file = tmp_path / "module.py"
        py_file.write_text("def get_data():\n    pass\n", encoding="utf-8")

        monkeypatch.setattr(
            "specweaver.standards.discovery.discover_files",
            lambda p: [py_file],
        )

        # First scan
        result1 = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert result1.exit_code == 0
        standards_before = _mock_db.get_standards("rescan")

        # Change style and re-scan
        py_file.write_text(
            "def getData():\n    pass\ndef processItem():\n    pass\n",
            encoding="utf-8",
        )
        result2 = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert result2.exit_code == 0
        standards_after = _mock_db.get_standards("rescan")

        # No duplicates — upsert on same PK
        assert len(standards_after) <= len(standards_before) + 1

    def test_show_handles_dict_data_directly(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """show() handles data that's already a dict (not JSON string)."""
        _init_project(_mock_db, "dict_proj", str(tmp_path))
        _mock_db.save_standard(
            project_name="dict_proj",
            scope=".",
            language="python",
            category="naming",
            data={"s": "ok"},
            confidence=0.95,
        )
        result = runner.invoke(app, ["standards", "show"])
        assert result.exit_code == 0
        # Verify table rendered without crash (the dict was handled)
        assert "naming" in result.output


# ---------------------------------------------------------------------------
# Item 4: sw standards clear
# ---------------------------------------------------------------------------


class TestStandardsClear:
    """CLI tests for sw standards clear."""

    def test_clear_no_active_project(self) -> None:
        """Clear without active project → error."""
        result = runner.invoke(app, ["standards", "clear"])
        assert result.exit_code != 0

    def test_clear_all(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Clear all standards for the active project."""
        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj")
        assert len(_mock_db.get_standards("proj")) == 2

        result = runner.invoke(app, ["standards", "clear"])
        assert result.exit_code == 0
        assert "Standards cleared" in result.output
        assert len(_mock_db.get_standards("proj")) == 0

    def test_clear_scoped(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Clear only standards matching --scope."""
        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj")  # scope="."
        _mock_db.save_standard(
            project_name="proj",
            scope="backend",
            language="python",
            category="error_handling",
            data={"style": "exceptions"},
            confidence=0.8,
        )
        # Should have 3 total
        assert len(_mock_db.get_standards("proj")) == 3

        result = runner.invoke(
            app,
            ["standards", "clear", "--scope", "backend"],
        )
        assert result.exit_code == 0
        assert "backend" in result.output
        # Only backend cleared
        remaining = _mock_db.get_standards("proj")
        assert len(remaining) == 2
        assert all(s["scope"] == "." for s in remaining)

    def test_clear_when_empty(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """Clear when no standards exist → success (idempotent)."""
        _init_project(_mock_db, "proj", str(tmp_path))
        result = runner.invoke(app, ["standards", "clear"])
        assert result.exit_code == 0
        assert "Standards cleared" in result.output

    def test_clear_help(self) -> None:
        """sw standards clear --help works."""
        result = runner.invoke(app, ["standards", "clear", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Item 5: _file_in_scope helper
# ---------------------------------------------------------------------------


class TestFileInScope:
    """Unit tests for _file_in_scope() helper in standards.py."""

    def test_file_in_named_scope(self, tmp_path: Path) -> None:
        """File under scope path → True."""
        from specweaver.cli.standards import _file_in_scope

        file_path = tmp_path / "backend" / "auth" / "login.py"
        scope_path = tmp_path / "backend" / "auth"
        assert (
            _file_in_scope(
                file_path,
                scope_path,
                tmp_path,
                "backend/auth",
                [".", "backend/auth"],
            )
            is True
        )

    def test_file_not_in_scope(self, tmp_path: Path) -> None:
        """File NOT under scope path → False."""
        from specweaver.cli.standards import _file_in_scope

        file_path = tmp_path / "frontend" / "app.ts"
        scope_path = tmp_path / "backend"
        assert (
            _file_in_scope(
                file_path,
                scope_path,
                tmp_path,
                "backend",
                [".", "backend"],
            )
            is False
        )

    def test_root_scope_excludes_named_scope_files(self, tmp_path: Path) -> None:
        """Root scope '.' excludes files belonging to named scopes."""
        from specweaver.cli.standards import _file_in_scope

        # File in backend/auth — should NOT be in root scope
        file_path = tmp_path / "backend" / "auth" / "login.py"
        scope_path = tmp_path
        assert (
            _file_in_scope(
                file_path,
                scope_path,
                tmp_path,
                ".",
                [".", "backend/auth"],
            )
            is False
        )

    def test_root_scope_includes_non_scoped_files(self, tmp_path: Path) -> None:
        """Root scope '.' includes files not in any named scope."""
        from specweaver.cli.standards import _file_in_scope

        file_path = tmp_path / "setup.py"
        scope_path = tmp_path
        assert (
            _file_in_scope(
                file_path,
                scope_path,
                tmp_path,
                ".",
                [".", "backend/auth"],
            )
            is True
        )

    def test_root_scope_with_no_other_scopes(self, tmp_path: Path) -> None:
        """Root scope '.' with only root → all files belong to root."""
        from specweaver.cli.standards import _file_in_scope

        file_path = tmp_path / "main.py"
        scope_path = tmp_path
        assert (
            _file_in_scope(
                file_path,
                scope_path,
                tmp_path,
                ".",
                ["."],
            )
            is True
        )


# ---------------------------------------------------------------------------
# Item 6: sw standards scopes
# ---------------------------------------------------------------------------


class TestStandardsScopes:
    """CLI tests for sw standards scopes."""

    def test_scopes_no_active_project(self) -> None:
        """scopes without active project → error."""
        result = runner.invoke(app, ["standards", "scopes"])
        assert result.exit_code != 0

    def test_scopes_no_stored_scopes(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """scopes with no stored scopes → friendly message."""
        _init_project(_mock_db, "empty", str(tmp_path))
        result = runner.invoke(app, ["standards", "scopes"])
        assert result.exit_code == 0
        assert "No scopes found" in result.output

    def test_scopes_renders_summary_table(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """scopes with standards → renders summary table."""
        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj", count=2)
        result = runner.invoke(app, ["standards", "scopes"])
        assert result.exit_code == 0
        assert "python" in result.output.lower()

    def test_scopes_multiple_scopes(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """scopes with multiple distinct scopes shows all."""
        _init_project(_mock_db, "proj", str(tmp_path))
        _seed_standards(_mock_db, "proj", count=1)
        _mock_db.save_standard(
            project_name="proj",
            scope="backend",
            language="python",
            category="imports",
            data={"style": "grouped"},
            confidence=0.8,
        )
        result = runner.invoke(app, ["standards", "scopes"])
        assert result.exit_code == 0
        assert "backend" in result.output

    def test_scopes_help(self) -> None:
        """sw standards scopes --help works."""
        result = runner.invoke(app, ["standards", "scopes", "--help"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Item 7: scan --scope flag
# ---------------------------------------------------------------------------


class TestScanScopeFlag:
    """Tests for the --scope flag on sw standards scan."""

    def test_scan_scope_flag(
        self,
        tmp_path: Path,
        _mock_db,
        monkeypatch,
    ) -> None:
        """--scope limits scanning to a single scope."""
        _init_project(_mock_db, "proj", str(tmp_path))
        py_file = tmp_path / "backend" / "app.py"
        py_file.parent.mkdir()
        py_file.write_text("def hello():\n    pass\n", encoding="utf-8")

        monkeypatch.setattr(
            "specweaver.standards.discovery.discover_files",
            lambda p: [py_file],
        )

        result = runner.invoke(
            app,
            ["standards", "scan", "--scope", "backend", "--no-review"],
        )
        assert result.exit_code == 0
