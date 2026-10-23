# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A sampling value no provider accepts is refused when the file is read, not mid-run.

Proves: C-FLOW-13 FR-4

| Bucket | Case |
|---|---|
| Happy | ordinary values are read |
| Boundary | the ends of each range are read: temperature 0 and 2, top_p 0 and 1, top_k 1 |
| Degradation | not applicable — the file is the only input |
| Hostile | temperature 50, a negative top_p and top_k 0 are refused, naming the key |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings_parse import parse_machine_file
from specweaver.core.config.settings_file import SettingsFileError

_FILE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = {{ model = "m@gb10", {field} = {value} }}
"""


@pytest.mark.parametrize(
    ("field", "value"),
    [("temperature", "0"), ("temperature", "2"), ("top_p", "0"), ("top_p", "1"), ("top_k", "1")],
)
def test_values_in_range_are_read(field: str, value: str) -> None:
    parse_machine_file(_FILE.format(field=field, value=value), "settings.toml")


@pytest.mark.parametrize(
    ("field", "value"), [("temperature", "50"), ("top_p", "-3"), ("top_p", "1.5"), ("top_k", "0")]
)
def test_values_out_of_range_are_refused(field: str, value: str) -> None:
    with pytest.raises(SettingsFileError) as caught:
        parse_machine_file(_FILE.format(field=field, value=value), "settings.toml")

    assert caught.value.key.endswith(field)
