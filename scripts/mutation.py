#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Run a mutation corpus as one session: lay a baseline, then measure every mutant against it.

`_mutate.py` answers one question and `_mutate_campaign.py` asks an ad-hoc list. Both stay — a
throwaway question mid-investigation is a real need. This is the third entry point and the durable
one: it takes the version-controlled corpus `_corpus.py` validates, and runs it.

## Verdicts come from the exit code, not from reading pytest's prose

Measured 2026-08-15: pytest exits `4` for a path that does not exist and `5` when everything is
deselected, printing no `FAILED` line in either case. Classifying by text therefore read a
**mis-typed scope as a survival** — a finding that says a requirement is unprotected when the truth
is that nothing was measured at all. Exit codes are a documented contract and no escape sequence
can break them, which is more than the text offered: parsing it is exactly what the colour defect
broke.

Output is still read, but only to learn *which* tests died. That list is what the in-scope-killer
rule needs, and no exit code can supply it.

## What this module does NOT do

It assigns no verdicts. `KILL` here means "tests failed", not "the requirement is proven" — that
needs the baseline compared against the campaign's scope and the killers checked for citation,
which is a later sub-feature's job. This produces raw, honest results and judges nothing.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _sibling(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_mutate = _sibling("_mutate")
_corpus = _sibling("_corpus")

_run_rc = _mutate._run_rc

#: What an exit code means for a run. `NOTHING_RAN` is the one that matters: it is the difference
#: between "no test objected" and "no test was asked", which look identical in the output.
_OUTCOMES = {0: "NO_KILL", 1: "KILL", 2: "BROKEN", 3: "BROKEN", 4: "NOTHING_RAN", 5: "NOTHING_RAN"}


def outcome_of(code: int) -> str:
    """Map pytest's exit code to an outcome, defaulting unknown codes to `BROKEN`.

    Unknown defaults to `BROKEN` rather than to `NO_KILL` deliberately: a code this mapping has
    never seen is a result nobody can interpret, and calling it "nothing objected" would let an
    unrecognised failure mode read as a finding about the code under test.
    """
    return _OUTCOMES.get(code, "BROKEN")


@dataclass(frozen=True)
class Baseline:
    """What the tree looked like before any mutant was applied."""

    green: bool
    failures: list[str] = field(default_factory=list)
    code: int = 0


@dataclass(frozen=True)
class MutantRun:
    """One mutant's raw result. No verdict — see the module docstring."""

    derived_id: str
    outcome: str
    killers: list[str] = field(default_factory=list)
    detail: str = ""
    leaked: list[str] = field(default_factory=list)
    drift: str = "OK"


@dataclass(frozen=True)
class Verdict:
    """What a mutant's run means for the requirement it was aimed at."""

    derived_id: str
    verdict: str
    reason: str = ""
    drift: str = "OK"


def _files_of(node_ids: list[str]) -> set[str]:
    """The files a list of node ids belongs to. Node ids are `path::test`."""
    return {node.split("::", 1)[0] for node in node_ids}


def verdict_of(
    run: MutantRun,
    *,
    scope: list[str],
    baseline_failures: list[str] | None = None,
    confirmed: bool = False,
) -> Verdict:
    """Seven ordered rules, first match wins. The order is the design, not an implementation detail.

    The distinction this whole sub-feature exists for: `KILL` means *tests failed*; `PASS` means
    *this requirement is protected*. A bystander test dying satisfies the first and not the second,
    and treating them as one is how a campaign certifies a requirement nothing covers.

    `drift` rides through rather than deciding anything. "The code moved" and "the requirement is
    unprotected" need different responses, and a result that can only say one of them makes the
    other invisible.
    """
    scoped = set(scope)

    def out(verdict: str, why: str = "") -> Verdict:
        return Verdict(run.derived_id, verdict, why, run.drift)

    # 1. A baseline failure inside this scope makes everything else unreadable.
    if _files_of(list(baseline_failures or [])) & scoped:
        return out("INDETERMINATE", "a test in this scope was already failing before the mutant")
    # 2. Nothing collected is not a survival — it is a scope that measured nothing.
    if run.outcome == "NOTHING_RAN":
        return out("FAIL", "no tests were collected for this scope")
    # 3. Pytest itself broke; there is nothing here to judge.
    if run.outcome == "BROKEN":
        return out("BROKEN", run.detail[:200])
    # 4. Nothing objected.
    if run.outcome == "NO_KILL":
        return out("FAIL", "no test noticed the behaviour disappearing")
    # 5. Something objected, but nothing the campaign named.
    if not (_files_of(run.killers) & scoped):
        return out("FAIL", "killed only by tests outside this campaign's scope")
    # 6/7. An in-scope kill counts only once it reproduces without the mutant.
    if not confirmed:
        return out("FAIL", "flaky: the killer fails without the mutant too")
    return out("PASS")


def campaign_verdict(verdicts: list[Verdict], *, declared: int) -> str:
    """`FR-8` — accounting first, then the worst verdict present.

    Accounting comes first because a campaign that lost a result cannot be scored on the results it
    kept: the missing one is exactly where a crash or a silent skip would hide.
    """
    if len(verdicts) != declared or not verdicts:
        return "FAILED"
    kinds = {v.verdict for v in verdicts}
    if "FAIL" in kinds or "BROKEN" in kinds:
        return "FAILED"
    if kinds - {"PASS"}:
        return "PARTIAL"
    return "PASSED"


def snapshot_cleanliness(sandbox: Path) -> set[str]:
    """What `git status --porcelain` says about the sandbox **immediately after it was built**.

    Not an empty set, and that is the point. `_build_sandbox` copies untracked files in on purpose
    so the run measures the tree you actually have, which means a freshly built sandbox is already
    "dirty". Comparing later checks against empty would fire on every mutant and the signal would
    be discarded within a day.
    """
    out, _code = _run_rc(["git", "status", "--porcelain"], sandbox)
    return {line for line in out.splitlines() if line.strip()}


def leaked_since(sandbox: Path, baseline: set[str]) -> list[str]:
    """Entries a mutant added that the build did not leave.

    Additions only. A file the build left and a test consumed is not a leak — it is a test cleaning
    up after itself, which is the behaviour we want rather than one to report.
    """
    return sorted(snapshot_cleanliness(sandbox) - baseline)


def run_baseline(sandbox: Path, *, tests: str = "tests") -> Baseline:
    """Run the suite once so every later result can be read against it.

    A failing baseline does not stop anything — it is context, not a gate. But a baseline that
    collected *nothing* is not green either: it would certify a tree it never ran.
    """
    env = _mutate.sandbox_env(sandbox)
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider", tests]
    out, code = _run_rc(cmd, sandbox, env)
    return Baseline(green=code == 0, failures=_mutate.killers(out), code=code)


def run_corpus(
    corpus: Any, *, baseline: Baseline | None = None, sandbox: Path | None = None
) -> list[MutantRun]:
    """Run every mutant in a validated corpus, one sandbox reused across all of them.

    `baseline` is accepted and carried rather than used: attributing a baseline failure to a scope
    is a later sub-feature's decision, and taking it here would put a verdict in a module that
    promises not to make one.
    """
    own_sandbox = sandbox is None
    if own_sandbox:
        sandbox = Path(__import__("tempfile").mkdtemp(prefix="sw-session-"))
        sandbox.rmdir()
        _mutate._build_sandbox(sandbox)

    assert sandbox is not None
    clean = snapshot_cleanliness(sandbox)
    results: list[MutantRun] = []
    try:
        for campaign in corpus.campaigns:
            if campaign.retired:
                continue
            target = " ".join(campaign.scope)
            for mutant in campaign.mutants:
                drift = _corpus.drift_of(mutant, REPO_ROOT)
                run = _run_mutant(sandbox, mutant, target, drift=drift)
                leaked = leaked_since(sandbox, clean)
                if leaked:
                    # Clean and carry on. Aborting would turn one leaky test into a night with no
                    # data, and would fail the accounting rule for a reason the corpus did not cause.
                    _mutate._run(["git", "clean", "-fdq"], sandbox)
                    run = replace(run, leaked=leaked)
                results.append(run)
    finally:
        if own_sandbox:
            _mutate._run(["git", "worktree", "remove", "--force", str(sandbox)], REPO_ROOT)
    return results


def _run_mutant(sandbox: Path, mutant: Any, target: str, *, drift: str = "OK") -> MutantRun:
    """Apply one mutant and report what happened, never why it matters.

    An anchor that will not apply is `STALE`, not `BROKEN`. `apply_mutation` raises `ValueError`
    for exactly one reason — the text it was told to replace is not there any more — and that is
    the code having moved, which is the finding `STALE` exists to carry. `BROKEN` keeps its own
    meaning: the runner could not run. The two need different responses and one word cannot say
    both.
    """
    try:
        raw = _mutate.run_one(
            sandbox, file=mutant.file, old=mutant.old, new=mutant.new, tests=target
        )
    except ValueError as exc:
        return MutantRun(mutant.derived_id, "STALE", detail=str(exc), drift=drift)
    except RuntimeError as exc:
        return MutantRun(mutant.derived_id, "BROKEN", detail=str(exc), drift=drift)

    code = int(raw.get("code", 1 if raw["killers"] else 0))
    return MutantRun(
        derived_id=mutant.derived_id,
        outcome=outcome_of(code),
        killers=list(raw["killers"]),
        detail=str(raw.get("detail", "")),
        drift=drift,
    )
