# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation stops when it cannot apply the target's DAL rules; it never judges without them.

Proves: TECH-076 FR-4, TECH-076 NFR-1

| Bucket | Case |
|---|---|
| Happy | the tier's override is layered over the settings |
| Boundary | a target whose tier has no entry keeps the project's settings |
| Degradation | the layering failing (forced) raises, naming the tier; the spec step is an ERROR, not PASSED |
| Hostile | not applicable — the matrix is validated on load (`test_project_settings_strict.py`) |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.settings import (
    DALImpactMatrix,
    RuleOverride,
    SpecWeaverSettings,
    ValidationSettings,
)
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers import validation
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path


def _settings() -> SpecWeaverSettings:
    tier = ValidationSettings(overrides={"S01": RuleOverride(rule_id="S01", enabled=False)})
    return SpecWeaverSettings(dal_matrix=DALImpactMatrix(matrix={DALLevel.DAL_A: tier}))


def _context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dal: DALLevel) -> RunContext:
    monkeypatch.setattr(validation, "target_dal", lambda _ctx, _path: dal)
    spec = tmp_path / "a_spec.md"
    spec.write_text("# A\n## 1. Purpose\nDoes A.\n", encoding="utf-8")
    return RunContext(project_path=tmp_path, spec_path=spec, settings=_settings())


async def test_the_tier_is_layered_over_the_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, monkeypatch, DALLevel.DAL_A)

    merged = await validation._resolve_merged_settings(context, context.spec_path)

    assert merged.validation.is_enabled("S01") is False


async def test_a_tier_without_an_entry_keeps_the_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, monkeypatch, DALLevel.DAL_E)

    merged = await validation._resolve_merged_settings(context, context.spec_path)

    assert merged is context.settings


def _merge_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_data: object) -> object:
        raise ValueError("merged settings are invalid")

    monkeypatch.setattr(SpecWeaverSettings, "model_validate", staticmethod(broken))


async def test_a_failed_layering_raises_naming_the_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, monkeypatch, DALLevel.DAL_A)
    _merge_fails(monkeypatch)

    with pytest.raises(ValueError, match="DAL_A"):
        await validation._resolve_merged_settings(context, context.spec_path)


async def test_the_spec_step_is_an_error_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context(tmp_path, monkeypatch, DALLevel.DAL_A)
    _merge_fails(monkeypatch)
    step = PipelineStep(name="validate_spec", action=StepAction.VALIDATE, target=StepTarget.SPEC)

    result = await validation.ValidateSpecHandler().execute(step, context)

    assert result.status == StepStatus.ERROR
    assert "DAL_A" in result.error_message
