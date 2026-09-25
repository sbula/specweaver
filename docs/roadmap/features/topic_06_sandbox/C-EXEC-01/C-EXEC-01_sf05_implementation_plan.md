# C-EXEC-01 SF-05 — Legacy Linter Subsumption

**Status**: APPROVED · **FRs owned**: none · **Feature ID**: 3.20a · Design:
[C-EXEC-01_design.md](C-EXEC-01_design.md) §Sub-features → SF-05

No FR of its own: existing checks moved onto tach. Recorded 2026-08-17 from `INT-US-01-SF02-MIG`.

## Goal

Remove internal Python architecture tests and custom deprecation scripts that Tach now covers.
Global PEP-420 `__init__.py` deletion is split out to SF-06 to limit blast radius.

## Changes

1. [x] **Deprecation subsumption** — hard delete `tests/unit/validation/test_runner_removals.py`
   (it asserted `ImportError` on legacy APIs). Instead, register `src.specweaver.assurance.validation`
   in `tach.toml` `modules` and `interfaces`, omitting `runner` from its exports: CI-level bounding,
   not file-level crashes.
2. [x] **Boilerplate verification subsumption** — remove
   `test_tach_toml_enforces_resource_layer_modules` and
   `test_core_layers_never_depend_on_presentation` (manual `.toml` parsing that checked
   `src.specweaver.interfaces.api` mapping) from `tests/unit/test_architecture.py`. Tach is the
   rules engine; PR review governs the TOML.

## As built

- Added `test_tach_keeps_runner_soft_deprecated`: `runner` is never re-added to `tach.toml`.
- Fixed `tach.toml` structure parsing in `test_architecture.py`, which exposed and removed several
  phantom/dead module exposures.
- Rollback, if `tach` strict checks fail after linking the Validation boundaries: standard Git
  rollback of the change.
- Deferred to **[SF-06]**: deleting the remaining 20 `__init__.py` files and global `strict = true`.
