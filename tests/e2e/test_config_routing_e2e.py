# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests — LLM model routing CLI commands (Feature 3.12b SF-2).

Exercises:
    sw config routing set <task_type> <profile_name>
    sw config routing show
    sw config routing clear
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.config.database import Database

runner = CliRunner()

_proj_counter = 0


def _unique_name(prefix: str = "test-route") -> str:
    """Generate unique project names to avoid DB collisions."""
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


class TestConfigRoutingE2E:
    """E2E tests for sw config routing commands."""

    def test_full_routing_lifecycle(self, tmp_path: Path, _mock_db: Database) -> None:
        """Full E2E lifecycle: set, show, and clear."""
        name = _unique_name("route-lifecycle")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        # Create some profiles backing the routes
        _mock_db.create_llm_profile("o1-mini-prof", provider="openai", model="o1-mini")
        _mock_db.create_llm_profile(
            "claude-prof",
            provider="anthropic",
            model="claude-3-5-sonnet",
        )

        # 1. SET
        result = runner.invoke(app, ["config", "routing", "set", "plan", "o1-mini-prof"])
        assert result.exit_code == 0
        assert "plan" in result.output
        assert "o1-mini-prof" in result.output

        result2 = runner.invoke(app, ["config", "routing", "set", "implement", "claude-prof"])
        assert result2.exit_code == 0

        # 2. SHOW
        show_result = runner.invoke(app, ["config", "routing", "show"])
        assert show_result.exit_code == 0
        assert "plan" in show_result.output
        assert "o1-mini-prof" in show_result.output
        assert "implement" in show_result.output
        assert "claude-prof" in show_result.output

        # 3. CLEAR specific
        clear_spec = runner.invoke(app, ["config", "routing", "clear", "plan"])
        assert clear_spec.exit_code == 0
        assert "Cleared routing for" in clear_spec.output
        assert "plan" in clear_spec.output

        # 4. SHOW after clear specific (plan is gone, implement remains)
        show_result2 = runner.invoke(app, ["config", "routing", "show"])
        assert "plan" not in show_result2.output
        assert "implement" in show_result2.output

        # 5. CLEAR all
        # By default 'clear' doesn't ask for confirmation right now (unless I add a prompt), wait in test CLI we didn't add prompt
        clear_all = runner.invoke(app, ["config", "routing", "clear"])
        assert clear_all.exit_code == 0
        assert "Cleared all" in clear_all.output

        # 6. SHOW after clear all
        show_result3 = runner.invoke(app, ["config", "routing", "show"])
        assert "No routing configured" in show_result3.output

    def test_show_orphaned_profile(self, tmp_path: Path, _mock_db: Database) -> None:
        """If a profile is deleted, 'show' renders it safely."""
        name = _unique_name("route-orphan")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        pid = _mock_db.create_llm_profile("doomed-prof", provider="gemini", model="gemini-1.5-pro")
        runner.invoke(app, ["config", "routing", "set", "review", "doomed-prof"])

        # Orphan the profile by deleting the underlying profile ID
        with _mock_db.connect() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM llm_profiles WHERE id = ?", (pid,))
            conn.execute("PRAGMA foreign_keys = ON")

        show_result = runner.invoke(app, ["config", "routing", "show"])
        assert show_result.exit_code == 0
        assert "review" in show_result.output
        assert "[deleted]" in show_result.output

    def test_invalid_terminal_inputs(self, tmp_path: Path, _mock_db: Database) -> None:
        """Invalid commands exit gracefully with non-zero exit codes."""
        name = _unique_name("route-invalid")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        # 1. Invalid task type
        res1 = runner.invoke(app, ["config", "routing", "set", "fly", "some-prof"])
        assert res1.exit_code != 0

        # 2. Nonexistent profile
        res2 = runner.invoke(app, ["config", "routing", "set", "draft", "nonexistent-prof"])
        assert res2.exit_code != 0
        assert "Profile 'nonexistent-prof' not found" in res2.output
