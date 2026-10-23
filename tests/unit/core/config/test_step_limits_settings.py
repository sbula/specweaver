# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`[step_limits]` lives in the machine file, with no value in code, and is checked when read.

Proves: B-FLOW-07 FR-8, B-FLOW-07 NFR-2

| Bucket | Case |
|---|---|
| Happy | `percentile = 90, min_steps = 10` is read |
| Boundary | `percentile` 1 and 100 are read; 0 and 101 are refused |
| Degradation | a missing section means no step limits (`None`) |
| Hostile | a project file that sets step limits is refused; `min_steps = 0` is refused |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import parse_machine_file, parse_project_llm
from specweaver.core.config.settings_file import SettingsFileError


def _machine(body: str) -> str:
    return f"[step_limits]\n{body}\n"


@pytest.mark.parametrize("percentile", [1, 90, 100])
def test_a_percentile_in_range_is_read(percentile: int) -> None:
    limits = parse_machine_file(
        _machine(f"percentile = {percentile}\nmin_steps = 10"), "settings.toml"
    ).step_limits

    assert limits is not None
    assert (limits.percentile, limits.min_steps) == (percentile, 10)


@pytest.mark.parametrize(
    ("body", "key"),
    [
        ("percentile = 0\nmin_steps = 10", "percentile"),
        ("percentile = 101\nmin_steps = 10", "percentile"),
        ("percentile = 90\nmin_steps = 0", "min_steps"),
        ("percentile = 90", "min_steps"),
    ],
)
def test_a_value_out_of_range_or_missing_is_refused(body: str, key: str) -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_machine_file(_machine(body), "settings.toml")

    assert caught.value.key == f"step_limits.{key}"


def test_no_section_means_no_step_limits() -> None:
    assert parse_machine_file("", "settings.toml").step_limits is None


def test_a_project_file_cannot_set_step_limits() -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_project_llm("[llm.step_limits]\npercentile = 50\nmin_steps = 1\n", "specweaver.toml")

    assert "step_limits" in caught.value.key
