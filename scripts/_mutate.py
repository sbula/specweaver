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
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: `FAILED <nodeid>` lines. `-q --tb=no` still prints these, and they are the only reliable
#: machine-readable statement of *which* tests objected.
_FAILED = re.compile(r"^FAILED (\S+)", re.MULTILINE)

#: A mutant that does not import is not evidence of anything. Collection errors are reported
#: separately so a nonsense edit cannot masquerade as coverage.
_ERROR = re.compile(r"^ERROR \S+|SyntaxError|IndentationError", re.MULTILINE)


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


def killers(output: str) -> list[str]:
    """Test ids that failed — sorted, so a run is comparable with the next one."""
    if is_broken(output):
        return []
    return sorted(set(_FAILED.findall(output)))


def is_broken(output: str) -> bool:
    """Whether the mutant failed to import/collect, which makes the run uninformative."""
    return bool(_ERROR.search(output))


def verdict(found: list[str]) -> str:
    return "KILLED" if found else "SURVIVED"


def _verify_isolated(module_file: str, sandbox: Path) -> None:
    """Prove the subprocess imported the SANDBOX's source, not the working tree's."""
    resolved = Path(module_file).resolve()
    if sandbox.resolve() not in resolved.parents:
        raise RuntimeError(
            f"not isolated: specweaver imported from {resolved}, expected a path under {sandbox}. "
            "Every verdict from this run would describe the unmutated tree."
        )


def _run(cmd: list[str], cwd: Path, env_extra: dict[str, str] | None = None) -> str:
    import os

    env = {**os.environ, **(env_extra or {})}
    done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    return done.stdout + done.stderr


def _build_sandbox(sandbox: Path) -> None:
    """A detached worktree at HEAD, plus the uncommitted diff, so the run measures the real tree."""
    _run(["git", "worktree", "add", "--detach", str(sandbox), "HEAD"], REPO_ROOT)
    diff = _run(["git", "diff", "HEAD"], REPO_ROOT)
    if diff.strip():
        patch = sandbox / ".mutant.patch"
        patch.write_text(diff, encoding="utf-8")
        _run(["git", "apply", str(patch)], sandbox)
        patch.unlink(missing_ok=True)


def prove_isolation(sandbox: Path, env: dict[str, str]) -> None:
    """Make the sandbox's interpreter say which tree it imported, and check it."""
    probe = _run(
        [sys.executable, "-c", "import specweaver.core as m; print(m.__path__[0])"], sandbox, env
    )
    lines = [line for line in probe.strip().splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"not isolated: the import probe produced no output.\n{probe[-800:]}")
    _verify_isolated(lines[-1], sandbox)


def sandbox_env(sandbox: Path) -> dict[str, str]:
    """`PYTHONPATH` must win over the editable-install `.pth` entry for the sandbox to be what runs."""
    return {"PYTHONPATH": str(sandbox / "src"), "PYTHONDONTWRITEBYTECODE": "1"}


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

    Leaves the mutated file in place — the caller resets it (`reset_file`) before the next mutant,
    which is what lets a campaign reuse one sandbox instead of building N.
    """
    target = sandbox / file
    if not target.is_file():
        return {"verdict": "BROKEN", "killers": [], "detail": f"{file} not in the sandbox"}
    apply_mutation(target, old, new)

    env = sandbox_env(sandbox)
    prove_isolation(sandbox, env)

    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-p", "no:cacheprovider"]
    if fast:
        cmd.append("-x")
    if tests:
        cmd.append(tests)
    else:
        cmd += ["-n", "auto"]
    out = _run(cmd, sandbox, env)

    if is_broken(out):
        return {"verdict": "BROKEN", "killers": [], "detail": out[-800:]}
    found = killers(out)
    return {"verdict": verdict(found), "killers": found, "detail": ""}


def reset_file(sandbox: Path, file: str) -> None:
    """Undo a mutant so the sandbox is reusable for the next one."""
    _run(["git", "checkout", "--", file], sandbox)


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
        if result["verdict"] == "BROKEN":
            print("BROKEN MUTANT — it does not import, so the run proves nothing.\n")
            print(result["detail"])
            return 2

        found = list(result["killers"])
        print(f"{verdict(found)} — {len(found)} test(s) objected to the change\n")
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
