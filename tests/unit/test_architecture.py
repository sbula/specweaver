# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import ast
import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType


def test_tach_architectural_boundaries() -> None:
    """
    Ensures that the Tach domain boundaries defined in tach.toml are strictly respected.
    This guarantees that the Layer Cake structure (Base -> Resource -> Capability -> Orchestrator)
    has no forbidden upstream dependencies, replacing the deleted __init__.py manual encapsulation.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    result = subprocess.run(["tach", "check"], cwd=root_dir, capture_output=True, text=True)

    if result.returncode != 0:
        # Count the number of [FAIL] lines
        fail_count = result.stdout.count("[FAIL]") + result.stderr.count("[FAIL]")

        # We are currently in Topic 07 Technical Debt epic.
        # The baseline is exactly 95 violations.
        assert fail_count <= 95, (
            f"Architecture boundary violation detected by tach! "
            f"Expected <= 95 baseline violations, got {fail_count}:\n"
            f"{result.stdout}\n{result.stderr}"
        )


def _interface_path_exists(root_dir: Path, base_parts: list[str], exposed_path: str) -> bool:
    """Check whether an exposed interface path resolves to a real file/dir,
    walking up ancestors to account for namespace packages lacking __init__.py."""
    parts = exposed_path.split(".")
    relative_path = Path(*base_parts) / Path(*parts)
    physical_dir = root_dir / relative_path
    physical_file = physical_dir.with_suffix(".py")

    if physical_dir.exists() or physical_file.exists():
        return True

    base_dir = root_dir / Path(*base_parts)
    current = physical_dir.parent
    while current != base_dir and current != root_dir:
        if current.with_suffix(".py").exists():
            return True
        if current.is_dir() and (current / "__init__.py").exists():
            return True
        current = current.parent
    return False


def test_tach_interfaces_map_to_valid_namespaces() -> None:
    """
    Edge Case: Prevention of Silent Namespace Ignore by Tach.
    Since __init__.py files were deleted (SF-4), these directories became Implicit Namespace Packages.
    Tach might silently skip checking a route if the dir has no __init__.py and doesn't map correctly.
    We formally assert that every path declared in [[interfaces]] exists as a physical directory or file.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    tach_path = root_dir / "tach.toml"
    assert tach_path.exists()

    with tach_path.open("rb") as f:
        config = tomllib.load(f)

    for interface in config.get("interfaces", []):
        from_bases = interface.get("from", [])
        if not from_bases:
            # Fallback for old tach syntax if any
            module_base = interface.get("module")
            if module_base:
                from_bases = [module_base]

        for module_base in from_bases:
            base_parts = module_base.split(".")
            if base_parts and base_parts[0] == "specweaver":
                base_parts.insert(0, "src")
            for exposed_path in interface.get("expose", []):
                path_exists = _interface_path_exists(root_dir, base_parts, exposed_path)
                assert path_exists, (
                    f"Tach explicit boundary violation risk! "
                    f"The interface {exposed_path} for module {module_base} listed in tach.toml does not map "
                    f"to any physical directory or file in the filesystem. Tach may silently ignore this."
                )


def test_tach_keeps_runner_soft_deprecated() -> None:
    """
    Integration Regression Guard:
    Ensures that the legacy 'runner' module is explicitly omitted from the 'src.specweaver.assurance.validation'
    expose list in tach.toml. This prevents accidental soft-deprecation regressions where a future
    developer might silently re-expose it, bypassing the architectural deprecation boundary.
    """
    root_dir = Path(__file__).resolve().parent.parent.parent
    tach_path = root_dir / "tach.toml"
    assert tach_path.exists()

    with tach_path.open("rb") as f:
        config = tomllib.load(f)

    for interface in config.get("interfaces", []):
        from_bases = interface.get("from", [])
        if "src.specweaver.assurance.validation" in from_bases:
            exposed = interface.get("expose", [])
            assert "runner" not in exposed, (
                "CRITICAL: The 'runner' module must remain soft-deprecated! "
                "Do NOT add 'runner' to the validation interfaces in tach.toml."
            )


def _load_check_coupling() -> ModuleType:
    """`scripts/` isn't an importable package; load `check_coupling.py` by path
    (same pattern as `tests/unit/scripts/test_check_coupling.py`)."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    path = root_dir / "scripts" / "check_coupling.py"
    spec = importlib.util.spec_from_file_location("check_coupling", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_coupling"] = module
    spec.loader.exec_module(module)
    return module


def test_core_config_has_no_cross_domain_runtime_imports() -> None:
    """TECH-001 SF-04 regression guard, proving FR-9 (Eliminate `core.config` Circular
    Dependencies).

    `core.config`'s own `context.yaml` declares `consumes: []` (a pure leaf), but two files
    (`db_bootstrap.py`, `settings_loader.py`) imported `infrastructure.llm`/`core.flow`/`workspace`
    directly, creating three separate `tach.toml`-declared circular dependencies -- only two of
    which (llm, flow) were ever named in TECH-001/TECH-022; the third (`workspace`) was found
    during this SF's own Red/Blue review. Both files moved to `core.config.bootstrap` (an
    `adapter`-archetype sub-boundary explicitly allowed to touch those domains) to fix it. This
    pins `core.config` itself -- excluding `bootstrap/` and `interfaces/`, both separately-scoped
    boundaries -- to never regrow a runtime import of those three domains.

    Uses `check_coupling.py`'s own `iter_runtime_imports` so `if TYPE_CHECKING:`-guarded imports
    are excluded the same way that script already had to fix for itself (see its test file): a
    check that flags correct code (a TYPE_CHECKING-only import breaks no cycle at runtime) is a
    check that gets suppressed.
    """
    check_coupling = _load_check_coupling()
    root_dir = Path(__file__).resolve().parent.parent.parent
    config_dir = root_dir / "src" / "specweaver" / "core" / "config"
    assert config_dir.is_dir(), f"expected {config_dir} to exist"

    forbidden_prefixes = (
        "specweaver.infrastructure.llm",
        "specweaver.core.flow",
        "specweaver.workspace",
    )

    def _imported_names(node: ast.Import | ast.ImportFrom) -> list[str]:
        if isinstance(node, ast.Import):
            return [alias.name for alias in node.names]
        return [node.module or ""]

    violations: list[str] = []
    for path in sorted(config_dir.glob("*.py")):  # top-level only: skips bootstrap/, interfaces/
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in check_coupling.iter_runtime_imports(tree):
            for name in _imported_names(node):
                if name.startswith(forbidden_prefixes):
                    violations.append(f"{path.name}: {name}")

    assert not violations, (
        "core.config regrew a cross-domain circular dependency (TECH-001 SF-04 regression): "
        f"{violations}"
    )


# ---------------------------------------------------------------------------
# TECH-001's architectural claims.
#
# Each was true whenever someone last looked and asserted by nothing until now.
# The logic takes a root so every invariant can be driven against a synthetic
# tree as well as the real one: an absence proof that has never been observed
# failing is indistinguishable from one that CANNOT fail, and mutating the real
# tree to find out breaks collection instead of failing an assertion.
# ---------------------------------------------------------------------------

SRC_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "specweaver"

#: Domain packages the config layer must not reach into. Prefixes, so submodules count.
DOMAIN_PREFIXES = (
    "specweaver.infrastructure",
    "specweaver.core.flow",
    "specweaver.workspace",
    "specweaver.graph",
    "specweaver.assurance",
    "specweaver.workflows",
    "specweaver.sandbox",
)


def domain_cli_modules(root: Path) -> list[str]:
    """Dotted path of every domain-local CLI, read from the tree rather than listed.

    A hard-coded set passes the day someone deletes the module AND its entry, which is the failure
    this exists to catch. `interfaces/cli/` (the root app package) is excluded — it is the thing
    the others are mounted ON.
    """
    return sorted(
        p.relative_to(root).as_posix().removesuffix("/cli.py").replace("/", ".")
        for p in root.rglob("interfaces/cli.py")
        if "interfaces/cli/" not in p.relative_to(root).as_posix()
    )


def unmounted_domain_clis(root: Path) -> list[str]:
    """Domain CLIs that exist on disk but are never registered on the root app."""
    main = root / "interfaces" / "cli" / "main.py"
    src = main.read_text(encoding="utf-8") if main.is_file() else ""
    return [m for m in domain_cli_modules(root) if f"specweaver.{m}.cli" not in src]


def sandbox_layer_violations(root: Path) -> tuple[list[str], list[str]]:
    """`(revived flat directories, feature directories carrying no layer)`."""
    sandbox = root / "sandbox"
    if not sandbox.is_dir():
        return [], []
    revived = [n for n in ("atoms", "tools", "commons") if (sandbox / n).is_dir()]
    features = [d for d in sandbox.iterdir() if d.is_dir() and not d.name.startswith(("_", "."))]
    layerless = [
        d.name
        for d in features
        if d.name not in revived
        and not any((d / layer).is_dir() for layer in ("core", "interfaces"))
    ]
    return revived, sorted(layerless)


def config_orchestration_offenders(root: Path) -> list[str]:
    """Domain imports in `core/config/`'s own modules — `bootstrap/` and `interfaces/` excluded.

    Whole-module, not import-time only: a domain import deferred inside a function is still a
    domain dependency, and this repo's cycle gate explicitly rejects deferring an import as a way
    to break one. That is the opposite scoping to `config_bootstrapping_offenders`, deliberately.

    Only ABSOLUTE imports are matched. A parent-relative one (`from ...workspace import store`)
    would slip past — and cannot occur: ruff's TID252 bans parent-relative imports repo-wide, and
    a sibling-relative import cannot reach out of `core/config/` at all. Verified, not assumed.
    Relaxing TID252 would silently open this hole.
    """
    offenders: list[str] = []
    for path in sorted((root / "core" / "config").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Import | ast.ImportFrom):
                continue
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            offenders.extend(f"{path.name}: {n}" for n in names if n.startswith(DOMAIN_PREFIXES))
    return offenders


#: Callee names that mean a module *opens* a database rather than describing one. Matched as
#: substrings of the called name at MODULE scope only. Deliberately not "any module-level call":
#: measured first, and `logging.getLogger`, `re.compile` and `frozenset` are all legitimate here.
BOOTSTRAP_CALL_HINTS = ("engine", "session", "database", "connect", "create_all", "migrat")


def _callee_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    return func.attr if isinstance(func, ast.Attribute) else ""


def _import_time_statements(body: list[ast.stmt]) -> list[ast.stmt]:
    """Statements that run when the module is imported.

    Class bodies count — `engine = create_engine(...)` as a class attribute executes at import.
    Function and method bodies do not: offering a way to open a database is not opening one, and
    `ast.walk` over the whole module conflates the two. A control test pins the difference.
    """
    out: list[ast.stmt] = []
    for node in body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        out.extend(_import_time_statements(node.body) if isinstance(node, ast.ClassDef) else [node])
    return out


def config_bootstrapping_offenders(root: Path) -> list[str]:
    """Import-time database work in `core/config/`'s own modules.

    Separate from the import check, and not implied by it: a module can bootstrap a database using
    nothing but stdlib and SQLAlchemy and still be orchestrating. `bootstrap/` is where that work
    legitimately lives, so importing it from a config module counts too.
    """
    offenders: list[str] = []
    for path in sorted((root / "core" / "config").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in _import_time_statements(tree.body):
            if isinstance(node, ast.Import | ast.ImportFrom):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                offenders += [f"{path.name}: imports {n}" for n in names if "bootstrap" in n]
                continue
            for call in (n for n in ast.walk(node) if isinstance(n, ast.Call)):
                name = _callee_name(call)
                if any(hint in name.lower() for hint in BOOTSTRAP_CALL_HINTS):
                    offenders.append(f"{path.name}: calls {name}() at import time")
    return offenders


def llm_database_coupling(root: Path) -> list[str]:
    """LLM entry points that reference `Database` as a real name.

    Resolved through the AST rather than by substring: `"Database" in source` also fires on
    `DatabaseError` and on the word appearing in a comment. A false positive here fails loudly and
    is survivable; the reason to tighten it is that the check is about to carry an FR citation, and
    a proof that reports on prose is not a proof.
    """
    llm = root / "infrastructure" / "llm"
    coupled = []
    for f in (llm / "factory.py", llm / "router.py"):
        if not f.is_file():
            continue
        names = {
            n.id if isinstance(n, ast.Name) else n.attr
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
            if isinstance(n, ast.Name | ast.Attribute)
        }
        aliases = {
            a.name
            for n in ast.walk(ast.parse(f.read_text(encoding="utf-8")))
            if isinstance(n, ast.Import | ast.ImportFrom)
            for a in n.names
        }
        if "Database" in names | aliases:
            coupled.append(f.name)
    return coupled


#: What the tree actually has. A floor, not an equality: adding a domain CLI is progress and must
#: not go red, losing one is decentralisation running backwards and must. The previous value was 5,
#: which let four domains re-centralise in silence.
DOMAIN_CLI_COUNT = 9


def test_the_invariants_below_are_reading_the_real_tree() -> None:
    """Every proof in this section is an ABSENCE proof, and absence is what a missing tree returns.

    Measured, not feared: called with a root that does not exist, `unmounted_domain_clis`,
    `sandbox_layer_violations`, `config_orchestration_offenders` and `config_bootstrapping_offenders`
    all report perfectly clean. The synthetic probes further down prove the LOGIC; not one of them
    touches `SRC_ROOT`, so only this test proves the live invocation is pointed at anything at all.

    Without it a moved test file or a renamed `src/` layout turns four proofs into ornaments,
    silently, while the FR ledger they back goes on reporting green.
    """
    assert (SRC_ROOT / "sandbox").is_dir(), "sandbox_layer_violations is inspecting nothing"
    assert [d for d in (SRC_ROOT / "sandbox").iterdir() if d.is_dir()], "no sandbox features found"
    assert list((SRC_ROOT / "core" / "config").glob("*.py")), "config offender scans see no modules"
    for entry in ("factory.py", "router.py"):
        assert (SRC_ROOT / "infrastructure" / "llm" / entry).is_file(), f"llm/{entry} not found"


def test_cli_commands_live_in_their_own_domains() -> None:
    """CLI commands sit in the domain that owns them, not in one central module.

    Proves: TECH-001 FR-4.
    """
    modules = domain_cli_modules(SRC_ROOT)

    assert len(modules) >= DOMAIN_CLI_COUNT, (
        f"CLI has re-centralised: {len(modules)} domains own their commands, "
        f"was {DOMAIN_CLI_COUNT} — {modules}"
    )


def test_every_domain_cli_is_mounted_on_the_root_app() -> None:
    """A domain CLI nobody wired up is dead code that looks like a feature.

    Proves: TECH-001 FR-5.
    """
    assert unmounted_domain_clis(SRC_ROOT) == []


def test_sandbox_is_grouped_by_feature_not_by_layer() -> None:
    """The flat atoms/tools/commons split became one directory per feature.

    Asserts the ABSENCE of the old split plus at least one layer directory per feature — not "every
    feature has both", which is false for three of them (`execution` and `language` are core-only,
    `web` interfaces-only) and would fail against correct code.

    Proves: TECH-001 FR-6.
    """
    revived, layerless = sandbox_layer_violations(SRC_ROOT)

    assert revived == [], f"sandbox regrew the flat layer split: {revived}"
    assert layerless == [], f"sandbox feature(s) with no core/ or interfaces/ layer: {layerless}"


def test_config_modules_hold_no_domain_orchestration() -> None:
    """Configuration declares; it does not orchestrate.

    Two halves, because neither implies the other: a module can reach into a domain without opening
    anything, and it can open a database using only stdlib and SQLAlchemy without importing a
    domain. The docstring used to claim both while only the first was checked.

    Distinct from the circular-import guard above on purpose: that one is about cycles, this about
    where control flow lives. One test cited for both loses a proof the day either is refactored.

    Proves: TECH-001 FR-7.
    """
    assert config_orchestration_offenders(SRC_ROOT) == []
    assert config_bootstrapping_offenders(SRC_ROOT) == []


def test_llm_entry_points_take_settings_not_a_database() -> None:
    """The LLM domain accepts pure settings by injection and knows nothing of project state.

    Proves: TECH-001 FR-8.
    """
    assert llm_database_coupling(SRC_ROOT) == []
    assert "SpecWeaverSettings" in (SRC_ROOT / "infrastructure" / "llm" / "factory.py").read_text(
        encoding="utf-8"
    ), "create_llm_adapter no longer takes SpecWeaverSettings — FR-8's DI seam is gone"


# --- the same invariants, driven against synthetic trees -------------------
# Without these, each assertion above is an absence proof nobody has seen fail:
# the easiest vacuous test to write, and the hardest to spot in review.


def _plant(root: Path, rel: str, body: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_an_unmounted_domain_cli_is_detected(tmp_path: Path) -> None:
    _plant(tmp_path, "graph/interfaces/cli.py", "graph_app = 1\n")
    _plant(tmp_path, "workspace/project/interfaces/cli.py", "workspace_cli = 1\n")
    _plant(tmp_path, "interfaces/cli/main.py", "from specweaver.graph.interfaces.cli import x\n")

    assert unmounted_domain_clis(tmp_path) == ["workspace.project.interfaces"]


def test_the_root_cli_package_is_not_counted_as_a_domain(tmp_path: Path) -> None:
    """`interfaces/cli/cli.py` would otherwise look like a domain mounting itself."""
    _plant(tmp_path, "interfaces/cli/cli.py")
    _plant(tmp_path, "graph/interfaces/cli.py")

    assert domain_cli_modules(tmp_path) == ["graph.interfaces"]


def test_a_revived_flat_sandbox_directory_is_detected(tmp_path: Path) -> None:
    _plant(tmp_path, "sandbox/atoms/thing.py")
    _plant(tmp_path, "sandbox/git/core/atom.py")

    revived, _ = sandbox_layer_violations(tmp_path)

    assert revived == ["atoms"]


def test_a_sandbox_feature_with_no_layer_is_detected(tmp_path: Path) -> None:
    _plant(tmp_path, "sandbox/git/core/atom.py")
    _plant(tmp_path, "sandbox/loose/thing.py")

    _, layerless = sandbox_layer_violations(tmp_path)

    assert layerless == ["loose"]


def test_a_domain_import_planted_in_a_config_module_is_detected(tmp_path: Path) -> None:
    _plant(tmp_path, "core/config/paths.py", "from specweaver.workspace import store\n")

    assert config_orchestration_offenders(tmp_path) == ["paths.py: specweaver.workspace"]


def test_config_submodule_packages_are_out_of_scope(tmp_path: Path) -> None:
    """`bootstrap/` and `interfaces/` are separately-scoped boundaries, allowed to reach domains."""
    _plant(tmp_path, "core/config/paths.py", "import os\n")
    _plant(tmp_path, "core/config/bootstrap/db.py", "from specweaver.workspace import store\n")

    assert config_orchestration_offenders(tmp_path) == []


def test_a_database_reference_planted_in_the_llm_factory_is_detected(tmp_path: Path) -> None:
    _plant(tmp_path, "infrastructure/llm/factory.py", "from x import Database\n")
    _plant(tmp_path, "infrastructure/llm/router.py", "settings_provider = None\n")

    assert llm_database_coupling(tmp_path) == ["factory.py"]


def test_a_word_that_merely_contains_database_is_not_a_coupling(tmp_path: Path) -> None:
    """`DatabaseError` and a comment both satisfy a substring match. Neither is a coupling."""
    _plant(
        tmp_path,
        "infrastructure/llm/factory.py",
        "# no Database is used here\nfrom x import DatabaseError\n\nDatabaseError\n",
    )
    _plant(tmp_path, "infrastructure/llm/router.py", "settings_provider = None\n")

    assert llm_database_coupling(tmp_path) == []


def test_import_time_database_work_in_a_config_module_is_detected(tmp_path: Path) -> None:
    _plant(tmp_path, "core/config/paths.py", "engine = create_engine('sqlite://')\n")

    assert config_bootstrapping_offenders(tmp_path) == [
        "paths.py: calls create_engine() at import time"
    ]


def test_a_config_module_importing_bootstrap_is_detected(tmp_path: Path) -> None:
    """`bootstrap/` is where opening a database legitimately lives — reaching for it is the tell."""
    _plant(tmp_path, "core/config/paths.py", "from specweaver.core.config.bootstrap import db\n")

    assert config_bootstrapping_offenders(tmp_path) == [
        "paths.py: imports specweaver.core.config.bootstrap"
    ]


def test_ordinary_module_level_constants_are_not_bootstrapping(tmp_path: Path) -> None:
    """The reason this is a hint list and not "any module-level call".

    Measured against the six real config modules before the rule was written: every one of these
    appears there, and a blanket rule would fail against correct code.
    """
    _plant(
        tmp_path,
        "core/config/paths.py",
        "import logging, re\n\n"
        "logger = logging.getLogger(__name__)\n"
        "_RE = re.compile(r'^x$')\n"
        "_NAMES = frozenset({'a', 'b'})\n",
    )

    assert config_bootstrapping_offenders(tmp_path) == []


def test_database_work_inside_a_function_is_not_import_time(tmp_path: Path) -> None:
    """Only MODULE scope counts — a config module may still *offer* a way to open a database."""
    _plant(
        tmp_path,
        "core/config/database.py",
        "def make_engine():\n    return create_engine('sqlite://')\n",
    )

    assert config_bootstrapping_offenders(tmp_path) == []
