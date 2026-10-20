# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A project's `[autonomy]` section is read strictly; a broken one stops the command, naming its line.

Proves: C-FLOW-11 FR-6
Proves: C-FLOW-11 NFR-2

| Bucket | Case |
|---|---|
| Happy | `mode` and `agentic_max_dal` are read as written |
| Boundary | no section: `oneshot`, and no ceiling — nothing is assumed |
| Degradation | not valid TOML is refused, naming the file |
| Hostile | an unknown key, mode or DAL, and a turn limit here, are each refused naming the line |
"""

from __future__ import annotations

import pytest

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.autonomy_policy import parse_autonomy
from specweaver.core.config.llm_settings import SettingsFileError


def test_mode_and_ceiling_are_read_as_written() -> None:
    policy = parse_autonomy(
        '[llm]\nprivate_only = false\n\n[autonomy]\nmode = "agentic"\nagentic_max_dal = "DAL_D"\n',
        "specweaver.toml",
    )

    assert (policy.mode, policy.agentic_max_dal) == ("agentic", DALLevel.DAL_D)


def test_no_section_assumes_nothing() -> None:
    policy = parse_autonomy("[llm]\nprivate_only = false\n", "specweaver.toml")

    assert (policy.mode, policy.agentic_max_dal) == ("oneshot", None)


def test_not_toml_is_refused() -> None:
    with pytest.raises(SettingsFileError, match="not valid TOML"):
        parse_autonomy("[autonomy\n", "specweaver.toml")


@pytest.mark.parametrize(
    ("body", "key", "line"),
    [
        ('mode = "free"\n', "autonomy.mode", 3),
        ('agentic_max_dal = "DAL_Z"\n', "autonomy.agentic_max_dal", 3),
        ("max_turns = 10\n", "autonomy.max_turns", 3),
    ],
)
def test_a_wrong_entry_is_refused_naming_its_line(body: str, key: str, line: int) -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_autonomy(f"# project\n[autonomy]\n{body}", "specweaver.toml")

    assert (caught.value.key, caught.value.line) == (key, line)
