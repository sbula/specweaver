# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The machine file's `[search]` section names the variable that holds the web-search key.

Proves: E-SENS-02 FR-4

| Bucket | Case |
|---|---|
| Happy | `[search] api_key_env` parses |
| Boundary | no `[search]` section: no search |
| Degradation | `[search]` without `api_key_env` refuses, naming the key |
| Hostile | a key pasted where the variable name goes; a typo'd key; a project file that names one |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import parse_machine_file, parse_project_llm
from specweaver.core.config.settings_file import SettingsFileError


def test_the_search_section_names_its_key_variable() -> None:
    # Proves: E-SENS-02 FR-4
    machine = parse_machine_file('[search]\napi_key_env = "TAVILY_API_KEY"\n', "settings.toml")
    assert machine.search is not None
    assert machine.search.api_key_env == "TAVILY_API_KEY"


def test_no_section_means_no_search() -> None:
    assert parse_machine_file("", "settings.toml").search is None


def test_a_section_without_its_variable_refuses() -> None:
    with pytest.raises(SettingsFileError, match="api_key_env"):
        parse_machine_file("[search]\n", "settings.toml")


def test_a_pasted_key_refuses_without_echoing_it() -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_machine_file('[search]\napi_key_env = "tvly-dev-abc123 xyz"\n', "settings.toml")
    assert "names the environment variable" in str(caught.value)
    assert "tvly-dev-abc123" not in str(caught.value)


def test_a_typo_refuses() -> None:
    with pytest.raises(SettingsFileError, match="api_key_envv"):
        parse_machine_file('[search]\napi_key_envv = "TAVILY_API_KEY"\n', "settings.toml")


def test_a_project_file_cannot_name_a_search_key() -> None:
    with pytest.raises(SettingsFileError):
        parse_project_llm('[llm.search]\napi_key_env = "MY_KEY"\n', "specweaver.toml")
