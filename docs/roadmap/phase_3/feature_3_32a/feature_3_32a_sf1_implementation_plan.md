# Implementation Plan: Adaptive Assurance Standards [SF-1: Adaptive Standard Configurations]
- **Feature ID**: 3.32a
- **Sub-Feature**: SF-1 — Adaptive Standard Configurations
- **Design Document**: docs/roadmap/phase_3/feature_3_32a/feature_3_32a_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_32a/feature_3_32a_sf1_implementation_plan.md
- **Status**: DRAFT

## Research Notes
- `StandardsScanner` dynamically loads Analyzers and runs `extract_all` across topological files. For greenfield repos this results in Empty Repository vacuums.
- Configuration is managed via `SpecWeaverSettings` inside `core/config/settings.py`. It uses Pydantic.
- Python 3.11 provides native `tomllib` for native `specweaver.toml` definitions parsing safely.
- `context.yaml` explicitly enforces that `assurance/standards` forbids `loom/*`. 

## Proposed Changes

### core/config/settings.py
Modify Pydantic models to ingest TOML based configurations securely.
#### [MODIFY] src/specweaver/core/config/settings.py
- [x] Define `StandardsSettings(BaseModel)` containing the configurable parameter `mode: Literal["mimicry", "best_practice"] = "mimicry"`.
- [x] Augment `SpecWeaverSettings` to incorporate `standards: StandardsSettings = StandardsSettings()`.
- [x] In `load_settings()`, parse `specweaver.toml` leveraging Python's built-in `tomllib`. If file is present within the project root, retrieve its values safely to load into the settings dictionary and merge it into the Pydantic payload, overriding base defaults.
- > [!IMPORTANT]
  > Centralization via `core/config/settings.py` isolates our architectural parsing logic directly out from `StandardsAnalyzer` bounds. (Option B Approved).

### assurance/standards/scanner.py
Connect the config state dynamically into the Scanner.
#### [MODIFY] src/specweaver/assurance/standards/scanner.py
- [x] Update the injection signature for scanning capabilities.
- [x] Intervene before returning an empty array logic execution: If `mode == "best_practice"` and `analyzer_to_files` triggers empty AST extractions (Empty repo), hydrate `CategoryResult` matrix directly from injected configurations.
- > [!CAUTION]
  > Execute the hydration mapping cleanly without embedding the SQLite `Database()` dependency directly into the module. Let higher-layer callers resolve settings.standards parameters before invoking `scan`. (Option A Approved).

#### [MODIFY] src/specweaver/core/flow/handlers/standards.py (Deviated from Plan)
- [x] Added dynamic passing of `mode` and `built_in_defaults` directly within `EnrichStandardsHandler` to securely connect the configurations to the Orchestrator without importing database components into the pure-logic configuration layer.

## Verification Plan

### Automated Tests
- [x] `pytest tests/unit/core/config/test_settings.py`: Verify TOML mapping defaults overlay Pydantic model configurations completely upon empty definitions or populated nodes.
- [x] `pytest tests/unit/assurance/standards/test_scanner.py`: Validate that an empty file matrix scan dynamically hydrates built_in schemas instead of failing outright.
- [x] `pytest tests/e2e/capabilities/assurance/test_standards_e2e.py`: Added explicit CLI seam orchestration E2E validation (`test_best_practice_mode_hydrates_empty_repo`).
