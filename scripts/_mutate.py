#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Change the code so a claim's behaviour no longer holds, then see whether anything objects.

A citation says a test *mentions* a requirement. This says whether any test *notices* when the
behaviour goes away — the question `check_fr_sweep.py` and `check_fr_coverage.py` structurally
cannot answer, and the one the closure contract points at `A-VAL-03` for.

`TECH-017` ran six of these by hand, and **four caught vacuous assertions in the audit's own work**:
a guard that passed with a bypass planted in `decompose.py`; a credential check that passed
un-isolated; a `parents[4]` repo root that globbed a directory which does not exist; a container
guard reading a toml the harness never loaded. Hand-rolling does not scale and leaves no citable
record.

The measurement it produces is one no citation can: neutralising `sw check --lineage` orphan
detection is caught by **exactly one test out of 6829** — and that test failed at `COLUMNS=80` until
2026-08-14, so the feature was unprotected on any 80-column CI.

## Isolation, and why it is the whole design

The mutant is applied inside a **detached `git worktree`**, never in your working tree, for two
reasons: a crashed run cannot leave your source mutated, and **you can keep working while it runs**
— a full-suite mutant costs about a minute, and editing files mid-run would otherwise corrupt it.

Uncommitted work is carried across with `git diff HEAD`, so the run measures the tree you actually
have rather than the last commit.

> [!CAUTION]
> **A mutation runner that silently tests the UNMUTATED tree reports every mutant as killed**, which
> is worse than no runner at all — it manufactures confidence. This package is installed editable
> via a `.pth` path entry, so `PYTHONPATH` must win over it for the sandbox to be what runs.
> :func:`_verify_isolated` makes the runner *prove* which tree it imported before any verdict is
> believed. `TECH-032`: a check that cannot find its subject must say so, not pass.

## Reuse for `A-VAL-03`

Everything here except argument parsing is the mechanism `A-VAL-03` needs: sandbox construction,
mutant application, isolation proof, run, and kill/survive classification. What that ticket adds is
**mutant generation** — operators that derive candidate edits from an AST rather than taking an
anchor string — and a corpus loop with a score. Deliberately not built here: generating mutants
without a way to trust the runner would have been the wrong order.

Usage:
    python scripts/_mutate.py --file src/specweaver/x.py --old 'a = f()' --new 'a = []'
    python scripts/_mutate.py --file ... --old ... --new ... --tests tests/unit/foo
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

#: `FAILED <nodeid>` lines. `-q --tb=no` still prints these, and they are the only reliable
#: machine-readable statement of *which* tests objected.
_FAILED = re.compile(r"^FAILED (\S+)", re.MULTILINE)

#: SGR escape sequences. Pytest colours the verdict word itself — `short_test_summary` builds the
#: line as `markup(word) + " " + nodeid` — so a coloured line starts with `\x1b[31m`, not `F`, and
#: `^FAILED` cannot match. Measured 2026-08-15: the same mutant read SURVIVED/0 killers with
#: `FORCE_COLOR=3` set and KILLED/2 without it.
#:
#: Stripping is the belt; `PY_COLORS=0` in :func:`sandbox_env` is the braces. Relaxing the `^`
#: anchor instead would be wrong — it is what stops the word `FAILED` inside a captured log line
#: or a test's own output from counting as a killer.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(output: str) -> str:
    """Output with colour removed, so the parsers see the text pytest meant for machines."""
    return _ANSI.sub("", output)


#: A mutant that does not import is not evidence of anything, and must never be reported as a kill.
#:
#: Read from pytest's SUMMARY line only. Two earlier versions matched the body of the output and
#: both produced false BROKENs that discarded real measurements: first the bare word `SyntaxError`,
#: which some tests legitimately print, then `^ERROR <path>.py`, which matches every captured
#: application log line at ERROR level — and a full-suite run is full of those. A false BROKEN is
#: worse than a miss, because it reads as a bad anchor rather than as a bug in the runner.
_SUMMARY_ERROR = re.compile(r"^=+.*\berrors?\b.*=+$|^\s*\d+ errors?\b", re.MULTILINE)
_INTERNAL = re.compile(r"^INTERNALERROR", re.MULTILINE)


def apply_mutation(path: Path, old: str, new: str) -> None:
    """Replace `old` with `new` in `path`, or refuse loudly.

    Refuses on: no match (the anchor is stale), several matches (the runner could not say which
    line it changed), and an identical replacement (which mutates nothing and would report a false
    `SURVIVED`).
    """
    if old == new:
        raise ValueError("old and new are identical — that mutates nothing")
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0:
        raise ValueError(f"anchor not found in {path}: {old!r}")
    if count > 1:
        raise ValueError(f"anchor appears {count} times in {path} — make it unique")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _log_records(path: Path) -> list[dict[str, Any]]:
    """Every record pytest wrote, as objects.

    Raises rather than returning nothing when the file is absent: no log means pytest died before
    writing one, and reading that as "no test objected" is a false survival — the most expensive
    wrong answer this runner can give.
    """
    if not path.is_file():
        raise FileNotFoundError(f"pytest wrote no report log: {path}")
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            with contextlib.suppress(json.JSONDecodeError):
                records.append(json.loads(line))
    return records


#: pytest colours its assertion diffs and `reprcrash.message` keeps the escapes verbatim. A
#: stored record is read by machines and by greps, neither of which has any use for them.
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _crash_message(record: dict[str, Any]) -> str | None:
    """The first line of why a test objected, or `None` when it left no crash repr.

    Only the first line: `reprcrash.message` carries the whole assertion diff with colour codes,
    and a record is for scanning. The full text is in the run's output, which is kept for
    diagnosis.
    """
    longrepr = record.get("longrepr")
    if not isinstance(longrepr, dict):
        return None
    crash = longrepr.get("reprcrash")
    if not isinstance(crash, dict) or not crash.get("message"):
        return None
    return _ANSI.sub("", str(crash["message"]).splitlines()[0])


def killer_records(path: Path) -> list[dict[str, Any]]:
    """Which tests objected and why, sorted, one entry per test.

    A bare node id cannot tell a mutant killed by the planted guard from one killed by an
    unrelated fixture error — both read as a kill, and the campaign then certifies a requirement
    nothing protects.
    """
    seen: dict[str, str | None] = {}
    for record in _log_records(path):
        if record.get("$report_type") != "TestReport" or record.get("outcome") != "failed":
            continue
        nodeid = str(record["nodeid"])
        if seen.get(nodeid) is None:
            seen[nodeid] = _crash_message(record)
    return [{"nodeid": nodeid, "message": seen[nodeid]} for nodeid in sorted(seen)]


def killers_from_log(path: Path) -> list[str]:
    """Test ids that objected, sorted, each named once however many phases failed.

    Derived from `killer_records` rather than parsed again: two readers of one log are two things
    that can disagree, and a disagreement here means one of them is lying about coverage.
    """
    return [str(record["nodeid"]) for record in killer_records(path)]


def collection_failed(path: Path) -> bool:
    """Whether pytest failed to collect — nothing ran, so nothing was measured."""
    return any(
        r.get("$report_type") == "CollectReport" and r.get("outcome") == "failed"
        for r in _log_records(path)
    )


def killers(output: str) -> list[str]:
    """Test ids that failed — sorted, so a run is comparable with the next one."""
    if is_broken(output):
        return []
    return sorted(set(_FAILED.findall(_plain(output))))


def is_broken(output: str) -> bool:
    """Whether pytest itself errored — collection failure, not a test failure."""
    plain = _plain(output)
    return bool(_INTERNAL.search(plain) or _SUMMARY_ERROR.search(plain))


def outcome(found: list[str]) -> str:
    """Whether any test objected. The raw fact, not what it means.

    Named `outcome` because `verdict` now means the judgement — scope, confirmation and baseline
    applied — and one word for two layers is how a reader comes to believe a bystander test
    proves a requirement. `OBJECTED`/`SILENT` describe the run; `PROTECTED`/`UNPROTECTED`
    describe our code.
    """
    return "OBJECTED" if found else "SILENT"


def _verify_isolated(module_file: str, sandbox: Path) -> None:
    """Prove the subprocess imported the SANDBOX's source, not the working tree's."""
    resolved = Path(module_file).resolve()
    if sandbox.resolve() not in resolved.parents:
        raise RuntimeError(
            f"not isolated: specweaver imported from {resolved}, expected a path under {sandbox}. "
            "Every verdict from this run would describe the unmutated tree."
        )


#: How long one mutant's test run may take before it is cut off and reported. A scoped run is
#: seconds and a whole-suite one is a couple of minutes, so this is far above any healthy
#: mutant and far below a session anyone would wait for.
MUTANT_TIMEOUT_SECONDS = 900.0

#: Exit code reported for a command the time box cut off. 124 is what `timeout(1)` uses, so a
#: reader who greps for it finds the convention rather than a number this repo invented.
TIMEOUT_RC = 124


def _run_rc(
    cmd: list[str],
    cwd: Path,
    env_extra: dict[str, str] | None = None,
    *,
    timeout: float | None = None,
) -> tuple[str, int]:
    """Output **and** the exit code.

    `_run` discarded the code, and pytest says things through it that it says nowhere else: `4` for
    a path that does not exist, `5` when everything was deselected. Neither prints a `FAILED` line,
    so a mis-typed test target read as "nothing objected" — a survival where in truth nothing ran.

    Kept as a sibling rather than a change to `_run` so the ten call sites that only want text stay
    where they are.
    """
    env = {**os.environ, **(env_extra or {})}
    try:
        done = subprocess.run(
            cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False, timeout=timeout
        )
    except subprocess.TimeoutExpired as expired:
        # A hang is the one failure this runner cannot inherit: every other bad mutant returns
        # something, and this one returns nothing for as long as the session is allowed to live.
        partial = (expired.stdout or b"") if isinstance(expired.stdout, bytes) else b""
        text = partial.decode("utf-8", "replace") if partial else ""
        return f"{text}\ncommand timed out after {timeout:g}s: {' '.join(cmd)}", TIMEOUT_RC
    return done.stdout + done.stderr, done.returncode


def _run(cmd: list[str], cwd: Path, env_extra: dict[str, str] | None = None) -> str:
    return _run_rc(cmd, cwd, env_extra)[0]


def run_pytest(
    cmd: list[str], sandbox: Path, env: dict[str, str]
) -> tuple[str, int, list[str], bool, list[dict[str, Any]]]:
    """A time-boxed pytest run whose results are **read**, not scraped.

    Returns the output and exit code for diagnosis, plus the killers and whether collection
    failed, both taken from `--report-log`. The human output is never parsed for results: a node
    id is not recoverable from it once the id contains a space.
    """
    # Outside the worktree on purpose: anything written inside it is picked up by the cleanliness
    # snapshot and reported as an artifact the mutant leaked.
    with tempfile.TemporaryDirectory(prefix="sw-mutation-log-") as tmp:
        log = Path(tmp) / "report.jsonl"
        args = [*cmd, f"--report-log={log}"]
        out, code = _run_rc(args, sandbox, env, timeout=MUTANT_TIMEOUT_SECONDS)
        if code == TIMEOUT_RC or not log.is_file():
            return out, code, [], False, []
        return (
            out,
            code,
            killers_from_log(log),
            collection_failed(log),
            killer_records(log),
        )


def _build_sandbox(sandbox: Path) -> None:
    """A detached worktree at HEAD carrying your uncommitted work, so it measures the real tree.

    Both halves of "uncommitted" are needed. `git diff HEAD` brings modifications to tracked files;
    **untracked files must be copied separately**, and forgetting them is not a subtle failure: a new
    test helper existed only in the working tree, so every file importing it failed to collect in the
    sandbox and the whole campaign reported BROKEN. Correctly — it refused to measure a tree that was
    not the one under test — but it cost a run to notice.
    """
    _run(["git", "worktree", "add", "--detach", str(sandbox), "HEAD"], REPO_ROOT)
    diff = _run(["git", "diff", "HEAD"], REPO_ROOT)
    if diff.strip():
        patch = sandbox / ".mutant.patch"
        patch.write_text(diff, encoding="utf-8")
        _run(["git", "apply", str(patch)], sandbox)
        patch.unlink(missing_ok=True)
    for name in _run(["git", "ls-files", "--others", "--exclude-standard"], REPO_ROOT).split():
        source = REPO_ROOT / name
        if source.is_file():
            target = sandbox / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _probe_path(probe: str, sandbox: Path) -> str:
    """The import path in the probe's output, which is not necessarily its last line.

    Taking `lines[-1]` cost a whole campaign: a `RuntimeWarning` printed after the path became the
    "path", `_verify_isolated` raised, and every mutant was recorded BROKEN. It failed closed, which
    is the right direction — but it reported a bad anchor when the fault was in the runner.
    """
    for line in reversed([line.strip() for line in probe.splitlines() if line.strip()]):
        if line.startswith(str(sandbox)):
            return line
    raise RuntimeError(
        f"not isolated: the import probe produced no path under {sandbox}.\n{probe[-800:]}"
    )


def prove_isolation(sandbox: Path, env: dict[str, str]) -> None:
    """Make the sandbox's interpreter say which tree it imported, and check it."""
    probe = _run(
        [sys.executable, "-c", "import specweaver.core as m; print(m.__path__[0])"], sandbox, env
    )
    _verify_isolated(_probe_path(probe, sandbox), sandbox)


def sandbox_env(sandbox: Path) -> dict[str, str]:
    """`PYTHONPATH` must win over the editable-install `.pth` entry for the sandbox to be what runs.

    `PY_COLORS=0` is the **first** check in pytest's `should_do_markup`, so it beats an inherited
    `FORCE_COLOR` — which every agent shell sets, and which otherwise outranks the isatty test that
    would have kept this output plain. Nothing here is read by a human; the sandbox is a detached
    worktree that is deleted at the end of the run.
    """
    return {
        "PYTHONPATH": str(sandbox / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PY_COLORS": "0",
    }


def run_one(
    sandbox: Path,
    *,
    file: str,
    old: str,
    new: str,
    tests: str = "",
    fast: bool = False,
) -> dict[str, object]:
    """Apply one mutant in an EXISTING sandbox and report what objected.

    **Restores the file itself**, so one sandbox serves a whole campaign. It restores the text it
    found, never `git checkout` — the sandbox is HEAD *plus* your uncommitted diff, and checking out
    would throw that diff away. Found by using this tool on itself on 2026-08-15: the same anchor
    read `KILLED` first in a campaign and `BROKEN` second, because the first reset had reverted the
    file to HEAD and the anchor lived only in the uncommitted work.

    The `finally` matters as much as the restore. A crash mid-run would otherwise carry a live
    mutant into the next one, and that verdict would look ordinary.
    """
    target = sandbox / file
    if not target.is_file():
        return {
            "outcome": "BROKEN",
            "killers": [],
            "killer_records": [],
            "detail": f"{file} not in the sandbox",
            "code": 3,
        }
    original = target.read_text(encoding="utf-8")
    apply_mutation(target, old, new)

    try:
        env = sandbox_env(sandbox)
        prove_isolation(sandbox, env)

        cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider"]
        if fast:
            cmd.append("-x")
        if tests:
            # split, never append: a multi-path target as one argv element is a path that exists
            # nowhere, and pytest answers that with exit 4 and no failures — a false survival.
            cmd += tests.split()
        else:
            cmd += ["-n", "auto"]
        out, code, found, collect_failed, records = run_pytest(cmd, sandbox, env)
    finally:
        target.write_text(original, encoding="utf-8")

    if code == TIMEOUT_RC:
        # Not a survival and not a kill: nothing was measured. Reported as BROKEN so the gate
        # blocks on it, because a mutant that hangs is a defect in the campaign or in the test,
        # and both need a human.
        return {
            "outcome": "BROKEN",
            "killers": [],
            "killer_records": [],
            "detail": f"timed out after {MUTANT_TIMEOUT_SECONDS:g}s — the mutant made a test wait "
            f"rather than fail. Choose one that breaks the behaviour without removing whatever "
            f"the test is waiting for.",
            "code": code,
        }
    if collect_failed or is_broken(out):
        return {
            "outcome": "BROKEN",
            "killers": [],
            "killer_records": [],
            "detail": out[-800:],
            "code": code,
        }
    return {
        "outcome": outcome(found),
        "killers": found,
        "killer_records": records,
        "detail": "",
        "code": code,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True, help="repo-relative source file to mutate")
    ap.add_argument("--old", required=True, help="exact, unique anchor to replace")
    ap.add_argument("--new", required=True, help="replacement")
    ap.add_argument("--tests", default="", help="pytest target (default: the whole suite)")
    ap.add_argument("--keep", action="store_true", help="leave the sandbox for inspection")
    args = ap.parse_args(argv)

    sandbox = Path(tempfile.mkdtemp(prefix="sw-mutant-"))
    sandbox.rmdir()  # git worktree add wants a non-existent path
    try:
        _build_sandbox(sandbox)
        target = sandbox / args.file
        if not target.is_file():
            print(f"could not run: {args.file} not found in the sandbox", file=sys.stderr)
            return 2
        result = run_one(sandbox, file=args.file, old=args.old, new=args.new, tests=args.tests)
        if result["outcome"] == "BROKEN":
            print("BROKEN MUTANT — it does not import, so the run proves nothing.\n")
            print(result["detail"])
            return 2

        found = list(result["killers"])
        print(f"{outcome(found)} — {len(found)} test(s) objected to the change\n")
        for test in found:
            print(f"  {test}")
        if not found:
            print(
                "\nNothing in the suite noticed this behaviour disappearing. The claim that rests "
                "on it is unproven regardless of what cites it.\n"
                "Before recording that: confirm the mutant actually changes observable behaviour — "
                "an equivalent mutant survives for a reason that is not a coverage gap."
            )
        elif len(found) == 1:
            print(
                "\nExactly one test protects this. Worth knowing on its own: a single point of "
                "protection is one flaky or skipped test away from none."
            )
        return 0
    finally:
        if args.keep:
            print(f"\nsandbox kept at {sandbox}")
        else:
            _run(["git", "worktree", "remove", "--force", str(sandbox)], REPO_ROOT)
            shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
