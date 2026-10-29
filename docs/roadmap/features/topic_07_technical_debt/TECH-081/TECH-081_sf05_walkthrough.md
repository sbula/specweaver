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
