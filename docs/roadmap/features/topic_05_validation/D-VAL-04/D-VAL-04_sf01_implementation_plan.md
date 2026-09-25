# D-VAL-04 SF-01 — Adaptive Standard Configurations

**Status**: DRAFT (implemented — all items below done) · **FRs owned**: FR-1, FR-2 · **Depends on**:
none · **Feature ID**: 3.32a · Design: [D-VAL-04_design.md](D-VAL-04_design.md) §Sub-features →
SF-01

## Goal

The configured `mimicry` / `best_practice` mode, and the built-in defaults supplied when the project
yields nothing. FRs recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-25-SF01-MIG`.

FR-2 shares a *path* with `E-VAL-02` FR-7 but not a mutant: this side supplies the defaults, that
side falls back to them. Two lines, two claims, cited separately.

## Where it plugs in

| Fact | Where |
|---|---|
| `StandardsScanner` loads Analyzers and runs `extract_all` across topological files; a greenfield repo yields nothing (Empty Repository vacuum). | `assurance/standards/scanner.py` |
| Configuration is Pydantic: `SpecWeaverSettings`. | `core/config/settings.py` |
| Python 3.11 `tomllib` parses `specweaver.toml`. | stdlib |
| `context.yaml`: `assurance/standards` forbids `loom/*`. | `assurance/standards/context.yaml` |

## Changes

1. **Settings** · `src/specweaver/core/config/settings.py`
   - `StandardsSettings(BaseModel)` with `mode: Literal["mimicry", "best_practice"] = "mimicry"`.
   - `SpecWeaverSettings` gains `standards: StandardsSettings = StandardsSettings()`.
   - `load_settings()` reads `specweaver.toml` from the project root with `tomllib` when present and
     merges its values over the defaults.
2. **Scanner** · `src/specweaver/assurance/standards/scanner.py`
   - `scan` takes the mode and defaults as injected parameters.
   - Before returning empty: if `mode == "best_practice"` and `analyzer_to_files` yields no AST
     extractions, hydrate the `CategoryResult` matrix from the injected defaults.
3. **Handler** (not in the original plan) · `src/specweaver/core/flow/handlers/standards.py` —
   `EnrichStandardsHandler` passes `mode` and `built_in_defaults` to the scanner, so the config
   layer
   stays pure logic and imports no database components.

> [!CAUTION]
> The scanner must not embed the SQLite `Database()` dependency. Higher-layer callers resolve
> `settings.standards` parameters before invoking `scan`.

## Tests

| Test | Proves |
|---|---|
| `pytest tests/unit/core/config/test_settings.py` | TOML values overlay the Pydantic defaults, for empty and populated definitions |
| `pytest tests/unit/assurance/standards/test_scanner.py` | an empty file matrix scan hydrates built_in schemas instead of failing |
| `pytest tests/e2e/capabilities/assurance/test_standards_e2e.py` | CLI seam E2E (`test_best_practice_mode_hydrates_empty_repo`) |

## Decisions (audit)

| Question | Chosen | Why |
|---|---|---|
| Where does TOML parsing live? | **Option B** — centralized in `core/config/settings.py` | keeps parsing logic out of `StandardsAnalyzer` |
| How do defaults reach the scanner? | **Option A** — injected by higher-layer callers | no SQLite `Database()` dependency in the scanner |

## As built

**Since moved** (noted 2026-09-25): TOML loading sits in
`core/config/bootstrap/settings_loader.py` (`_load_toml_standards`); the `loom/*` forbid is now
`specweaver/sandbox/*`. The `built_in_defaults` are a literal dict in the handler (python
`snake_case`, javascript/typescript `camelCase` naming), not read from `context.db`.
