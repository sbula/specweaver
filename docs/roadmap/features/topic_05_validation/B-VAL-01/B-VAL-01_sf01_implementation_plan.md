# B-VAL-01 SF-01 — AST Drift & Coverage Engine

**Status**: COMPLETE (2026-04-02) · **FRs owned**: FR-3, FR-4 (recorded 2026-08-17 under
`specweaver-dev` §3.2c, from `INT-US-10-SF01-MIG`) · **Depends on**: none · Design:
[B-VAL-01_design.md](B-VAL-01_design.md) §Sub-features → SF-01

## Goal

A pure-logic engine that takes a file's AST and its parent `PlanArtifact` and reports drift (structural
mutations) and coverage gaps (what the plan expects and the code lacks). No LLM.

## Where it plugs in

| Fact | Where |
|---|---|
| The `# sw-artifact` UUID tracks the file; the DB trace leads to the `run_id` and its `PlanArtifact` | `LineageMixin.get_artifact_history` |
| `PlanArtifact` models tech stack, file layout, constraints, tasks (schema stored in YAML) | `specweaver.workflows.planning.models` |
| `TreeSitterAnalyzer` — language-agnostic parse into AST nodes | `src/specweaver/standards/tree_sitter_base.py` |

## Changes

1. **`src/specweaver/planning/models.py`** — add `MethodSignature(BaseModel)` (`name`, `parameters`
   as a list of types, `return_type`). Put `sequence_number: int` (auto-incrementing) and
   `expected_signatures: list[MethodSignature] = Field(default_factory=list)` **on the
   `ImplementationTask` model** (the "story"), not on the root `PlanArtifact`.
2. **`src/specweaver/planning/planner.py`** — the extraction prompts tell the LLM to populate
   `expected_signatures` when it generates a plan.
3. **`src/specweaver/validation/models.py`** — add `DriftFinding(BaseModel)` (`severity`,
   `node_type`, `description`, `expected_signature`, `actual_signature`; the same schema later feeds
   the LLM for `--analyze`) and `DriftReport(BaseModel)` (list of findings + boolean `is_drifted`).
4. **[NEW] `src/specweaver/validation/drift_detector.py`** —
   `def detect_drift(file_ast: tree_sitter.Tree, plan: PlanArtifact) -> DriftReport:`
   1. Turn `PlanArtifact.file_layout` (module existence) and `PlanArtifact.tasks` (functions) into
      node expectations.
   2. Walk `file_ast` with `tree_sitter_base`.
   3. Flag expected method signatures, classes or modules that are missing or mutated.

> [!IMPORTANT]
> **Architecture Constraint**: `drift_detector` stays pure-logic. The SQLite lookup of the
> `PlanArtifact` happens in `flow/_drift.py` (SF-02). `detect_drift` takes the pre-loaded AST and Plan.

## Tests

| File | Case |
|---|---|
| [NEW] `tests/unit/validation/test_drift_detector.py` | hand-made static JSON/YAML fixtures mimicking Phase 3.6 planner output; < 10ms, no LLM. Missed-method gap, unauthorized added method (drift), perfect match |

Gate: `python -m pytest tests/unit/validation/test_drift_detector.py -v` passes 100% in under 500ms;
`ruff check` clean; `specweaver.assurance.validation` imports neither `specweaver.core.config.Database`
nor `LineageMixin`. Current proof and mutants: `tests/unit/assurance/validation/test_validation_drift_detector.py`.

## As built

- `expected_signatures` is `dict[str, list[MethodSignature]]` (keyed by file), not a flat list.
- `tree-sitter` quirks handled with Python syntax mappings (`*args`, `@staticmethod`).
- Flow pipeline hook deferred to SF-02.
