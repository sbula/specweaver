# Feature 3.1: Feature Spec Layer (L2 Decomposition) — Implementation Plan

> **Date**: 2026-03-17 (v4 — with confidence scoring)
> **Status**: Awaiting final approval
> **Scope**: 2A (Feature Spec authoring + validation) + 2B (Decomposition agent)
> **Out of scope**: 2C (Multi-spec pipeline fan-out) — moved to Feature 3.14
> **Roadmap**: 3.14 (fan-out) ✅ written, 3.9 ✅ renamed to "Automated iterative decomposition (multi-level)"

---

## 1. Design Principles

### 1.1 Two Orthogonal Axes

| Feature axis (value) | Architecture axis (structure) |
|---|---|
| "What does the user/system need?" | "How is the code organized?" |
| Feature → Sub-features → ... | System → Service → Module → Sub-module |
| Decomposed by business concern | Defined by `context.yaml` boundaries |
| `SpecKind.FEATURE` | `SpecKind.COMPONENT` |

The decomposition step is the **bridge** where features cross into architecture.

### 1.2 Three Forces Drive Decomposition

1. **Business features** — user value ("Sell My Shares"). The primary decomposition driver.
2. **Technical features** — NFRs ("Add mTLS", "Parallelize pipeline"). Same Feature Spec template, different stakeholders (security team, ops team).
3. **Architectural gravity** — existing structure pulls new features into established boundaries. Once an architecture is established, follow it. Exceptions are acceptable (1–2 deviations), but beyond that consider refactoring.

### 1.3 Rules Are Advisory

The 10-test battery provides **signals**, not verdicts. They flag "you might need to split" or "this looks too detailed for this level". The decision gate (currently HITL) makes the call.

> [!IMPORTANT]
> All HITL gates are designed with **structured decision criteria** so they can be replaced by automated gates in the future. Each gate produces a machine-readable score/recommendation, not just "please review".

### 1.4 Sweet Spot: Business-Driven Stopping Point

Decompose until each piece describes a **business outcome**, not a technical step:
- ✅ "Validate order limits" (business-meaningful)
- ❌ "Parse the order JSON" (technical step — too far)
- Feature Specs never decompose to class/function level

If following the business view consistently, the decomposition naturally lands at services (in SOA/microservice architectures) and modules (within services). This is expected — the architecture should emerge from business needs. Only when business decomposition is exhausted does technical decomposition apply.

### 1.5 Confidence-Based Scoring

All LLM-generated findings (review, decomposition) carry a `confidence: int` score (0–100). This enables:

- **Noise reduction**: Only surface findings ≥ configurable threshold (default: 80)
- **Auto-gate path**: Gate can decide "proceed if no findings ≥ threshold" without HITL
- **Structured decisions**: Each gate gets quantified data, not prose

Applies to: `ReviewFinding` (existing reviewer), `ComponentChange` (3.1 decomposition), `IntegrationSeam` (3.1 decomposition), and future arbiter findings (3.13).

---

## 2. Key Decisions (from discussion)

| # | Decision |
|---|---|
| 1 | Scope: 2A + 2B only. 2C (fan-out) → Feature 3.14 |
| 2 | Level parameter: Option A — parameterize existing rules via `SpecKind` |
| 3 | Hierarchy Map: Derive from `context.yaml` via topology graph |
| 4 | Output format: YAML plan (source of truth) + stub Component Specs. Drift detection later (3.8) |
| 5 | Pipeline: New `feature_decomposition.yaml`, composable into parent pipelines |
| 6 | Fan-out: Sequential for now, designed for future parallel (3.14) |
| 7 | Greenfield: Decomposition must work without existing code/topology |
| 8 | `SpecKind` has exactly 2 values: `feature` / `component` |
| 9 | Architecture granularity (service/module/sub-module) comes from `context.yaml`, not from the spec |
| 10 | Confidence-based scoring on all LLM review findings — threshold-filterable, enables future auto-gates |

---

## 3. Boundary Clarification: 3.1 vs 3.9

| Aspect | **3.1** (this feature) | **3.9** (later) |
|---|---|---|
| **Focus** | Infrastructure + basic decomposition | Smart, iterative decomposition |
| **Decomposition depth** | Feature → components (L1→L2) | Recursive: feature → sub-features → components (any depth) |
| **Agent complexity** | Single LLM call with structured output | DMZ-style iterative loop (propose → deduplicate → DONE×3) |
| **Quality gate** | HITL reviews the plan | Automated: Structure Tests 1-5 + Change Map coverage check |
| **Greenfield** | Basic: outputs stub specs | Smart: proposes directory structure + `context.yaml` + dependency graph |
| **What 3.1 builds that 3.9 needs** | `SpecKind`, Feature Spec template, `DecomposeHandler`, pipeline, structured output format |

---

## 4. `SpecKind` Enum

```python
class SpecKind(enum.StrEnum):
    FEATURE = "feature"      # Value-driven spec (Feature axis)
    COMPONENT = "component"  # Structure-driven spec (Architecture axis, default)
```

Two values. Architecture granularity (service/module/sub-module) comes from `context.yaml`.

---

## 5. Rule Adjustments by SpecKind

### Rules that change behavior

| Rule | `feature` | `component` (default) |
|---|---|---|
| **S01** (One-Sentence) | warn=2, fail=4 — feature intents coordinate across boundaries | warn=0, fail=2 — unchanged |
| **S03** (Stranger) | **Abstraction leak detection**: flags file paths, class names, function signatures. Module/service references are valid. | Counts external references (unchanged) |
| **S04** (Dep. Direction) | **SKIP** — architecture concern, not relevant at feature level | Unchanged |
| **S05** (Day Test) | warn=60, fail=100 — Feature Specs are larger | warn=25, fail=40 — unchanged |
| **S08** (Ambiguity) | warn=2, fail=5 — slightly more tolerance for process language | warn=1, fail=3 — unchanged |

### Rules that stay the same

S02 (Single Setup), S06 (Concrete Example), S07 (Test-First), S09 (Error Path), S10 (Done Definition), S11 (Terminology) — their signals are spec-quality concerns independent of SpecKind.

### S03 "Abstraction Leak" Mode (Feature Specs)

When `kind=FEATURE`, S03 switches from counting external references to detecting implementation-level detail in a business-level document:

```
VALID in Feature Spec:
  "involves services: depotManager, broker, trader"
  "affects the billing module"
  
FLAGGED as abstraction leak:
  "[TaxCalculator](src/billing/taxes/vat.py)"    ← file path
  "`TaxCalculator.calculate()`"                   ← class.method
  "imports from `specweaver.validation.runner`"   ← import path
```

Implementation: regex scan for path-like patterns (`/`, `.py`, `::`, dotted import paths with 3+ segments) outside code blocks.

---

## 6. Proposed Changes

### 6.1 Sub-Feature 2A: Feature Spec Authoring & Validation

#### [NEW] `src/specweaver/validation/spec_kind.py`

`SpecKind` enum + `get_presets(rule_id, kind)` function returning threshold overrides per rule.

#### [MODIFY] `src/specweaver/validation/rules/spec/s01_one_sentence.py`

Add `kind: SpecKind | None = None` to constructor. When set, use kind-specific thresholds. **Header matching is configurable**: S01 uses `## Intent` for `FEATURE`, `## 1. Purpose` for `COMPONENT` (default). Implemented via `_HEADER_MAP[SpecKind] → regex`.

#### [MODIFY] `src/specweaver/validation/rules/spec/s03_stranger.py`

Add `kind: SpecKind | None = None`. When `kind=FEATURE`, switch to abstraction leak detection mode (flag file paths, class names, function signatures instead of counting external file references).

#### [MODIFY] `src/specweaver/validation/rules/spec/s04_dependency_dir.py`

Add `kind: SpecKind | None = None`. When `kind=FEATURE`, return SKIP immediately.

#### [MODIFY] `src/specweaver/validation/rules/spec/s05_day_test.py`

Add `kind: SpecKind | None = None`. Use kind-specific thresholds.

#### [MODIFY] `src/specweaver/validation/rules/spec/s08_ambiguity.py`

Add `kind: SpecKind | None = None`. Use kind-specific thresholds.

#### [MODIFY] `src/specweaver/validation/runner.py`

`get_spec_rules()` gains `kind: SpecKind | None = None`. Passed to rule constructors.

#### [MODIFY] `src/specweaver/cli.py`

`sw check --level` extended from 2 to 3 values: `feature` | `component` | `code`. `feature` and `component` run spec rules (with different `SpecKind` thresholds); `code` runs code rules (unchanged).

#### [NEW] `src/specweaver/drafting/feature_drafter.py`

`FeatureDrafter` — 5-section template (Intent, Blast Radius, Change Map, Integration Seams, Sequence). Works for greenfield. Supports both business and technical features.

#### [MODIFY] `src/specweaver/review/reviewer.py`

- Add `confidence: int = 0` field to `ReviewFinding` model
- Update LLM prompt to request confidence scoring (0-100) for each finding
- Add `confidence_threshold: int = 80` param to `Reviewer.__init__()`
- `_parse_response()` extracts confidence from LLM output and filters by threshold
- Findings below threshold are kept in `ReviewResult` but marked `below_threshold=True`

#### [MODIFY] `src/specweaver/flow/handlers.py`

- New `DraftFeatureHandler` (draft+feature)
- `ValidateSpecHandler` reads `kind` from `step.params`
- `ReviewSpecHandler` / `ReviewCodeHandler` can read `confidence_threshold` from `step.params`

---

### 6.2 Sub-Feature 2B: Decomposition Agent

#### [NEW] `src/specweaver/drafting/decomposition.py`

```python
class ComponentChange(BaseModel):
    component: str          # service/module name
    exists: bool            # true=modify, false=create new
    change_nature: str      # "new_interface" | "schema" | "behavior" | "config"
    description: str
    dependencies: list[str]
    confidence: int         # 0-100: LLM's confidence in this proposal

class IntegrationSeam(BaseModel):
    between: tuple[str, str]
    contract: str
    format: str             # "shared type" | "event" | "API call" | ...
    confidence: int         # 0-100: LLM's confidence in this seam

class DecompositionPlan(BaseModel):
    feature_spec: str                 # source path
    components: list[ComponentChange]
    integration_seams: list[IntegrationSeam]
    build_sequence: list[str]
    # Structured decision criteria (for future auto-gate)
    coverage_score: float             # % of Blast Radius entries covered by ComponentChanges
    alignment_notes: list[str]        # topology matches/mismatches
    timestamp: str
```

`coverage_score` = (ComponentChange entries matching Blast Radius entries) / (total Blast Radius entries). LLM-assisted matching since Blast Radius may be free-form. `alignment_notes` and per-item `confidence` scores exist so a future auto-gate can replace HITL.

#### [MODIFY] `src/specweaver/flow/models.py`

- `StepAction.DECOMPOSE = "decompose"`
- `StepTarget.FEATURE = "feature"`
- New valid combinations: `(DRAFT, FEATURE)`, `(VALIDATE, FEATURE)`, `(DECOMPOSE, FEATURE)`

#### [NEW] `DecomposeHandler` in `src/specweaver/flow/handlers.py`

1. Read Feature Spec
2. Load topology as **guidance** (optional — greenfield works without it)
3. LLM prompt: Feature Spec + topology → `DecompositionPlan` JSON
4. When topology exists: new components = **signals** (not errors) in `alignment_notes`
5. Write `features/<name>_decomposition.yaml` + stub Component Specs
6. Gate: HITL reviews (structured data supports future auto-gate)

The decompose step can produce **sub-Feature Specs** (recursive) OR Component Specs — the gate decides.

#### [NEW] `src/specweaver/pipelines/feature_decomposition.yaml`

```yaml
name: feature_decomposition
description: >
  Draft Feature Spec, validate at feature thresholds,
  decompose into component changes (or sub-features), HITL review.
version: "1.0"

steps:
  - name: draft_feature
    action: draft
    target: feature
    description: "Co-author Feature Spec with HITL"
    gate:
      type: hitl          # Future: auto (when drafter quality is proven)
      condition: completed

  - name: validate_feature
    action: validate
    target: feature
    params:
      kind: feature
    description: "Run spec rules with feature-level thresholds"
    gate:
      type: auto
      condition: all_passed
      on_fail: loop_back
      loop_target: draft_feature
      max_retries: 3

  - name: decompose
    action: decompose
    target: feature
    description: "Decompose into component changes or sub-features"
    gate:
      type: hitl          # Future: auto (when coverage_score + alignment_notes are reliable)
      condition: completed
```

---

## 7. Verification Plan

### Regression

```bash
uv run pytest tests/ -x -q
```

All ~1696 tests must pass with zero regressions.

### New Tests

| Test File | Covers |
|---|---|
| `tests/unit/validation/test_spec_kind.py` | `SpecKind` enum, preset lookup, None fallback |
| `tests/unit/validation/rules/spec/test_rules_by_kind.py` | S01/S05/S08 feature thresholds; S03 abstraction leak mode; S04 skip for feature |
| `tests/unit/validation/test_runner.py` (extend) | `get_spec_rules(kind=...)` passes through |
| `tests/unit/drafting/test_feature_drafter.py` | 5-section template, mock LLM, greenfield |
| `tests/unit/drafting/test_decomposition.py` | Model construction, YAML round-trip, stub generation, coverage_score, confidence field |
| `tests/unit/flow/test_decompose_handler.py` | Valid/invalid LLM response, greenfield, with topology, alignment_notes |
| `tests/unit/flow/test_models.py` (extend) | New enum values, valid combinations, pipeline loads |
| `tests/unit/review/test_reviewer.py` (extend) | Confidence parsing, threshold filtering, below_threshold marking |

### Manual Verification

1. `sw check --kind feature <feature_spec.md>` → applies feature-level thresholds
2. `sw check <module_spec.md>` → identical to today (default = component)
3. `sw pipelines` → lists `feature_decomposition`
