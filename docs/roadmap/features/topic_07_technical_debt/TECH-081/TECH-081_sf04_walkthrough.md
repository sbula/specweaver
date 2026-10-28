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

## CB-2 — the caller hands the runner its registry (FR-12)

### What changed

- `PipelineRunner(..., *, registry: StepHandlerRegistry, ...)`: required, keyword-only; the engine no
  longer builds one. `runner.py` names the class under `TYPE_CHECKING` only (CB-4 replaces it with an
  engine-owned port).
- The 9 outside `src` callers pass `StepHandlerRegistry()`: `run_doors`, the API `_llm` and
  `pipelines` (2), `core/flow/interfaces/cli.py` (2), the drafting, implementation and review CLIs.
- 36 test calls in 18 files gain `registry=StepHandlerRegistry()` (an AST script found every call
  without one); two files patch `StepHandlerRegistry.get` at its home, not through `runner`.
- 49 mutants in 12 corpora re-pinned: their symbols are the callers above, and only the runner call
  changed. Anchors checked inside the symbol; three anchors sit on a decorator or a last line, which
  the symbol check cannot see, so those were checked as unique in the file.

### Red first

`test_runner_takes_its_registry.py`: no default and a runner built without a registry both failed
before the change.

### Proof

Mutant `runner-builds-its-registry` (`__init__` builds its own registry again): OBJECTED.

### Gate notes

Kind `tooling` `[agreed 2026-10-28]`: test calls gained an argument.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) nine callers each write `StepHandlerRegistry()`. Blue: the caller is the composition
  root by design (AD-7); SF-05 folds the CLI doors.
- R2 (MEDIUM) the runner still names the registry type. Blue: CB-4 swaps it for `HandlerLookup`.
- R3 (LOW) tests patch `StepHandlerRegistry.get` on the class. Blue: as before; only the path changed.
- Cycle 2: no new finding.
