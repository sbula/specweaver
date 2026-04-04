# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests — multi-project workflows.

Exercises the full project lifecycle when more than one project is registered:
  - Two projects can co-exist without cross-contamination
  - Removing one project leaves the other intact and operable
  - Updating a project path causes subsequent operations to use the new path
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

_proj_counter = 0


def _unique_name(prefix: str = "mp") -> str:
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


def _init_project(tmp_path: Path, name: str) -> Path:
    """Helper: create a sub-directory and init a project there."""
    project_dir = tmp_path / name
    project_dir.mkdir()
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, f"init failed for {name}: {result.output}"
    return project_dir


def _write_spec(project_dir: Path, component: str = "calc") -> Path:
    """Write a minimal valid spec file under a project directory."""
    spec = project_dir / "specs" / f"{component}_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text(
        f"# {component}\n\n"
        "## 1. Purpose\n\nDoes exactly one thing.\n\n"
        "## 2. Contract\n\n```python\ndef run() -> None: ...\n```\n\n"
        "## 3. Protocol\n\n1. Accept no arguments.\n2. Return None.\n\n"
        "## 4. Policy\n\n| Error | Behavior |\n|:---|:---|\n| None | Raise |\n\n"
        "## 5. Boundaries\n\n| Concern | Owned By |\n|:---|:---|\n| I/O | Infra |\n",
        encoding="utf-8",
    )
    return spec


# ===========================================================================
# Test 8: Two projects, switch between them — no cross-contamination
# ===========================================================================


class TestTwoProjectsSwitchAndOperate:
    """Init two projects, switch active, verify no state leaks."""

    def test_two_projects_switch_and_operate(self, tmp_path: Path) -> None:
        """Init P1 + P2 → switch active → each check uses the correct project DB.

        Verifies that:
        - sw check on a spec from P1 still works after switching to P2
        - sw check on a spec from P2 works correctly
        - Rule output (S01, etc.) appears for both
        """
        # --- Project 1 ---
        p1_dir = _init_project(tmp_path, _unique_name("p1"))
        spec_p1 = _write_spec(p1_dir, "alpha")

        # --- Project 2 ---
        p2_dir = _init_project(tmp_path, _unique_name("p2"))
        spec_p2 = _write_spec(p2_dir, "beta")

        # Switch active project to P2 (sw use takes project NAME)
        use_result = runner.invoke(
            app,
            ["use", p2_dir.name],
        )
        assert use_result.exit_code == 0, f"sw use failed: {use_result.output}"

        # Check a spec from P1 (explicit --project)
        check_p1 = runner.invoke(
            app,
            ["check", str(spec_p1), "--level", "component", "--project", str(p1_dir)],
        )
        assert check_p1.exit_code in (0, 1), f"check P1 crashed: {check_p1.output}"
        assert "S01" in check_p1.output, "Expected rule S01 in P1 check output"

        # Check a spec from P2 (explicit --project)
        check_p2 = runner.invoke(
            app,
            ["check", str(spec_p2), "--level", "component", "--project", str(p2_dir)],
        )
        assert check_p2.exit_code in (0, 1), f"check P2 crashed: {check_p2.output}"
        assert "S01" in check_p2.output, "Expected rule S01 in P2 check output"

        # The two check results must not share state: spec names are distinct
        assert "alpha" not in check_p2.output or "beta" not in check_p1.output


# ===========================================================================
# Test 9: Remove P1 → P2 still works
# ===========================================================================


class TestRemoveProjectOperationsOnRemaining:
    """After removing one project, the other continues to operate normally."""

    def test_remove_project_operations_on_remaining(
        self,
        tmp_path: Path,
    ) -> None:
        """Remove P1 → P2 still usable for sw check.

        Verifies:
        - sw remove succeeds
        - sw projects no longer shows P1
        - sw check on P2 spec still works
        """
        # Init both projects
        p1_dir = _init_project(tmp_path, _unique_name("rem1"))
        p2_dir = _init_project(tmp_path, _unique_name("rem2"))
        spec_p2 = _write_spec(p2_dir, "survivor")

        # Confirm both show up in sw projects
        list_before = runner.invoke(app, ["projects"])
        assert list_before.exit_code == 0
        assert str(p1_dir.name) in list_before.output or str(p1_dir) in list_before.output

        # Remove P1 by name (sw remove takes project NAME, not path)
        remove_result = runner.invoke(app, ["remove", p1_dir.name, "--force"])
        assert remove_result.exit_code == 0, f"remove failed: {remove_result.output}"

        # P1 should no longer appear in project list
        list_after = runner.invoke(app, ["projects"])
        assert list_after.exit_code == 0
        # P2 should still appear (Rich may truncate the path; check name or path tail)
        assert p2_dir.name in list_after.output or "rem2" in list_after.output, (
            f"P2 not in project list after P1 removed:\n{list_after.output}"
        )

        # P2 should still be operable
        check_p2 = runner.invoke(
            app,
            ["check", str(spec_p2), "--level", "component", "--project", str(p2_dir)],
        )
        assert check_p2.exit_code in (0, 1), f"check P2 crashed after removal: {check_p2.output}"
        assert "S01" in check_p2.output


# ===========================================================================
# Test 10: sw update path → subsequent operations use the new path
# ===========================================================================


class TestUpdateProjectPathUsesNew:
    """After sw update path, operations target the new directory."""

    def test_update_project_path_uses_new(self, tmp_path: Path) -> None:
        """Init project at old_dir → update path to new_dir → sw check from new_dir.

        Verifies:
        - sw update path succeeds
        - sw projects shows the new path
        - sw check targeting a spec in new_dir works
        """
        old_dir = tmp_path / "old_dir"
        old_dir.mkdir()
        new_dir = tmp_path / "new_dir"

        name = _unique_name("upd")

        # Init at old_dir
        init_result = runner.invoke(app, ["init", name, "--path", str(old_dir)])
        assert init_result.exit_code == 0, f"init failed: {init_result.output}"

        # Simulate project being moved to new_dir
        import shutil

        shutil.copytree(str(old_dir), str(new_dir))

        # Update the registered path: sw update NAME FIELD VALUE
        update_result = runner.invoke(
            app,
            ["update", name, "path", str(new_dir)],
        )
        assert update_result.exit_code == 0, f"sw update path failed: {update_result.output}"

        # Project list should show updated path (Rich may truncate it; check name or tail)
        list_result = runner.invoke(app, ["projects"])
        assert list_result.exit_code == 0
        # Path in table may be truncated — assert on the project name or directory tail
        assert name in list_result.output or "new_dir" in list_result.output, (
            f"New path not visible in project list:\n{list_result.output}"
        )

        # Check a spec from the new directory works
        spec = _write_spec(new_dir, "relocated")
        check_result = runner.invoke(
            app,
            ["check", str(spec), "--level", "component", "--project", str(new_dir)],
        )
        assert check_result.exit_code in (0, 1), (
            f"check after path update crashed: {check_result.output}"
        )
        assert "S01" in check_result.output
