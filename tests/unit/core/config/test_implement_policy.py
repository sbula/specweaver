# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's `[implement] language` and `build_tool` are read strictly; a wrong one stops the command, naming its line.

Proves: D-INTL-08 FR-2
Proves: TECH-079 FR-2

| Bucket | Case |
|---|---|
| Happy | each of the five languages and each build tool is read as written |
| Boundary | no section: no language and no build tool — detection decides; the allowed values are the ones the profile decision knows |
| Degradation | not valid TOML is refused |
| Hostile | an unknown language, build tool or key is refused, naming the line |
"""

from __future__ import annotations

import pytest

from specweaver.commons.project_profile import BUILD_TOOLS, GENERATED_LANGUAGES
from specweaver.core.config.implement_policy import parse_implement
from specweaver.core.config.settings_file import SettingsFileError


@pytest.mark.parametrize("language", ["python", "java", "kotlin", "typescript", "rust"])
def test_each_language_is_read(language: str) -> None:
    policy = parse_implement(f'[implement]\nlanguage = "{language}"\n', "specweaver.toml")

    assert policy.language == language


@pytest.mark.parametrize("tool", ["uv", "maven", "gradle", "cargo", "npm"])
def test_each_build_tool_is_read(tool: str) -> None:
    policy = parse_implement(f'[implement]\nbuild_tool = "{tool}"\n', "specweaver.toml")

    assert policy.build_tool == tool


def test_no_section_names_no_language() -> None:
    policy = parse_implement("[docs]\n", "specweaver.toml")

    assert (policy.language, policy.build_tool) == (None, None)


def test_the_allowed_values_are_the_ones_the_profile_decision_knows() -> None:
    for language in GENERATED_LANGUAGES:
        assert parse_implement(f'[implement]\nlanguage = "{language}"\n', "s").language == language
    for tool in BUILD_TOOLS:
        assert parse_implement(f'[implement]\nbuild_tool = "{tool}"\n', "s").build_tool == tool


def test_not_toml_is_refused() -> None:
    with pytest.raises(SettingsFileError, match="not valid TOML"):
        parse_implement("[implement\n", "specweaver.toml")


@pytest.mark.parametrize(
    ("body", "key"),
    [
        ('language = "cobol"\n', "implement.language"),
        ('build_tool = "ant"\n', "implement.build_tool"),
        ("layout = 1\n", "implement.layout"),
    ],
)
def test_a_wrong_entry_is_refused_naming_its_line(body: str, key: str) -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_implement(f"# project\n[implement]\n{body}", "specweaver.toml")

    assert (caught.value.key, caught.value.line) == (key, 3)
