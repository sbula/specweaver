# Walkthrough: INT-US-21 SF-01 CB-1 — Registry Completeness (FR-1)

- **Design**: `INT-US-21_design.md` (APPROVED 2026-07-25)
- **Plan**: `INT-US-21_sf01_implementation_plan.md` (APPROVED 2026-07-25)
- **Commit boundary**: 1 of 4
- **Date**: 2026-07-25

---

## What changed and why

`feature_decomposition.yaml` ships with `draft+feature` and `validate+feature` as steps 1–2. Both
pairs are declared valid in `VALID_STEP_COMBINATIONS` (`engine/models.py:115-117`) but neither was
mapped in `StepHandlerRegistry`. The runner therefore errored at step 1 with
`No handler registered for draft+feature` — the shipped pipeline was unrunnable. `FeatureDrafter`
existed (`workflows/drafting/feature_drafter.py:178`) but was unexposed and had no handler.

| File | Change |
|---|---|
| `core/flow/handlers/draft.py` | **+`DraftFeatureHandler`** wrapping `FeatureDrafter` with full `DraftSpecHandler` parity; **`_pop_feedback` extracted** to module-level `_pop_step_feedback` (delegate retained) |
| `core/flow/handlers/registry.py` | **+2 rows**: `(DRAFT, FEATURE)` → `DraftFeatureHandler`; `(VALIDATE, FEATURE)` → `ValidateSpecHandler` |
| `workflows/drafting/context.yaml` | `exposes:` gains `FeatureDrafter` |
| `docs/architecture/06_lessons_and_future/known_boundary_violations.md` | **+1 row** for the `forbids: specweaver/drafting` breach (AD-3) |
| `docs/architecture/02_bounded_contexts/domain_flow_engine.md` | Registry table corrected — 9 missing handlers added, all stale module paths fixed |
| `docs/dev_guides/special_patterns_and_adaptations.md` | **+Pattern 24** — Round-Trip Name Derivation for Self-Naming Writers |
| `tests/unit/core/flow/handlers/test_draft_feature_handler.py` | **NEW** — 41 tests |
| `tests/integration/core/flow/engine/test_feature_pipeline.py` | +2 tests; **`PIPELINES_DIR` inherited defect fixed** |

### The core design problem

`FeatureDrafter.draft()` takes `(name, output_dir)` and **derives its own output path** as
`output_dir/f"{name}_feature_spec.md"` — it never accepts a target file. Every downstream step reads
`context.spec_path`. Wrapping it naively means the drafter writes a file nothing downstream opens,
and the failure surfaces two steps later as "spec not found". `DraftFeatureHandler` inverts the
derivation so the drafter's self-chosen path IS `context.spec_path` by construction, guards the
filename shape before spending any tokens, and asserts the round trip after the call.

`(VALIDATE, FEATURE)` needed **no handler work at all** — `ValidateSpecHandler` already routes
`kind=feature` to the `validation_spec_feature` battery (`validation.py:155-156`), and the shipped
YAML already passes that param. A registry line was the whole fix.

---

## Test results

| Suite | Result |
|---|---|
| Unit | **4884 passed**, 15 skipped |
| Integration | **515 passed**, 3 skipped, 15 deselected |
| E2E | **166 passed**, 1 skipped |
| **Grand total** | **5565 passed, 19 skipped** |

Baseline before CB-1 was 5548 passed / 21 skipped. Net **+17 passed, −2 skipped** — the two
skip-reductions are the previously-dead tests described below.

## Quality gates

| Check | Result |
|---|---|
| `ruff check src/ tests/` | All checks passed |
| `mypy src/` | Success — no issues in 304 source files |
| `ruff check src/ --select C901` | All checks passed |
| `scripts/check_file_sizes.py` | 0 errors, 34 warnings (all pre-existing; none in changed files. `draft.py` is 445/500) |
| `tach check` | All modules validated |
| `scripts/check_roadmap_sync.py` | Dependency boxes fully in sync |

---

## HITL gate decisions

Every gate fired and was answered by the user. **None were skipped or auto-approved.**

| Gate | Findings presented | User decision |
|---|---|---|
| **Design Phase 6** | Consistency check + Red/Blue cycles 1–2: 9 findings (2 HIGH), 9 corrections applied. OQ-1 (registry ID `SUB` vs `SF01`) escalated with 3 options | **Approved.** OQ-1 → Option B (keep naming as-is). Added **AD-9**: audit the delivered `INT-US-21-SUB` add-on at epic closure, audit-only, findings → new story |
| **Plan Phase 4** | 8 audit questions (2 HIGH: approval-signal seam, three-session E6/E7) + 1 architectural violation (AD-3 evidence misattributed) | **All 8 proposals approved** → recorded as binding decisions D1–D8 |
| **Plan Phase 5** | Red/Blue cycles 1–2 on the plan: 7 findings, 5 fixes, 1 invalid, 1 accepted | **Approved** |
| **Dev Phase 2** | Task list + Red/Blue: 5 fixes (notably `_pop_feedback` extraction needing a delegate, and 2 missing steps in T1.5 without which the handler cannot be constructed) | **Approved** |
| **Pre-commit Phase 1+2** | Architecture: no new violations. Coverage matrix + 12 proposed stories. Headline gap: FR-1's acceptance criterion had **no test at any level** | **Approved** |
| **Pre-commit Phase 3** | 12 stories implemented + 1 inherited defect fixed | **Approved** |
| **Pre-commit Phase 7.5** | Red/Blue on the diff, 2 cycles: 1 HIGH fixed, 1 MEDIUM accepted, 1 LOW actioned | *presented at the commit gate* |

### Phase 7.5 Red/Blue detail

- **HIGH — fixed.** `_execute_drafting` could return `PASSED` for a spec that does not exist: after
  the round-trip path assertion, every remaining guard is existence-checked (`if
  result_path.exists()`), so a drafter returning the right path without writing anything fell
  through silently. Added an explicit existence check + test
  (`test_correct_path_but_no_file_written_errors`). `DraftSpecHandler` has the same hole; not
  changed here (no FR covers it) — **candidate for a TECH ticket**.
- **MEDIUM — accepted risk.** `gen_config` construction and `_build_base_prompt` sit outside the
  `try`, so a malformed `context.config` (e.g. `config.llm is None`) raises and is caught by the
  runner rather than producing a handler-specific message. This is verbatim `DraftSpecHandler`
  structure; diverging without an FR would break the parity FR-1 asks for.
- **LOW — actioned.** `FEATURE_SPEC_SUFFIX` is deliberately a public module constant so SF-03's
  `_resolve_spec_path` can import it instead of re-hardcoding `_feature_spec.md`. Recorded in the
  plan's Backlog against D6 — this is the concrete mitigation for the CB-1↔SF-03 coupling risk.

---

## Inherited defects fixed (not deferred)

1. **`PIPELINES_DIR` pointed at a nonexistent path.** `test_feature_pipeline.py` used
   `Path(__file__).resolve().parents[4]`, which is `tests/`, not the repo root. Both tests in
   `TestFeatureDecompositionPipelineIntegration` are guarded by
   `if not path.exists(): pytest.skip(...)` — so they had **never once executed** since being
   written. Corrected to `parents[5]`; integration skips dropped 5 → 3.

2. **Stale registry table** in `domain_flow_engine.md` — missing 9 shipped handlers, and every
   module path referenced files (`flow/_draft.py`) that no longer exist. The design had assigned
   this to SF-03's docs pass; corrected here since CB-1 modifies that registry.

> **Pattern worth flagging for SF-03.** This is the *third* vacuous-proof instance found in this
> feature: INT-US-02's E6/E7 assert only `exit_code == 0` (PARKED and COMPLETED both exit 0);
> `test_pipeline_yaml_loads_and_parks_at_hitl` overwrites every handler with `_AlwaysPassHandler`
> before running the "real" pipeline; and these two tests never ran at all. When SF-03 writes the
> verifiable proof for FR-10, assume nothing about existing coverage until it is re-read.

---

## What CB-1 deliberately does NOT do

- No CLI change. `sw run feature_decomposition <name>` still does not resolve a bare module name —
  `_resolve_spec_path` special-cases `new_feature` only. **Deferred to SF-03/FR-8 (D6)**, which
  MUST derive `specs/{name}_feature_spec.md` or every drafting run trips CB-1's convention guard.
- No hydration, rehydration or approve-on-resume — CB-2/3/4.
- No e2e proof — FR-8/FR-10 are SF-03's scope.
- US-21 is **not** marked 🟢 and no roadmap checkbox moved; the story is 1 of 4 commit boundaries
  into its first sub-feature.
