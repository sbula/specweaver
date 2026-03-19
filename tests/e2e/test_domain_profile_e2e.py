# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""E2E tests — domain profile CLI commands (Feature 3.3).

Exercises:
    sw config profiles / show-profile / set-profile / get-profile / reset-profile
    Profile + individual override layering
    Profile-aware sw check flow
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

# Counter for unique project names in tests
_proj_counter = 0


def _unique_name(prefix: str = "test") -> str:
    """Generate unique project names to avoid DB collisions."""
    global _proj_counter
    _proj_counter += 1
    return f"{prefix}-{_proj_counter}"


@pytest.fixture(autouse=True)
def _mock_db(tmp_path, monkeypatch):
    """Patch get_db() to use a temp DB for all e2e tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli.get_db", lambda: db)
    return db


# ===========================================================================
# Domain Profile CLI E2E (Feature 3.3)
# ===========================================================================


class TestDomainProfileCLI:
    """E2E tests for sw config profile commands."""

    def test_profiles_lists_all(self, _mock_db) -> None:
        """sw config profiles lists all available profiles."""
        result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "web-app" in result.output
        assert "data-pipeline" in result.output
        assert "library" in result.output
        assert "microservice" in result.output
        assert "ml-model" in result.output

    def test_show_profile(self, _mock_db) -> None:
        """sw config show-profile shows overrides for a profile."""
        result = runner.invoke(app, ["config", "show-profile", "web-app"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "S05" in result.output
        assert "S08" in result.output
        assert "C04" in result.output

    def test_show_profile_unknown(self, _mock_db) -> None:
        """sw config show-profile with unknown profile shows error."""
        result = runner.invoke(app, ["config", "show-profile", "doesnt-exist"])
        assert result.exit_code != 0

    def test_set_profile(self, tmp_path: Path, _mock_db) -> None:
        """sw config set-profile applies profile overrides."""
        name = _unique_name("profile")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        result = runner.invoke(app, ["config", "set-profile", "web-app"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "web-app" in result.output

        # Verify overrides are now set
        overrides = _mock_db.get_validation_overrides(name)
        rule_ids = {o["rule_id"] for o in overrides}
        assert "S05" in rule_ids
        assert "C04" in rule_ids

    def test_set_profile_unknown(self, tmp_path: Path, _mock_db) -> None:
        """sw config set-profile with unknown profile shows error."""
        name = _unique_name("profile-bad")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        result = runner.invoke(app, ["config", "set-profile", "quantum"])
        assert result.exit_code != 0

    def test_get_profile_none(self, tmp_path: Path, _mock_db) -> None:
        """sw config get-profile shows no profile when none set."""
        name = _unique_name("profget")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        result = runner.invoke(app, ["config", "get-profile"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "no" in result.output.lower() or "none" in result.output.lower()

    def test_get_profile_after_set(self, tmp_path: Path, _mock_db) -> None:
        """sw config get-profile shows the active profile name."""
        name = _unique_name("profget2")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)
        runner.invoke(app, ["config", "set-profile", "library"])

        result = runner.invoke(app, ["config", "get-profile"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "library" in result.output

    def test_reset_profile(self, tmp_path: Path, _mock_db) -> None:
        """sw config reset-profile clears profile and overrides."""
        name = _unique_name("profreset")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)
        runner.invoke(app, ["config", "set-profile", "web-app"])

        result = runner.invoke(app, ["config", "reset-profile"])
        assert result.exit_code == 0, f"Failed: {result.output}"

        # Profile should be cleared
        assert _mock_db.get_domain_profile(name) is None
        assert _mock_db.get_validation_overrides(name) == []

    def test_individual_override_on_top_of_profile(
        self, tmp_path: Path, _mock_db,
    ) -> None:
        """Individual override on top of profile works."""
        name = _unique_name("proflayer")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)
        runner.invoke(app, ["config", "set-profile", "web-app"])

        # Fine-tune S08 on top of profile
        result = runner.invoke(app, ["config", "set", "S08", "--fail", "3"])
        assert result.exit_code == 0

        # S08 should now have fail=3 (our override) instead of fail=8 (profile)
        o = _mock_db.get_validation_override(name, "S08")
        assert o is not None
        assert o["fail_threshold"] == 3

    def test_set_profile_then_check_spec(
        self, tmp_path: Path, _mock_db,
    ) -> None:
        """Full flow: set-profile → check spec works with profile thresholds."""
        name = _unique_name("profcheck")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        # Apply profile
        result = runner.invoke(app, ["config", "set-profile", "web-app"])
        assert result.exit_code == 0

        # Create a minimal spec and check it
        spec = tmp_path / "specs" / "test_spec.md"
        spec.parent.mkdir(parents=True, exist_ok=True)
        spec.write_text(
            "# Test Spec\n\n## 1. Purpose\nA simple test spec.\n\n"
            "## 2. Requirements\n- Do something.\n",
        )
        result = runner.invoke(app, [
            "check", str(spec), "--level", "component", "--project", str(tmp_path),
        ])
        # Should run (may pass or warn, but not crash)
        assert result.exit_code in (0, 1), f"Crashed: {result.output}"

    def test_config_list_shows_profile_overrides(
        self, tmp_path: Path, _mock_db,
    ) -> None:
        """sw config list after set-profile shows all profile overrides."""
        name = _unique_name("proflist")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)
        runner.invoke(app, ["config", "set-profile", "web-app"])

        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        # Should show the profile's overrides
        assert "S05" in result.output
        assert "C04" in result.output

    def test_set_profile_no_active_project(self, _mock_db) -> None:
        """sw config set-profile without active project shows error."""
        result = runner.invoke(app, ["config", "set-profile", "web-app"])
        assert result.exit_code != 0
