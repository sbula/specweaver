# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for specweaver.config.settings — TDD (tests first)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import pytest
from ruamel.yaml import YAML

from specweaver.config.settings import load_settings

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    """Create a .specweaver directory with a config.yaml."""
    sw_dir = tmp_path / ".specweaver"
    sw_dir.mkdir()
    return sw_dir


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    yaml = YAML()
    with open(path, "w") as f:
        yaml.dump(data, f)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


class TestLoadSettings:
    """Test loading settings from YAML config file."""

    def test_load_from_yaml(self, config_dir: Path) -> None:
        """Settings load model name and temperature from config.yaml."""
        _write_yaml(
            config_dir / "config.yaml",
            {
                "llm": {"model": "gemini-2.5-pro", "temperature": 0.3},
            },
        )
        settings = load_settings(config_dir.parent)
        assert settings.llm.model == "gemini-2.5-pro"
        assert settings.llm.temperature == 0.3

    def test_defaults_when_no_config(self, tmp_path: Path) -> None:
        """Settings use defaults when no .specweaver/config.yaml exists."""
        settings = load_settings(tmp_path)
        assert settings.llm.model == "gemini-2.5-flash"
        assert settings.llm.temperature == 0.7
        assert settings.llm.max_output_tokens == 4096

    def test_defaults_when_config_dir_exists_but_no_yaml(self, config_dir: Path) -> None:
        """Settings use defaults when .specweaver/ exists but config.yaml doesn't."""
        settings = load_settings(config_dir.parent)
        assert settings.llm.model == "gemini-2.5-flash"

    def test_partial_config_uses_defaults_for_missing(self, config_dir: Path) -> None:
        """Missing fields fall back to defaults; present fields are used."""
        _write_yaml(
            config_dir / "config.yaml",
            {
                "llm": {"model": "gemini-3.0-turbo"},
                # temperature and max_output_tokens not specified
            },
        )
        settings = load_settings(config_dir.parent)
        assert settings.llm.model == "gemini-3.0-turbo"
        assert settings.llm.temperature == 0.7  # default
        assert settings.llm.max_output_tokens == 4096  # default


class TestSettingsFromEnv:
    """Test that env vars override config file values."""

    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """GEMINI_API_KEY env var is picked up."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
        settings = load_settings(tmp_path)
        assert settings.llm.api_key == "test-key-123"

    def test_api_key_default_is_empty(self, tmp_path: Path) -> None:
        """API key defaults to empty string when not set."""
        # Ensure env var is not set
        os.environ.pop("GEMINI_API_KEY", None)
        settings = load_settings(tmp_path)
        assert settings.llm.api_key == ""


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestSettingsEdgeCases:
    """Edge cases for config loading."""

    def test_malformed_yaml_raises(self, config_dir: Path) -> None:
        """Malformed YAML should raise a clear error, not crash."""
        (config_dir / "config.yaml").write_text("{{{{invalid yaml: [")
        with pytest.raises(ValueError, match=r"config\.yaml"):
            load_settings(config_dir.parent)

    def test_unknown_keys_are_ignored(self, config_dir: Path) -> None:
        """Unknown keys in config.yaml are silently ignored."""
        _write_yaml(
            config_dir / "config.yaml",
            {
                "llm": {"model": "gemini-2.5-pro"},
                "unknown_section": {"foo": "bar"},
                "another_unknown": 42,
            },
        )
        settings = load_settings(config_dir.parent)
        assert settings.llm.model == "gemini-2.5-pro"

    def test_empty_yaml_file(self, config_dir: Path) -> None:
        """Empty config.yaml should use all defaults."""
        (config_dir / "config.yaml").write_text("")
        settings = load_settings(config_dir.parent)
        assert settings.llm.model == "gemini-2.5-flash"

    def test_yaml_with_only_null(self, config_dir: Path) -> None:
        """YAML containing only null/~ is treated as empty."""
        (config_dir / "config.yaml").write_text("~\n")
        settings = load_settings(config_dir.parent)
        assert settings.llm.model == "gemini-2.5-flash"

    def test_invalid_temperature_type(self, config_dir: Path) -> None:
        """Non-numeric temperature should raise a validation error."""
        _write_yaml(
            config_dir / "config.yaml",
            {
                "llm": {"temperature": "hot"},
            },
        )
        with pytest.raises(ValueError):
            load_settings(config_dir.parent)


class TestSettingsModel:
    """Test the SpecWeaverSettings Pydantic model directly."""

    def test_response_format_default(self, tmp_path: Path) -> None:
        """Default response format is 'text'."""
        settings = load_settings(tmp_path)
        assert settings.llm.response_format == "text"

    def test_response_format_json(self, config_dir: Path) -> None:
        """Can set response_format to 'json'."""
        _write_yaml(
            config_dir / "config.yaml",
            {
                "llm": {"response_format": "json"},
            },
        )
        settings = load_settings(config_dir.parent)
        assert settings.llm.response_format == "json"

    def test_invalid_response_format_raises(self, config_dir: Path) -> None:
        """Invalid response_format should raise a validation error."""
        _write_yaml(
            config_dir / "config.yaml",
            {
                "llm": {"response_format": "xml"},
            },
        )
        with pytest.raises(ValueError):
            load_settings(config_dir.parent)


# ---------------------------------------------------------------------------
# Settings — behavioral tests (unexpected input)
# ---------------------------------------------------------------------------


class TestSettingsBehavioral:
    """Behavioral tests: unexpected input."""

    def test_llm_key_is_string_not_dict(self, tmp_path: Path) -> None:
        """Unexpected input: 'llm' value is a string → uses defaults."""
        sw_dir = tmp_path / ".specweaver"
        sw_dir.mkdir()
        (sw_dir / "config.yaml").write_text(
            "llm: just_a_string\n",
            encoding="utf-8",
        )
        settings = load_settings(tmp_path)
        assert settings.llm.model == "gemini-2.5-flash"

    def test_nested_unknown_key_in_llm(self, tmp_path: Path) -> None:
        """Unexpected input: unknown key under llm → ignored by Pydantic."""
        sw_dir = tmp_path / ".specweaver"
        sw_dir.mkdir()
        (sw_dir / "config.yaml").write_text(
            "llm:\n  model: gemini-2.5-pro\n  nonexistent_key: 42\n",
            encoding="utf-8",
        )
        settings = load_settings(tmp_path)
        assert settings.llm.model == "gemini-2.5-pro"

