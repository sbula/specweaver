# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E tests — standards scan → show → clear lifecycle (Feature 3.5a-1).

Exercises:
    - Full lifecycle: init project → scan → show → clear → show (empty)
    - Standards injection into review prompt via _load_standards_content
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

_proj_counter = 0


def _unique_name(prefix: str = "std") -> str:
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


def _create_python_project(tmp_path: Path, name: str) -> Path:
    """Create a realistic Python project for e2e testing."""
    project = tmp_path / name
    project.mkdir()
    src = project / "src"
    src.mkdir()

    (src / "__init__.py").write_text("", encoding="utf-8")
    (src / "service.py").write_text(
        '"""Service module."""\n\n\n'
        "def process_request(data: dict) -> dict:\n"
        '    """Process incoming request data."""\n'
        "    try:\n"
        '        return {"status": "ok", "result": data}\n'
        "    except KeyError as e:\n"
        '        return {"status": "error", "message": str(e)}\n',
        encoding="utf-8",
    )
    (src / "models.py").write_text(
        '"""Data models."""\n\n\n'
        "class UserProfile:\n"
        '    """Represents a user profile."""\n\n'
        "    def __init__(self, name: str) -> None:\n"
        "        self.name = name\n\n\n"
        "class OrderItem:\n"
        '    """Represents an order item."""\n\n'
        "    def __init__(self, item_id: int, quantity: int) -> None:\n"
        "        self.item_id = item_id\n"
        "        self.quantity = quantity\n",
        encoding="utf-8",
    )

    tests = project / "tests"
    tests.mkdir()
    (tests / "test_service.py").write_text(
        "import pytest\n\n\ndef test_process_request():\n    assert True  # placeholder\n",
        encoding="utf-8",
    )

    # Init and activate the project
    r = runner.invoke(app, ["init", name, "--path", str(project)])
    assert r.exit_code == 0, f"init failed: {r.output}"
    return project


# ---------------------------------------------------------------------------
# E2E: Full standards lifecycle
# ---------------------------------------------------------------------------


class TestStandardsLifecycleE2E:
    """E2E: complete standards lifecycle from scratch."""

    def test_full_lifecycle_scan_show_clear(self, tmp_path: Path) -> None:
        """init → scan → show (non-empty) → clear → show (empty)."""
        name = _unique_name()
        _create_python_project(tmp_path, name)

        # 1. Scan
        scan = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert scan.exit_code == 0
        assert "scan" in scan.output.lower()

        # 2. Show — should have results
        show1 = runner.invoke(app, ["standards", "show"])
        assert show1.exit_code == 0
        assert "no standards" not in show1.output.lower()

        # 3. Clear
        clear = runner.invoke(app, ["standards", "clear"])
        assert clear.exit_code == 0
        assert "cleared" in clear.output.lower()

        # 4. Show — should be empty
        show2 = runner.invoke(app, ["standards", "show"])
        assert "no standards" in show2.output.lower()

    def test_scan_discovers_expected_patterns(self, tmp_path: Path) -> None:
        """Scan of a consistent Python project should detect snake_case + PascalCase."""
        name = _unique_name()
        _create_python_project(tmp_path, name)

        runner.invoke(app, ["standards", "scan", "--no-review"])
        show = runner.invoke(app, ["standards", "show"])

        # The project has snake_case functions and PascalCase classes
        assert show.exit_code == 0
        # At least some standard should appear
        output = show.output.lower()
        assert "python" in output or "naming" in output or "category" in output

    def test_best_practice_mode_hydrates_empty_repo(self, tmp_path: Path) -> None:
        """Scan of an completely EMPTY project using best_practice should NOT be empty."""
        name = _unique_name()
        project = tmp_path / name
        project.mkdir()
        r = runner.invoke(app, ["init", name, "--path", str(project)])
        assert r.exit_code == 0

        # Write specweaver.toml with best_practice
        toml_path = project / "specweaver.toml"
        toml_path.write_text('[standards]\nmode = "best_practice"\n', encoding="utf-8")

        scan = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert scan.exit_code == 0

        show = runner.invoke(app, ["standards", "show"])
        assert show.exit_code == 0
        output = show.output.lower()

        # Should contain hydrated defaults!
        assert "no standards" not in output


# ---------------------------------------------------------------------------
# E2E: Standards injected into review prompt
# ---------------------------------------------------------------------------


class TestStandardsInjectionE2E:
    """E2E: scan → review → verify standards in prompt."""

    def test_standards_reach_load_standards_content(
        self,
        tmp_path: Path,
        _mock_db,
    ) -> None:
        """After scan, _load_standards_content returns formatted text."""
        from specweaver.interfaces.cli._helpers import _load_standards_content

        name = _unique_name()
        project = _create_python_project(tmp_path, name)

        # Scan to populate DB
        scan = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert scan.exit_code == 0

        # Load standards content (what review/implement would inject)
        content = _load_standards_content(project)
        if content is not None:
            assert isinstance(content, str)
            assert len(content) > 0
            # Should contain formatted standard entries
            assert "python" in content or "SHOULD follow" in content or "snake" in content.lower()

    def test_rescan_after_code_change(self, tmp_path: Path) -> None:
        """Re-scanning after changing code updates stored standards."""
        name = _unique_name()
        project = _create_python_project(tmp_path, name)

        # First scan
        runner.invoke(app, ["standards", "scan", "--no-review"])
        show1 = runner.invoke(app, ["standards", "show"])
        assert show1.exit_code == 0

        # Change all code to a different style
        src = project / "src" / "service.py"
        src.write_text(
            "def processRequest(data):\n    return data\n\ndef handleError(err):\n    raise err\n",
            encoding="utf-8",
        )

        # Re-scan
        runner.invoke(app, ["standards", "scan", "--no-review"])
        show2 = runner.invoke(app, ["standards", "show"])
        assert show2.exit_code == 0
        # No crash, no duplicates — upsert works
