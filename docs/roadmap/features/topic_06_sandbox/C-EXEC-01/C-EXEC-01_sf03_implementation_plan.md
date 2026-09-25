# C-EXEC-01 SF-03 — Presentation Layer Sterilization

**Status**: APPROVED · **FRs owned**: FR-2 · **Feature ID**: 3.20a · Design:
[C-EXEC-01_design.md](C-EXEC-01_design.md) §Sub-features → SF-03

FR-2 (no domain module may depend on `api` or `cli`) recorded 2026-08-17 under `specweaver-dev`
§3.2c, from `INT-US-01-SF02-MIG`. The enforcing assertion is zero violations; it allowed 95 until
2026-08-17 (a 2026-05-25 baseline) — see the design's Architecture guards.

## Goal

No domain logic inside `src/specweaver` may depend on `api` or `cli`.

## Changes

1. **`tach.toml`** — declare `src.specweaver.interfaces.api` and `src.specweaver.interfaces.cli`
   as tracked modules; `tach sync` fills their large `depends_on` lists (they consume almost every
   component). They sit at the top of the stack, so no other module lists them as a dependency.
2. **`src/specweaver/cli/__init__.py`** — kept: it holds the Typer `@app.callback()` lifecycle.
   Prune lines 78-95, the backward-compatible re-exports
   (`from specweaver.interfaces.cli._helpers import...`); `tach` now defines the interface bounds.
3. **`src/specweaver/api/__init__.py`** — no change: no `__all__` blocks or domain logic; kept for
   package compliance.

## Tests

1. `tach sync` establishes the DAG.
2. `tach check` — `api` and `cli` sit at the top of the dependency funnel.
3. `ruff` and `pytest` — no broken CLI integrations.
