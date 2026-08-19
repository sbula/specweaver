#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Test-tier runner: which tiers run, over how much, for THIS story at THIS commit point.

Sibling of `scripts/quality.py`, deliberately not part of it. Quality checks are static and cost
seconds; tests execute code and cost minutes. Folding them together would make the fast gate slow,
and a slow gate stops being run.

Unlike the quality matrix, the tier depends on TWO things, not one: `cb` in a capability story and
`cb` in an integration story want different tiers. So the profile is chosen by story type, the row
by commit state, and DAL shifts the whole thing earlier or later.

    python scripts/tests.py cb C-FLOW-12
    python scripts/tests.py cb US-21
    python scripts/tests.py sf TECH-020 --kind refactor

STORY TYPE comes from the ID:

  `[A-E]-<TOPIC>-NN`  capability story — unit-led, integration and e2e arrive late
  `US-NN`             (sub)story — NO unit tier at all; its spanning tests are integration + e2e
  `TECH-NNN`          technical debt — has no single profile, see KIND below

An INT story has no DAL letter of its own, so it INHERITS the most critical DAL among the
capabilities it integrates (user, 2026-07-29). Note the direction carefully: DAL-A is
Mission-Critical and DAL-E is Prototyping, so "highest DAL" means most critical, which is the
alphabetically LOWEST letter. A naive max() over the letters returns E and silently selects the
weakest profile — the exact opposite of what is wanted.

TECH tickets are not one kind of work, so each declares a KIND and everything follows from it:

  refactor  behaviour must not change, so the proof is that the EXISTING tests still pass
            unmodified. This runner asserts that: a diff touching both a module and the tests
            covering it is either a behaviour change or tests adjusted to match, and both need
            saying out loud rather than going green.
  bugfix    needs a regression test at the tier where the bug actually manifested.
  tooling   the deliverable is a guardrail script; its own unit tests are the proof.
  audit     produces findings, not code. Declares NO tiers — and says so explicitly, because a
            silent zero-tier run is indistinguishable from a passing one.

A tier whose scope resolves to ZERO tests FAILS. Especially `touched`: if you changed a source
file and nothing mirrors it, that is not a clean run, it is code with no direct test.

Source means `src/specweaver/` **and** `scripts/`, both mirrored under `tests/<tier>/`. The gates
in `scripts/` were excluded until 2026-08-08, so every scripts-only change resolved to zero paths
and was refused for having no mirror — while `tests/unit/scripts/` sat there mirroring them.

A CHANGED TEST contributes its own module too (2026-08-08). A test belongs to the module it covers,
so it is scoped exactly like a source file — and the two sets are UNIONED, so a changed test can
add a module but never redirect or remove one. Before this, a tests-only change resolved to zero
paths and was refused as "source that nothing mirrors", which is false when no source changed at
all; it blocked every commit whose work is tests and documents. Tier-specific, because a test's
tier is embedded in its own path while a source file serves every tier.

Both gaps have the same root: this selector was written assuming every change is source-shaped.
CB-1's adversarial review found the same root a third time, in `domain` scope, where a test under
`capabilities/` resolved to every capability. The path-to-module mapping now lives in
`_changed_file_mapping.py`, so this file keeps only the decision of what to RUN for a module.

`domain` is used by the e2e tier alone, and it names a directory: `tests/e2e/capabilities/<domain>`,
or `tests/e2e/scripts` for the dev tooling that has no capability to sit under. A single-part path —
a file directly in the tier root — therefore selects nothing, and `tests/unit/test_macro_domain_layout.py`
is what refuses such a file in the first place.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_sibling(module_name: str) -> ModuleType:
    """Load a same-directory script by path.

    `scripts/` is not an importable package (no `__init__.py`, matching the rest of this repo's
    namespace-package convention), so a plain `from _refactor_diff_safety import ...` only
    resolves when `python scripts/tests.py` puts `scripts/` on `sys.path[0]` for free — a test
    harness loading this file via `importlib.util.spec_from_file_location` gets no such freebie.
    """
    path = Path(__file__).resolve().parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


refactor_violations = _load_sibling("_refactor_diff_safety").refactor_violations

SRC_PACKAGE = REPO_ROOT / "src" / "specweaver"

STATES = ("quick", "cb", "sf", "feature")
TIERS = ("unit", "integration", "e2e")
DAL_LETTERS = ("A", "B", "C", "D", "E")
TECH_KINDS = ("refactor", "bugfix", "tooling", "audit")

CAPABILITY_ID = re.compile(r"\b([A-E])-(UI|SENS|FLOW|INTL|VAL|EXEC)-\d{2}\b")
STORY_ID = re.compile(r"^US-\d{1,2}$", re.I)
TECH_ID = re.compile(r"^TECH-(\d{3})$", re.I)
CAP_ID = re.compile(r"^([A-E])-(UI|SENS|FLOW|INTL|VAL|EXEC)-\d{2}$", re.I)


#: Defined in the sibling and re-exported, NOT redeclared here. Two classes of the same name are
#: two different exceptions, and `main`'s `except UsageError` would silently miss whatever the
#: sibling raised — a usage error would surface as a traceback instead of a message.
_story_resolution = _load_sibling("_story_resolution")
UsageError = _story_resolution.UsageError

#: "What module does a changed file belong to" — a pure mapping over paths, split out so this file
#: keeps only the decision of what to RUN for it. Underscore-prefixed aliases because the tests and
#: `paths_for` already know them by those names.
_changed_file_mapping = _load_sibling("_changed_file_mapping")
_src_relative = _changed_file_mapping.src_relative
_tier_relative = _changed_file_mapping.tier_relative
_blocked_reason = _changed_file_mapping.blocked_reason
domain_parts = _changed_file_mapping.domain_parts


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

#: tier -> state -> scope. A state absent from a tier means that tier does not run there.
CAPABILITY_PROFILE: dict[str, dict[str, str]] = {
    "unit": {"quick": "touched", "cb": "module", "sf": "all", "feature": "all"},
    "integration": {"sf": "module", "feature": "all"},
    "e2e": {"feature": "all"},
}

#: No unit tier by design. Writing unit tests in an INT story is not a coverage win — it is the
#: signal that the capability underneath shipped incomplete, and the fix belongs upstream.
STORY_PROFILE: dict[str, dict[str, str]] = {
    "integration": {"quick": "module", "cb": "all", "sf": "all", "feature": "all"},
    "e2e": {"quick": "domain", "cb": "domain", "sf": "all", "feature": "all"},
}

TECH_PROFILES: dict[str, dict[str, dict[str, str]]] = {
    "refactor": {
        "unit": {"quick": "module", "cb": "module", "sf": "all", "feature": "all"},
        "integration": {"cb": "module", "sf": "all", "feature": "all"},
    },
    "bugfix": {
        "unit": {"quick": "touched", "cb": "module", "sf": "all", "feature": "all"},
        "integration": {"cb": "module", "sf": "all", "feature": "all"},
        "e2e": {"sf": "domain", "feature": "all"},
    },
    "tooling": {
        "unit": {"quick": "touched", "cb": "module", "sf": "all", "feature": "all"},
    },
    #: Deliberately empty — an audit produces findings, not code.
    "audit": {},
}


@dataclass(frozen=True)
class Selection:
    tier: str
    scope: str


@dataclass(frozen=True)
class Story:
    story_id: str
    kind: str  # "capability" | "story" | "tech"
    dal: str
    tech_kind: str | None = None
    dal_source: str = ""


# ---------------------------------------------------------------------------
# Story identity and DAL
# ---------------------------------------------------------------------------


def most_critical(letters: list[str]) -> str:
    """DAL-A is the most critical, DAL-E the least — so this is min(), not max().

    Spelled out because the obvious implementation is wrong in the dangerous direction: max()
    over the letters yields 'E' and quietly selects the weakest possible profile.
    """
    if not letters:
        raise UsageError("no DAL letters to compare")
    return sorted(letters)[0]


#: Re-exported so `tests.py` stays the single entry point callers and tests already know.
BASE_SECTION = _story_resolution.BASE_SECTION
SUBSTORY_SECTION = _story_resolution.SUBSTORY_SECTION
INTEGRATION_DESCRIPTION = _story_resolution.INTEGRATION_DESCRIPTION
story_scope_text = _story_resolution.story_scope_text
spanned_capabilities = _story_resolution.spanned_capabilities


def resolve_story(story_id: str, tech_kind: str | None, dal_override: str | None) -> Story:
    if (m := CAP_ID.match(story_id)) is not None:
        dal = dal_override or m.group(1).upper()
        return Story(story_id, "capability", dal, dal_source="capability ID prefix")

    if STORY_ID.match(story_id) is not None:
        if dal_override:
            return Story(story_id, "story", dal_override, dal_source="--dal override")
        caps = spanned_capabilities(story_id)
        letters = [c[0].upper() for c in caps]
        if not letters:
            raise UsageError(
                f"{story_id}: found no capability IDs in its path document, so its DAL cannot "
                "be derived. Pass --dal, or name the spanned capabilities in the document."
            )
        dal = most_critical(letters)
        return Story(story_id, "story", dal, dal_source=f"most critical of {', '.join(caps)}")

    if TECH_ID.match(story_id) is not None:
        if tech_kind is None:
            raise UsageError(
                f"{story_id} is a TECH ticket and must declare a kind: "
                f"--kind {'|'.join(TECH_KINDS)}. A refactor, a bug fix, a tooling change and an "
                "audit need different proof; guessing would pick the wrong one silently."
            )
        if tech_kind not in TECH_KINDS:
            raise UsageError(
                f"unknown --kind {tech_kind!r}; expected one of {', '.join(TECH_KINDS)}"
            )
        # TECH work inherits the DAL of whatever it touches; source files carry no capability
        # annotation today, so this defaults to the baseline and says so rather than pretending.
        dal = dal_override or "C"
        source = (
            "--dal override" if dal_override else "TECH default (baseline; pass --dal to raise)"
        )
        return Story(story_id, "tech", dal, tech_kind=tech_kind, dal_source=source)

    if story_id.upper().startswith("INT-US-"):
        raise UsageError(
            f"{story_id} is an `INT-US` id, and `ADR-005` retired the family. Pass the (sub)story "
            "as `US-21`, or the capability the add-on ships as `C-FLOW-12` — a capability carries "
            "its DAL in its own prefix."
        )
    raise UsageError(
        f"unrecognised story ID {story_id!r}. Expected a capability ID (C-FLOW-12), a (sub)story "
        "(US-21) or a TECH ticket (TECH-020). Refusing to guess a profile."
    )


# ---------------------------------------------------------------------------
# Profile + DAL
# ---------------------------------------------------------------------------


def base_profile(story: Story) -> dict[str, dict[str, str]]:
    if story.kind == "capability":
        return CAPABILITY_PROFILE
    if story.kind == "story":
        return STORY_PROFILE
    assert story.tech_kind is not None
    return TECH_PROFILES[story.tech_kind]


def _forward_fill(scopes: dict[str, str]) -> dict[str, str]:
    """Once a tier starts running it never stops — carry the last scope to the end."""
    out: dict[str, str] = {}
    last: str | None = None
    for state in STATES:
        if state in scopes:
            last = scopes[state]
        if last is not None:
            out[state] = scopes.get(state, last)
    return out


def apply_dal(profile: dict[str, dict[str, str]], dal: str) -> dict[str, dict[str, str]]:
    """DAL shifts the whole profile earlier (more critical) or later (less)."""
    if dal == "A":
        # Mission-critical: no scoping from the first commit point onward.
        return {
            tier: {
                **({"quick": scopes["quick"]} if "quick" in scopes else {}),
                "cb": "all",
                "sf": "all",
                "feature": "all",
            }
            for tier, scopes in profile.items()
        }

    shift = {"B": -1, "C": 0, "D": 1, "E": 2}[dal]
    if shift == 0:
        return profile

    shifted: dict[str, dict[str, str]] = {}
    for tier, scopes in profile.items():
        moved: dict[str, str] = {}
        for state, scope in scopes.items():
            index = STATES.index(state) + shift
            if 0 <= index < len(STATES):
                moved[STATES[index]] = scope
        if moved:
            shifted[tier] = _forward_fill(moved)
    return shifted


def resolve_selections(story: Story, state: str, also: list[str] | None = None) -> list[Selection]:
    """The tiers to run, in tier order. Widening is allowed; narrowing never is."""
    if state not in STATES:
        raise UsageError(f"unknown state {state!r}; expected one of {', '.join(STATES)}")

    profile = apply_dal(base_profile(story), story.dal)
    selections = {
        tier: Selection(tier, scopes[state]) for tier, scopes in profile.items() if state in scopes
    }

    for tier in also or []:
        if tier not in TIERS:
            raise UsageError(f"unknown tier {tier!r}; expected one of {', '.join(TIERS)}")
        # --also can only widen: an already-selected tier keeps the wider of the two scopes.
        if tier not in selections:
            selections[tier] = Selection(tier, "all")

    return [selections[t] for t in TIERS if t in selections]


# ---------------------------------------------------------------------------
# Scope -> pytest paths
# ---------------------------------------------------------------------------


def changed_files(base: str | None = None) -> list[Path]:
    specs = [
        ["git", "diff", "--name-only", "--diff-filter=d"],
        ["git", "diff", "--name-only", "--diff-filter=d", "--cached"],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ]
    if base:
        specs.insert(0, ["git", "diff", "--name-only", "--diff-filter=d", f"{base}...HEAD"])
    found: set[str] = set()
    for spec in specs:
        try:
            proc = subprocess.run(spec, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
        except OSError:
            continue
        if proc.returncode == 0:
            found.update(line.strip() for line in proc.stdout.splitlines() if line.strip())
    return sorted(Path(p) for p in found)


def _scoped_paths(rel: Path, tier_root: Path, scope: str, repo_root: Path) -> set[Path]:
    """The paths one module-relative contributes at this scope."""
    if scope == "touched":
        # tests/<tier>/ mirrors src/specweaver/ and scripts/, so a module's own tests sit
        # alongside it.
        mirror = tier_root / rel.parent
        return {
            p.relative_to(repo_root)
            for p in (repo_root / mirror).glob(f"test_{rel.stem}*.py")
            if p.is_file()
        }
    if scope == "module":
        mirror = tier_root / rel.parent
        return {mirror} if (repo_root / mirror).is_dir() else set()
    if scope == "domain":
        # e2e is organised by top-level domain rather than by full package path. Both candidates are
        # tried because `domain` names a directory whether or not `capabilities/` contains it:
        # `tests/e2e/capabilities/core` today, `tests/e2e/scripts` for the dev tooling that has no
        # capability to sit under.
        parts = domain_parts(rel)
        if not parts:
            # Only reachable if a path is the container itself; `parts[0]` below would raise.
            return set()
        return {
            candidate
            for candidate in (tier_root / "capabilities" / parts[0], tier_root / parts[0])
            if (repo_root / candidate).is_dir()
        }
    raise UsageError(f"unknown scope {scope!r}")


def paths_for(
    tier: str, scope: str, changed: list[Path], repo_root: Path = REPO_ROOT
) -> list[Path]:
    """Resolve one tier + scope to concrete pytest paths that exist on disk."""
    tier_root = Path("tests") / tier
    if scope == "all":
        return [tier_root] if (repo_root / tier_root).is_dir() else []

    relatives = [r for r in (_src_relative(p) for p in changed) if r is not None]
    found: set[Path] = set()

    # A changed test resolves to ITSELF at `touched` scope; the `test_{stem}*.py` glob below cannot
    # serve it, since it would look for `test_test_x*.py`. At every other scope it contributes its
    # module through the same machinery as a source file.

    for rel in (r for r in (_tier_relative(p, tier) for p in changed) if r is not None):
        if scope == "touched":
            if (repo_root / tier_root / rel).is_file():
                found.add(tier_root / rel)
        else:
            relatives.append(rel)

    for rel in relatives:
        found |= _scoped_paths(rel, tier_root, scope, repo_root)

    return sorted(found)


# ---------------------------------------------------------------------------
# Execution  (the refactor rule lives in scripts/_refactor_diff_safety.py)
# ---------------------------------------------------------------------------


def venv_python() -> str:
    for rel in ("Scripts/python.exe", "bin/python"):
        candidate = REPO_ROOT / ".venv" / rel
        if candidate.exists():
            return str(candidate)
    return sys.executable


def pytest_argv(paths: list[Path], workers: str) -> list[str]:
    return [
        venv_python(),
        "-m",
        "pytest",
        *(str(p) for p in paths),
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "-n",
        workers,
        # Free-form distribution. `--dist loadfile` was needed while three tests were
        # parallel-unsafe: a shared event-loop corruption (`nest_asyncio` re-entrancy, fixed in
        # `commons.async_bridge`) and a wall-clock assertion that measured machine load. With
        # those fixed all three tiers pass unpinned, and per-file pinning cost ~20s on e2e alone.
        # If a test needs pinning again, fix the shared state rather than restoring this.
    ]


def run_tier(selection: Selection, paths: list[Path], workers: str) -> int:
    print(
        f"\n{'=' * 72}\n== {selection.tier}  [scope: {selection.scope}]  {', '.join(str(p) for p in paths)}\n{'=' * 72}"
    )
    argv = pytest_argv(paths, workers)
    proc = subprocess.run(argv, cwd=REPO_ROOT, check=False)
    return proc.returncode


def run_selections(
    selections: list[Selection], changed: list[Path], workers: str
) -> list[tuple[Selection, int, int]]:
    """Run each selected tier, treating an empty selection as a failure rather than a pass."""
    results: list[tuple[Selection, int, int]] = []
    for selection in selections:
        paths = paths_for(selection.tier, selection.scope, changed)
        if not paths:
            print(
                f"\nBLOCKED: {selection.tier} at scope '{selection.scope}' selected NO tests: "
                f"{_blocked_reason(selection.tier, changed)}."
            )
            results.append((selection, 1, 0))
            continue
        results.append((selection, run_tier(selection, paths, workers), len(paths)))
    return results


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("state", choices=[*STATES, "matrix"], help="commit point")
    ap.add_argument("story", nargs="?", help="story ID (C-FLOW-12 / US-21 / TECH-020)")
    ap.add_argument("--kind", choices=TECH_KINDS, help="required for TECH tickets")
    ap.add_argument("--dal", choices=DAL_LETTERS, help="override the derived DAL")
    ap.add_argument("--also", help="comma-separated extra tiers (widen only)")
    ap.add_argument("--all", action="store_true", help="run every tier at full scope")
    ap.add_argument("--base", help="git ref that 'changed' is measured against")
    ap.add_argument("-n", "--workers", default="auto", help="xdist workers (default: auto)")
    args = ap.parse_args(argv)

    if args.state == "matrix":
        print(render_matrix())
        return 0

    if not args.story:
        print("error: a story ID is required (the profile depends on it)", file=sys.stderr)
        return 2

    try:
        story = resolve_story(args.story, args.kind, args.dal)
        also = (
            TIERS if args.all else ([s.strip() for s in args.also.split(",")] if args.also else [])
        )
        selections = resolve_selections(story, args.state, list(also))
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        f"\nStory {story.story_id}  ({story.kind}"
        f"{'/' + story.tech_kind if story.tech_kind else ''})"
        f"  DAL-{story.dal}  [{story.dal_source}]  state={args.state}"
    )

    if story.tech_kind == "audit":
        # An explicit no-op, printed as one. A silent zero-tier run reads as a pass.
        print(
            "\nAudit-only TECH ticket: NO test tiers apply by declaration.\n"
            "The deliverable is findings, which become new stories. Nothing was run."
        )
        return 0

    if not selections:
        print(
            f"\nNo tier runs at state '{args.state}' for a DAL-{story.dal} {story.kind} story.\n"
            "That is the profile, not a failure — but nothing was verified, so do not read this "
            "as a pass. Use a higher state, or --also/--all to widen."
        )
        return 0

    changed = changed_files(args.base)

    failed = False
    if story.tech_kind == "refactor" and (touched_tests := refactor_violations(changed)):
        failed = True
        print(
            f"\nBLOCKED: a refactor modified {len(touched_tests)} test file(s). A refactor's "
            "claim is that behaviour did not change, and the proof is that the EXISTING tests "
            "pass unmodified. Modified tests mean either the behaviour moved or the tests were "
            "bent to fit:\n"
        )
        for path in touched_tests:
            print(f"    {path.as_posix()}")
        print("\nIf the behaviour genuinely had to change, this is not a refactor — reclassify it.")

    results = run_selections(selections, changed, args.workers)
    failed = failed or any(code != 0 for _, code, _ in results)

    print(f"\n{'=' * 72}\nSummary — {story.story_id} @ {args.state} (DAL-{story.dal})")
    for selection, code, count in results:
        status = "ok  " if code == 0 else "FAIL"
        print(f"  {status}  {selection.tier:<12} scope={selection.scope:<8} ({count} path(s))")
    return 1 if failed else 0


def render_matrix() -> str:
    lines = []
    for title, profile in (
        ("CAPABILITY story ([A-E]-TOPIC-NN)", CAPABILITY_PROFILE),
        ("(SUB)STORY (US-NN)", STORY_PROFILE),
        *[(f"TECH --kind {k}", p) for k, p in TECH_PROFILES.items()],
    ):
        lines.append(f"\n{title}   [baseline DAL-C]")
        lines.append(f"  {'tier':<14}" + "".join(f"{s:<10}" for s in STATES))
        lines.append("  " + "-" * (14 + 10 * len(STATES)))
        if not profile:
            lines.append("  (no tiers — declares no test coverage by design)")
            continue
        for tier in TIERS:
            if tier in profile:
                row = profile[tier]
                lines.append(f"  {tier:<14}" + "".join(f"{row.get(s, '-'):<10}" for s in STATES))
    lines.append("\nDAL modifier: A = all tiers at full scope from cb; B = one state earlier;")
    lines.append("C = baseline; D = one state later; E = two states later.")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
