# Hard Dependency Rules

What each module may import, and what it must not. This page does not list the rules: a copy here
went stale twice. It says where they live and which check keeps each one true. Picture:
[Module Dependency Graph](module_dependency_graph.md). Field semantics:
[Context YAML Specification](context_yaml_spec.md).

## Where the rules live

| Rule | Lives in |
|---|---|
| The modules, and which module may import which | `tach.toml`: each `[[modules]]` entry and its `depends_on` |
| What a module offers to others | `tach.toml`: its `[[interfaces]]` `expose` list |
| A module's archetype, its consumes and its forbids | the module's `context.yaml` |
| Violations that are known and kept on purpose | [Known Boundary Violations](../06_lessons_and_future/known_boundary_violations.md) |

## The settings that make the check strict

| Setting in `tach.toml` | Effect |
|---|---|
| `exact = true` | a declared dependency that no import uses fails |
| `root_module = "forbid"` | a file in no module fails |
| `ignore_type_checking_imports = false` | an import under `if TYPE_CHECKING:` counts |
| `forbid_circular_dependencies = true` | an import loop between modules fails |

No dependency is marked `deprecated` (reported but allowed), and none may be added (`TECH-081`
FR-20).

## The checks

| Check | Keeps true |
|---|---|
| the `tach` gate in `scripts/quality.py`, and `tests/unit/test_architecture.py::test_tach_architectural_boundaries` | `tach check` passes: every import follows `tach.toml` |
| `tests/unit/test_tach_sees_every_module.py` | the four settings above; every file is in a module; no `deprecated` edge |
| `tests/unit/test_manifests_match_tach.py` | each `depends_on` edge is covered by a `consumes` entry; no manifest forbids what tach allows |
| `tests/unit/test_manifests_are_complete.py` | each manifest has `name`, `purpose` and `archetype`, and each name in its `exposes` exists |
| `tests/unit/test_pure_modules_do_no_io.py` | a `pure-logic` or `contract` module reads no files and runs no processes, except files the ledger names |
