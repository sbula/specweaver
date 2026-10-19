# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Both settings files say which schema they follow, and only a known one is read.

Proves: C-FLOW-13 FR-4, NFR-5

| Bucket | Case |
|---|---|
| Happy | no `schema_version`, or `1`, is read |
| Boundary | a newer schema is refused, asking for an upgrade |
| Degradation | not applicable — a missing version means the current one |
| Hostile | `"2"`, `0` and `true` are refused, naming the line |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import (
    SettingsFileError,
    parse_machine_file,
    parse_project_llm,
)


def _machine(version: str) -> str:
    return f"schema_version = {version}\n"


def _project(version: str) -> str:
    return f"[llm]\nschema_version = {version}\n"


@pytest.mark.parametrize(
    "parse",
    [lambda v: parse_machine_file(_machine(v), "m"), lambda v: parse_project_llm(_project(v), "p")],
)
def test_the_current_version_is_read(parse) -> None:
    parse("1")


@pytest.mark.parametrize("version", ['"2"', "0", "true", "1.0"])
@pytest.mark.parametrize(
    ("parse", "text"),
    [(parse_machine_file, _machine), (parse_project_llm, _project)],
)
def test_a_wrong_version_is_refused(parse, text, version: str) -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse(text(version), "settings")

    assert caught.value.key.endswith("schema_version")
    assert caught.value.line == text(version).splitlines().index(f"schema_version = {version}") + 1


@pytest.mark.parametrize(
    ("parse", "text"),
    [(parse_machine_file, _machine), (parse_project_llm, _project)],
)
def test_a_newer_schema_asks_for_an_upgrade(parse, text) -> None:
    with pytest.raises(SettingsFileError, match="upgrade SpecWeaver"):
        parse(text("2"), "settings")
