# Walkthrough: TECH-081 SF-01 — The check sees every module

Plan: [TECH-081_sf01_implementation_plan.md](TECH-081_sf01_implementation_plan.md).

## CB-1 — the check sees every module (FR-1, FR-2, FR-3, FR-5)

### What changed

- `tach.toml`: `root_module = "forbid"` and `ignore_type_checking_imports = false`; six new modules
  (`commons` as `utility`, `assurance.graph`, `workflows.scenarios`, `workflows.evaluators`,
  `_version`, `telemetry_logger`); the plain edges and the 20 `deprecated` edges of the plan's
  table; 7 type-only names added to `[[interfaces]]` (`LLMAdapter`, `RenderProfile`, `Price`,
  `PriceBook`, `AnalyzerFactoryProtocol`, `ValidationPipeline`, `Rule`).
- `assurance/validation/context.yaml`: `exposes` gains `models.Rule` and `pipeline.ValidationPipeline`,
  so it still equals `tach.toml` (`test_validation_context_exposes.py`).
- The ledger: six stale rows removed; the `topology.py` I/O row added; the drafting and
  `assurance/graph` rows now say which FR removes them; a new "Owed by TECH-081" table, one row per
  deprecated edge.

### Red first

`tests/unit/test_tach_sees_every_module.py`: 4 of 5 failed before the change — no settings, two
root files and four packages outside a module, no deprecated edge, and ledger row `:11` citing
`src/specweaver/llm/prompt_builder.py`, which moved. The fifth (each owed row names a design FR)
passed vacuously with no rows; its mutant now kills it.

### Proof

Six corpus mutants in `TECH-081_mutants.json`, all OBJECTED: `root_module` set to `ignore`;
type-only imports ignored; one deprecated edge made plain; one owed row dropped; one owed row naming
`FR-99`; one ledger path pointing at a moved file.

### Gate notes

- `scripts/tests.py cb TECH-081 --kind refactor` blocks a new test file ("a refactor's tests pass
  unmodified"). SF-01 changes a gate, not behaviour, so it ran as `--kind tooling`; the design's
  Kind line now says which SFs are which.
- Full suite 11805 passed, 9 skipped; `quality.py cb` and `doc` green; `tach check` green.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) the owed-row pattern is strict, so a reformatted row would vanish from the parse.
  Blue: then its edge is deprecated with no row, and the equality test fails; nothing goes silent.
- R2 (MEDIUM) `commons` as `utility` could let it import anything. Blue: `utility` only frees its
  importers; its own `depends_on = []` is still checked.
- R3 (LOW) the ledger path pattern reads only `src/specweaver/...py` in backticks. Blue: that is
  how every row cites code; prose paths without `src/` are not claims about a file.
- Cycle 2: no new finding.
