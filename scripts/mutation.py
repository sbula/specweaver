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
import json
import sys
import time
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
_report = _sibling("_mutation_report")
_timer = _sibling("_mutation_timer")
_gate = _sibling("_mutation_gate")
_pool = _sibling("_mutation_pool")

UNIT_NAME = _timer.UNIT_NAME
timer_units = _timer.timer_units
install_timer = _timer.install_timer

_run_rc, run_pytest = _mutate._run_rc, _mutate.run_pytest

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
    killer_records: list[dict[str, Any]] = field(default_factory=list)
    detail: str = ""
    leaked: list[str] = field(default_factory=list)
    drift: str = "OK"
    confirmed: bool = False


#: What a mutant taught us about our own code. Named for the conclusion, not for the mutant's
#: fate: `KILLED`/`SURVIVED` invert against test semantics, so the good line reads as the bad one.
# The verdict vocabulary lives beside this module. Re-exported at module level, not imported
# where used: the session tests patch these names on `mutation` itself.
_verdict_mod = _sibling("_mutation_verdict")
PROTECTED = _verdict_mod.PROTECTED
UNPROTECTED = _verdict_mod.UNPROTECTED
UNMEASURED = _verdict_mod.UNMEASURED
Verdict = _verdict_mod.Verdict
is_finding = _verdict_mod.is_finding
verdict_of = _verdict_mod.verdict_of
campaign_verdict = _verdict_mod.campaign_verdict
scope_killers = _verdict_mod.scope_killers


#: The prefix every session sandbox carries. Used to recognise our own orphans and, just as
#: importantly, to leave everyone else's worktrees alone.
_SANDBOX_PREFIX = "sw-session-"

#: How old a session sandbox must be before it counts as abandoned. Longer than any plausible run
#: (NFR-1 puts a full corpus near 100 minutes) and far shorter than a day, so last night's leak is
#: collected tonight.
#:
#: Age, not just the prefix. The first version of this pruning matched on the prefix alone and so
#: deleted sandboxes that concurrent xdist workers were mid-run in — adding orphan cleanup broke
#: parallel runs that had been working. A live session is minutes old; a leak outlives the night.
_ORPHAN_AFTER_SECONDS = 2 * 60 * 60


def prune_orphaned_sandboxes() -> list[str]:
    """Remove session worktrees an earlier run left behind, and report what went.

    `run_corpus` removes its sandbox in a `finally`, which survives a crash but not a kill — and a
    nightly timer meets kills: a reboot, an OOM, a closed lid. The run that has to clean up is
    therefore the NEXT one, because the one that died cannot.

    Matched by prefix so a human's own worktree is never touched: this cleans up after itself, not
    after everybody.
    """
    listing = _mutate._run(["git", "worktree", "list"], REPO_ROOT)
    removed = []
    for line in listing.splitlines():
        path = line.split()[0] if line.split() else ""
        if _SANDBOX_PREFIX not in Path(path).name:
            continue
        try:
            age = time.time() - Path(path).stat().st_mtime
        except OSError:
            age = _ORPHAN_AFTER_SECONDS + 1  # gone from disk but still registered: prune it
        if age > _ORPHAN_AFTER_SECONDS:
            _mutate._run(["git", "worktree", "unlock", path], REPO_ROOT)
            _mutate._run(["git", "worktree", "remove", "--force", path], REPO_ROOT)
            removed.append(path)
    if removed:
        _mutate._run(["git", "worktree", "prune"], REPO_ROOT)
    return removed


def build_sandbox() -> Path:
    """A detached worktree carrying the tree under test. The caller removes it."""
    import tempfile

    prune_orphaned_sandboxes()
    sandbox = Path(tempfile.mkdtemp(prefix=_SANDBOX_PREFIX))
    sandbox.rmdir()
    _mutate._build_sandbox(sandbox)
    return sandbox


def remove_sandbox(sandbox: Path) -> None:
    _mutate._run(["git", "worktree", "remove", "--force", str(sandbox)], REPO_ROOT)


def confirm_kill(sandbox: Path, killer_ids: list[str]) -> bool:
    """Do these tests pass when the mutant is **not** applied?

    `FR-6`. A killer that fails either way protects nothing — it was already broken and the mutant
    merely arrived to take the blame. Left unchecked, a permanently red test in scope would certify
    every requirement it touches forever, and the corpus would report its healthiest numbers on
    exactly the campaigns worth distrusting.

    Only the killer node ids are re-run, never the whole scope: that is one to three tests in
    practice, which is what keeps confirmation affordable enough to be unconditional.

    No killers is not confirmation. Neither is a run that collected nothing — a node id that no
    longer exists exits `4`, and reading that as a green re-run would confirm a kill against tests
    that were never executed.
    """
    if not killer_ids:
        return False
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider", *killer_ids]
    _out, code, failed, broke, _records = run_pytest(cmd, sandbox, _mutate.sandbox_env(sandbox))
    return code == 0 and not failed and not broke


def snapshot_cleanliness(sandbox: Path) -> set[str]:
    """What `git status --porcelain` says about the sandbox **immediately after it was built**.

    Not an empty set, and that is the point. `_build_sandbox` copies untracked files in on purpose
    so the run measures the tree you actually have, which means a freshly built sandbox is already
    "dirty". Comparing later checks against empty would fire on every mutant and the signal would
    be discarded within a day.
    """
    out, _code = _run_rc(["git", "status", "--porcelain"], sandbox)
    return {line for line in out.splitlines() if line.strip()}


#: `git status --porcelain` status codes we can name. Anything else is kept as `other` rather
#: than dropped or guessed: a rename, a copy and a merge conflict all have codes, and hiding one
#: would hide a leak while misnaming it would misreport one.
_LEAK_STATUS = {"??": "untracked", "M": "modified", "D": "deleted", "A": "untracked"}


def leaked_entries(lines: set[str]) -> list[dict[str, str]]:
    """Porcelain lines as `{path, status}`, ordered so two runs compare.

    Porcelain is git's wire format. Embedding it made our schema depend on theirs and left the
    two-character code undocumented in our own contract.
    """
    entries = []
    for line in sorted(lines):
        code, _, path = line.strip().partition(" ")
        entries.append({"path": path.strip(), "status": _LEAK_STATUS.get(code.strip(), "other")})
    return sorted(entries, key=lambda e: e["path"])


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
    # `-n auto` because this is a whole-suite run, exactly like `_mutate.run_one`'s unscoped path,
    # which has always added it. Measured 2026-08-16 in a real sandbox: 291.2s serial against 77.3s
    # here — 3.8x, and 69% of a session that did 129.5s of mutant work. A warm second serial run
    # took 291.7s, so a cold `__pycache__` was not the cause; the flag simply was not there
    # (`TECH-058`).
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider"]
    cmd += ["-n", "auto", tests]
    out, code = _run_rc(cmd, sandbox, env)
    return Baseline(green=code == 0, failures=_mutate.killers(out), code=code)


def _default_workers() -> int:
    """Sandboxes to run mutants across unless told otherwise.

    Capped below the core count: each worker runs a scoped pytest, so the pool competes with
    pytest's own parallelism rather than adding to it.
    """
    import os

    return max(1, min(4, os.cpu_count() or 1))


def run_corpus(
    corpus: Any,
    *,
    baseline: Baseline | None = None,
    sandbox: Path | None = None,
    confirm: bool = False,
    workers: int = 1,
) -> list[MutantRun]:
    """Run every mutant in a validated corpus, across a pool of `workers` sandboxes.

    Each concurrent mutant gets a worktree of its own, so mutants cannot overlap. An explicit
    `sandbox` pins the run to that worktree, and therefore to one worker.

    `confirm` re-runs each kill's killers without the mutant before believing it (`FR-6`). It is
    opt-in here and on by default in a session, because the cost is real and the callers that only
    want raw outcomes should not pay it.

    `baseline` is carried rather than applied: turning it into `INDETERMINATE` is `verdict_of`'s
    job, and doing it here would put a judgement inside the function that gathers the evidence.
    """
    work = [
        (mutant, " ".join(campaign.scope))
        for campaign in corpus.campaigns
        if not campaign.retired
        for mutant in campaign.mutants
    ]
    if not work:
        return []

    def measure(box: Path, item: tuple[Any, str], clean: Any) -> MutantRun:
        mutant, target = item
        run = _run_mutant(box, mutant, target, drift=_corpus.drift_of(mutant, REPO_ROOT))
        if confirm and run.outcome == "KILL":
            run = replace(run, confirmed=confirm_kill(box, run.killers))
        leaked = leaked_since(box, clean)
        if leaked:
            # Aborting would turn one leaky test into a night with no data, and would fail the
            # accounting rule for a reason the corpus did not cause.
            _mutate._run(["git", "clean", "-fdq"], box)
            run = replace(run, leaked=leaked)
        return run

    def serial(box: Path) -> list[MutantRun]:
        clean = snapshot_cleanliness(box)
        return [measure(box, item, clean) for item in work]

    if sandbox is not None:
        return serial(sandbox)

    pool_size = _pool.size_for(workers, len(work))
    if pool_size == 1:
        only = build_sandbox()
        try:
            return serial(only)
        finally:
            remove_sandbox(only)

    return _pool.run_ordered(
        work,
        pool_size,
        run_one=measure,
        build=build_sandbox,
        remove=remove_sandbox,
        prepare=snapshot_cleanliness,
    )


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
        killer_records=list(raw.get("killer_records", [])),
        detail=str(raw.get("detail", "")),
        drift=drift,
    )


def discover_corpora(root: Path) -> list[Path]:
    """Every corpus file under `root`. The filename is the contract, so the glob and the validator
    agree by construction rather than by convention."""
    return sorted(root.rglob("*_mutants.json"))


def _cmd_confirm(args: Any, ap: Any) -> int:
    """Record one decision. `--as` and `--why` are both required, and that is the point."""
    if not args.disposition or not args.why:
        ap.error("--confirm needs --as <disposition> and --why <reason>")
    try:
        _gate.confirm(Path(args.ledger), args.confirm, disposition=args.disposition, why=args.why)
    except ValueError as exc:
        print(f"could not confirm: {exc}", file=sys.stderr)
        return 2
    print(f"{args.confirm}: {args.disposition} — {args.why}")
    return 0


def _cmd_gate(args: Any) -> int:
    """Blocked or clear, and when blocked, exactly what to do about it."""
    result = _gate.gate_verdict(Path(args.out), Path(args.ledger))
    if not result.blocked:
        print(f"CLEAR: {result.reason}")
        return 0
    print(f"BLOCKED: {result.reason}")
    for finding in result.unconfirmed:
        print(f"  unconfirmed: {finding}")
    if result.unconfirmed:
        # Only when there is something to confirm. A block on staleness or a red baseline is not
        # fixed by recording a disposition, and offering that sends the reader nowhere.
        print("\nconfirm with: mutation.py --confirm '<id>' --as <disposition> --why '<why>'")
    return 1


def _cmd_install() -> int:
    for path in install_timer():
        print(f"wrote {path}")
    print(f"enable with: systemctl --user enable --now {UNIT_NAME}.timer")
    return 0


def _cmd_summary(report: Path) -> int:
    """Re-render a report already on disk. Reads nothing else and runs nothing."""
    if not report.is_file():
        print(f"no report at {report} — run the corpus first", file=sys.stderr)
        return 1
    print(_report.render_summary(json.loads(report.read_text(encoding="utf-8"))))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run a session and write the report a gate will read hours later.

    Exit codes report the health of the RUN: `0` nothing failed, `1` something did, `2` it could not
    run. Whether feature work continues is a separate decision made against the report, not against
    this number.
    """
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", action="append", default=[], help="a corpus file; repeatable")
    ap.add_argument("--corpus-dir", help="discover every <ID>_mutants.json beneath this directory")
    ap.add_argument("--out", default=str(REPO_ROOT / ".tmp" / "mutation_report.json"))
    ap.add_argument("--no-baseline", action="store_true", help="skip the full-suite baseline")
    ap.add_argument("--no-confirm", action="store_true", help="do not re-run killers unmutated")
    ap.add_argument(
        "--workers",
        type=int,
        default=_default_workers(),
        help="sandboxes to run mutants across (1 = serial)",
    )
    ap.add_argument(
        "--install-timer", action="store_true", help="write the nightly systemd user units"
    )
    ap.add_argument(
        "--summary",
        action="store_true",
        help="re-render the last report as prose; runs nothing",
    )
    ap.add_argument("--gate", action="store_true", help="decide whether findings have been read")
    ap.add_argument("--confirm", metavar="DERIVED_ID", help="record a decision about ONE finding")
    ap.add_argument("--as", dest="disposition", choices=_gate.DISPOSITIONS)
    ap.add_argument("--why", help="why (required with --confirm)")
    ap.add_argument(
        "--ledger",
        default=str(REPO_ROOT / "scripts" / "baselines" / "mutation_findings.json"),
    )
    args = ap.parse_args(argv)

    if args.confirm:
        return _cmd_confirm(args, ap)
    if args.gate:
        return _cmd_gate(args)
    if args.install_timer:
        return _cmd_install()

    if args.summary:
        return _cmd_summary(Path(args.out))

    paths = [Path(p) for p in args.corpus]
    if args.corpus_dir:
        paths += discover_corpora(Path(args.corpus_dir))

    campaigns: list[dict[str, Any]] = []
    # Every mutant the corpus asked for, whether or not it returned a verdict. The ledger needs
    # it to tell a mutant somebody deleted from one that failed to run: those close for opposite
    # reasons, and treating a deletion as a fix would let the ledger be cleared by tidying.
    declared: set[str] = set()
    baseline: Baseline | None = None
    head = _mutate._run(["git", "rev-parse", "--short", "HEAD"], REPO_ROOT).strip()
    dirty = bool(_mutate._run(["git", "status", "--porcelain"], REPO_ROOT).strip())

    if paths:
        sandbox = build_sandbox()
        try:
            if not args.no_baseline:
                baseline = run_baseline(sandbox)
            for path in paths:
                declared |= _declared_ids(path)
                campaigns += _judge(
                    path, sandbox, baseline, confirm=not args.no_confirm, workers=args.workers
                )
        finally:
            remove_sandbox(sandbox)

    document = _report.build_session_record(
        campaigns=campaigns, head=head, dirty=dirty, baseline=baseline
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    # The nightly's journal used to carry a path and nothing else, so a FAILED run looked identical
    # to a clean one until somebody opened the file. The verdict travels with the run now.
    summary = _report.render_summary(document)
    readable = out.with_suffix(".md")
    readable.write_text(summary + "\n", encoding="utf-8")
    print(summary)
    print(f"\nreport: {out}\nsummary: {readable}")
    if campaigns:
        # Recurrence is counted where the evidence arrives, not where it is read: the gate must be
        # able to run days later against a ledger that already knows how long a finding has been here.
        _gate.record_run(out, Path(args.ledger), declared=declared)
    return _report.exit_code_for(document)


def _declared_ids(path: Path) -> set[str]:
    """Every mutant id a corpus file declares, readable without running anything."""
    try:
        corpus = _corpus.load_corpus(path)
    except Exception:
        return set()
    return {mutant.derived_id for campaign in corpus.campaigns for mutant in campaign.mutants}


def _judge(
    path: Path, sandbox: Path, baseline: Baseline | None, *, confirm: bool, workers: int = 1
) -> list[dict[str, Any]]:
    """One corpus file, run and judged into report-shaped campaigns.

    Above one worker the session's sandbox is not reused — handing one worktree to two workers is
    the overlap the pool avoids. It stays for the baseline, which has nothing to parallelise.
    """
    corpus = _corpus.load_corpus(path)
    runs = (
        run_corpus(corpus, baseline=baseline, confirm=confirm, workers=workers)
        if workers > 1
        else run_corpus(corpus, baseline=baseline, sandbox=sandbox, confirm=confirm)
    )
    by_id = {run.derived_id: run for run in runs}
    failures = list(getattr(baseline, "failures", []) or [])

    judged = []
    for campaign in corpus.campaigns:
        if campaign.retired:
            continue
        judgements: list[Verdict] = []
        verdicts = []
        for mutant in campaign.mutants:
            run = by_id.get(mutant.derived_id)
            if run is None:
                continue
            judgement = verdict_of(
                run, scope=campaign.scope, baseline_failures=failures, confirmed=run.confirmed
            )
            judgements.append(judgement)
            # The verdict answers "is it protected"; the run carries the evidence for that answer.
            # The report needs both, and `detail` is where a sandbox path would hide.
            verdicts.append(
                {
                    "id": judgement.derived_id,
                    "verdict": judgement.verdict,
                    "reason": judgement.reason,
                    "explanation": judgement.explanation,
                    "drift": judgement.drift,
                    "confirmed": run.confirmed,
                    # Scoped here because this is the only place that holds both the killers and
                    # the campaign that asked for them.
                    "killers": scope_killers(run.killer_records, scope=campaign.scope),
                    "leaked": leaked_entries(set(run.leaked)),
                    "detail": run.detail,
                }
            )
        judged.append(
            {
                "feature": corpus.feature,
                "requirement": campaign.requirement,
                "verdict": campaign_verdict(judgements, declared=len(campaign.mutants)),
                "mutants_declared": len(campaign.mutants),
                "verdicts_returned": len(verdicts),
                "results": verdicts,
            }
        )
    return judged


if __name__ == "__main__":
    sys.exit(main())
