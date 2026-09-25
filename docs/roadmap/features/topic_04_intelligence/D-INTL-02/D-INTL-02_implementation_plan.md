# D-INTL-02 — Feature Spec Layer (L2 Decomposition) (implementation plan)

**Status**: Awaiting final approval · **Feature**: 3.1 · **Date**: 2026-03-17 (v4 — with confidence
scoring)

| | |
|---|---|
| Scope | 2A (Feature Spec authoring + validation) + 2B (Decomposition agent) |
| Out of scope | 2C (Multi-spec pipeline fan-out) — moved to Feature 3.14 |
| Roadmap | 3.14 (fan-out) ✅ written, 3.9 ✅ renamed to "Automated iterative decomposition (multi-level)" |

## Goal

Add a Feature Spec layer above Component Specs and a decomposition step that turns one Feature Spec
into component changes. The decomposition step is the **bridge** where features cross into
architecture.

## Principles

**Two orthogonal axes.**

| Feature axis (value) | Architecture axis (structure) |
|---|---|
| "What does the user/system need?" | "How is the code organized?" |
| Feature → Sub-features → ... | System → Service → Module → Sub-module |
| Decomposed by business concern | Defined by `context.yaml` boundaries |
| `SpecKind.FEATURE` | `SpecKind.COMPONENT` |

**Three forces drive decomposition.**

1. **Business features** — user value ("Sell My Shares"). The primary driver.
2. **Technical features** — NFRs ("Add mTLS", "Parallelize pipeline"). Same Feature Spec template,
   different stakeholders (security team, ops team).
3. **Architectural gravity** — existing structure pulls new features into established boundaries.
   Once an architecture is established, follow it. 1–2 deviations are acceptable; beyond that,
   consider refactoring.

**Rules are advisory.** The 10-test battery gives **signals**, not verdicts — "you might need to
split", "too detailed for this level". The decision gate (currently HITL) makes the call.

> [!IMPORTANT]
> All HITL gates are designed with **structured decision criteria** so they can be replaced by
> automated gates in the future. Each gate produces a machine-readable score/recommendation, not
> just "please review".

**Stop at business outcomes.** Decompose until each piece describes a **business outcome**, not a
technical step:

- ✅ "Validate order limits" (business-meaningful)
- ❌ "Parse the order JSON" (technical step — too far)
- Feature Specs never decompose to class/function level

Followed consistently, the business view lands at services (in SOA/microservice architectures) and
modules (within services) — the architecture emerges from business needs. Technical decomposition
applies only once business decomposition is exhausted.

**Confidence scoring.** Every LLM-generated finding (review, decomposition) carries
`confidence: int` (0–100). This gives:

- **Noise reduction**: surface only findings ≥ a configurable threshold (default: 80)
- **Auto-gate path**: a gate can "proceed if no findings ≥ threshold" without HITL
- **Structured decisions**: each gate gets numbers, not prose

Applies to `ReviewFinding` (existing reviewer), `ComponentChange` and `IntegrationSeam` (3.1
decomposition), and future arbiter findings (3.13).

## Decisions

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

**3.1 vs 3.9.**

| Aspect | **3.1** (this feature) | **3.9** (later) |
|---|---|---|
| **Focus** | Infrastructure + basic decomposition | Smart, iterative decomposition |
| **Decomposition depth** | Feature → components (L1→L2) | Recursive: feature → sub-features → components (any depth) |
| **Agent complexity** | Single LLM call with structured output | DMZ-style iterative loop (propose → deduplicate → DONE×3) |
| **Quality gate** | HITL reviews the plan | Automated: Structure Tests 1-5 + Change Map coverage check |
| **Greenfield** | Basic: outputs stub specs | Smart: proposes directory structure + `context.yaml` + dependency graph |
| **What 3.1 builds that 3.9 needs** | `SpecKind`, Feature Spec template, `DecomposeHandler`, pipeline, structured output format |

## `SpecKind`

```python
class SpecKind(enum.StrEnum):
    FEATURE = "feature"      # Value-driven spec (Feature axis)
    COMPONENT = "component"  # Structure-driven spec (Architecture axis, default)
```

Two values. Architecture granularity (service/module/sub-module) comes from `context.yaml`.

### Rule thresholds by kind

| Rule | `feature` | `component` (default) |
|---|---|---|
| **S01** (One-Sentence) | warn=2, fail=4 — feature intents coordinate across boundaries | warn=0, fail=2 — unchanged |
| **S03** (Stranger) | **Abstraction leak detection**: flags file paths, class names, function signatures. Module/service references are valid. | Counts external references (unchanged) |
| **S04** (Dep. Direction) | **SKIP** — architecture concern, not relevant at feature level | Unchanged |
| **S05** (Day Test) | warn=60, fail=100 — Feature Specs are larger | warn=25, fail=40 — unchanged |
| **S08** (Ambiguity) | warn=2, fail=5 — slightly more tolerance for process language | warn=1, fail=3 — unchanged |

Unchanged: S02 (Single Setup), S06 (Concrete Example), S07 (Test-First), S09 (Error Path), S10 (Done
Definition), S11 (Terminology) — spec-quality signals independent of SpecKind.

**S03 abstraction-leak mode.** With `kind=FEATURE`, S03 stops counting external references and flags
implementation detail in a business-level document:

```
VALID in Feature Spec:
  "involves services: depotManager, broker, trader"
  "affects the billing module"
  
FLAGGED as abstraction leak:
  "[TaxCalculator](src/billing/taxes/vat.py)"    ← file path
  "`TaxCalculator.calculate()`"                   ← class.method
  "imports from `specweaver.assurance.validation.runner`"   ← import path
```

Implementation: regex scan for path-like patterns (`/`, `.py`, `::`, dotted import paths with 3+
segments) outside code blocks.

## Changes

### 2A — Feature Spec authoring & validation

1. `src/specweaver/validation/spec_kind.py` [NEW] — `SpecKind` enum + `get_presets(rule_id, kind)`
   returning threshold overrides per rule.
2. `src/specweaver/validation/rules/spec/s01_one_sentence.py` — constructor gains
   `kind: SpecKind | None = None`; when set, kind-specific thresholds. **Header matching is
   configurable**: `## Intent` for `FEATURE`, `## 1. Purpose` for `COMPONENT` (default), via
   `_HEADER_MAP[SpecKind] → regex`.
3. `src/specweaver/validation/rules/spec/s03_stranger.py` — `kind: SpecKind | None = None`;
   `kind=FEATURE` switches to abstraction-leak mode (flag file paths, class names, function
   signatures instead of counting external file references).
4. `src/specweaver/validation/rules/spec/s04_dependency_dir.py` — `kind: SpecKind | None = None`;
   `kind=FEATURE` returns SKIP immediately.
5. `src/specweaver/validation/rules/spec/s05_day_test.py` — `kind: SpecKind | None = None`;
   kind-specific thresholds.
6. `src/specweaver/validation/rules/spec/s08_ambiguity.py` — `kind: SpecKind | None = None`;
   kind-specific thresholds.
7. `src/specweaver/validation/runner.py` — `get_spec_rules()` gains `kind: SpecKind | None = None`,
   passed to rule constructors.
8. `src/specweaver/cli.py` — `sw check --level` goes from 2 to 3 values: `feature` | `component` |
   `code`. `feature` and `component` run spec rules (different `SpecKind` thresholds); `code` runs
   code rules (unchanged).
9. `src/specweaver/drafting/feature_drafter.py` [NEW] — `FeatureDrafter`, 5-section template (Intent,
   Blast Radius, Change Map, Integration Seams, Sequence). Works for greenfield; business and
   technical features.
10. `src/specweaver/review/reviewer.py`:
    - `confidence: int = 0` field on `ReviewFinding`
    - LLM prompt asks for a confidence score (0-100) per finding
    - `confidence_threshold: int = 80` param on `Reviewer.__init__()`
    - `_parse_response()` extracts confidence and filters by threshold
    - findings below threshold stay in `ReviewResult`, marked `below_threshold=True`
11. `src/specweaver/flow/handlers.py`:
    - new `DraftFeatureHandler` (draft+feature)
    - `ValidateSpecHandler` reads `kind` from `step.params`
    - `ReviewSpecHandler` / `ReviewCodeHandler` can read `confidence_threshold` from `step.params`

### 2B — Decomposition agent

1. `src/specweaver/drafting/decomposition.py` [NEW]:

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

   `coverage_score` = (ComponentChange entries matching Blast Radius entries) / (total Blast Radius
   entries), LLM-assisted because Blast Radius may be free-form. `alignment_notes` and per-item
   `confidence` exist so a future auto-gate can replace HITL.
2. `src/specweaver/flow/models.py`:
   - `StepAction.DECOMPOSE = "decompose"`
   - `StepTarget.FEATURE = "feature"`
   - new valid combinations: `(DRAFT, FEATURE)`, `(VALIDATE, FEATURE)`, `(DECOMPOSE, FEATURE)`
3. `DecomposeHandler` in `src/specweaver/flow/handlers.py` [NEW]:
   1. Read the Feature Spec
   2. Load topology as **guidance** (optional — greenfield works without it)
   3. LLM prompt: Feature Spec + topology → `DecompositionPlan` JSON
   4. With topology: new components are **signals** (not errors) in `alignment_notes`
   5. Write `features/<name>_decomposition.yaml` + stub Component Specs
   6. Gate: HITL reviews (structured data supports a future auto-gate)

   The step can produce **sub-Feature Specs** (recursive) OR Component Specs — the gate decides.
4. `src/specweaver/pipelines/feature_decomposition.yaml` [NEW]:

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

## Tests

Regression — all ~1696 tests must pass, zero regressions:

```bash
uv run pytest tests/ -x -q
```

| Test File | Covers |
|---|---|
| `tests/unit/validation/test_spec_kind.py` | `SpecKind` enum, preset lookup, None fallback |
| `tests/unit/validation/rules/spec/test_rules_by_kind.py` | S01/S05/S08 feature thresholds; S03 abstraction leak mode; S04 skip for feature |
| `tests/unit/validation/qa_runner.py` (extend) | `get_spec_rules(kind=...)` passes through |
| `tests/unit/drafting/test_feature_drafter.py` | 5-section template, mock LLM, greenfield |
| `tests/unit/drafting/test_decomposition.py` | Model construction, YAML round-trip, stub generation, coverage_score, confidence field |
| `tests/unit/flow/test_decompose_handler.py` | Valid/invalid LLM response, greenfield, with topology, alignment_notes |
| `tests/unit/flow/test_models.py` (extend) | New enum values, valid combinations, pipeline loads |
| `tests/unit/review/test_reviewer.py` (extend) | Confidence parsing, threshold filtering, below_threshold marking |

Manual:

1. `sw check --kind feature <feature_spec.md>` → applies feature-level thresholds
2. `sw check <module_spec.md>` → identical to today (default = component)
3. `sw pipelines` → lists `feature_decomposition`
