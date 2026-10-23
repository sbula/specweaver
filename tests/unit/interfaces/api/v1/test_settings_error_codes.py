# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A broken setting is named to an API client by the setting that stopped the run.

Proves: TECH-076 FR-4

| Bucket | Case |
|---|---|
| Happy | a `[sandbox]` key, a `[standards]` key, a DAL file key each get their code |
| Boundary | a whole table of the wrong type (`sandbox = 1`) has the bare name and still maps |
| Degradation | a TOML syntax error names no section: `SANDBOX_SETTINGS` (decision 1 of the SF-02 plan); another lookup failure gives no settings and no refusal |
| Hostile | a key that merely starts with `standards` (`standardsx`) is not `[standards]` |
"""

from __future__ import annotations

import pytest

from specweaver.core.config.settings_file import SettingsFileError
from specweaver.interfaces.api.v1.run_settings import _settings_code


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
    ],
)
def test_each_setting_has_its_code(source: str, key: str, code: str) -> None:
    assert _settings_code(SettingsFileError(source, key, 1, "bad")) == code


async def test_another_lookup_failure_stays_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    """Design decision 5: only a broken settings file refuses; an unknown project does not."""
    from specweaver.interfaces.api.v1 import run_settings

    async def unknown(_db: object, _project: str) -> object:
        raise ValueError("Project 'p' not found")

    monkeypatch.setattr(run_settings, "load_settings_async", unknown)

    assert await run_settings.isolation_settings(object(), "p") is None
