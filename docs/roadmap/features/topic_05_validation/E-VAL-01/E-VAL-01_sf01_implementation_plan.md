# E-VAL-01 SF-01 — Validation Engine & Static Rules

**Phase**: 1, build step 2 · Design: [E-VAL-01_design.md](E-VAL-01_design.md)

## Goal

**Runnable:** `sw check --level=component good_spec.md` → all PASS.

## Changes

Created (nothing copied from FM):

- `validation/models.py`, `validation/runner.py`
- 8 static spec rules: S01, S02, S05, S06, S08, S09, S10, S11
- Test fixtures: good/bad specs
- Per-rule unit tests + runner integration test

**Since moved** (noted 2026-09-25): `validation/` lives at `src/specweaver/assurance/validation/`.
