# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's `[implement] language` is read strictly; a wrong one stops the command, naming its line.

Proves: D-INTL-08 FR-2

| Bucket | Case |
|---|---|
| Happy | each of the five languages is read as written |
| Boundary | no section: no language — detection decides |
| Degradation | not valid TOML is refused |
| Hostile | an unknown language or key is refused, naming the line |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.implement_policy import parse_implement
from specweaver.core.config.llm_settings import SettingsFileError


@pytest.mark.parametrize("language", ["python", "java", "kotlin", "typescript", "rust"])
def test_each_language_is_read(language: str) -> None:
    policy = parse_implement(f'[implement]\nlanguage = "{language}"\n', "specweaver.toml")

    assert policy.language == language


def test_no_section_names_no_language() -> None:
    assert parse_implement("[docs]\n", "specweaver.toml").language is None


def test_not_toml_is_refused() -> None:
    with pytest.raises(SettingsFileError, match="not valid TOML"):
        parse_implement("[implement\n", "specweaver.toml")


@pytest.mark.parametrize(
    ("body", "key"),
    [('language = "cobol"\n', "implement.language"), ("layout = 1\n", "implement.layout")],
)
def test_a_wrong_entry_is_refused_naming_its_line(body: str, key: str) -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_implement(f"# project\n[implement]\n{body}", "specweaver.toml")

    assert (caught.value.key, caught.value.line) == (key, 3)
