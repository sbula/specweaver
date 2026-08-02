# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for scripts/check_story_preconditions.py's story-ID-shape handling.

TECH-NNN tickets don't have an INT-US-style topic_08 integration contract, and their roadmap
headers read "### TECH-042: <name>" rather than "### US-1: <name>". Before this fix,
`_story_block` mangled "TECH-042" into the token "TECH" (`.replace("INT-US-", "").split("-")[0]`)
and searched for a literal "US-TECH:" heading, which never matches -- every TECH-NNN precondition
check failed with "no roadmap section found" and "contract document missing", even though the
real roadmap section and Verifiable Proof were present all along. Discovered blocking TECH-001
SF-04 planning on 2026-08-01.

`scripts/` is not an importable package, so the module is loaded by path (same pattern as
test_check_coupling.py).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]

ROADMAP_FIXTURE = """\
# Master User Story Roadmap

### \U0001f7e2 US-1: The Validation Engine
*   **Core Required (MVS):**
    *   `✅` **US-1:** placeholder

### \U0001f7e1 TECH-042: Example Technical Debt Ticket
**Benefit:** *Example.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-042:** [Example](features/topic_07_technical_debt/TECH-042/TECH-042_design.md)
*   **Verifiable Proof:**
    *   `tests/unit/scripts/test_check_story_preconditions.py`
"""


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mod() -> ModuleType:
    return _load("check_story_preconditions")


@pytest.fixture
def roadmap(tmp_path: Path, mod: ModuleType) -> Path:
    path = tmp_path / "roadmap.md"
    path.write_text(ROADMAP_FIXTURE, encoding="utf-8")
    return path


def test_story_block_finds_tech_ticket_by_its_own_literal_id(
    mod: ModuleType, roadmap: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "ROADMAP", roadmap)

    block = mod._story_block("TECH-042")

    assert block is not None
    assert "Example Technical Debt Ticket" in block
    assert "The Validation Engine" not in block  # must not spill into the next section


def test_story_block_unaffected_for_int_us_ticket(
    mod: ModuleType, roadmap: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "ROADMAP", roadmap)

    block = mod._story_block("US-1")

    assert block is not None
    assert "The Validation Engine" in block


def test_story_block_returns_none_for_unknown_id(
    mod: ModuleType, roadmap: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "ROADMAP", roadmap)

    assert mod._story_block("TECH-999") is None


def test_tech_ticket_proof_read_from_its_own_roadmap_section(
    mod: ModuleType, roadmap: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "ROADMAP", roadmap)
    # No topic_08_integration directory at all -- a TECH ticket must not require one.
    monkeypatch.setattr(mod, "CONTRACTS", tmp_path / "does_not_exist")

    report = mod.Report()
    mod.check_contract_and_proof("TECH-042", report, fast=True)

    assert not report.failures, report.failures
    assert any("declared proof present" in p for p in report.passes)


def test_tech_ticket_declared_dependencies_use_its_own_section(
    mod: ModuleType, roadmap: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "ROADMAP", roadmap)

    report = mod.Report()
    mod.check_declared_dependencies("TECH-042", report)

    assert not report.failures, report.failures
