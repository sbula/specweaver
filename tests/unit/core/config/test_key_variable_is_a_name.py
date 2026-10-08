# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`api_key_env` names a variable; a key pasted there is refused and never shown back.

Proves: C-FLOW-13 FR-4

| Bucket | Case |
|---|---|
| Happy | a variable name is accepted |
| Boundary | a lower-case name with digits and underscores is a name too |
| Degradation | not applicable — an unset variable is proven by the resolver tests |
| Hostile | a pasted key is refused, and the refusal does not contain it |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.llm_settings import SettingsFileError, parse_machine_file

_SERVER = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2
api_key_env = "{value}"
"""


@pytest.mark.parametrize("name", ["GB10_KEY", "gb10_key_2"])
def test_a_variable_name_is_accepted(name: str) -> None:
    server = parse_machine_file(_SERVER.format(value=name), "settings.toml").servers["gb10"]

    assert server.api_key_env == name


def test_a_pasted_key_is_refused_without_showing_it() -> None:
    secret = "sk-proj-AbC123/xyz+Q=="

    with pytest.raises(SettingsFileError) as caught:
        parse_machine_file(_SERVER.format(value=secret), "settings.toml")

    assert "api_key_env" in str(caught.value)
    assert secret not in str(caught.value)
