# Walkthrough: TECH-081 SF-04 — The flow engine stands alone

Plan: [TECH-081_sf04_implementation_plan.md](TECH-081_sf04_implementation_plan.md).

## CB-1 — the store and the language name (FR-16, FR-14)

### What changed

- `tach.toml` registers `specweaver.core.flow.store` (`depends_on = ["specweaver.core.config"]`: the
  tables use `StrictISODateTime`; the plan said `[]`). Bootstrap's owed edge to all of `core.flow` is
  now the plain edge to `core.flow.store`; the ledger row is gone.
- `sandbox/language/core/_detect.py` → `detect.py`; five `src` imports, two tests, the tach expose and
  `language_support_guide.md` follow.
- Manifests: bootstrap consumes `core/flow/store`; `core/flow` consumes it.
- Three mutants re-pinned (`D-INTL-08` ×2, `TECH-078`): only the import line inside their symbols
  changed; every anchor still matches.

### Red first

Registering the module and renaming the expose first turned `test_tach_architectural_boundaries`,
`test_tach_interfaces_map_to_valid_namespaces` and `test_every_allowed_dependency_is_declared` red.

### Proof

Mutant `bootstrap-imports-flow` (`get_db` imports `core.flow.engine.models`): OBJECTED.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) `core.flow` still holds `store.py` on disk while tach treats it as its own module.
  Blue: tach resolves the most specific module path; `core.flow` declares the edge to it, and the
  bootstrap mutant proves the rest of `core.flow` stays out of reach.
- R2 (LOW) old plans cite `_detect.py`. Blue: dated plan evidence, not live guides; the live guide
  is fixed.
- Cycle 2: no new finding.
