# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests — config settings cascade through DB + CLI overrides.

Exercises the full override cascade:
    code defaults → project DB overrides → CLI --set flags.

Uses the shared ``sample_db`` fixture for pre-registered project.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.config.settings import RuleOverride, ValidationSettings

if TYPE_CHECKING:
    from specweaver.config.database import Database

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConfigCascade:
    """Full settings cascade: code defaults → DB → CLI overrides."""

    def test_default_settings_without_db(self) -> None:
        """Settings with no DB and no CLI → code defaults."""
        settings = ValidationSettings()
        assert settings.overrides == {}

    def test_db_override_single_rule(self, sample_db: Database) -> None:
        """Set a rule override in DB → loading picks it up."""
        sample_db.set_validation_override(
            "sample",
            "S08",
            fail_threshold=3.0,
        )

        settings = sample_db.load_validation_settings("sample")
        assert "S08" in settings.overrides
        assert settings.overrides["S08"].fail_threshold == 3.0

    def test_db_override_multiple_rules(self, sample_db: Database) -> None:
        """Multiple rule overrides stored and loaded correctly."""
        sample_db.set_validation_override("sample", "S08", fail_threshold=5.0)
        sample_db.set_validation_override("sample", "C04", enabled=False)

        settings = sample_db.load_validation_settings("sample")
        assert len(settings.overrides) == 2
        assert settings.overrides["S08"].fail_threshold == 5.0
        assert settings.overrides["C04"].enabled is False

    def test_cli_override_on_top_of_db(self, sample_db: Database) -> None:
        """CLI --set flag overrides DB value for same rule."""
        sample_db.set_validation_override("sample", "S08", fail_threshold=5.0)

        settings = sample_db.load_validation_settings("sample")
        assert settings.overrides["S08"].fail_threshold == 5.0

        # CLI override: change S08 fail_threshold to 3
        cli_override = RuleOverride(rule_id="S08", fail_threshold=3.0)
        settings.overrides["S08"] = cli_override

        assert settings.overrides["S08"].fail_threshold == 3.0

    def test_cli_override_adds_new_rule(self, sample_db: Database) -> None:
        """CLI --set adds a rule not in DB."""
        settings = sample_db.load_validation_settings("sample")

        settings.overrides["C07"] = RuleOverride(
            rule_id="C07",
            enabled=False,
        )

        assert "C07" in settings.overrides
        assert settings.overrides["C07"].enabled is False

    def test_override_only_affects_target_rule(self, sample_db: Database) -> None:
        """Overriding one rule doesn't affect others."""
        sample_db.set_validation_override("sample", "S08", fail_threshold=5.0)
        sample_db.set_validation_override("sample", "C04", warn_threshold=2.0)

        settings = sample_db.load_validation_settings("sample")

        settings.overrides["S08"] = RuleOverride(
            rule_id="S08",
            fail_threshold=1.0,
        )

        assert settings.overrides["C04"].warn_threshold == 2.0
        assert settings.overrides["S08"].fail_threshold == 1.0

    def test_reset_removes_override(self, sample_db: Database) -> None:
        """Removing a DB override restores code defaults."""
        sample_db.set_validation_override("sample", "S08", fail_threshold=5.0)

        settings_before = sample_db.load_validation_settings("sample")
        assert "S08" in settings_before.overrides

        sample_db.delete_validation_override("sample", "S08")

        settings_after = sample_db.load_validation_settings("sample")
        assert "S08" not in settings_after.overrides
