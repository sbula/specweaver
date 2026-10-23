# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run root stops on a broken settings file and stays best-effort on anything else.

Proves: TECH-076 FR-4

| Bucket | Case |
|---|---|
| Happy | settings that load set the isolation policy |
| Boundary | not applicable — the policy's own shapes are proven by the isolation tests |
| Degradation | another lookup failure (an unknown project) leaves isolation at its default, no exit |
| Hostile | a `SettingsFileError` exits 1 with the located message |
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
import typer

from specweaver.core.config.settings import SandboxSettings, SpecWeaverSettings
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.interfaces import cli as run_cli

if TYPE_CHECKING:
    from pathlib import Path


def _context(tmp_path: Path) -> RunContext:
    return RunContext(project_path=tmp_path, spec_path=tmp_path / "a_spec.md")


def _loads(monkeypatch: pytest.MonkeyPatch, outcome: object) -> None:
    import specweaver.core.config.bootstrap.settings_loader as loader

    def fake(_db: object, _project: str) -> object:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(loader, "load_settings", fake)


def test_settings_that_load_set_the_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SpecWeaverSettings(sandbox=SandboxSettings(enforce_worktree_isolation=True))
    _loads(monkeypatch, settings)
    context = _context(tmp_path)

    run_cli._apply_isolation_policy(context, MagicMock(), "p")

    assert context.isolation.enforce_isolation is True


def test_another_failure_stays_best_effort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _loads(monkeypatch, ValueError("Project 'p' not found"))
    context = _context(tmp_path)

    run_cli._apply_isolation_policy(context, MagicMock(), "p")

    assert context.isolation.enforce_isolation is False


def test_a_broken_settings_file_exits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _loads(monkeypatch, SettingsFileError("p/specweaver.toml", "sandbox.x", 2, "Extra inputs"))

    with pytest.raises(typer.Exit) as caught:
        run_cli._apply_isolation_policy(_context(tmp_path), MagicMock(), "p")

    assert caught.value.exit_code == 1
