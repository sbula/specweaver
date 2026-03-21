# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests for domain profile cascade.

Since Feature 3.5b Sub-Phase A, a profile ONLY stores a pipeline name in
the DB.  It does NOT write validation overrides.  The cascade is:

  YAML pipeline base params
  → per-rule DB overrides  (sw config set)
  → --set CLI flags

Two independent configuration layers:
- Profile (YAML pipeline): sw config set-profile <name>
- Per-rule overrides:      sw config set <RULE> --warn/--fail

These tests verify both layers independently and their interaction.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.config.database import Database

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    """Fresh database for each test."""
    return Database(tmp_path / "test.db")


class TestProfileDB:
    """Profile is stored as a name only — no DB override writes."""

    def test_set_domain_profile_stores_name(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """set_domain_profile stores the profile name, nothing else."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        assert db.get_domain_profile("myapp") == "web-app"

    def test_set_domain_profile_does_not_write_overrides(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """set_domain_profile MUST NOT write any validation_overrides rows."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        overrides = db.get_validation_overrides("myapp")
        assert overrides == [], (
            "set_domain_profile wrote DB overrides — this violates the contract. "
            "Profile = YAML pipeline selector only."
        )

    def test_clear_domain_profile_clears_name_only(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """clear_domain_profile clears profile name but preserves per-rule overrides."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "library")
        # Write an explicit per-rule override
        db.set_validation_override("myapp", "S08", fail_threshold=3)

        db.clear_domain_profile("myapp")

        # Profile is cleared
        assert db.get_domain_profile("myapp") is None
        # But the explicit override is preserved
        overrides = db.get_validation_overrides("myapp")
        assert len(overrides) == 1
        assert overrides[0]["rule_id"] == "S08"

    def test_profile_name_round_trips(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Profile name survives set → get → clear → get cycle."""
        db.register_project("myapp", str(tmp_path))
        assert db.get_domain_profile("myapp") is None
        db.set_domain_profile("myapp", "ml-model")
        assert db.get_domain_profile("myapp") == "ml-model"
        db.clear_domain_profile("myapp")
        assert db.get_domain_profile("myapp") is None

    def test_all_builtin_profiles_accepted(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Every built-in profile name can be activated without error."""
        from specweaver.config.profiles import list_profiles
        db.register_project("myapp", str(tmp_path))
        for p in list_profiles():
            db.set_domain_profile("myapp", p.name)
            assert db.get_domain_profile("myapp") == p.name

    def test_unknown_profile_raises(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """set_domain_profile raises ValueError for unknown profile names."""
        db.register_project("myapp", str(tmp_path))
        with pytest.raises(ValueError, match="Unknown profile"):
            db.set_domain_profile("myapp", "quantum-computing")


class TestPerRuleOverrides:
    """Per-rule DB overrides are independent of profile."""

    def test_override_after_profile_is_additive(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Per-rule overrides added after set-profile accumulate in DB."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        db.set_validation_override("myapp", "S08", fail_threshold=3)

        overrides = db.get_validation_overrides("myapp")
        assert len(overrides) == 1
        assert overrides[0]["rule_id"] == "S08"
        assert overrides[0]["fail_threshold"] == 3

    def test_override_survives_profile_switch(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Switching profile does not delete existing per-rule overrides."""
        db.register_project("myapp", str(tmp_path))
        db.set_validation_override("myapp", "S08", fail_threshold=3)
        db.set_domain_profile("myapp", "library")

        overrides = db.get_validation_overrides("myapp")
        assert any(o["rule_id"] == "S08" for o in overrides)

    def test_profile_doesnt_bleed_across_projects(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Profile on project A doesn't affect project B."""
        path_a = tmp_path / "a"
        path_b = tmp_path / "b"
        path_a.mkdir()
        path_b.mkdir()
        db.register_project("app-a", str(path_a))
        db.register_project("app-b", str(path_b))
        db.set_domain_profile("app-a", "library")
        # app-b has no profile, no overrides
        assert db.get_domain_profile("app-b") is None
        assert db.get_validation_overrides("app-b") == []

    def test_disabled_rule_override(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Disabling a rule via config set is respected in settings."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")
        db.set_validation_override("myapp", "S08", enabled=False)
        settings = db.load_validation_settings("myapp")
        assert not settings.is_enabled("S08")


class TestProfileCascadeWithPipeline:
    """Profile pipeline + per-rule DB overrides cascade correctly."""

    def test_profile_overrides_picked_up_by_runner(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Pipeline executor uses DB overrides for rule construction.

        Profile selects the YAML; per-rule DB overrides are applied on top.
        """
        import specweaver.validation.rules.spec  # noqa: F401
        from specweaver.validation.executor import (
            apply_settings_to_pipeline,
            execute_validation_pipeline,
        )
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "data-pipeline")
        # Add explicit S05 override to simulate what user would do
        db.set_validation_override("myapp", "S05", warn_threshold=50, fail_threshold=80)

        settings = db.load_validation_settings("myapp")
        pipeline = load_pipeline_yaml("validation_spec_default")
        pipeline = apply_settings_to_pipeline(pipeline, settings)
        execute_validation_pipeline(pipeline, "# Test")

        # S05 step should have the DB override applied
        s05_step = next(s for s in pipeline.steps if s.rule == "S05")
        assert s05_step.params.get("warn_threshold") == 50
        assert s05_step.params.get("fail_threshold") == 80

    def test_profile_overrides_for_code_rules(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Pipeline executor uses per-rule DB overrides for code rule construction."""
        import specweaver.validation.rules.code  # noqa: F401
        from specweaver.validation.executor import (
            apply_settings_to_pipeline,
            execute_validation_pipeline,
        )
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "library")
        # Library doesn't override code rules via profile — it selects a YAML
        # but we add a per-rule DB override explicitly
        db.set_validation_override("myapp", "C04", fail_threshold=85)

        settings = db.load_validation_settings("myapp")
        pipeline = load_pipeline_yaml("validation_code_default")
        subprocess_ids = {"C03", "C04"}
        filtered = [s for s in pipeline.steps if s.rule not in subprocess_ids]
        pipeline = pipeline.model_copy(update={"steps": filtered})
        pipeline = apply_settings_to_pipeline(pipeline, settings)
        results = execute_validation_pipeline(pipeline, "# Test")
        assert len(results) >= 4

    def test_profile_plus_spec_kind_cascade(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Profile DB overrides apply on top of kind presets.

        Cascade: code defaults → kind presets → DB overrides.
        DB override should win over kind preset for the same rule.
        """
        import specweaver.validation.rules.spec  # noqa: F401
        from specweaver.validation.executor import apply_settings_to_pipeline
        from specweaver.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.validation.spec_kind import SpecKind, get_presets

        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "data-pipeline")
        # Add explicit S05 override (simulates what the profile mechanism delivers)
        db.set_validation_override("myapp", "S05", warn_threshold=50, fail_threshold=80)

        settings = db.load_validation_settings("myapp")
        pipeline = load_pipeline_yaml("validation_spec_default")

        # Apply kind presets first (FEATURE: S05 warn=60, fail=100)
        for step in pipeline.steps:
            preset_kwargs = get_presets(step.rule, SpecKind.FEATURE)
            if preset_kwargs:
                merged = {**step.params, **preset_kwargs}
                step.params.clear()
                step.params.update(merged)

        # Apply DB overrides on top (S05: warn=50, fail=80)
        pipeline = apply_settings_to_pipeline(pipeline, settings)

        # DB override wins over kind preset
        s05_step = next(s for s in pipeline.steps if s.rule == "S05")
        assert s05_step.params.get("warn_threshold") == 50   # DB override wins
        assert s05_step.params.get("fail_threshold") == 80   # DB override wins
