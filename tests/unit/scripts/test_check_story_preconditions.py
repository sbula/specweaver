# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reserved band `TECH-9xx`: these IDs are fixtures and are never minted.

They were `TECH-042`/`043`/`099` until 2026-08-13, which burned the next two real IDs and made the
repo-wide collision grep that `specweaver-ticket` Phase 2 mandates report near-misses a minter had
to reason about every time. A reserved band cannot be confused with a candidate.

Tests for scripts/check_story_preconditions.py's story-ID-shape handling.

TECH-NNN tickets don't have an INT-US-style topic_08 integration contract, and their roadmap
headers read "### TECH-901: <name>" rather than "### US-1: <name>". Before this fix,
`_story_block` mangled "TECH-901" into the token "TECH" (`.replace("INT-US-", "").split("-")[0]`)
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

### \U0001f7e1 TECH-901: Example Technical Debt Ticket
**Benefit:** *Example.*
*   **Core Required (MVS):**
    *   `[ ]` **TECH-901:** [Example](features/topic_07_technical_debt/TECH-901/TECH-901_design.md)
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

    block = mod._story_block("TECH-901")

    assert block is not None
    assert "Example Technical Debt Ticket" in block
    assert "The Validation Engine" not in block  # must not spill into the next section


def test_story_block_unaffected_for_a_multi_segment_id(
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
    mod.check_contract_and_proof("TECH-901", report, fast=True)

    assert not report.failures, report.failures
    assert any("declared proof present" in p for p in report.passes)


def test_tech_ticket_declared_dependencies_use_its_own_section(
    mod: ModuleType, roadmap: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "ROADMAP", roadmap)

    report = mod.Report()
    mod.check_declared_dependencies("TECH-901", report)

    assert not report.failures, report.failures


# ---------------------------------------------------------------------------
# Dead-promise scan
# ---------------------------------------------------------------------------


def _fake_src(tmp_path: Path, body: str) -> Path:
    src = tmp_path / "src" / "pkg"
    src.mkdir(parents=True)
    (src / "models.py").write_text(body, encoding="utf-8")
    return tmp_path


FROZEN_MODEL = '''\
class PlanContext(BaseModel):
    """A frozen model: assignment raises, so the only legal write is model_copy."""

    model_config = ConfigDict(frozen=True)

    plan: str | None = None  # PlanArtifact content (set by hydrate_plan_context)
'''


def test_model_copy_update_counts_as_a_write_on_a_frozen_model(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A frozen model cannot be written by assignment -- model_copy(update=) is the only way.

    Reading only `.field =` and `Class(field=...)` makes the scan structurally blind to every
    field on a frozen model, and the codebase freezes the models the engine copies per step.
    That reported `PlanContext.plan` and `.decomposition` as dead promises while
    `hydration.py` had been writing both since INT-US-21 SF-02 -- a false positive that
    blocked every story behind an unoverridable gate.
    """
    writer = 'ctx.plan_context = ctx.plan_context.model_copy(update={"plan": text})\n'
    monkeypatch.setattr(mod, "REPO_ROOT", _fake_src(tmp_path, FROZEN_MODEL + writer))

    report = mod.Report()
    mod.check_no_dead_promises(report)

    assert not report.failures, report.failures


def test_unwritten_field_still_fails(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The widening must not blunt the check: no writer of any form is still a failure."""
    monkeypatch.setattr(mod, "REPO_ROOT", _fake_src(tmp_path, FROZEN_MODEL))

    report = mod.Report()
    mod.check_no_dead_promises(report)

    assert any("nothing in src/ writes it" in f for f in report.failures), report.failures


def test_model_copy_of_a_different_field_does_not_count(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keyed on the field name, not on model_copy appearing anywhere in the file."""
    decoy = 'ctx.other = ctx.other.model_copy(update={"decomposition": text})\n'
    monkeypatch.setattr(mod, "REPO_ROOT", _fake_src(tmp_path, FROZEN_MODEL + decoy))

    report = mod.Report()
    mod.check_no_dead_promises(report)

    assert any("'plan' is documented" in f for f in report.failures), report.failures


#: A roadmap where TECH tickets are capability-level lines rather than `###` sections — the shape
#: the user mandated (2026-08-12): a TECH ticket sits alongside `C-FLOW-02`, not alongside a user
#: story, so it carries no `Benefit:` / `Core Required (MVS)` / `Verifiable Proof:` fields.
CAPABILITY_ROADMAP_FIXTURE = """\
# Master User Story Roadmap

### \U0001f7e2 US-1: The Validation Engine
*   **Core Required (MVS):**
    *   `✅` **US-1:** placeholder

### \U0001f534 Technical Debt — registered, not yet scheduled

    *   `[ ]` **TECH-901:** [Example](features/topic_07_technical_debt/TECH-901/TECH-901_design.md)
    *   `[ ]` **TECH-902:** [Another](features/topic_07_technical_debt/TECH-902/TECH-902_design.md)
"""


def test_story_block_finds_a_tech_ticket_written_as_a_capability_line(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A TECH ticket with no `###` section of its own must still resolve.

    Before this fallback existed, `_story_block` searched only for a `^### .*<ID>:` heading, so
    writing a TECH entry in the mandated capability shape made every gate report "no roadmap
    section found" and block the ticket. Following the convention produced a red gate while
    breaking it produced green — which is why TECH entries kept being rewritten as user stories.
    """
    path = tmp_path / "roadmap.md"
    path.write_text(CAPABILITY_ROADMAP_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(mod, "ROADMAP", path)

    block = mod._story_block("TECH-901")

    assert block is not None, "a capability-line TECH entry must resolve"
    assert "TECH-901" in block
    assert "TECH-902" not in block, "must return only the line asked for, not its neighbours"


def test_capability_line_lookup_does_not_match_a_different_ticket(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback must not resolve an ID that is absent just because siblings are present.

    Without this, a regex loose enough to find any list line would report success for every ID in
    the family and the "no roadmap section found" guard would stop guarding anything.
    """
    path = tmp_path / "roadmap.md"
    path.write_text(CAPABILITY_ROADMAP_FIXTURE, encoding="utf-8")
    monkeypatch.setattr(mod, "ROADMAP", path)

    assert mod._story_block("TECH-903") is None


def test_the_section_form_still_wins_when_both_shapes_are_present(
    mod: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """During the conversion both shapes coexist; the richer `###` block must take precedence.

    A one-line entry carries no `Verifiable Proof:`, so preferring it over a real section would
    silently drop proof discovery for every ticket not yet converted.
    """
    path = tmp_path / "roadmap.md"
    path.write_text(
        ROADMAP_FIXTURE + "\n### \U0001f534 Technical Debt\n\n"
        "    *   `[ ]` **TECH-901:** [Dup](features/topic_07_technical_debt/TECH-901/x.md)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ROADMAP", path)

    block = mod._story_block("TECH-901")

    assert block is not None
    assert "Verifiable Proof" in block, "the ### section must win over the capability line"
