# Walkthrough: TECH-077 SF-02 — The run builder

- **Design**: [TECH-077_design.md](TECH-077_design.md)
- **Plan**: [TECH-077_sf02_implementation_plan.md](TECH-077_sf02_implementation_plan.md)

## CB-1 — FR-4 (one project) and FR-1 (the builder's parts)

### What changed

- New `tach` module `specweaver.interfaces.run_setup` (`context.yaml`, no `__init__.py`), linked to
  `core.flow`, `core.config`, `core.config.bootstrap`, `workspace`, `workspace.project`,
  `workspace.analyzers`, `assurance.standards`, `infrastructure.llm`; it forbids the CLI and the API.
- `run_setup/builder.py`:
  - `project_for(db, root, *, named=None)`: the named project, else the one registered at the
    folder, else (no folder) the active one; an unregistered folder raises `UnknownProjectError`
    naming it and `sw init` (decision 1).
  - `RunRequest` and `build_run` / `build_run_sync`: sections, rule file, standards (async), settings
    once (a broken file raises; an unknown project gives none), router and `config` only for a
    model step (`models`: `required` / `optional` / `none`, decision 2), topology slice.
- `workspace/store.py`: `active_project(db)` beside SF-01's lookups.
- `module_dependency_graph.md` names the module.

### Red first

`test_project_for.py`, `test_build_run.py`: import errors (no module, then no `RunRequest`). The
first green run left the topology empty: the test project had one module and the selector only
answers with a neighbour, so the project gained a second module (`billing` consumes `orders`).

### Combined analysis

| Function | Integration |
|---|---|
| `project_for` | registered, named, active, none active, unregistered refused |
| `build_run_sync` | every part for a model run; no router/config without a model step; optional with no role; broken setting raises; unknown project builds without settings |

Mutants (OBJECTED, pinned): `unregistered-folder-takes-active`, `no-rule-file`, `no-standards`,
`no-topology`, `optional-model-refuses`. Drifted: 0.

### Gates

Full suite 11479 passed, 9 skipped (first run: the two new `__init__.py` lacked the copyright
header — the conventions test). `quality.py sf` 18/18 after `ruff format` and an escaped `match=`.
`tach check` clean.

### Red/Blue (code)

- R1 (MEDIUM) no door uses the builder yet, so nothing changed for users. By plan: SF-03 and SF-04.
- R2 (LOW) `build_run` reads small local files synchronously inside the coroutine. Accepted
  (plan R2).
- Cycle 2: no new finding.
