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

**Why these baselines are enumerated and not counted.** Three FRs are only partly true (see below), so
the guards for them carry exceptions. Every exception is a *named* path, never a number. A count
absorbs the next violation silently — which is exactly what `test_tach_architectural_boundaries` did
for three months with `fail_count <= 95`, fixed the same day as this file. A named list absorbs
nothing: a fourth stray directory, or a fifth flat e2e file, fails here.

Three FRs describe a tree that is not there, and all three are recorded in the design:

- **FR-5** claims `flow`, `loom` and `config` moved into `core/`. `flow` and `config` did. **There is
  no `loom` anywhere in `src/`** — it is the top-level `sandbox` package (hence
  `test_loom_stack.py`), and it is top-level by design, not under `core/`.
- **FR-7** claims 1:1 parity between the test tiers and `src/`. Four test directories have no `src/`
  counterpart, and one — `tests/unit/graph_store/`, an empty `__init__.py` left behind when
  `graph/core/store` moved — was deleted rather than excepted.
- **FR-8** claims `tests/e2e/` was restructured from a flat tree into capability folders.
  `capabilities/` exists and holds seven of them; the flat tree it was meant to replace is **also
  still there** — four loose test files and five layer-shaped directories.
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


#: FR-7: test directories with no `src/specweaver` counterpart. Named, so a fifth one fails.
#: `scripts` mirrors the repo's `scripts/` rather than `src/`, which is the point of it.
MIRROR_EXCEPTIONS: dict[str, str] = {
    "scripts": "mirrors repo-root scripts/, not src/ — deliberate",
    "alembic": "migration tests; alembic lives at the repo root, not in src/",
    "constitution": "cross-cutting integration tests with no single owning package",
    "engine": "caller-migration integration tests, predate the restructure",
}

#: FR-8: what is left of the pre-restructure flat e2e tree. Named, so a new flat file fails.
E2E_FLAT_REMAINDER_FILES = {
    "test_polyglot_validation_e2e.py",
    "test_logging_e2e.py",
    "test_cli_bootstrap_e2e.py",
    "test_cli_decentralized_e2e.py",
}
E2E_FLAT_REMAINDER_DIRS = {"core", "flow", "interfaces", "sandbox", "scripts"}

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
    """FR-7: 1:1 structural parity, with the four non-mirroring directories named.

    A named exception list is the point. `tests/unit/graph_store/` — an empty `__init__.py` stranded
    when `graph/core/store` moved — was deleted rather than added here, because a leftover is the
    restructure's own unfinished business and not an exception to it.
    """
    src_packages = _packages(SRC_ROOT)
    for tier in ("unit", "integration"):
        tier_root = REPO_ROOT / "tests" / tier
        unmirrored = _packages(tier_root) - src_packages - set(MIRROR_EXCEPTIONS)
        assert not unmirrored, (
            f"tests/{tier}/ has directories with no src/specweaver counterpart: {sorted(unmirrored)}. "
            f"Either mirror them or add each to MIRROR_EXCEPTIONS with the reason."
        )


def test_e2e_is_organised_by_capability_and_the_flat_remainder_cannot_grow() -> None:
    """FR-8: the capability tree exists; what predates it is enumerated and frozen.

    FR-8 claims the flat tree was replaced. Half of it was — `capabilities/` holds real capability
    folders — and the other half is still sitting beside it. This test refuses to call that finished:
    it pins both the new shape and the exact remainder, so the restructure can only continue in one
    direction. A new loose e2e file, or a new layer-shaped directory, fails here.
    """
    e2e = REPO_ROOT / "tests" / "e2e"
    capabilities = e2e / "capabilities"
    assert capabilities.is_dir(), "tests/e2e/capabilities/ is gone — FR-8's new shape with it"
    assert _packages(capabilities), "tests/e2e/capabilities/ holds no capability folders"

    flat_files = {p.name for p in e2e.glob("test_*.py")}
    new_files = flat_files - E2E_FLAT_REMAINDER_FILES
    assert not new_files, (
        f"new flat e2e test file(s) outside a capability folder: {sorted(new_files)}"
    )

    new_dirs = _packages(e2e) - E2E_FLAT_REMAINDER_DIRS - {"capabilities"}
    assert not new_dirs, f"new layer-shaped e2e director(ies): {sorted(new_dirs)}"


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
