#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Consolidated static-quality gate runner.

One entry point for every lint / static-analysis gate, selected by *lifecycle point* rather than
by check name:

    python scripts/quality.py quick     # inner loop, run as often as you like
    python scripts/quality.py cb        # commit boundary (CB-N)
    python scripts/quality.py sf        # sub-feature (SF-N) complete
    python scripts/quality.py feature   # feature / story close

    python scripts/quality.py doc       # documentation registries — a SEPARATE track

`doc` is deliberately NOT a rung on that ladder. It checks registries (roadmap checkboxes, skill
tree parity) rather than code, and a stale checkbox should not fail a code gate — the two answer
different questions and get fixed by different people at different moments. Run it alongside.

The code gates are cumulative (`feature` >= `sf` >= `cb` >= `quick`) and the *scope* each check
runs at is derived from the gate, not passed in — so a caller cannot quietly pick a cheaper scope. The
governing rule (user, 2026-07-28): from the first commit point up, core checks cover ALL source
regardless of what was touched; only the checks that produce false signal on half-built code are
diff-scoped, and they widen as the gate rises.

This runner deliberately uses stdlib `subprocess` rather than `SubprocessExecutor`. That is a
DECLARED exemption to CLAUDE.md rule 1 (user, 2026-07-28), not an oversight: `SubprocessExecutor`
lives in `src/specweaver/sandbox/`, and a quality gate that imports the product it is checking
cannot run when that product is broken — which is exactly when the gate is needed.

Checks execute in parallel but their output is buffered and replayed in a fixed order, because
interleaved parallel stdout is unreadable. Nothing fails fast: every check runs to completion so
one invocation reports every problem at once.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_sibling(module_name: str) -> ModuleType:
    """Load a same-directory script by path.

    `scripts/` is not an importable package, so a plain import only resolves when this file is run
    as a script. A test harness loading it via `spec_from_file_location` gets no such freebie —
    which is exactly how the extraction below first broke 43 tests.
    """
    path = Path(__file__).resolve().parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_venv = _load_sibling("_venv")
venv_python = _venv.venv_python
venv_tool = _venv.venv_tool

#: The four static-analysis gates form one escalating ladder. `doc` is a SEPARATE TRACK, not a
#: rung on it: it checks documentation registries rather than code, so folding it into `cb` would
#: make a code gate fail for a stale roadmap checkbox. Run it alongside, not instead.
CODE_GATES = ("quick", "cb", "sf", "feature")
DOC_GATES = ("doc",)
GATES = (*CODE_GATES, *DOC_GATES)
SCOPES = ("changed", "module", "all")
#: Scope ordering, used to assert a gate never narrows what a lower gate widened.
SCOPE_RANK = {"changed": 0, "module": 1, "all": 2}

#: Cognitive-complexity ceiling for complexipy. complexipy's own default is 15.
MAX_COGNITIVE_COMPLEXITY = 15


class UsageError(Exception):
    """Caller asked for something the matrix does not offer."""


# ---------------------------------------------------------------------------
# The matrix — the single source of truth for what runs where
# ---------------------------------------------------------------------------

#: check name -> gate -> scope. A gate absent from a check's row means it does not run there.
MATRIX: dict[str, dict[str, str]] = {
    # -- always repo-wide, cheap enough to run everywhere -------------------
    "ruff": {"quick": "all", "cb": "all", "sf": "all", "feature": "all"},
    # `pyproject.toml` disables E501 saying "line length handled by formatter" — but nothing ran
    # the formatter, in the gate or in any skill, so line length was enforced by nobody and 106
    # files had drifted. Cheap enough to run everywhere.
    "format": {"quick": "all", "cb": "all", "sf": "all", "feature": "all"},
    "test_basenames": {"quick": "all", "cb": "all", "sf": "all", "feature": "all"},
    # -- scoped only in the inner loop, repo-wide from the first commit ----
    "file_sizes": {"quick": "changed", "cb": "all", "sf": "all", "feature": "all"},
    "complexipy": {"quick": "changed", "cb": "all", "sf": "all", "feature": "all"},
    "useless_asserts": {"quick": "changed", "cb": "all", "sf": "all", "feature": "all"},
    "conventions": {"quick": "changed", "cb": "all", "sf": "all", "feature": "all"},
    # -- commit-point checks, never scoped --------------------------------
    "mypy": {"cb": "all", "sf": "all", "feature": "all"},
    "tach": {"cb": "all", "sf": "all", "feature": "all"},
    "suppressions": {"cb": "all", "sf": "all", "feature": "all"},
    # -- design metrics: widen as the design settles ----------------------
    # Diff-scoped at `cb` because a class is legitimately half-built mid-commit-boundary and an
    # unactionable finding is one that gets suppressed. Not because it is expensive.
    "class_health": {"cb": "changed", "sf": "module", "feature": "all"},
    # Cycles are a separate check from coupling metrics, not a cheaper mode of one. An import
    # cycle cannot be seen in a diff at all, so this is global from the first commit point and
    # never narrows. Splitting it also lets the metrics start later without weakening cycles.
    "cycles": {"cb": "all", "sf": "all", "feature": "all"},
    # Duplication is cross-file by definition: a clone's twin may be in a file the commit never
    # touched, so there is no meaningful `changed` scope and this never narrows. `quick` is left
    # out on purpose — it shells out to npx and the inner loop should stay fast.
    "duplication": {"cb": "all", "sf": "all", "feature": "all"},
    # Fan-in likewise needs every importer, so the ANALYSIS is always global; `module` narrows
    # which modules are judged against thresholds, never what is computed.
    "coupling": {"sf": "module", "feature": "all"},
    # -- the `doc` track: registries, not code --------------------------------
    # Both are inherently repo-wide and take no paths: a roadmap checkbox is stale relative to the
    # whole registry, and a skill file drifts relative to its twin in the other tree.
    "roadmap_sync": {"doc": "all"},
    "roadmap_placement": {"doc": "all"},
    "skill_sync": {"doc": "all"},
    # Same track, same reason: an instruction's references are stale relative to the whole repo,
    # not to a diff. Doc-gate-only mirrors the two above -- the accepted gap is that a *code*
    # commit deleting a referenced document is not caught until the next doc-gate run.
    "skill_references": {"doc": "all"},
    # Same track. Takes no story argument ON PURPOSE: `check_story_preconditions.py` holds a check
    # that would have caught INT-US-25's `✅`-with-no-proof from the day it was written, and never
    # fired because it only runs when a human passes that story ID. A sweep cannot be forgotten.
    "proof_tier": {"doc": "all"},
    # R-DEPTH. `R-LENGTH` capped the roadmap and its rationale pushed the detail into the topic
    # doc, which nothing then checked -- 33.5% of topic lines over 200 chars, longest 5624.
    # Ratcheted per file; the remedy is redistribution into the design doc, not deletion.
    "entry_depth": {"doc": "all"},
}


@dataclass(frozen=True)
class Plan:
    """A single check, resolved to the scope it runs at for one gate."""

    check: str
    scope: str


@dataclass(frozen=True)
class Check:
    """How to invoke one check, and which trees it reads."""

    name: str
    trees: tuple[str, ...]
    #: argv builder. Receives the resolved paths (possibly a tree root).
    build: object
    #: Checks whose analysis is inherently global ignore resolved paths entirely.
    ignores_paths: bool = False
    #: Script this check needs on disk; None for tools invoked as modules.
    script: str | None = None


@dataclass
class Result:
    check: str
    scope: str
    status: str
    exit_code: int = 0
    duration: float = 0.0
    output: str = ""
    command: list[str] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return self.status in {"FAILED", "MISSING", "ERROR"}


# ---------------------------------------------------------------------------
# Interpreter / tool resolution
# ---------------------------------------------------------------------------


PY = venv_python()


_r = _load_sibling("_quality_runners")

CHECKS: dict[str, Check] = {
    # `scripts/` is included so the gate lints itself — it was previously unlinted by anything.
    "ruff": Check("ruff", ("src", "tests", "scripts"), _r._ruff),
    "format": Check("format", ("src", "tests", "scripts"), _r._format),
    "mypy": Check("mypy", ("src",), _r._mypy),
    "tach": Check("tach", ("src",), _r._tach, ignores_paths=True),
    # `script=` is not decoration: it is the pre-flight that reports MISSING instead of letting
    # the shell-out fail with a confusing error. This entry declared None while its runner
    # shells out to check_complexity.py, so complexipy alone lacked that guard (`TECH-037`).
    "complexipy": Check("complexipy", ("src",), _r._complexipy, script="check_complexity.py"),
    "file_sizes": Check(
        "file_sizes", ("src", "tests", "scripts"), _r._file_sizes, script="check_file_sizes.py"
    ),
    "test_basenames": Check(
        "test_basenames", ("tests",), _r._test_basenames, script="check_test_basenames.py"
    ),
    "useless_asserts": Check(
        "useless_asserts", ("tests",), _r._useless_asserts, script="check_useless_asserts.py"
    ),
    "suppressions": Check(
        "suppressions", ("src",), _r._suppressions, script="check_suppressions.py"
    ),
    "class_health": Check(
        "class_health", ("src",), _r._class_health, script="check_class_health.py"
    ),
    "coupling": Check("coupling", ("src",), _r._coupling, script="check_coupling.py"),
    "cycles": Check("cycles", ("src",), _r._cycles, script="check_coupling.py"),
    "duplication": Check(
        "duplication",
        ("src",),
        _r._duplication,
        ignores_paths=True,
        script="check_duplication.py",
    ),
    "roadmap_placement": Check(
        "roadmap_placement",
        ("docs",),
        _r._whole_repo("check_roadmap_placement.py"),
        ignores_paths=True,
        script="check_roadmap_placement.py",
    ),
    "roadmap_sync": Check(
        "roadmap_sync",
        ("docs",),
        _r._whole_repo("check_roadmap_sync.py"),
        ignores_paths=True,
        script="check_roadmap_sync.py",
    ),
    "skill_sync": Check(
        "skill_sync",
        (".agents",),
        _r._whole_repo("check_skill_sync.py"),
        ignores_paths=True,
        script="check_skill_sync.py",
    ),
    "skill_references": Check(
        "skill_references",
        (".agents", "docs"),
        _r._whole_repo("check_skill_references.py"),
        ignores_paths=True,
        script="check_skill_references.py",
    ),
    "entry_depth": Check(
        "entry_depth",
        ("docs",),
        _r._whole_repo("_entry_depth.py"),
        ignores_paths=True,
        script="_entry_depth.py",
    ),
    "proof_tier": Check(
        "proof_tier",
        ("docs",),
        _r._whole_repo("check_proof_tier.py"),
        ignores_paths=True,
        script="check_proof_tier.py",
    ),
    # `tests` is in scope so R5 (e2e naming) can see e2e files; R2 stays src/scripts-only.
    "conventions": Check(
        "conventions", ("src", "tests"), _r._conventions, script="check_conventions.py"
    ),
}


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def resolve_plans(gate: str, only: list[str] | None = None, scope: str | None = None) -> list[Plan]:
    """Resolve a gate to the exact set of checks that must run, in stable order."""
    if gate not in GATES:
        raise UsageError(f"unknown gate {gate!r}; expected one of {', '.join(GATES)}")
    if scope is not None and scope not in SCOPES:
        raise UsageError(f"unknown scope {scope!r}; expected one of {', '.join(SCOPES)}")

    plans = [
        Plan(check=name, scope=scope or row[gate])
        for name, row in sorted(MATRIX.items())
        if gate in row
    ]

    if only:
        available = {p.check for p in plans}
        for name in only:
            if name not in CHECKS:
                raise UsageError(f"unknown check {name!r}")
            if name not in available:
                raise UsageError(
                    f"check {name!r} does not run at gate {gate!r} "
                    f"(available: {', '.join(sorted(available))})"
                )
        plans = [p for p in plans if p.check in set(only)]

    return plans


def widen_to_modules(paths: list[Path]) -> list[Path]:
    """Widen changed files to the packages that own them."""
    return sorted({p.parent for p in paths})


def paths_for(check: Check, scope: str, changed: list[Path]) -> list[Path]:
    """Resolve the paths one check should be handed at a given scope."""
    if scope == "all":
        return [Path(t) for t in check.trees]

    relevant = [
        p
        for p in changed
        if p.suffix == ".py"
        and any(p.as_posix().startswith(f"{t}/") for t in check.trees)
        and (REPO_ROOT / p).exists()
    ]
    if scope == "module":
        return widen_to_modules(relevant)
    return relevant


def changed_files(base: str | None = None) -> list[Path]:
    """Files touched relative to `base` (default: everything not yet committed)."""
    specs = [
        ["git", "diff", "--name-only", "--diff-filter=d"],
        ["git", "diff", "--name-only", "--diff-filter=d", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    if base:
        specs = [["git", "diff", "--name-only", "--diff-filter=d", f"{base}...HEAD"], *specs]

    found: set[str] = set()
    for spec in specs:
        try:
            proc = subprocess.run(  # fixed argv, never shell=True
                spec, cwd=REPO_ROOT, capture_output=True, text=True, check=False
            )
        except OSError:
            continue
        if proc.returncode == 0:
            found.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return sorted(Path(p) for p in found)


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


def run_plan(plan: Plan, changed: list[Path], repo_root: Path = REPO_ROOT) -> Result:
    """Execute one check. Never raises — a crash is reported as a result."""
    check = CHECKS[plan.check]

    if check.script is not None and not (repo_root / "scripts" / check.script).exists():
        return Result(
            plan.check,
            plan.scope,
            "MISSING",
            output=f"not implemented yet: scripts/{check.script}",
        )

    paths = paths_for(check, plan.scope, changed)
    if not paths and not check.ignores_paths:
        return Result(plan.check, plan.scope, "SKIPPED", output="nothing in scope")

    argv = check.build(paths)  # type: ignore[operator]
    if argv[0] is None:
        return Result(plan.check, plan.scope, "MISSING", output=f"tool not found: {plan.check}")

    # complexipy emits non-cp1252 glyphs and dies on a Windows console without this.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    started = time.monotonic()
    try:
        proc = subprocess.run(  # fixed argv, never shell=True
            argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )
    except OSError as exc:
        return Result(
            plan.check,
            plan.scope,
            "ERROR",
            duration=time.monotonic() - started,
            output=str(exc),
            command=argv,
        )

    return Result(
        check=plan.check,
        scope=plan.scope,
        status="PASSED" if proc.returncode == 0 else "FAILED",
        exit_code=proc.returncode,
        duration=time.monotonic() - started,
        output=(proc.stdout + proc.stderr).strip(),
        command=argv,
    )


def run_gate(plans: list[Plan], changed: list[Path]) -> list[Result]:
    """Run every plan concurrently, returning results in the plans' declared order."""
    if not plans:
        return []
    results: dict[str, Result] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(plans))) as pool:
        futures = {pool.submit(run_plan, p, changed): p for p in plans}
        for future in concurrent.futures.as_completed(futures):
            plan = futures[future]
            results[plan.check] = future.result()
    return [results[p.check] for p in plans]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

_ICON = {
    "PASSED": "ok  ",
    "FAILED": "FAIL",
    "MISSING": "MISS",
    "SKIPPED": "skip",
    "ERROR": "ERR ",
}


def render(gate: str, results: list[Result], changed_count: int | None) -> str:
    # None means git was never consulted (every check at this gate is repo-wide). Printing "0
    # changed files" there would read as "nothing was modified", which is a different claim.
    scope_note = (
        "all checks repo-wide" if changed_count is None else f"{changed_count} changed file(s)"
    )
    lines = [
        "",
        f"Quality gate: {gate}   ({scope_note})",
        "-" * 72,
        f"{'':4}  {'check':<18}{'scope':<10}{'time':>8}  detail",
    ]
    for r in results:
        detail = "" if r.status in {"PASSED", "SKIPPED"} else f"exit {r.exit_code}"
        if r.status == "SKIPPED":
            detail = r.output
        if r.status == "MISSING":
            detail = r.output
        lines.append(f"{_ICON[r.status]}  {r.check:<18}{r.scope:<10}{r.duration:>7.1f}s  {detail}")

    failures = [r for r in results if r.failed]
    if failures:
        lines.append("")
        lines.append("=" * 72)
        for r in failures:
            lines.append("")
            lines.append(f"--- {r.check} [{r.status}] " + "-" * (60 - len(r.check)))
            if r.command:
                lines.append(f"$ {' '.join(r.command)}")
            lines.append(r.output or "(no output)")

    passed = sum(1 for r in results if r.status == "PASSED")
    skipped = sum(1 for r in results if r.status == "SKIPPED")
    lines.append("")
    lines.append(
        f"{len(failures)} failed, {passed} passed, {skipped} skipped "
        f"of {len(results)} checks at gate '{gate}'"
    )
    return "\n".join(lines)


def render_matrix() -> str:
    lines = [f"{'check':<18}" + "".join(f"{g:<10}" for g in GATES)]
    lines.append("-" * (18 + 10 * len(GATES)))
    for name, row in sorted(MATRIX.items()):
        lines.append(f"{name:<18}" + "".join(f"{row.get(g, '-'):<10}" for g in GATES))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _force_utf8_stdout() -> None:
    """Make our own stdout survive the tool output we replay.

    Setting PYTHONIOENCODING for the children is not enough: complexipy emits U+274C, and on a
    Windows console the PARENT's cp1252 stdout then dies with UnicodeEncodeError while printing
    the captured text — turning a reportable finding into a crashed gate.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            with contextlib.suppress(OSError, ValueError):
                reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    parser = argparse.ArgumentParser(
        prog="quality.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("gate", choices=[*GATES, "matrix"], help="lifecycle point to gate at")
    parser.add_argument("--only", help="comma-separated subset of checks to run")
    parser.add_argument("--scope", choices=SCOPES, help="override the gate-derived scope")
    parser.add_argument("--base", help="git ref that 'changed' is measured against")
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args(argv)

    if args.gate == "matrix":
        print(render_matrix())
        return 0

    try:
        plans = resolve_plans(
            args.gate,
            only=[s.strip() for s in args.only.split(",")] if args.only else None,
            scope=args.scope,
        )
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    needs_git = any(p.scope != "all" for p in plans)
    changed = changed_files(args.base) if needs_git else None

    results = run_gate(plans, changed or [])

    if args.json:
        print(
            json.dumps(
                {
                    "gate": args.gate,
                    "changed_files": None if changed is None else len(changed),
                    "results": [
                        {
                            "check": r.check,
                            "scope": r.scope,
                            "status": r.status,
                            "exit_code": r.exit_code,
                            "duration_s": round(r.duration, 2),
                            "output": r.output,
                        }
                        for r in results
                    ],
                },
                indent=2,
            )
        )
    else:
        print(render(args.gate, results, None if changed is None else len(changed)))

    return 1 if any(r.failed for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
