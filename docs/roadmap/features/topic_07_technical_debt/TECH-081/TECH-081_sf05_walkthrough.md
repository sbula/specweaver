# Walkthrough: TECH-081 SF-05 — The CLIs stop importing the shell

Plan: [TECH-081_sf05_implementation_plan.md](TECH-081_sf05_implementation_plan.md).

## CB-1 — the shared helpers move to `interfaces/cli_kit` (FR-15)

### What changed

- `interfaces/cli/_core.py` moved to `interfaces/cli_kit/_core.py` (new tach module, archetype
  `adapter`). The root `app` and `_version_callback` stayed in the shell, in `main.py`.
- Every `from specweaver.interfaces.cli import _core` now imports from `cli_kit`, in 11 modules
  and the shell itself. Test patch strings re-pointed.
- `graph`, `core.config`, `infrastructure.llm` and `workspace.project` interfaces lost their
  `deprecated` edge to the shell and its ledger row. The other six CLIs and the shell depend on
  `cli_kit`; the shell lost its unused `core.config.bootstrap` edge. Eleven manifests consume
  `cli_kit`; the shell's manifest no longer exposes `console` or `get_db`.
- Four unit tests whose subject is a `_core` function moved to `tests/unit/interfaces/cli_kit/`;
  three mutant corpora name their new path.
- Seven mutants on `_core.py` point at the new file; re-run, all OBJECTED; their symbols did not
  change, so no re-pin. 0 stale.
- Two tests import from two modules now (`app` from `main`, `run_doors` from the shell, `_core` from
  `cli_kit`), so the kind is `tooling` (Q1 `[agreed 2026-10-29]`).

### Red first

Registering `cli_kit` and deleting the four edges first turned `tach check` red (11 failures).

### Gate notes

Full suite 11829 passed, 9 skipped; `tests.py cb --kind tooling`, `quality.py cb`, `doc`,
`check_proof_tier.py`, `tach check`, mypy green. The first suite run had two import errors from the
mixed imports above.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `cli_kit` exposes a module named `_core`. Blue: the name keeps 335 `_core.x` uses and
  every test patch unchanged; the manifest says it is the interface.
- R2 (MEDIUM) `main.py` still re-imports `console` and `logger` from the kit. Blue: a use, not a
  second home; the shell prints with the shared console.
- R3 (LOW) `pyproject.toml`'s `sw = specweaver.interfaces.cli.main:app` still holds: `app` lives in
  `main.py`.
- Cycle 2: no new finding.

## CB-2 — the run doors move to `interfaces/run_doors` (FR-15)

### What changed

- `interfaces/cli/run_doors.py` moved to `interfaces/run_doors/run_doors.py` (new tach module,
  archetype `orchestrator`). The file kept its name, so every test edit is a path change and the
  boundary runs the `refactor` gate.
- `assurance.standards`, `assurance.validation`, `core.flow`, `workflows.implementation` and
  `workflows.review` interfaces lost their `deprecated` edge to the shell and its ledger row; they
  and `workflows.drafting.interfaces` depend on `interfaces.run_doors` and their manifests consume
  it. The shell lost five unused edges (`core.flow.*`, `run_setup`, `workspace`).
- `test_run_one_step.py` and `test_run_doors.py` moved to `tests/{unit,integration}/interfaces/run_doors/`.
- `domain_driven_cli_creation.md` and one test docstring name the new path.
- Mutants: the corpora name the moved file and tests. 15 mutants whose symbol held a re-pointed
  import were re-run (all OBJECTED), then re-pinned one by one. 0 stale.

### Red first

Registering `run_doors` and deleting the five edges first turned `tach check` red (9 failures).

### Gate notes

Full suite 11829 passed, 9 skipped; `tests.py cb --kind refactor`, `quality.py cb`, `doc`,
`check_proof_tier.py`, `tach check`, mypy green. A path sed also touched a finished plan
(`TECH-077_sf03_implementation_plan.md`); reverted before staging.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `run_doors.run_doors` repeats its name. Blue: the price of path-only test edits,
  which is what lets this boundary prove it changed no behaviour; the plan records the choice.
- R2 (MEDIUM) `drafting.interfaces` now holds both a `run_doors` edge and its shell edge. Blue: the
  shell edge is for `HITLProvider` only; CB-3 removes it.
- R3 (LOW) the shell manifest still lists consumes it no longer uses (`run_setup`, `workspace`).
  Blue: the manifest test checks edges are covered, not the reverse; CB-3 tidies the shell manifest.
- Cycle 2: no new finding.

## CB-3 — `sw draft` gets its channel from the shell (FR-15) — closes SF-05

### What changed

- `workflows/drafting/interfaces/cli.py` gained `set_hitl_provider_factory`, the same shape as
  `core/flow`'s setter. `sw draft` calls the factory per run; with none registered it attaches no
  provider. It no longer imports `interfaces/cli`.
- `main.py` registers `_hitl_provider`, which imports `hitl_provider` when called, so tests that
  patch `HITLProvider` still see their double. No TTY check: `sw draft` asks as before (NFR-1).
- The last `deprecated` edge (`workflows.drafting.interfaces → interfaces.cli`) and its row are
  gone. `tach.toml` has no `deprecated` edge left; the ledger's "Owed by TECH-081" table says none
  are left, and `test_tach_sees_every_module` accepts that state only while the section says so.
- `domain_driven_cli_creation.md` imports from `cli_kit` and names the setter pattern; the shell
  manifest dropped an unused consume.

### Red first

The five new tests (`test_draft_channel.py`) failed: no setter. Deleting the edge turned `tach
check` red on `cli.py:173`. `test_tach_sees_every_module` then failed on "no deprecated edge",
the guard written when some were still owed.

### Proof

FR-15 mutants `cli-imports-shell-again`, `door-back-in-shell` (tach), `draft-loses-its-channel`
(the new test and the draft e2e): all OBJECTED. `TECH-077` `draft-no-terminal` re-anchored on the
factory call; it and two other draft mutants re-run (OBJECTED) and re-pinned. 0 stale.

### Gate notes

Full suite 11834 passed, 9 skipped; `tests.py cb --kind tooling`, `quality.py cb`, `doc`,
`check_proof_tier.py`, `tach check`, mypy green.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) a `sw draft` reached without the shell asks nothing. Blue: only a test that calls
  `drafting_cli` alone gets there; `test_the_shell_registers_its_hitl_provider` and the mutant hold
  the shell's registration.
- R2 (MEDIUM) the factory is typed `Callable[[], Any]`. Blue: drafting may not import
  `workspace.context` (tach); `core/flow`'s setter has the same type.
- R3 (MEDIUM) relaxing the "no deprecated edge" guard could hide a dropped list. Blue: tach fails
  any import whose edge was dropped, and the test still fails if the section disappears or stops
  saying none are left.
- Cycle 2: no new finding.
