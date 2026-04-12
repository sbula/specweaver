# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for _resolve_pipeline_name (cli/validation.py).

Tests the pipeline-selection logic in full isolation using monkeypatching.
Covers all precedence rules without any real DB or YAML access.

Precedence (highest to lowest):
1. --pipeline flag — always wins
2. --level feature — uses feature pipeline, ignores profile
3. Active project domain profile — auto-selects profile pipeline
4. --level component / --level code — default YAML
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import typer

from specweaver.interfaces.cli.validation import _resolve_pipeline_name

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db(profile_name: str | None = None) -> MagicMock:
    """Create a mock DB that returns the given profile name."""
    db = MagicMock()
    db.get_domain_profile.return_value = profile_name
    return db


# ===========================================================================
# Precedence rule 1: --pipeline flag always wins
# ===========================================================================


class TestExplicitPipelineFlag:
    """--pipeline always takes priority over everything else."""

    def test_explicit_pipeline_beats_level(self) -> None:
        """--pipeline overrides --level component."""
        result = _resolve_pipeline_name(
            level="component",
            pipeline="my_custom_pipeline",
        )
        assert result == "my_custom_pipeline"

    def test_explicit_pipeline_beats_feature_level(self) -> None:
        """--pipeline overrides --level feature."""
        result = _resolve_pipeline_name(
            level="feature",
            pipeline="my_custom_pipeline",
        )
        assert result == "my_custom_pipeline"

    def test_explicit_pipeline_beats_active_profile(self) -> None:
        """--pipeline overrides active domain profile."""
        with patch(
            "specweaver.interfaces.cli.validation._core.get_db",
            return_value=_make_db("web-app"),
        ):
            result = _resolve_pipeline_name(
                level="component",
                pipeline="explicit_pipeline",
                active_project="myapp",
            )
        assert result == "explicit_pipeline"

    def test_explicit_empty_string_pipeline_ignored(self) -> None:
        """Empty string pipeline is treated as None → level routing applies."""
        result = _resolve_pipeline_name(level="feature", pipeline="")
        assert result == "validation_spec_feature"


# ===========================================================================
# Precedence rule 2: --level feature
# ===========================================================================


class TestFeatureLevel:
    """--level feature always uses feature pipeline, ignores active profile."""

    def test_feature_level_returns_feature_pipeline(self) -> None:
        result = _resolve_pipeline_name(level="feature", pipeline=None)
        assert result == "validation_spec_feature"

    def test_feature_level_ignores_active_profile(self) -> None:
        """Even if there is an active profile, feature level ignores it."""
        with patch(
            "specweaver.interfaces.cli.validation._core.get_db",
            return_value=_make_db("web-app"),
        ):
            result = _resolve_pipeline_name(
                level="feature",
                pipeline=None,
                active_project="myapp",
            )
        assert result == "validation_spec_feature"


# ===========================================================================
# Precedence rule 3: Active project domain profile
# ===========================================================================


class TestActiveProfileRouting:
    """Profile sets the pipeline when --level component is used."""

    def test_component_with_profile_uses_profile_pipeline(self) -> None:
        """Active profile for a project auto-selects profile YAML."""
        db = _make_db("web-app")
        with patch("specweaver.interfaces.cli.validation._core.get_db", return_value=db):
            result = _resolve_pipeline_name(
                level="component",
                pipeline=None,
                active_project="myapp",
            )
        assert result == "validation_spec_web_app"

    def test_component_with_library_profile(self) -> None:
        db = _make_db("library")
        with patch("specweaver.interfaces.cli.validation._core.get_db", return_value=db):
            result = _resolve_pipeline_name(
                level="component",
                pipeline=None,
                active_project="myapp",
            )
        assert result == "validation_spec_library"

    def test_component_with_data_pipeline_profile(self) -> None:
        db = _make_db("data-pipeline")
        with patch("specweaver.interfaces.cli.validation._core.get_db", return_value=db):
            result = _resolve_pipeline_name(
                level="component",
                pipeline=None,
                active_project="myapp",
            )
        assert result == "validation_spec_data_pipeline"


# ===========================================================================
# Precedence rule 4: Default level fallback
# ===========================================================================


class TestDefaultLevelFallback:
    """When no profile is active, level determines the pipeline."""

    def test_component_no_project_returns_default(self) -> None:
        """--level component with no active project uses spec_default."""
        result = _resolve_pipeline_name(
            level="component",
            pipeline=None,
            active_project=None,
        )
        assert result == "validation_spec_default"

    def test_component_no_profile_returns_default(self) -> None:
        """Project with no profile set falls back to spec_default."""
        db = _make_db(None)  # no profile set
        with patch("specweaver.interfaces.cli.validation._core.get_db", return_value=db):
            result = _resolve_pipeline_name(
                level="component",
                pipeline=None,
                active_project="myapp",
            )
        assert result == "validation_spec_default"

    def test_code_level_returns_code_default(self) -> None:
        result = _resolve_pipeline_name(level="code", pipeline=None)
        assert result == "validation_code_default"

    def test_code_level_ignores_active_profile(self) -> None:
        """code level routes to code pipeline regardless of profile."""
        db = _make_db("web-app")
        with patch("specweaver.interfaces.cli.validation._core.get_db", return_value=db):
            result = _resolve_pipeline_name(
                level="code",
                pipeline=None,
                active_project="myapp",
            )
        assert result == "validation_code_default"


# ===========================================================================
# Error path: Unknown level
# ===========================================================================


class TestUnknownLevel:
    """Unknown --level value exits with code 1."""

    def test_unknown_level_raises_exit(self) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            _resolve_pipeline_name(level="invalid-level", pipeline=None)
        assert exc_info.value.exit_code == 1

    def test_unknown_level_empty_string(self) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            _resolve_pipeline_name(level="", pipeline=None)
        assert exc_info.value.exit_code == 1
