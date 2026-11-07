# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""check-rot finds a file's plan through its lineage: the file's uuid, its parent in
`specweaver.db`, the plan carrying that parent's uuid.

Proves: TECH-090 FR-14

| Bucket | Case |
|---|---|
| Happy | a file whose lineage parent is a plan's uuid finds that plan |
| Boundary | a file with no lineage event finds no plan |
| Degradation | a file with no `sw-artifact` tag finds no plan, without a database read failing |
| Hostile | a parent uuid no plan carries finds no plan |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.assurance.validation.interfaces.cli_drift import _resolve_plan_by_lineage
from specweaver.core.config.paths import config_db_path
from specweaver.graph.lineage.store.lineage_repository import LineageRepository
from specweaver.interfaces.cli_kit import _core

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_PLAN = "11111111-1111-4111-8111-111111111111"
_FILE = "22222222-2222-4222-8222-222222222222"


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path / "data"))
    _core.get_db()
    plan = tmp_path / "orders_plan.yaml"
    plan.write_text(f"# sw-artifact: {_PLAN}\nname: orders\n", encoding="utf-8")
    target = tmp_path / "orders.py"
    target.write_text(f"# sw-artifact: {_FILE}\nx = 1\n", encoding="utf-8")
    return plan, target


def _event(artifact: str, parent: str | None) -> None:
    LineageRepository(config_db_path()).log_artifact_event(
        artifact, parent, "run", "generated", "m"
    )


def test_a_file_finds_its_plan_through_its_lineage_parent(world: tuple[Path, Path]) -> None:
    plan, target = world
    _event(_FILE, _PLAN)

    assert _resolve_plan_by_lineage(target, [plan], "orders.py") == plan


def test_a_file_with_no_lineage_event_finds_no_plan(world: tuple[Path, Path]) -> None:
    plan, target = world

    assert _resolve_plan_by_lineage(target, [plan], "orders.py") is None


def test_a_file_with_no_tag_finds_no_plan(world: tuple[Path, Path]) -> None:
    plan, target = world
    target.write_text("x = 1\n", encoding="utf-8")
    _event(_FILE, _PLAN)

    assert _resolve_plan_by_lineage(target, [plan], "orders.py") is None


def test_a_parent_no_plan_carries_finds_no_plan(world: tuple[Path, Path]) -> None:
    plan, target = world
    _event(_FILE, "33333333-3333-4333-8333-333333333333")

    assert _resolve_plan_by_lineage(target, [plan], "orders.py") is None
