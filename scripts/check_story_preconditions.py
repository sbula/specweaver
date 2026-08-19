#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Verify a story's prerequisites are green in CODE, not just in documents.

Every precondition gate in the lifecycle skills used to assert only against markdown: is the
design `Status: APPROVED`, is the tracker box `✅`, is the dependency `Committed ✅`. INT-US-21
showed why that is not enough — all three of its prerequisites were marked ✅ and all three were
materially broken:

* `D-INTL-02` — `draft+feature`/`validate+feature` were never registered, so the shipped
  `feature_decomposition.yaml` could not execute a single step.
* `D-INTL-03` — `RunContext.plan` was documented as "(set by runner hook)" with **zero** writes
  anywhere in `src/`.
* `C-INTL-01` — `DecompositionPlan.proposed_dal` is a required enum that cannot be serialized to
  YAML at all.

Every checkbox was true as written and false in fact. This script verifies the *evidence* behind
the checkbox instead of the checkbox.

Usage:
    python scripts/check_story_preconditions.py INT-US-21
    python scripts/check_story_preconditions.py INT-US-21 --fast   # skip running the proof suite

Exit code 1 blocks the story. There is deliberately no override flag: an overridable gate becomes
a habit.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Shared with `check_proof_tier.py`: this gate read `(.{0,600})` of the proof field, so a long
#: declaration was verified less than a short one and it still printed PASS. `TECH-017`.
_spec = importlib.util.spec_from_file_location(
    "_proof_field", Path(__file__).parent / "_proof_field.py"
)
assert _spec is not None and _spec.loader is not None
_proof_field = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_proof_field)
proof_segment = _proof_field.proof_segment
ROADMAP = REPO_ROOT / "docs" / "roadmap" / "master_story_roadmap.md"
CONTRACTS = REPO_ROOT / "docs" / "roadmap" / "stories"
PIPELINES = REPO_ROOT / "src" / "specweaver" / "workflows" / "pipelines"

#: Fields documented as "(set by X)" that legitimately have no writer yet, with the reason.
#: An entry here is a TRACKED exception, not a silent pass — each must name why and who owns it.
DEAD_PROMISE_ALLOWLIST = {
    "workspace_roots": (
        "INT-US-21 design: per-component boundary scoping is an execution concern, deliberately "
        "deferred to the C-FLOW-12 / INT-US-21-SF02 add-on. Consumed (read) by review.py today."
    ),
}


class Report:
    """Collects check results; any failure blocks the story."""

    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.passes: list[str] = []

    def ok(self, msg: str) -> None:
        self.passes.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)


# ---------------------------------------------------------------------------
# Story-specific checks
# ---------------------------------------------------------------------------


def _story_block(story_id: str) -> str | None:
    """Return the master-roadmap section for a story ID.

    Two heading shapes exist. `INT-US-NN` contracts are headed "### US-N: ..." (unpadded, the
    "INT-" prefix dropped). Every other family — e.g. `TECH-NNN` — is headed with its own literal
    ID, e.g. "### TECH-901: ...". Treating every ID as the INT-US shape mangled "TECH-901" into
    the token "TECH" and searched for a literal "US-TECH:" heading, which never matches — a
    failure mode that blocked every TECH-NNN ticket outright (found blocking TECH-001 SF-04
    planning, 2026-08-01).
    """
    if not ROADMAP.exists():
        return None
    text = ROADMAP.read_text(encoding="utf-8", errors="replace")

    if story_id.startswith("INT-US-"):
        num = story_id.replace("INT-US-", "").split("-")[0]
        # Story IDs are zero-padded (INT-US-01) but the roadmap headings are not (### US-1:), so
        # both spellings must be tried. Matching only the padded form reported six delivered
        # stories as "no roadmap section found" — a failure mode that would have blocked every
        # one of them.
        variants = {num, num.lstrip("0") or "0"}
        m = None
        for v in variants:
            m = re.search(rf"^###\s+.*US-{v}:.*$", text, re.M)
            if m:
                break
    else:
        m = re.search(rf"^###\s+.*\b{re.escape(story_id)}:.*$", text, re.M)

    if m:
        nxt = re.search(r"^###\s+", text[m.end() :], re.M)
        return text[m.start() : m.end() + (nxt.start() if nxt else len(text))]

    # Capability-level entry: one list line, no `###` section of its own.
    #
    # A `TECH-NNN` is not a user story — it sits alongside `C-FLOW-02` and `E-INTL-02` (user,
    # 2026-08-12), and those appear as a single line inside a parent's list rather than as a
    # top-level section with `Benefit:` / `Core Required (MVS)` / `Verifiable Proof:` fields.
    # Requiring a `###` heading here is what kept pushing TECH tickets back into user-story shape:
    # writing the entry correctly made this checker report "no roadmap section found", so the
    # checker was quietly enforcing the wrong convention. `TECH-026` owns the contract; this
    # accepts the correct shape so it stops being unwritable.
    line = re.search(rf"^\s*\*\s+`[^`]*`\s+\*\*{re.escape(story_id)}:\*\*.*$", text, re.M)
    return line.group(0) if line else None


def _check_proof_in_roadmap_block(story_id: str, report: Report, *, fast: bool) -> list[Path]:
    """Proof check for families with no separate integration contract (e.g. `TECH-NNN`).

    These declare their `Verifiable Proof` directly inside their own master-roadmap section
    instead of a `topic_08_integration/US-N_integration.md` file — requiring one there is what
    made `check_contract_and_proof` fail every TECH-NNN ticket with a nonsensical path like
    `US-TECH_integration.md`.
    """
    block = _story_block(story_id)
    if block is None:
        report.fail(f"no roadmap section found for {story_id}")
        return []

    segment = proof_segment(block)
    if segment is None:
        report.warn(f"{story_id}: no 'Verifiable Proof' field in its roadmap section")
        return []

    declared = [REPO_ROOT / p for p in re.findall(r"tests/[\w/]+\.py", segment)]
    if not declared:
        report.warn(f"{story_id}: Verifiable Proof field names no test path")
        return []

    missing = [p for p in declared if not p.exists()]
    for p in missing:
        report.fail(f"declared proof file does not exist: {p.relative_to(REPO_ROOT)}")
    present = [p for p in declared if p.exists()]
    for p in present:
        report.ok(f"declared proof present: {p.relative_to(REPO_ROOT)}")

    if present and not fast:
        _run_proof_suite(present, report)
    elif present:
        report.warn("--fast: proof suite NOT executed (existence checked only)")
    return present


def check_contract_and_proof(story_id: str, report: Report, *, fast: bool) -> list[Path]:
    """Checks 1-3, 5: the contract exists, its proof is declared, present, and actually passes.

    Only `INT-US-NN` stories have a separate `topic_08_integration` contract document. Other
    families (e.g. `TECH-NNN`) are delegated to `_check_proof_in_roadmap_block`.
    """
    if not story_id.startswith("INT-US-"):
        return _check_proof_in_roadmap_block(story_id, report, fast=fast)
    return _check_int_us_contract_and_proof(story_id, report, fast=fast)


def _check_int_us_contract_and_proof(story_id: str, report: Report, *, fast: bool) -> list[Path]:
    """The `INT-US-NN` branch of `check_contract_and_proof`, split out to stay under C901."""
    num = story_id.replace("INT-US-", "").split("-")[0]
    contract = CONTRACTS / f"US-{num}.md"
    if not contract.exists():
        report.fail(f"contract document missing: {contract.relative_to(REPO_ROOT)}")
        return []
    report.ok(f"contract document present: {contract.name}")

    text = contract.read_text(encoding="utf-8", errors="replace")
    segment = proof_segment(text)
    if segment is None:
        report.fail(f"{contract.name} has no 'Verifiable Proof' field")
        return []

    declared = [REPO_ROOT / p for p in re.findall(r"tests/[\w/]+\.py", segment)]
    block = _story_block(story_id) or ""
    # NB: the roadmap wraps the marker in backticks — `✅` **INT-US-25:** — so the backtick must be
    # optional here. Omitting it made this check silently report every story as "not delivered",
    # i.e. it could never fail. Verified against master_story_roadmap.md line 562.
    delivered = bool(re.search(rf"(?:✅|\[x\])`?\s*\*\*{re.escape(story_id)}:", block))

    if "Pending" in segment[:60] and not declared:
        if delivered:
            report.fail(
                f"{story_id} is marked DELIVERED in the roadmap but its Verifiable Proof is "
                "'[Pending]' — a delivered contract with no proof"
            )
        else:
            report.ok(f"{story_id} not yet delivered; proof pending (expected)")
        return []

    if not declared:
        report.fail(f"{contract.name} declares a proof but names no test path")
        return []

    missing = [p for p in declared if not p.exists()]
    for p in missing:
        report.fail(f"declared proof file does not exist: {p.relative_to(REPO_ROOT)}")
    present = [p for p in declared if p.exists()]
    for p in present:
        report.ok(f"declared proof present: {p.relative_to(REPO_ROOT)}")

    if present and not fast:
        _run_proof_suite(present, report)
    elif present:
        report.warn("--fast: proof suite NOT executed (existence checked only)")
    return present


def _run_proof_suite(paths: list[Path], report: Report) -> None:
    """Check 5: the proof must PASS and must not SKIP. A skipped proof is not proof."""
    # Critical Rule 1: no raw `subprocess` — route through SubprocessExecutor, which also gives
    # timeout escalation and credential stripping for free.
    from specweaver.sandbox.execution.executor import SubprocessExecutor

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--no-header",
        "-p",
        "no:randomly",
        *[str(p) for p in paths],
    ]
    result = SubprocessExecutor(cwd=REPO_ROOT, timeout_seconds=1800).execute(cmd)

    tail = (result.stdout or "")[-4000:]
    if result.exit_code != 0:
        report.fail(f"declared proof suite FAILED (exit {result.exit_code}). Tail:\n{tail[-800:]}")
        return

    skipped = re.search(r"(\d+) skipped", tail)
    if skipped and int(skipped.group(1)) > 0:
        report.fail(
            f"declared proof suite has {skipped.group(1)} SKIPPED test(s) — a skipped proof is "
            "not proof. Resolve the skip or stop citing it as the contract's evidence."
        )
        return
    passed = re.search(r"(\d+) passed", tail)
    report.ok(
        f"declared proof suite passed ({passed.group(1) if passed else '?'} tests, 0 skipped)"
    )


def check_declared_dependencies(story_id: str, report: Report) -> None:
    """Check 6: every Core-Required (MVS) prerequisite is marked done in the roadmap."""
    block = _story_block(story_id)
    if block is None:
        report.fail(f"no roadmap section found for {story_id}")
        return

    mvs = re.search(r"Core Required \(MVS\):\*\*(.*?)(?:\*\s+\*\*Sub-Story|\Z)", block, re.S)
    if not mvs:
        report.warn(f"{story_id}: no 'Core Required (MVS)' list found — dependencies unverified")
        return

    unmet = []
    for line in mvs.group(1).splitlines():
        m = re.search(r"(`?(?:✅|\[x\]|\[ \]|🔜|🔴)`?)\s*\*\*([A-Z0-9\-]+(?:\s+Core)?)[:\*]", line)
        if not m:
            continue
        mark, dep = m.group(1), m.group(2).strip()
        if dep == story_id:
            continue  # the contract itself
        if "✅" not in mark and "[x]" not in mark:
            unmet.append(f"{dep} ({mark.strip('`')})")
    if unmet:
        report.fail(f"{story_id} has unmet MVS prerequisites: {', '.join(unmet)}")
    else:
        report.ok(f"{story_id}: all Core-Required (MVS) prerequisites marked done")


# ---------------------------------------------------------------------------
# Generic invariants — story-independent, and the ones with real teeth
# ---------------------------------------------------------------------------


def _unresolved_steps(registry: Any, path: Path, data: dict[str, Any]) -> tuple[list[str], int]:
    """Return (unresolved step descriptions, number of steps inspected) for one pipeline file.

    Module-level rather than nested: a closure counts toward its enclosing function's cyclomatic
    complexity, so nesting it pushed check_registry_completeness over the C901 limit instead of
    under it.
    """
    from specweaver.core.flow.engine.models import StepAction, StepTarget

    bad: list[str] = []
    seen = 0
    steps = data.get("steps") or []
    for step in steps:
        action, target = step.get("action"), step.get("target")
        if not action or not target:
            continue
        seen += 1
        try:
            resolved = registry.get(StepAction(action), StepTarget(target))
        except ValueError:
            bad.append(f"{path.name}:{step.get('name')} -> invalid {action}+{target}")
            continue
        if resolved is None:
            bad.append(f"{path.name}:{step.get('name')} -> {action}+{target}")
    return bad, seen


def check_registry_completeness(report: Report) -> None:
    """Every (action, target) a bundled pipeline declares must resolve to a real handler.

    This is the check that would have rejected D-INTL-02's "✅" outright: the shipped
    feature_decomposition.yaml declared draft+feature and validate+feature, and the registry
    mapped neither, so the pipeline could not run a single step.
    """
    try:
        from ruamel.yaml import YAML

        from specweaver.core.flow.handlers.registry import StepHandlerRegistry
    except Exception as exc:  # pragma: no cover - import-time environment problem
        report.fail(f"cannot import the flow engine to verify the registry: {exc}")
        return

    registry = StepHandlerRegistry()
    yaml = YAML(typ="safe")
    unresolved: list[str] = []
    checked = 0
    for path in sorted(PIPELINES.glob("*.yaml")):
        if path.name == "context.yaml":
            continue
        try:
            data = yaml.load(path) or {}
        except Exception as exc:
            report.fail(f"bundled pipeline {path.name} is not loadable: {exc}")
            continue
        bad, seen = _unresolved_steps(registry, path, data)
        unresolved.extend(bad)
        checked += seen

    for u in unresolved:
        report.fail(f"bundled pipeline step has NO registered handler: {u}")
    if not unresolved:
        report.ok(f"registry completeness: all {checked} bundled pipeline steps resolve")


def check_no_dead_promises(report: Report) -> None:
    """A field documented as "(set by X)" must actually be written somewhere in src/.

    This is the check that would have caught RunContext.plan, documented as "(set by runner hook)"
    with zero writers.

    Counting is deliberately CLASS-AWARE. A naive "is `<field>=` used anywhere" test is worthless:
    `review.py` passes `workspace_roots=` to a *different* constructor while only reading
    RunContext's value, and `Generator.generate_code(plan=...)` exists — so a naive check reports
    both fields as written and can never fail for the right reason. Three things count as a
    write: `.<field> =` attribute assignment, `<DeclaringClass>(... <field>=...)`, or
    `model_copy(update={"<field>": ...})`.

    That third form is not a convenience. A frozen model raises on attribute assignment, so
    `model_copy` is the *only* legal way to write one — and this codebase freezes exactly the
    models the engine copies per step (`PlanContext`, `IsolationPolicy`) to keep a step's copy
    from mutating the original. Reading only the first two forms therefore made this scan
    structurally blind to every field on those models: it reported `PlanContext.plan` and
    `.decomposition` as dead promises while `hydration.py` had been writing both since
    INT-US-21 SF-02, and the resulting false failure blocked every story behind a gate with no
    override.
    """
    src_files = list((REPO_ROOT / "src").rglob("*.py"))
    blob = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in src_files)

    found = 0
    for f in src_files:
        owner = "<module>"
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            cls = re.match(r"class\s+(\w+)", line)
            if cls:
                owner = cls.group(1)
            m = re.match(r"\s*(\w+)\s*:\s*[^=]+=.*#.*\(set by ([^)]+)\)", line)
            if not m:
                continue
            name, who = m.group(1), m.group(2)
            found += 1
            attr_writes = len(re.findall(rf"\.{name}\s*=(?!=)", blob))
            # Constructor kwargs, but only inside a call to the DECLARING class.
            ctor_writes = sum(
                1
                for call in re.finditer(rf"{owner}\s*\(", blob)
                if re.search(rf"(?<![\w.]){name}\s*=(?!=)", blob[call.end() : call.end() + 1200])
            )
            # `model_copy(update={"<field>": ...})` — the only legal write on a frozen model.
            copy_writes = len(
                re.findall(
                    rf"model_copy\s*\(\s*update\s*=\s*\{{[^}}]*[\"']{name}[\"']\s*:",
                    blob,
                )
            )
            if attr_writes or ctor_writes or copy_writes:
                continue
            reason = DEAD_PROMISE_ALLOWLIST.get(name)
            msg = f"'{name}' is documented as (set by {who}) but nothing in src/ writes it"
            if reason:
                report.warn(f"{msg} — ALLOWLISTED: {reason}")
            else:
                report.fail(msg)
    report.ok(f"dead-promise scan: {found} documented '(set by ...)' field(s) checked")


# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("story_id", help="e.g. INT-US-21")
    ap.add_argument("--fast", action="store_true", help="skip executing the declared proof suite")
    args = ap.parse_args(argv)

    story = args.story_id.strip().upper()
    report = Report()

    print(f"Story precondition check: {story}\n")
    check_declared_dependencies(story, report)
    check_contract_and_proof(story, report, fast=args.fast)
    check_registry_completeness(report)
    check_no_dead_promises(report)

    for m in report.passes:
        print(f"  PASS  {m}")
    for m in report.warnings:
        print(f"  WARN  {m}")
    for m in report.failures:
        print(f"  FAIL  {m}")

    print(
        f"\n{len(report.passes)} passed, {len(report.warnings)} warning(s), "
        f"{len(report.failures)} failure(s)"
    )
    if report.failures:
        print(
            f"\nBLOCKED: {story} must not start until the failures above are resolved.\n"
            "These are code-level facts, not document state — a green checkbox is not evidence."
        )
        return 1
    print(f"\n{story} preconditions are green in code as well as in documents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
