# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The line of a key path in YAML loaded with line marks.

Proves: TECH-076 FR-3

| Bucket | Case |
|---|---|
| Happy | a nested key answers its own line |
| Boundary | an empty path, and a path whose deeper part is missing, answer the deepest line found |
| Degradation | data without line marks (a plain dict) answers 1 |
| Hostile | a path through a list or a scalar stops at the last mapping |
"""

from __future__ import annotations

from ruamel.yaml import YAML

from specweaver.core.config.yaml_lines import yaml_line

_TEXT = "matrix:\n  DAL_E:\n    overrides:\n      S01:\n        enabled: no\nlist:\n  - a: 1\n"


def _data() -> object:
    return YAML(typ="rt").load(_TEXT)


def test_a_nested_key_answers_its_own_line() -> None:
    assert yaml_line(_data(), ("matrix", "DAL_E", "overrides", "S01", "enabled")) == 5


def test_a_missing_part_answers_the_deepest_line_found() -> None:
    assert yaml_line(_data(), ()) == 1
    assert yaml_line(_data(), ("matrix", "DAL_E", "nope", "x")) == 2


def test_data_without_marks_answers_one() -> None:
    assert yaml_line({"matrix": {"DAL_E": {}}}, ("matrix", "DAL_E")) == 1


def test_a_path_through_a_list_stops_at_the_last_mapping() -> None:
    assert yaml_line(_data(), ("list", "0", "a")) == 6
    assert yaml_line(_data(), ("matrix", "DAL_E", "overrides", "S01", "enabled", "x")) == 5
