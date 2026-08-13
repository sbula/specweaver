# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for scripts/check_skill_references.py -- TECH-019 SF-02.

Proves: TECH-019 FR-1, FR-2, FR-3, FR-4, FR-5, NFR-2.

`TECH-008` deleted `docs/architecture/architecture_reference.md` and six live instruction sites
went on ordering the agent to read it, so every design, implementation-plan and pre-commit run
since loaded nothing where it expected architecture. The checker asserts the invariant that would
have caught it on the commit that broke it: *a declared reference must resolve*.

The interesting tests here are the negative ones. A naive "every path-shaped token must resolve"
rule flags 34 distinct references on this repo of which 4 are real -- an 88% false-positive rate,
and a checker that cries wolf is switched off within a day. Rules 4 and 5 (uppercase stand-in
tokens, allowlisted worked examples) exist because rules 1-3 alone produced two measured false
positives on the live tree; `test_uppercase_placeholder_segment_is_ignored` and
`test_allowlisted_example_is_ignored` name both. Do not delete them as redundant.

`scripts/` is not an importable package, so the module is loaded by path (same pattern as
test_check_story_preconditions.py).
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
    return _load("check_skill_references")


def _scan_line(mod: ModuleType, tmp_path: Path, line: str) -> list[tuple[Path, int, str]]:
    """Scan a one-line instruction file rooted at an empty tmp repo."""
    doc = tmp_path / "AGENTS.md"
    doc.write_text(line, encoding="utf-8")
    return mod.scan_files([doc], tmp_path)


# ---------------------------------------------------------------------------
# FR-4 -- a declared reference must resolve
# ---------------------------------------------------------------------------


def test_resolving_reference_passes(mod: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "real.md").write_text("x", encoding="utf-8")

    assert _scan_line(mod, tmp_path, "Read `docs/real.md` first.") == []


def test_dangling_reference_is_reported_with_file_line_and_ref(
    mod: ModuleType, tmp_path: Path
) -> None:
    """NFR-2: the finding must be actionable without a second search."""
    findings = _scan_line(mod, tmp_path, "Read `docs/gone.md` first.")

    assert len(findings) == 1
    path, lineno, ref = findings[0]
    assert path.name == "AGENTS.md"
    assert lineno == 1
    assert ref == "docs/gone.md"


def test_reference_inside_a_fenced_block_is_enforced(mod: ModuleType, tmp_path: Path) -> None:
    """The TECH-019 site at phase-1-architecture.md:13 sat in a fence, not inline backticks.

    A backtick-only scan missed it, which is how one of the six original sites stayed invisible
    to the first survey run for this ticket.
    """
    doc = tmp_path / "AGENTS.md"
    doc.write_text("Read:\n```\ndocs/gone.md\n```\n", encoding="utf-8")

    findings = mod.scan_files([doc], tmp_path)

    assert [f[2] for f in findings] == ["docs/gone.md"]


def test_reference_resolving_only_outside_the_repo_is_reported(
    mod: ModuleType, tmp_path: Path
) -> None:
    """A repo-rooted reference that resolves only by climbing out of the repo is not valid.

    `os.path.exists` alone would call this green: the file really is there. But an instruction
    that reaches outside the repository is unresolvable for anyone who checks the repo out
    somewhere else, which is the failure this whole check exists to prevent.
    """
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    outsider = tmp_path / "outsider.md"
    outsider.write_text("x", encoding="utf-8")

    doc = repo / "AGENTS.md"
    doc.write_text("Read `docs/../../outsider.md` now.", encoding="utf-8")

    findings = mod.scan_files([doc], repo)

    assert [f[2] for f in findings] == ["docs/../../outsider.md"]


def test_unreadable_file_degrades_to_a_finding_not_a_traceback(
    mod: ModuleType, tmp_path: Path
) -> None:
    missing = tmp_path / "vanished.md"  # never created

    findings = mod.scan_files([missing], tmp_path)

    assert len(findings) == 1
    assert "unreadable" in findings[0][2]


# ---------------------------------------------------------------------------
# FR-5 -- things that are not assertions about a path on disk
# ---------------------------------------------------------------------------


def test_bare_basename_is_ignored(mod: ModuleType, tmp_path: Path) -> None:
    """`check_fr_coverage.py` names a real file without asserting where it lives."""
    assert _scan_line(mod, tmp_path, "Run `check_fr_coverage.py` at closure.") == []


def test_shorthand_path_is_ignored(mod: ModuleType, tmp_path: Path) -> None:
    """`flow/models.py` is shorthand -- `flow` is not a top-level entry of the repo."""
    assert _scan_line(mod, tmp_path, "Cross-reference `flow/models.py` here.") == []


@pytest.mark.parametrize(
    "template",
    [
        "docs/roadmap/features/[Topic]/[ID]/[ID]_design.md",
        ".agents/skills/<skill-name>/SKILL.md",
        "docs/roadmap/topics/topic_*.md",
    ],
)
def test_template_placeholders_are_ignored(mod: ModuleType, tmp_path: Path, template: str) -> None:
    assert _scan_line(mod, tmp_path, f"See `{template}` for the shape.") == []


def test_uppercase_placeholder_segment_is_ignored(mod: ModuleType, tmp_path: Path) -> None:
    """Rule 4, measured into existence.

    `US-NN_integration.md` is a template whose placeholder is `NN` -- not one of the `[`/`<`/`*`
    metacharacters rule 3 catches. Rules 1-3 alone reported it as a dangling reference.
    """
    ref = "docs/roadmap/topics/topic_08_integration/US-NN_integration.md"

    assert _scan_line(mod, tmp_path, f"Update `{ref}` too.") == []


def test_allowlisted_example_is_ignored_and_states_a_reason(
    mod: ModuleType, tmp_path: Path
) -> None:
    """Rule 5, measured into existence.

    `tests/unit/test_foo.py` is a stand-in filename in specweaver-dev's TDD walkthrough, repeated
    four times. An allowlist entry is a TRACKED exception, so an empty reason is not acceptable.
    """
    assert mod.EXAMPLE_ALLOWLIST, "the allowlist must not be silently emptied"
    for path, reason in mod.EXAMPLE_ALLOWLIST.items():
        assert reason.strip(), f"allowlisted {path!r} states no reason"

    example = next(iter(mod.EXAMPLE_ALLOWLIST))

    assert _scan_line(mod, tmp_path, f"e.g. `{example}`") == []


# ---------------------------------------------------------------------------
# FR-1 -- the live tree holds the invariant
# ---------------------------------------------------------------------------


def test_live_instruction_tree_has_no_dangling_references(mod: ModuleType) -> None:
    """Proves FR-1. Green because TECH-019 SF-01 took the tree from 10 dangling sites to 0.

    If this goes red, an instruction started pointing at a file that does not exist -- repair the
    reference. Do NOT loosen the rule to make it pass.

    The positive control is load-bearing: a scan scope that resolves to zero files also reports
    zero findings, and the two outcomes are indistinguishable from the assertion alone. That trap
    is not hypothetical -- during SF-01 verification `grep -r` reported a clean `.claude/` tree it
    had never traversed, because Git Bash does not follow the directory junction.
    """
    files = mod.default_scan_scope()

    assert len(files) > 20, f"scan scope collapsed to {len(files)} file(s) -- the check is blind"

    findings = mod.scan_files(files, mod.REPO_ROOT)

    assert findings == [], "\n".join(f"{p}:{n} -> {r}" for p, n, r in findings)


def test_delivered_designs_and_plans_are_outside_the_scan_scope(mod: ModuleType) -> None:
    """Non-goal, pinned. Delivered docs are records of what was true then.

    They legitimately mention `docs/architecture/architecture_reference.md`, which TECH-008
    deleted. Scanning them would demand edits to finished stories -- exactly what
    finished-stories-immutable forbids.
    """
    scoped = mod.default_scan_scope()

    assert not [p for p in scoped if "roadmap" in p.parts and "features" in p.parts]


# ---------------------------------------------------------------------------
# FR-2 / FR-3 -- the SF-01 repairs, guarded against silent regression
# ---------------------------------------------------------------------------

_PRE_COMMIT = REPO_ROOT / ".agents" / "skills" / "specweaver-pre-commit" / "references"
_ARCH_PHASE = _PRE_COMMIT / "phase-1-architecture.md"
_GAP_PHASE = _PRE_COMMIT / "phase-2-test-gap.md"


def test_boundary_violations_are_directed_at_the_live_ledger() -> None:
    """Proves FR-2.

    Before TECH-019, phase 1.8 told the agent to record NEW boundary violations in a file
    TECH-008 had deleted -- worse than a dead read, because findings were written nowhere at all.
    """
    ledger = "docs/architecture/06_lessons_and_future/known_boundary_violations.md"
    assert (REPO_ROOT / ledger).exists(), "the ledger itself must exist"

    text = _ARCH_PHASE.read_text(encoding="utf-8")

    assert ledger in text
    assert "architecture_reference.md" not in text


def test_exactly_one_instruction_states_the_combined_analysis_format() -> None:
    """Proves FR-3.

    Phase 1.9 said the combined analysis MUST go to chat and MUST NOT be an Artifact; phase 2.8
    said the reverse. Same output, same moment, both marked MUST -- so compliance was a coin flip
    whichever the agent picked. 2.8 survived as the actively maintained one; 1.9 now defers to it.
    """
    arch = _ARCH_PHASE.read_text(encoding="utf-8")
    gap = _GAP_PHASE.read_text(encoding="utf-8")
    # The mandate is wrapped across lines and quoted with `> `, so match on collapsed whitespace
    # rather than pinning one particular line break.
    gap_flat = " ".join(gap.replace(">", " ").split())

    assert "FORMAT EXCEPTION" not in arch, "the losing format order came back"
    assert "MUST NOT print the Coverage Matrix" in gap_flat, "the surviving format order is gone"
    assert "IsArtifact" not in gap, "a harness-specific mechanism came back into the instruction"
