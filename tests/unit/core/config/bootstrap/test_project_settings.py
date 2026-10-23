# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One loader reads any section of a project's `specweaver.toml` with that section's parser.

Proves: TECH-076 FR-7

| Bucket | Case |
|---|---|
| Happy | `[autonomy]`, `[implement]` and `[docs]` are read through the one loader |
| Boundary | no file gives each parser's empty value; a file written with a BOM is still read |
| Degradation | a broken file raises the same `SettingsFileError` whichever section is asked for |
| Hostile | not applicable — the parsers' own refusals are proven in their tests |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.autonomy_policy import parse_autonomy
from specweaver.core.config.bootstrap.project_settings import PROJECT_FILE_NAME, load_section
from specweaver.core.config.doc_policy import parse_doc_policy
from specweaver.core.config.implement_policy import parse_implement
from specweaver.core.config.settings_file import SettingsFileError

if TYPE_CHECKING:
    from pathlib import Path

_TEXT = """[autonomy]
mode = "agentic"

[implement]
language = "typescript"

[[docs.rule]]
paths = ["docs/**"]
access = "open"
"""


def test_each_section_is_read_through_the_one_loader(tmp_path: Path) -> None:
    (tmp_path / PROJECT_FILE_NAME).write_text(_TEXT, encoding="utf-8")

    assert load_section(tmp_path, parse_autonomy).mode == "agentic"
    assert load_section(tmp_path, parse_implement).language == "typescript"
    assert [rule.access for rule in load_section(tmp_path, parse_doc_policy).rule] == ["open"]


def test_no_file_gives_each_empty_value(tmp_path: Path) -> None:
    assert load_section(tmp_path, parse_autonomy).mode == "oneshot"
    assert load_section(tmp_path, parse_implement).language is None
    assert load_section(tmp_path, parse_doc_policy).rule == []


def test_a_bom_written_file_is_read(tmp_path: Path) -> None:
    (tmp_path / PROJECT_FILE_NAME).write_text("﻿" + _TEXT, encoding="utf-8")

    assert load_section(tmp_path, parse_autonomy).mode == "agentic"


@pytest.mark.parametrize("parse", [parse_autonomy, parse_implement, parse_doc_policy])
def test_a_broken_file_fails_alike_for_every_section(tmp_path: Path, parse: object) -> None:
    path = tmp_path / PROJECT_FILE_NAME
    path.write_text("[autonomy]\nmode = = 1\n", encoding="utf-8")

    with pytest.raises(SettingsFileError) as caught:
        load_section(tmp_path, parse)

    assert (caught.value.source, caught.value.key, caught.value.line) == (str(path), "(syntax)", 2)
