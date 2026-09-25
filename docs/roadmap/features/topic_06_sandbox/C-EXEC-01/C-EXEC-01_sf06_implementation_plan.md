# C-EXEC-01 SF-06 — Global Implicit Namespace Conversion

**Status**: COMPLETED · **FRs owned**: none (NFR-1) · **Feature ID**: 3.20a · Design:
[C-EXEC-01_design.md](C-EXEC-01_design.md) §Sub-features → SF-06

No FR: deleting the last 20 `__init__.py` proxies is NFR-1, marked `[proof: meta]` because it is a
one-time refactor over the tree, not a runtime behaviour. Recorded 2026-08-17 from
`INT-US-01-SF02-MIG`.

## Goal

Finish the move to a PEP-420 layout: delete all remaining `__init__.py` encapsulation proxies inside
`src/specweaver/` and enforce global strict topology with Tach.

## Changes

1. **Delete `src/specweaver/**/__init__.py`** — the 20 internal files in the `src/specweaver/`
   tree.
   > [!IMPORTANT]
   > Do NOT touch `tests/` unless strictly necessary; this change targets the `src/` runtime only.
2. **`pyproject.toml`** — an implicit namespace package is no longer discoverable, so add
   `pythonpath = ["src"]` to `[tool.pytest.ini_options]`; otherwise all 3,700+ tests fail with
   `ModuleNotFoundError`.
3. **`tach.toml`** — layer boundaries existed, but undeclared lateral crossings were not blocked.
   Set global `strict = true` or `exact = true` (whichever this Tach configuration supports);
   document or explicitly whitelist any newly flagged implicit dependency.

## Tests

1. `tach check` succeeds.
2. `python -m pytest tests/` passes as before.
3. `/pre-commit`.
