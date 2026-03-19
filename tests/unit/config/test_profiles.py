# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.config.profiles — TDD (tests first).

Test structure:
- DomainProfile model
- Profile registry (PROFILES dict)
- get_profile() lookup
- list_profiles() enumeration
- Profile override validation (all profiles produce valid RuleOverrides)
"""

from __future__ import annotations

import pytest

from specweaver.config.profiles import (
    PROFILES,
    DomainProfile,
    get_profile,
    list_profiles,
)
from specweaver.config.settings import RuleOverride

# ===========================================================================
# DomainProfile Model
# ===========================================================================


class TestDomainProfileModel:
    """DomainProfile dataclass behavior."""

    def test_construction(self) -> None:
        profile = DomainProfile(
            name="test",
            description="A test profile",
            overrides={
                "S05": RuleOverride(rule_id="S05", warn_threshold=30, fail_threshold=50),
            },
        )
        assert profile.name == "test"
        assert profile.description == "A test profile"
        assert len(profile.overrides) == 1
        assert profile.overrides["S05"].warn_threshold == 30

    def test_frozen(self) -> None:
        """DomainProfile is immutable."""
        profile = DomainProfile(
            name="test",
            description="test",
            overrides={},
        )
        with pytest.raises(AttributeError):
            profile.name = "hacked"  # type: ignore[misc]

    def test_empty_overrides(self) -> None:
        """A profile with no overrides is valid (uses all defaults)."""
        profile = DomainProfile(name="empty", description="empty", overrides={})
        assert profile.overrides == {}


# ===========================================================================
# Profile Registry
# ===========================================================================


class TestProfileRegistry:
    """PROFILES dict contains all expected profiles."""

    def test_all_expected_profiles_exist(self) -> None:
        expected = {"web-app", "data-pipeline", "library", "microservice", "ml-model"}
        assert set(PROFILES.keys()) == expected

    def test_profile_count(self) -> None:
        assert len(PROFILES) == 5

    def test_all_profiles_are_domain_profile_instances(self) -> None:
        for name, profile in PROFILES.items():
            assert isinstance(profile, DomainProfile), f"{name} is not DomainProfile"

    def test_all_profiles_have_descriptions(self) -> None:
        for name, profile in PROFILES.items():
            assert profile.description, f"{name} has empty description"
            assert len(profile.description) > 10, f"{name} description too short"

    def test_profile_names_match_keys(self) -> None:
        """Profile.name must match its dict key."""
        for key, profile in PROFILES.items():
            assert profile.name == key, f"Key '{key}' != profile.name '{profile.name}'"

    def test_all_overrides_are_rule_overrides(self) -> None:
        for name, profile in PROFILES.items():
            for rule_id, override in profile.overrides.items():
                assert isinstance(override, RuleOverride), (
                    f"{name}.{rule_id} is not RuleOverride"
                )

    def test_all_override_rule_ids_match_keys(self) -> None:
        """RuleOverride.rule_id must match its dict key."""
        for name, profile in PROFILES.items():
            for key, override in profile.overrides.items():
                assert override.rule_id == key, (
                    f"{name}: key '{key}' != override.rule_id '{override.rule_id}'"
                )

    def test_all_override_rule_ids_are_valid(self) -> None:
        """All rule IDs in profiles must be known rules (S01-S11, C01-C08)."""
        valid_ids = {
            f"S{i:02d}" for i in range(1, 12)
        } | {
            f"C{i:02d}" for i in range(1, 9)
        }
        for name, profile in PROFILES.items():
            for rule_id in profile.overrides:
                assert rule_id in valid_ids, (
                    f"{name}: unknown rule_id '{rule_id}'"
                )


# ===========================================================================
# Individual Profile Spot Checks
# ===========================================================================


class TestProfileValues:
    """Spot-check key values in each profile."""

    def test_web_app_has_s05_override(self) -> None:
        p = PROFILES["web-app"]
        assert "S05" in p.overrides
        assert p.overrides["S05"].warn_threshold == 30
        assert p.overrides["S05"].fail_threshold == 50

    def test_web_app_has_c04_override(self) -> None:
        p = PROFILES["web-app"]
        assert "C04" in p.overrides
        assert p.overrides["C04"].fail_threshold == 70

    def test_data_pipeline_lenient_coverage(self) -> None:
        p = PROFILES["data-pipeline"]
        assert "C04" in p.overrides
        assert p.overrides["C04"].fail_threshold == 60

    def test_library_strict_coverage(self) -> None:
        p = PROFILES["library"]
        assert "C04" in p.overrides
        assert p.overrides["C04"].fail_threshold == 85

    def test_ml_model_very_lenient(self) -> None:
        p = PROFILES["ml-model"]
        assert "C04" in p.overrides
        assert p.overrides["C04"].fail_threshold == 50
        # ML tolerates high complexity
        assert "S05" in p.overrides
        assert p.overrides["S05"].warn_threshold == 80

    def test_microservice_coverage(self) -> None:
        p = PROFILES["microservice"]
        assert "C04" in p.overrides
        assert p.overrides["C04"].fail_threshold == 75


# ===========================================================================
# get_profile()
# ===========================================================================


class TestGetProfile:
    """get_profile() lookup behavior."""

    def test_existing_profile(self) -> None:
        result = get_profile("web-app")
        assert result is not None
        assert result.name == "web-app"

    def test_case_insensitive(self) -> None:
        result = get_profile("WEB-APP")
        assert result is not None
        assert result.name == "web-app"

    def test_unknown_profile_returns_none(self) -> None:
        result = get_profile("quantum-computing")
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        result = get_profile("")
        assert result is None


# ===========================================================================
# list_profiles()
# ===========================================================================


class TestListProfiles:
    """list_profiles() enumeration."""

    def test_returns_all_profiles(self) -> None:
        result = list_profiles()
        assert len(result) == 5

    def test_sorted_by_name(self) -> None:
        result = list_profiles()
        names = [p.name for p in result]
        assert names == sorted(names)

    def test_returns_domain_profile_instances(self) -> None:
        result = list_profiles()
        for p in result:
            assert isinstance(p, DomainProfile)
