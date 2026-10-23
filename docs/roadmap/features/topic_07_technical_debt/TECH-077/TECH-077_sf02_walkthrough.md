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

## CB-2 — FR-3 (isolation in the builder) and NFR-3

### Decision taken with the user before this boundary (2026-10-23)

I had told the user a high-DAL project without git *stops* in `sw implement`. The code
(`core/flow/engine/isolation.py`) warned and ran on the host instead — `INT-US-03` AD-8
(2026-07-21). Asked again with the correct facts, the user chose to fail closed: high-DAL code never
runs unbounded. The design's FR-3 and risk row now say so `[agreed 2026-10-23]`.

### What changed

- `isolation._dal_requires_isolation`: with no `.git`, escalation stays on and logs that the run will
  stop (`git init`, or `auto_isolate_min_dal = "off"`); the run then stops where the worktree cannot
  start, as an explicit `enforce_session_isolation` already did.
- `run_setup/builder.py` `_apply_isolation`: `enforce_isolation` from
  `sandbox.enforce_worktree_isolation`, then `apply_session_policy(..., dal_auto_escalate=True)`;
  with no settings (unknown project) both stay off (TECH-076 decision 5).
- `pipeline_engine_guide.md`: the escalation and the non-git stop.
- New `tests/unit/interfaces/run_setup/test_no_exit.py`: an AST scan that the builder imports no CLI
  or HTTP framework and raises no exit.

### Red first

- `test_session_policy.py` and `test_cli_implement_isolation.py` pinned the old fallback; flipped to
  expect isolation on, both failed on the old code.
- `test_build_run.py` isolation cases: DAL_B and `enforce_worktree_isolation` failed (the builder set
  no isolation yet).
- The no-exit scan passed on first run (nothing to find); its proof is the mutant planting `import
  typer` (OBJECTED).

### Combined analysis

| Function | Unit | Integration |
|---|---|---|
| `_apply_isolation` | — | ✅ DAL_B on, per-step on, DAL_E off, no settings off |
| `_dal_requires_isolation` | ✅ non-git still escalates | ✅ `sw implement` context |
| sync vs async builder | — | ✅ same isolation, guidance, topology |
| NFR-3 | ✅ scan + planted exit | — |

Mutants (OBJECTED, pinned): `no-dal-escalation`, `per-step-policy-ignored`, `non-git-runs-on-host`,
`builder-imports-typer`. Drifted: 0.

### Gates

Full suite 11486 passed, 9 skipped (first run: a comment named the ticket — reworded). `quality.py sf`
18/18 after `ruff format`. `tach check` clean.

### Red/Blue (code)

- R1 (MEDIUM, **for SF-03**) `sw implement` does not catch the worktree-start `RuntimeError`, so a
  high-DAL non-git project now ends in a traceback there (`sw run` prints `Error: …` and exits 1).
  SF-03 moves `sw implement` onto the builder and maps this error; the feature is pushed only after.
- R2 (LOW) `apply_session_policy`'s docstring still says `sw run`/`sw resume` never escalate; true
  until SF-03 moves them onto the builder, which updates it.
- Cycle 2: no new finding.
