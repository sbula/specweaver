# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A broken setting is named to an API client by the setting that stopped the run.

Proves: TECH-076 FR-4
Proves: TECH-077 FR-12

| Bucket | Case |
|---|---|
| Happy | a `[sandbox]`, `[standards]`, `[docs]`, `[autonomy]`, `[implement]`, `[llm]` key and a DAL file key each get their code |
| Boundary | a whole table of the wrong type (`sandbox = 1`) has the bare name and still maps; any key of the machine's `settings.toml` is `LLM_SETTINGS` |
| Degradation | a TOML syntax error in `specweaver.toml` names no section: `SANDBOX_SETTINGS` (TECH-076 SF-02 decision 1); an unknown project gives no settings — `test_build_run.py` |
| Hostile | a key that merely starts with `standards` (`standardsx`) is not `[standards]` |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.settings_file import SettingsFileError
from specweaver.interfaces.api.v1.run_doors import settings_error_code


@pytest.mark.parametrize(
    ("source", "key", "code"),
    [
        ("p/specweaver.toml", "sandbox.execution_mod", "SANDBOX_SETTINGS"),
        ("p/specweaver.toml", "standards.mod", "STANDARDS_SETTINGS"),
        ("p/.specweaver/dal_definitions.yaml", "matrx", "DAL_DEFINITIONS"),
        ("p/specweaver.toml", "standards", "STANDARDS_SETTINGS"),
        ("p/specweaver.toml", "sandbox", "SANDBOX_SETTINGS"),
        ("p/specweaver.toml", "(syntax)", "SANDBOX_SETTINGS"),
        ("p/specweaver.toml", "standardsx.mode", "SANDBOX_SETTINGS"),
        ("p/specweaver.toml", "docs.rule.0.access", "DOC_POLICY"),
        ("p/specweaver.toml", "autonomy.mode", "AUTONOMY_POLICY"),
        ("p/specweaver.toml", "implement.language", "IMPLEMENT_POLICY"),
        ("p/specweaver.toml", "llm.private_only", "LLM_SETTINGS"),
        ("/home/u/.specweaver/settings.toml", "brake.hosted_spend_per_run", "LLM_SETTINGS"),
        ("/home/u/.specweaver/settings.toml", "(syntax)", "LLM_SETTINGS"),
    ],
)
def test_each_setting_has_its_code(source: str, key: str, code: str) -> None:
    assert settings_error_code(SettingsFileError(source, key, 1, "bad")) == code
