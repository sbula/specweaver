# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests for domain profile cascade.

Verifies that profile overrides flow correctly through the validation
runner: code defaults → kind presets → DB overrides (from profile) → merged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.config.database import Database
from specweaver.config.profiles import PROFILES

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    """Fresh database for each test."""
    return Database(tmp_path / "test.db")


class TestProfileCascade:
    """Profile overrides are picked up by the validation runner."""

    def test_profile_overrides_appear_in_validation_settings(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """After set_domain_profile, load_validation_settings returns overrides."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")

        settings = db.load_validation_settings("myapp")
        # web-app profile sets S05, S08, C04, S03
        s05 = settings.get_override("S05")
        assert s05 is not None
        assert s05.warn_threshold == 30
        assert s05.fail_threshold == 50

    def test_individual_override_wins_over_profile(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Individual override after profile replaces that rule's values."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")

        # Fine-tune S08 on top
        db.set_validation_override("myapp", "S08", fail_threshold=3)

        settings = db.load_validation_settings("myapp")
        s08 = settings.get_override("S08")
        assert s08 is not None
        assert s08.fail_threshold == 3  # individual override
        assert s08.warn_threshold == 3  # from profile (preserved)

    def test_reset_returns_to_defaults(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """After clear_domain_profile, no overrides remain."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "library")
        db.clear_domain_profile("myapp")

        settings = db.load_validation_settings("myapp")
        assert settings.overrides == {}

    def test_profile_switch_replaces_all_overrides(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Switching profiles replaces old profile's overrides entirely."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "library")

        # Library has S11; web-app does not
        settings = db.load_validation_settings("myapp")
        assert settings.get_override("S11") is not None

        db.set_domain_profile("myapp", "web-app")
        settings = db.load_validation_settings("myapp")
        assert settings.get_override("S11") is None  # gone after switch

    def test_all_profiles_produce_valid_settings(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Every profile produces a valid ValidationSettings object."""
        db.register_project("myapp", str(tmp_path))
        for name in PROFILES:
            db.set_domain_profile("myapp", name)
            settings = db.load_validation_settings("myapp")
            assert len(settings.overrides) == len(PROFILES[name].overrides)

    def test_profile_overrides_picked_up_by_runner(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Pipeline executor uses profile overrides for rule construction."""
        import specweaver.validation.rules.spec  # noqa: F401

        from specweaver.validation.executor import (
            apply_settings_to_pipeline,
            execute_validation_pipeline,
        )
        from specweaver.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.validation.runner import run_rules

        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "data-pipeline")

        settings = db.load_validation_settings("myapp")
        pipeline = load_pipeline_yaml("validation_spec_default")
        pipeline = apply_settings_to_pipeline(pipeline, settings)
        results = execute_validation_pipeline(pipeline, "# Test")

        # Find S05 (Day Test) — should have data-pipeline thresholds
        # With settings applied, the step params should include the override
        s05_step = next(s for s in pipeline.steps if s.rule == "S05")
        # data-pipeline profile: warn=50, fail=80
        assert s05_step.params.get("warn_threshold") == 50
        assert s05_step.params.get("fail_threshold") == 80

    def test_profile_overrides_for_code_rules(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Pipeline executor uses profile overrides for code rule construction."""
        import specweaver.validation.rules.code  # noqa: F401

        from specweaver.validation.executor import (
            apply_settings_to_pipeline,
            execute_validation_pipeline,
        )
        from specweaver.validation.pipeline_loader import load_pipeline_yaml

        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "library")

        settings = db.load_validation_settings("myapp")
        # Load code pipeline, filter out subprocess rules (C03, C04) for test
        pipeline = load_pipeline_yaml("validation_code_default")
        subprocess_ids = {"C03", "C04"}
        filtered = [s for s in pipeline.steps if s.rule not in subprocess_ids]
        pipeline = pipeline.model_copy(update={"steps": filtered})
        pipeline = apply_settings_to_pipeline(pipeline, settings)
        results = execute_validation_pipeline(pipeline, "# Test")

        # Library doesn't override any non-subprocess code rules
        # (C04 is subprocess-based). Just confirm rules loaded without error.
        assert len(results) >= 4

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


class TestProfileEdgeCases:
    """Critical edge cases for profile interactions."""

    def test_profile_plus_spec_kind_cascade(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Profile overrides and SpecKind presets merge correctly.

        Cascade: code defaults → kind presets → DB overrides (profile).
        Profile should win over kind presets for the same rule.
        """
        import specweaver.validation.rules.spec  # noqa: F401

        from specweaver.validation.executor import (
            apply_settings_to_pipeline,
        )
        from specweaver.validation.pipeline_loader import load_pipeline_yaml
        from specweaver.validation.spec_kind import SpecKind, get_presets

        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "data-pipeline")

        settings = db.load_validation_settings("myapp")
        pipeline = load_pipeline_yaml("validation_spec_default")
        # Apply kind presets first (FEATURE: S05 warn=60, fail=100)
        from specweaver.validation.registry import get_registry
        registry = get_registry()
        for step in pipeline.steps:
            preset_kwargs = get_presets(step.rule, SpecKind.FEATURE)
            if preset_kwargs:
                merged = {**step.params, **preset_kwargs}
                step.params.clear()
                step.params.update(merged)

        # Apply profile overrides on top (data-pipeline S05: warn=50, fail=80)
        pipeline = apply_settings_to_pipeline(pipeline, settings)

        # S05: kind=FEATURE preset has warn=60, fail=100
        # data-pipeline profile has warn=50, fail=80
        # Profile (DB override) should win over kind preset
        s05_step = next(s for s in pipeline.steps if s.rule == "S05")
        assert s05_step.params.get("warn_threshold") == 50  # profile wins
        assert s05_step.params.get("fail_threshold") == 80  # profile wins

    def test_disabled_rule_on_top_of_profile(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Disabling a rule after applying profile is respected."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "web-app")

        # Disable S08 (which the profile set)
        db.set_validation_override("myapp", "S08", enabled=False)

        settings = db.load_validation_settings("myapp")
        assert not settings.is_enabled("S08")

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

        # app-b should have no overrides
        settings_b = db.load_validation_settings("app-b")
        assert settings_b.overrides == {}
        assert db.get_domain_profile("app-b") is None

    def test_config_list_shows_profile_overrides(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """After set-profile, get_validation_overrides returns all profile rules."""
        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "ml-model")

        overrides = db.get_validation_overrides("myapp")
        rule_ids = {o["rule_id"] for o in overrides}
        # ml-model has: S03, S05, S07, S08, S11, C04
        assert rule_ids == {"S03", "S05", "S07", "S08", "S11", "C04"}

