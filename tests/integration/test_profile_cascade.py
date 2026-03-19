# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests for domain profile cascade.

Verifies that profile overrides flow correctly through the validation
runner: code defaults → kind presets → DB overrides (from profile) → merged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specweaver.config.database import Database
from specweaver.config.profiles import PROFILES


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
        """Runner's get_spec_rules uses profile overrides for rule construction."""
        from specweaver.validation.runner import get_spec_rules

        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "data-pipeline")

        settings = db.load_validation_settings("myapp")
        rules = get_spec_rules(settings=settings)

        # Find S05 (Day Test) — should have data-pipeline thresholds
        s05 = next(r for r in rules if r.rule_id == "S05")
        assert s05._warn_threshold == 50
        assert s05._fail_threshold == 80

    def test_profile_overrides_for_code_rules(
        self, db: Database, tmp_path: Path,
    ) -> None:
        """Runner's get_code_rules uses profile overrides for rule construction."""
        from specweaver.validation.runner import get_code_rules

        db.register_project("myapp", str(tmp_path))
        db.set_domain_profile("myapp", "library")

        settings = db.load_validation_settings("myapp")
        # Don't run subprocess rules in tests
        rules = get_code_rules(include_subprocess=False, settings=settings)

        # Library doesn't override any non-subprocess code rules
        # (C04 is subprocess-based). Just confirm rules loaded without error.
        assert len(rules) >= 4

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
