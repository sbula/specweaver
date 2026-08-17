# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The macro-domain layout: where every package sits, and which old places are gone.

Proves: C-EXEC-03 FR-1, C-EXEC-03 FR-2, C-EXEC-03 FR-3, C-EXEC-03 FR-4, C-EXEC-03 FR-5
Proves: C-EXEC-03 FR-6, C-EXEC-03 FR-7, C-EXEC-03 FR-8, C-EXEC-03 FR-9, C-EXEC-03 FR-10
Proves: C-EXEC-03 FR-11, C-EXEC-03 FR-12

Cited under `specweaver-dev` §3.2c, from `INT-US-01-SF02-MIG`. `C-EXEC-03` is a restructure: twelve
FRs, each of the form "directory X now lives at Y". None had a test, and there is a reason for that
— a completed move leaves nothing running to observe. What it does leave is a **shape**, and a shape
is falsifiable: put a package back where it was and this file fails.

**Why any exception here is a named path and never a number.** A count absorbs the next violation
silently — which is exactly what `test_tach_architectural_boundaries` did for three months with
`fail_count <= 95`, fixed the same day as this file. A named list absorbs nothing.

One FR still describes a tree that is not there, and it is recorded in the design:

- **FR-5** claims `flow`, `loom` and `config` moved into `core/`. `flow` and `config` did. **There is
  no `loom` anywhere in `src/`** — it is the top-level `sandbox` package (hence
  `test_loom_stack.py`), and it is top-level by design, not under `core/`.

**FR-7 is closed.** It claims 1:1 parity between the test tiers and `src/`. Of the four directories
that had no `src/` counterpart, `tests/integration/constitution/` and `tests/integration/engine/`
turned out to be ordinary tests of `workspace.project` and `core.flow.handlers` filed under invented
top-level names — they were moved to their mirrors, not excused. A fifth,
`tests/unit/graph_store/`, was an empty `__init__.py` stranded when `graph/core/store` moved, and was
deleted. What remains is `scripts` and `alembic`, and both mirror a repo-root directory that really
exists rather than nothing at all.

**FR-8 is closed.** It claimed `tests/e2e/` moved from a flat tree into capability folders, and for a
while both existed side by side: `capabilities/` with seven domains, and beside it four loose test
files plus five layer-shaped directories. Sixteen files moved on 2026-08-17, two capability folders
were added (`interfaces`, `sandbox`), and `E2E_FLAT_REMAINDER_FILES` is now empty — a loose file at the
tier root is a failure rather than a new exception. `tests/e2e/scripts/` stays and is not a leftover:
it drives the repo's own dev tooling, which has no product capability to belong to.

Two side effects are worth knowing, because they are the reason a restructure is not just `git mv`:

- `test_cli_colour_e2e.py` computed the repo root as `parents[3]` and handed it to a subprocess as
  `cwd`. One directory deeper, that resolves to `tests/e2e/`. It now walks up to the directory holding
  `pyproject.toml`, so position in the tree stops being a hidden dependency.
- The old `tests/e2e/interfaces/` had no `__init__.py`; its destination does. Inside a package,
  `from tests.rendering import shows` reclassifies as first-party, so two files needed their import
  blocks regrouped. A file's lint profile is not invariant under moving it.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_ROOT = REPO_ROOT / "src" / "specweaver"

#: FR-1..FR-6: each macro-domain and the packages it took in. `sandbox` is deliberately absent — see
#: the module docstring on FR-5's `loom` clause.
MACRO_DOMAINS: dict[str, set[str]] = {
    "workflows": {"drafting", "planning", "implementation", "review"},
    "assurance": {"validation", "standards"},
    "workspace": {"project", "context"},
    "interfaces": {"cli", "api"},
    "core": {"flow", "config"},
    "infrastructure": {"llm"},
}

#: FR-9: the top-level names these packages used to have. None may be a package or an import root
#: again. `context` and `config` are omitted deliberately: `specweaver.core.config` legitimately
#: starts with neither, and a bare `specweaver.context` cannot be told from `...core.context` by a
#: prefix match, so the import sweep below anchors on the module boundary instead.
LEGACY_TOP_LEVEL = (
    "drafting",
    "planning",
    "implementation",
    "review",
    "validation",
    "standards",
    "project",
    "cli",
    "api",
    "flow",
    "loom",
    "llm",
)

_LEGACY_ROOTS = {f"specweaver.{name}" for name in LEGACY_TOP_LEVEL}


def _imported_modules(tree: ast.Module) -> set[str]:
    """Every module name this file imports, from both statement forms.

    Read from the AST rather than matched in the text, because the text contains *fixture* imports:
    `test_runner_architecture.py` writes `from specweaver.llm import Client` into a temp file inside a
    triple-quoted string to exercise the forbids checker. A regex over source counts that as a real
    import of a package deleted three restructures ago; the AST does not see inside string literals.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
    return names


#: FR-7: the only test directories that do not mirror `src/specweaver`, and both mirror something
#: else that genuinely exists — a repo-root directory. Neither is a leftover, and the list is named
#: rather than counted so a third fails here.
#:
#: `constitution` and `engine` used to sit alongside these and were **not** in this category: they
#: held ordinary tests of `workspace.project` and `core.flow.handlers`, filed under invented
#: top-level names. They were moved to their mirrors rather than excused.
MIRROR_EXCEPTIONS: dict[str, str] = {
    "scripts": "mirrors repo-root scripts/ — the dev gates, which are not product code",
    "alembic": "mirrors repo-root alembic/; the migration it loads is not an importable package",
}

#: FR-8: nothing outside a capability folder. The set is empty and stays empty — every e2e test lives
#: under `tests/e2e/capabilities/<domain>/`, so a loose file at the tier root is a failure, not an
#: exception to be added here.
E2E_FLAT_REMAINDER_FILES: set[str] = set()

#: FR-8's one permanent exception, and it is not a leftover. `tests/e2e/scripts/` drives the repo's own
#: dev tooling — the mutation corpus CLI and the nightly timer. Those are not product capabilities and
#: have no capability folder to belong to, which is the same reason `scripts` is excused from the
#: src-mirror check above.
E2E_NON_CAPABILITY_DIRS = {"scripts"}

_SKIP = {"__pycache__", ".pytest_cache"}


def _packages(root: Path) -> set[str]:
    return {d.name for d in root.iterdir() if d.is_dir() and d.name not in _SKIP}


def test_every_macro_domain_holds_the_packages_it_took_in() -> None:
    """FR-1..FR-4, FR-6, and the surviving half of FR-5."""
    for domain, packages in MACRO_DOMAINS.items():
        domain_dir = SRC_ROOT / domain
        assert domain_dir.is_dir(), f"macro-domain '{domain}' is missing from src/specweaver/"
        missing = packages - _packages(domain_dir)
        assert not missing, f"{domain}/ is missing {sorted(missing)}"


def test_the_loom_package_is_the_top_level_sandbox() -> None:
    """FR-5's third clause, corrected.

    The FR says `loom` moved into `core/`. It did not: there is no `loom` package in the tree at all.
    The Loom is `src/specweaver/sandbox/`, top-level, and `tests/integration/sandbox/test_loom_stack.py`
    is what exercises it. Asserting the FR as written would fail; asserting nothing would let a future
    reader believe a `core/loom` exists somewhere.
    """
    assert not (SRC_ROOT / "core" / "loom").exists(), (
        "a core/loom package appeared — FR-5 as written would now be satisfiable, so this test and "
        "the design's FR-5 note both need revisiting"
    )
    assert not (SRC_ROOT / "loom").exists(), "a top-level loom package appeared"
    assert (SRC_ROOT / "sandbox").is_dir(), "the Loom (sandbox/) is missing from src/specweaver/"


def test_no_legacy_top_level_package_came_back() -> None:
    """FR-1..FR-6: the places these packages used to live are empty."""
    present = _packages(SRC_ROOT)
    revived = present & set(LEGACY_TOP_LEVEL)
    assert not revived, (
        f"pre-restructure top-level package(s) back in src/specweaver/: {sorted(revived)}"
    )


def test_no_module_imports_a_pre_restructure_path() -> None:
    """FR-9: every import resolves inside the new domains.

    Measured at the time of writing: zero occurrences across `src/` and `tests/`. That is the whole
    claim of FR-9, and it is the one FR of the twelve that was already fully true.
    """
    offenders: list[str] = []
    scanned = 0
    for root in (REPO_ROOT / "src", REPO_ROOT / "tests"):
        for path in root.rglob("*.py"):
            if any(part in _SKIP for part in path.parts):
                continue
            scanned += 1
            for module in _imported_modules(ast.parse(path.read_text(encoding="utf-8"))):
                if module in _LEGACY_ROOTS or any(
                    module.startswith(f"{root_name}.") for root_name in _LEGACY_ROOTS
                ):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {module}")

    assert scanned > 1000, (
        f"the sweep only reached {scanned} files; it is pointed at the wrong tree"
    )
    assert not offenders, "imports still name pre-restructure paths:\n" + "\n".join(offenders)


def test_the_unit_and_integration_tiers_mirror_src() -> None:
    """FR-7: 1:1 structural parity, with the two genuine non-mirrors named.

    A named exception list is the point, and the bar for joining it is that the directory mirrors
    something real. Three of the original five did not clear it: `constitution` and `engine` held
    ordinary tests of `workspace.project` and `core.flow.handlers` under invented top-level names and
    were moved to their mirrors; `graph_store` was an empty `__init__.py` stranded when
    `graph/core/store` moved and was deleted. A leftover is the restructure's own unfinished business,
    not an exception to it.

    `scripts` and `alembic` remain because each mirrors a repo-root directory — the dev gates, and the
    migrations, neither of which is product code under `src/`.
    """
    src_packages = _packages(SRC_ROOT)
    for tier in ("unit", "integration"):
        tier_root = REPO_ROOT / "tests" / tier
        unmirrored = _packages(tier_root) - src_packages - set(MIRROR_EXCEPTIONS)
        assert not unmirrored, (
            f"tests/{tier}/ has directories with no src/specweaver counterpart: {sorted(unmirrored)}. "
            f"Either mirror them or add each to MIRROR_EXCEPTIONS with the reason."
        )


def test_every_e2e_test_lives_in_a_capability_folder() -> None:
    """FR-8: `tests/e2e/` is organised by capability, with nothing left beside it.

    FR-8 said the flat tree was replaced by capability folders. Until 2026-08-17 both were present:
    `capabilities/` held seven domains, and the tree it was meant to replace still sat next to it —
    four loose test files and five layer-shaped directories (`core`, `flow`, `interfaces`, `sandbox`,
    `scripts`). Sixteen files moved; the remainder is now empty and the guard is unconditional.

    The one permanent exception is `tests/e2e/scripts/`, and it is not a leftover: it drives the repo's
    own dev tooling, which has no product capability to belong to. `scripts` is excused from the
    src-mirror check above for exactly the same reason.

    Note what this refuses. A loose file at the tier root is a failure rather than something to add to
    an exception list — the point of finishing a restructure is that the escape hatch closes behind it.
    """
    e2e = REPO_ROOT / "tests" / "e2e"
    capabilities = e2e / "capabilities"
    assert capabilities.is_dir(), "tests/e2e/capabilities/ is gone — FR-8's new shape with it"
    assert _packages(capabilities), "tests/e2e/capabilities/ holds no capability folders"

    flat_files = {p.name for p in e2e.glob("test_*.py")} - E2E_FLAT_REMAINDER_FILES
    assert not flat_files, (
        f"e2e test file(s) outside a capability folder: {sorted(flat_files)}. "
        f"Move each into tests/e2e/capabilities/<domain>/ — do not except it here."
    )

    stray_dirs = _packages(e2e) - E2E_NON_CAPABILITY_DIRS - {"capabilities"}
    assert not stray_dirs, (
        f"layer-shaped e2e director(ies) beside capabilities/: {sorted(stray_dirs)}"
    )

    #: Every capability folder must mirror a src macro-domain, so "by capability" cannot drift back
    #: into "by whatever seemed handy".
    unknown = _packages(capabilities) - _packages(SRC_ROOT)
    assert not unknown, (
        f"capability folder(s) with no src/specweaver counterpart: {sorted(unknown)}"
    )


def test_the_documentation_tree_is_where_the_restructure_left_it() -> None:
    """FR-11, FR-12: design docs under `docs/architecture/`, roadmap at `docs/roadmap/`, no proposals."""
    assert (REPO_ROOT / "docs" / "architecture").is_dir()
    assert (REPO_ROOT / "docs" / "roadmap").is_dir()
    assert not (REPO_ROOT / "docs" / "proposals").exists(), (
        "docs/proposals/ is back; FR-11 and FR-12 moved everything out of it"
    )


def test_tach_describes_the_macro_domains() -> None:
    """FR-10: the boundary config names the domains the tree actually has.

    `C-EXEC-01` FR-1 proves `tach.toml` is internally consistent — every declared path resolves. This
    is the other direction: that the six macro-domains are each *represented* there, so the config
    describes this tree rather than a previous one.
    """
    tach = (REPO_ROOT / "tach.toml").read_text(encoding="utf-8")
    for domain in MACRO_DOMAINS:
        assert f"specweaver.{domain}" in tach, (
            f"tach.toml never mentions macro-domain '{domain}' — its boundaries describe some other tree"
        )
