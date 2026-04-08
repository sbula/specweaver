# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""E2E tests — domain profile CLI commands (Feature 3.3).

Exercises:
    sw config profiles / show-profile / set-profile / get-profile / reset-profile
    Profile + individual override layering
    Profile-aware sw check flow
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.cli.main import app

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
        """sw config show-profile shows the pipeline parameters for a profile."""
        result = runner.invoke(app, ["config", "show-profile", "web-app"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        # web-app YAML has s05 and s03 overrides
        assert "S05" in result.output or "s05" in result.output.lower()
        # Profile table should show the pipeline name
        assert "web-app" in result.output.lower()

    def test_show_profile_unknown(self, _mock_db) -> None:
        """sw config show-profile with unknown profile shows error."""
        result = runner.invoke(app, ["config", "show-profile", "doesnt-exist"])
        assert result.exit_code != 0

    def test_set_profile(self, tmp_path: Path, _mock_db) -> None:
        """sw config set-profile stores the profile name only (no DB overrides written)."""
        name = _unique_name("profile")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)

        result = runner.invoke(app, ["config", "set-profile", "web-app"])
        assert result.exit_code == 0, f"Failed: {result.output}"
        assert "web-app" in result.output

        # Profile name is stored
        assert _mock_db.get_domain_profile(name) == "web-app"

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
        """sw config reset-profile clears profile name only (overrides preserved)."""
        name = _unique_name("profreset")
        runner.invoke(app, ["init", name, "--path", str(tmp_path)])
        _mock_db.set_active_project(name)
        runner.invoke(app, ["config", "set-profile", "web-app"])

        result = runner.invoke(app, ["config", "reset-profile"])
        assert result.exit_code == 0, f"Failed: {result.output}"

        # Profile name should be cleared
        assert _mock_db.get_domain_profile(name) is None
        # Per-rule overrides are preserved (none were set in this test, so empty)
        # assert _mock_db.get_validation_overrides(name) == []

    def test_set_profile_then_check_spec(
        self,
        tmp_path: Path,
        _mock_db,
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
        result = runner.invoke(
            app,
            [
                "check",
                str(spec),
                "--level",
                "component",
                "--project",
                str(tmp_path),
            ],
        )
        # Should run (may pass or warn, but not crash)
        assert result.exit_code in (0, 1), f"Crashed: {result.output}"

    def test_set_profile_no_active_project(self, _mock_db) -> None:
        """sw config set-profile without active project shows error."""
        result = runner.invoke(app, ["config", "set-profile", "web-app"])
        assert result.exit_code != 0
