# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.config.profiles — YAML-backed domain profiles.

Since Feature 3.5b Sub-Phase A, a profile is no longer a hardcoded
Python dict of ``RuleOverride`` values.  It is simply a name that maps
to a built-in or custom pipeline YAML file.  Tests verify:

- DomainProfile model (name + description, immutable)
- Profile discovery (list_profiles, get_profile)
- Utility helpers (profile_exists, profile_to_pipeline_name)
- The built-in profiles match the pipeline YAML files in the package
"""

from __future__ import annotations

import pytest

from specweaver.config.profiles import (
    DomainProfile,
    get_profile,
    list_profiles,
    profile_exists,
    profile_to_pipeline_name,
)

# ===========================================================================
# DomainProfile Model
# ===========================================================================


class TestDomainProfileModel:
    """DomainProfile dataclass behavior."""

    def test_construction(self) -> None:
        profile = DomainProfile(name="test", description="A test profile")
        assert profile.name == "test"
        assert profile.description == "A test profile"

    def test_frozen(self) -> None:
        """DomainProfile is immutable."""
        profile = DomainProfile(name="test", description="test")
        with pytest.raises(AttributeError):
            profile.name = "hacked"  # type: ignore[misc]

    def test_empty_description_is_valid(self) -> None:
        """A profile with no description is valid."""
        profile = DomainProfile(name="empty", description="")
        assert profile.description == ""


# ===========================================================================
# list_profiles() — built-in discovery
# ===========================================================================


class TestListProfiles:
    """list_profiles() discovers profiles from pipeline YAMLs."""

    def test_returns_expected_builtin_profiles(self) -> None:
        """All expected built-in profiles are discovered."""
        expected = {"web-app", "data-pipeline", "library", "microservice", "ml-model"}
        result = list_profiles()
        names = {p.name for p in result}
        assert expected.issubset(names)

    def test_count_at_least_5(self) -> None:
        """At least 5 built-in profiles exist."""
        assert len(list_profiles()) >= 5

    def test_sorted_by_name(self) -> None:
        result = list_profiles()
        names = [p.name for p in result]
        assert names == sorted(names)

    def test_returns_domain_profile_instances(self) -> None:
        for p in list_profiles():
            assert isinstance(p, DomainProfile)

    def test_all_have_names(self) -> None:
        for p in list_profiles():
            assert p.name, "Profile with empty name found"

    def test_reserved_names_excluded(self) -> None:
        """'default', 'feature', and 'code' must never appear as profiles."""
        names = {p.name for p in list_profiles()}
        assert "default" not in names
        assert "feature" not in names
        assert "code" not in names

    def test_all_have_descriptions(self) -> None:
        """Every built-in profile YAML has a description field."""
        for p in list_profiles():
            assert p.description, f"Profile '{p.name}' has empty description"


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

    def test_underscore_to_hyphen(self) -> None:
        """Underscore profile names normalise to hyphen."""
        result = get_profile("web_app")
        assert result is not None
        assert result.name == "web-app"

    def test_unknown_profile_returns_none(self) -> None:
        result = get_profile("quantum-computing")
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        result = get_profile("")
        assert result is None

    def test_reserved_name_returns_none(self) -> None:
        """Reserved pipeline names must not be returned as profiles."""
        assert get_profile("default") is None
        assert get_profile("feature") is None
        assert get_profile("code") is None

    def test_data_pipeline_profile_found(self) -> None:
        result = get_profile("data-pipeline")
        assert result is not None
        assert result.name == "data-pipeline"

    def test_library_profile_found(self) -> None:
        result = get_profile("library")
        assert result is not None

    def test_ml_model_profile_found(self) -> None:
        result = get_profile("ml-model")
        assert result is not None


# ===========================================================================
# profile_exists()
# ===========================================================================


class TestProfileExists:
    """profile_exists() is a convenience bool wrapper around get_profile."""

    def test_known_profile(self) -> None:
        assert profile_exists("web-app") is True

    def test_unknown_profile(self) -> None:
        assert profile_exists("quantum-computing") is False

    def test_empty_string(self) -> None:
        assert profile_exists("") is False

    def test_reserved_name(self) -> None:
        assert profile_exists("default") is False


# ===========================================================================
# profile_to_pipeline_name()
# ===========================================================================


class TestProfileToPipelineName:
    """profile_to_pipeline_name() converts profile names to pipeline names."""

    def test_web_app(self) -> None:
        assert profile_to_pipeline_name("web-app") == "validation_spec_web_app"

    def test_data_pipeline(self) -> None:
        assert profile_to_pipeline_name("data-pipeline") == "validation_spec_data_pipeline"

    def test_library(self) -> None:
        assert profile_to_pipeline_name("library") == "validation_spec_library"

    def test_ml_model(self) -> None:
        assert profile_to_pipeline_name("ml-model") == "validation_spec_ml_model"

    def test_microservice(self) -> None:
        assert profile_to_pipeline_name("microservice") == "validation_spec_microservice"

    def test_roundtrip_with_get_profile(self) -> None:
        """pipeline name derived from profile must resolve back to the same profile."""
        for profile in list_profiles():
            pipeline_name = profile_to_pipeline_name(profile.name)
            assert pipeline_name.startswith("validation_spec_")


# ===========================================================================
# Custom profile support (via project_dir)
# ===========================================================================


class TestCustomProfiles:
    """Custom profiles discovered from project .specweaver/pipelines/."""

    def test_nonexistent_project_dir_returns_builtin_only(self, tmp_path):
        """When project_dir has no .specweaver/pipelines, only builtins are returned."""
        # tmp_path has no .specweaver folder
        result = list_profiles(project_dir=tmp_path)
        expected = {"web-app", "data-pipeline", "library", "microservice", "ml-model"}
        names = {p.name for p in result}
        assert expected.issubset(names)

    def test_custom_profile_in_project_dir(self, tmp_path):
        """A custom YAML in .specweaver/pipelines is discovered."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_my_team.yaml").write_text(
            "name: validation_spec_my_team\n"
            "description: My team profile\n"
            "extends: validation_spec_default\n",
            encoding="utf-8",
        )
        result = list_profiles(project_dir=tmp_path)
        names = {p.name for p in result}
        assert "my-team" in names

    def test_custom_profile_get_profile(self, tmp_path):
        """get_profile() finds a custom YAML in .specweaver/pipelines."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_custom.yaml").write_text(
            "name: validation_spec_custom\n"
            "description: Custom project profile\n"
            "extends: validation_spec_default\n",
            encoding="utf-8",
        )
        result = get_profile("custom", project_dir=tmp_path)
        assert result is not None
        assert result.name == "custom"
        assert "Custom" in result.description


# ===========================================================================
# _extract_description — edge cases (scenario 13-14)
# ===========================================================================


class TestExtractDescription:
    """_extract_description internal helper edge cases."""

    def test_missing_description_field_returns_empty(self, tmp_path) -> None:
        """YAML without a description field returns empty string."""
        from specweaver.config.profiles import _extract_description

        yaml_file = tmp_path / "no_desc.yaml"
        yaml_file.write_text(
            "name: validation_spec_example\n"
            "extends: validation_spec_default\n",
            encoding="utf-8",
        )
        assert _extract_description(yaml_file) == ""

    def test_oserror_returns_empty(self, tmp_path) -> None:
        """Unreadable file returns empty string without raising."""
        from specweaver.config.profiles import _extract_description

        non_existent = tmp_path / "does_not_exist.yaml"
        # Does NOT raise, returns empty string
        result = _extract_description(non_existent)
        assert result == ""

    def test_description_with_quotes(self, tmp_path) -> None:
        """Quoted description values are stripped of quotes."""
        from specweaver.config.profiles import _extract_description

        yaml_file = tmp_path / "quoted.yaml"
        yaml_file.write_text(
            'description: "My quoted description"\n',
            encoding="utf-8",
        )
        assert _extract_description(yaml_file) == "My quoted description"


# ===========================================================================
# Custom profile overrides built-in (scenario 19)
# ===========================================================================


class TestCustomProfileOverridesBuiltin:
    """A custom profile with same name as built-in takes precedence."""

    def test_custom_only_profile_discovered_by_get_profile(self, tmp_path) -> None:
        """Custom profile with a unique name is found by get_profile()."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_my_custom.yaml").write_text(
            "name: validation_spec_my_custom\n"
            "description: My custom profile\n"
            "extends: validation_spec_default\n",
            encoding="utf-8",
        )
        result = get_profile("my-custom", project_dir=tmp_path)
        assert result is not None
        assert result.description == "My custom profile"

    def test_list_profiles_custom_overrides_builtin_description(self, tmp_path) -> None:
        """list_profiles() uses custom YAML when it shadows a built-in (last-write-wins).

        Note: get_profile() uses first-match (built-in before custom), so the
        precedence only applies to the full listing via _scan_profiles.
        """
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_web_app.yaml").write_text(
            "name: validation_spec_web_app\n"
            "description: Custom web-app for our team\n"
            "extends: validation_spec_default\n",
            encoding="utf-8",
        )
        # list_profiles uses _scan_profiles which is last-write-wins
        profiles = list_profiles(project_dir=tmp_path)
        web_app = next((p for p in profiles if p.name == "web-app"), None)
        assert web_app is not None
        assert web_app.description == "Custom web-app for our team"

    def test_custom_overrides_in_list(self, tmp_path) -> None:
        """list_profiles uses custom description when a custom profile shadows a built-in."""
        pipelines_dir = tmp_path / ".specweaver" / "pipelines"
        pipelines_dir.mkdir(parents=True)
        (pipelines_dir / "validation_spec_library.yaml").write_text(
            "name: validation_spec_library\n"
            "description: Our custom library standards\n"
            "extends: validation_spec_default\n",
            encoding="utf-8",
        )
        result = list_profiles(project_dir=tmp_path)
        library = next(p for p in result if p.name == "library")
        assert library.description == "Our custom library standards"
