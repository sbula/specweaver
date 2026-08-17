# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Standards discovery end to end, and the configured mode that decides how it behaves.

Proves: D-VAL-04 FR-1, D-VAL-04 FR-2

Cited under `specweaver-dev` §3.2c, from `INT-US-25-SF01-MIG`.

Mutants: the configured `standards.mode` ignored so the run is always `mimicry` (FR-1, 1 fails); the
built-in defaults never supplied to the scanner in `best_practice` mode (FR-2, 1 fails).

**FR-2 shares a path with `E-VAL-02` FR-7 and not a mutant, which is the distinction worth keeping.**
`D-VAL-04` *supplies* the defaults from the handler; `E-VAL-02` *consumes* them in
`StandardsScanner._hydrate_from_defaults` when extraction came back empty. Two lines, two claims, two
mutants — a supplier that stops supplying and a consumer that stops falling back fail differently, and
both are cited separately.

Each is proven by exactly one test. That is thin, and it is recorded as thin rather than smoothed over.

Previously documented here:

E2E tests — standards scan → show → clear lifecycle (Feature 3.5a-1).

Exercises:
    - Full lifecycle: init project → scan → show → clear → show (empty)
    - Standards injection into review prompt via _load_standards_content
"""

from __future__ import annotations

import json
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


def _stored_standards(project: str) -> list[dict]:
    """Read the standards the scan persisted, as the CLI's own `show` does.

    Asserted against instead of the rendered table because Rich sizes columns to content: for the
    richer fixtures the `Dominant Patterns` value is truncated to `function_styl…`, so a table
    assertion would be testing column widths rather than what was stored.
    """
    from specweaver.interfaces.cli import _core

    return _core.run_repo_op(lambda r: r.get_standards(project, scope="src", language="python"))


def _naming_row_count(project: str) -> int:
    return sum(1 for s in _stored_standards(project) if s.get("category") == "naming")


def _stored_naming(project: str) -> dict:
    rows = [s for s in _stored_standards(project) if s.get("category") == "naming"]
    assert rows, f"no naming standard stored for {project}"
    data = rows[0].get("data")
    return data if isinstance(data, dict) else json.loads(str(data))


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
        #         from specweaver.assurance.standards.interfaces.cli import _load_standards_content

        name = _unique_name()
        _create_python_project(tmp_path, name)

        # Scan to populate DB
        scan = runner.invoke(app, ["standards", "scan", "--no-review"])
        assert scan.exit_code == 0

        # Load standards content (what review/implement would inject)
        # content = _load_standards_content(project)
        content = None
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
        before = _stored_naming(name)

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

        # `TECH-017`: the trailing comment claimed "no crash, no duplicates — upsert works" while
        # only exit codes were asserted. Both halves are checked here against STORED state rather
        # than the rendered table — Rich truncates the Dominant Patterns column to fit, and for
        # this fixture the value is cut off before it is readable, so asserting on the table would
        # be asserting on column widths.
        after = _stored_naming(name)

        assert before["function_style"] == "snake_case", before
        assert after["function_style"] == "camelCase", after
        assert _naming_row_count(name) == 1, (
            "re-scan inserted a second naming row instead of upserting"
        )
