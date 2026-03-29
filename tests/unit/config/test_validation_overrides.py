# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for validation override DB methods and settings models."""

from __future__ import annotations

import pytest

from specweaver.config.database import Database
from specweaver.config.settings import RuleOverride, ValidationSettings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db(tmp_path):
    """Fresh database with one registered project."""
    d = Database(tmp_path / "test.db")
    d.register_project("demo", str(tmp_path / "demo"))
    return d


# ---------------------------------------------------------------------------
# RuleOverride / ValidationSettings model tests
# ---------------------------------------------------------------------------


class TestRuleOverrideModel:
    def test_defaults(self):
        o = RuleOverride(rule_id="S08")
        assert o.rule_id == "S08"
        assert o.enabled is True
        assert o.warn_threshold is None
        assert o.fail_threshold is None

    def test_custom_values(self):
        o = RuleOverride(rule_id="C04", enabled=False, warn_threshold=60.0, fail_threshold=80.0)
        assert o.enabled is False
        assert o.warn_threshold == 60.0
        assert o.fail_threshold == 80.0


class TestValidationSettingsModel:
    def test_empty_overrides(self):
        vs = ValidationSettings()
        assert vs.overrides == {}
        assert vs.is_enabled("S01") is True
        assert vs.get_override("S01") is None

    def test_with_overrides(self):
        vs = ValidationSettings(
            overrides={
                "S08": RuleOverride(rule_id="S08", warn_threshold=5.0),
            }
        )
        assert vs.is_enabled("S08") is True
        override = vs.get_override("S08")
        assert override is not None
        assert override.warn_threshold == 5.0

    def test_disabled_rule(self):
        vs = ValidationSettings(
            overrides={
                "C01": RuleOverride(rule_id="C01", enabled=False),
            }
        )
        assert vs.is_enabled("C01") is False
        assert vs.is_enabled("C02") is True  # not overridden → enabled


# ---------------------------------------------------------------------------
# DB: validation_overrides CRUD
# ---------------------------------------------------------------------------


class TestDBValidationOverrides:
    def test_set_override(self, db):
        db.set_validation_override("demo", "S08", warn_threshold=5.0, fail_threshold=10.0)
        o = db.get_validation_override("demo", "S08")
        assert o is not None
        assert o["warn_threshold"] == 5.0
        assert o["fail_threshold"] == 10.0
        assert o["enabled"] == 1

    def test_set_override_enabled_false(self, db):
        db.set_validation_override("demo", "C01", enabled=False)
        o = db.get_validation_override("demo", "C01")
        assert o is not None
        assert o["enabled"] == 0

    def test_set_override_upsert(self, db):
        db.set_validation_override("demo", "S08", warn_threshold=5.0)
        db.set_validation_override("demo", "S08", warn_threshold=10.0)
        o = db.get_validation_override("demo", "S08")
        assert o["warn_threshold"] == 10.0

    def test_get_override_not_found(self, db):
        assert db.get_validation_override("demo", "S99") is None

    def test_get_all_overrides(self, db):
        db.set_validation_override("demo", "S08", warn_threshold=5.0)
        db.set_validation_override("demo", "C04", fail_threshold=80.0)
        overrides = db.get_validation_overrides("demo")
        assert len(overrides) == 2
        rule_ids = {o["rule_id"] for o in overrides}
        assert rule_ids == {"S08", "C04"}

    def test_get_all_overrides_empty(self, db):
        assert db.get_validation_overrides("demo") == []

    def test_delete_override(self, db):
        db.set_validation_override("demo", "S08", warn_threshold=5.0)
        db.delete_validation_override("demo", "S08")
        assert db.get_validation_override("demo", "S08") is None

    def test_delete_override_not_found(self, db):
        # Should not raise — idempotent
        db.delete_validation_override("demo", "S99")

    def test_cascade_on_project_removal(self, db):
        db.set_validation_override("demo", "S08", warn_threshold=5.0)
        db.remove_project("demo")
        # Override should be cascade-deleted
        # Re-register to query the table
        db.register_project("demo2", str(db._db_path.parent / "demo2"))
        assert db.get_validation_overrides("demo") == []

    def test_set_override_nonexistent_project(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.set_validation_override("nope", "S08", warn_threshold=5.0)

    def test_override_isolation_between_projects(self, db, tmp_path):
        db.register_project("other", str(tmp_path / "other"))
        db.set_validation_override("demo", "S08", warn_threshold=5.0)
        db.set_validation_override("other", "S08", warn_threshold=99.0)
        assert db.get_validation_override("demo", "S08")["warn_threshold"] == 5.0
        assert db.get_validation_override("other", "S08")["warn_threshold"] == 99.0


# ---------------------------------------------------------------------------
# DB → ValidationSettings loading
# ---------------------------------------------------------------------------


class TestLoadValidationSettings:
    def test_load_empty(self, db):
        vs = db.load_validation_settings("demo")
        assert vs.overrides == {}

    def test_load_with_overrides(self, db):
        db.set_validation_override("demo", "S08", warn_threshold=5.0, fail_threshold=10.0)
        db.set_validation_override("demo", "C01", enabled=False)
        vs = db.load_validation_settings("demo")
        assert vs.is_enabled("C01") is False
        s08 = vs.get_override("S08")
        assert s08 is not None
        assert s08.warn_threshold == 5.0

    def test_load_nonexistent_project(self, db):
        with pytest.raises(ValueError, match="not found"):
            db.load_validation_settings("nope")


# ---------------------------------------------------------------------------
# Edge-case tests (DB layer)
# ---------------------------------------------------------------------------


class TestDBValidationOverridesEdgeCases:
    """Edge cases for validation override CRUD operations."""

    def test_upsert_preserves_untouched_fields(self, db):
        """Setting warn_threshold should preserve an existing fail_threshold."""
        db.set_validation_override("demo", "S08", warn_threshold=5.0, fail_threshold=10.0)
        # Now update only warn — fail should survive
        db.set_validation_override("demo", "S08", warn_threshold=99.0)
        o = db.get_validation_override("demo", "S08")
        assert o["warn_threshold"] == 99.0
        assert o["fail_threshold"] == 10.0  # preserved

    def test_upsert_preserves_enabled_when_setting_threshold(self, db):
        """Disabling a rule, then setting a threshold should keep it disabled."""
        db.set_validation_override("demo", "S08", enabled=False)
        db.set_validation_override("demo", "S08", warn_threshold=5.0)
        o = db.get_validation_override("demo", "S08")
        assert o["enabled"] == 0  # still disabled
        assert o["warn_threshold"] == 5.0

    def test_upsert_reenable_disabled_rule(self, db):
        """An override can be disabled and then re-enabled."""
        db.set_validation_override("demo", "S01", enabled=False)
        assert db.get_validation_override("demo", "S01")["enabled"] == 0
        db.set_validation_override("demo", "S01", enabled=True)
        assert db.get_validation_override("demo", "S01")["enabled"] == 1

    def test_zero_threshold_stored(self, db):
        """Zero is a valid threshold (means everything triggers)."""
        db.set_validation_override("demo", "S08", warn_threshold=0.0, fail_threshold=0.0)
        o = db.get_validation_override("demo", "S08")
        assert o["warn_threshold"] == 0.0
        assert o["fail_threshold"] == 0.0

    def test_negative_threshold_stored(self, db):
        """Negative thresholds are stored (validation is the caller's job)."""
        db.set_validation_override("demo", "S03", warn_threshold=-1.0, fail_threshold=-5.0)
        o = db.get_validation_override("demo", "S03")
        assert o["warn_threshold"] == -1.0
        assert o["fail_threshold"] == -5.0

    def test_large_threshold_value(self, db):
        """Very large thresholds are stored without precision loss."""
        db.set_validation_override("demo", "S05", fail_threshold=999999.99)
        o = db.get_validation_override("demo", "S05")
        assert o["fail_threshold"] == 999999.99

    def test_set_explicit_enabled_true(self, db):
        """Setting enabled=True explicitly should store 1."""
        db.set_validation_override("demo", "S08", enabled=True)
        o = db.get_validation_override("demo", "S08")
        assert o["enabled"] == 1

    def test_load_settings_disabled_and_thresholds(self, db):
        """load_validation_settings respects both disabled flag and threshold."""
        db.set_validation_override("demo", "S08", enabled=False, warn_threshold=99.0)
        vs = db.load_validation_settings("demo")
        assert vs.is_enabled("S08") is False
        override = vs.get_override("S08")
        assert override is not None
        assert override.warn_threshold == 99.0

    def test_multiple_overrides_for_same_project(self, db):
        """Adding many overrides for one project should all persist."""
        for rule in ["S01", "S03", "S04", "S05", "S07", "S08", "S11"]:
            db.set_validation_override("demo", rule, warn_threshold=float(len(rule)))
        overrides = db.get_validation_overrides("demo")
        assert len(overrides) == 7

    def test_delete_one_preserves_others(self, db):
        """Deleting one override should not affect other overrides."""
        db.set_validation_override("demo", "S08", warn_threshold=5.0)
        db.set_validation_override("demo", "S03", warn_threshold=9.0)
        db.delete_validation_override("demo", "S08")
        assert db.get_validation_override("demo", "S08") is None
        assert db.get_validation_override("demo", "S03")["warn_threshold"] == 9.0

    def test_overrides_sorted_by_rule_id(self, db):
        """get_validation_overrides returns results ordered by rule_id."""
        db.set_validation_override("demo", "S11", warn_threshold=1.0)
        db.set_validation_override("demo", "S01", warn_threshold=2.0)
        db.set_validation_override("demo", "C04", fail_threshold=3.0)
        overrides = db.get_validation_overrides("demo")
        rule_ids = [o["rule_id"] for o in overrides]
        assert rule_ids == sorted(rule_ids)
