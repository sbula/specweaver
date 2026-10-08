# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An error names the line that sets the key, whatever TOML shape sets it.

Proves: C-FLOW-13 FR-4

| Bucket | Case |
|---|---|
| Happy | a key in its table, and a table header |
| Boundary | a dotted key (`roles.review = ...`) at the top level or inside a table |
| Degradation | a key nobody set names its table, else line 1 |
| Hostile | a line inside a multi-line string that looks like `key = ...` is never named |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import line_of

_TEXT = '''\
schema_version = 1
roles.review = "m@gb10"
notes = """
max_parallel = 99
"""

[servers.gb10]
kind = "openai-compatible"
limits.other = 1
limits.max_parallel = 4
max_parallel = 2
'''


def _line(text: str) -> int:
    return _TEXT.splitlines().index(text) + 1


@pytest.mark.parametrize(
    ("key", "line"),
    [
        ("servers.gb10.kind", 'kind = "openai-compatible"'),
        ("servers.gb10", "[servers.gb10]"),
        ("roles.review", 'roles.review = "m@gb10"'),
        ("servers.gb10.limits.max_parallel", "limits.max_parallel = 4"),
        ("servers.gb10.max_parallel", "max_parallel = 2"),
    ],
)
def test_the_line_that_sets_the_key(key: str, line: str) -> None:
    assert line_of(_TEXT, key) == _line(line)


def test_a_key_nobody_set_names_its_table() -> None:
    assert line_of(_TEXT, "servers.gb10.base_url") == _line("[servers.gb10]")


def test_a_line_inside_a_multiline_string_is_never_named() -> None:
    assert line_of(_TEXT, "max_parallel") == 1
