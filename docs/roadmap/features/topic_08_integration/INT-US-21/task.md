# Task List: INT-US-21 SF-01 — Flow-Engine Substrate

- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_sf01_implementation_plan.md
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_design.md
- **Commit boundaries**: 4 — CB-1 registry completeness (FR-1); CB-2 `decomposition` field + shared
  hydration (FR-2); CB-3 cross-session rehydration (FR-3); CB-4 approve-on-resume + NFR-1
  re-assertions (FR-4).
- **Scope**: engine substrate ONLY. Artifact persistence, stub specs and the seam pins are SF-02;
  the CLI journey, e2e proof and registry closure are SF-03. Do NOT pull them forward.
- **Binding**: plan decisions D1–D8 and its Red/Blue corrections (`R/B C1.x` / `C2.x`) are settled.

---

## CB-1 — Registry completeness (FR-1)  ← CURRENT

### Adversarial Test Matrix

| Bucket | Covered by |
|--------|-----------|
| **Happy path** | exists-skip → PASSED + `artifact_uuid`; drafting writes exactly `context.spec_path`; registry resolves `(DRAFT,FEATURE)` and `(VALIDATE,FEATURE)` |
| **Boundary/Edge** | `_feature_spec.md` (empty derived name) → loud ERROR; `foo.md` (no suffix) → loud ERROR; derived `name` can never contain a path separator; nested specs dir |
| **Graceful degradation** | `context.db` unset → lineage skipped, still PASSES; `FeatureDrafter.draft` raises → ERROR result, not a propagated exception; drafter returns a path ≠ `spec_path` → ERROR |
| **Hostile/Wrong input** | `spec_path` pointing at a *directory* → no unhandled exception; traversal-shaped name (`../../x_feature_spec.md`) cannot make the derived `name` escape `spec_path.parent`; `None`-ish context (`llm`/`context_provider` unset) → park, never crash |

### Handler step order (fixed — R/B T9)

`_pop_step_feedback` MUST run first (R-10 item 1: otherwise the exists-skip fires on re-entry and
the loop_back rejection path is dead). Full order:

1. pop feedback (consumed exactly once, whatever happens next)
2. name-derivation guard (suffix + non-empty) → ERROR
3. feedback branches (re-draft / headless park with findings)
4. path-kind guard (exists but not a file → ERROR)
5. exists-skip (`is_file()`) → PASSED
6. no provider / no llm → headless park
7. draft

> **Deviation from the first draft (as implemented):** the name guard was moved *ahead of* the
> feedback branches. An unusable spec path is fatal regardless of whether reviewer findings are
> present — with the original order, feedback + interactive would have entered drafting with a
> name that cannot round-trip. The pop still happens first so the once-only contract holds.

### Tasks

- [x] **T1.1** — Name-derivation guard: reject a `spec_path` whose name lacks the
      `_feature_spec.md` suffix **or** whose derived name is empty, with a loud ERROR naming the
      convention. Runs before any LLM/prompt setup so failure costs nothing.
      *src*: `core/flow/handlers/draft.py` · *test*: `tests/unit/core/flow/handlers/test_draft_feature_handler.py`
- [x] **T1.2** — Exists-skip → PASSED with `artifact_uuid` extracted from the file. Split the
      `exists()` check (R/B T2): a path that exists but is **not a file** → loud ERROR rather than
      either `read_text()`-ing a directory (today's `DraftSpecHandler` behaviour, which surfaces as
      an opaque runner-level ERROR) or silently falling through to drafting. Skip on `is_file()`.
      *src*: `draft.py` · *test*: same
- [x] **T1.3** — Headless park: no `context_provider` / no `llm` → `WAITING_FOR_INPUT` with an
      actionable message (`DraftSpecHandler` parity, R-10 item 4).
      *src*: `draft.py` · *test*: same
- [x] **T1.4** — Pop-once feedback parity (R-10 items 1–2): feedback + interactive → re-draft;
      feedback + headless → park carrying `reviewer_findings`.
      **Extract `_pop_feedback` to a module-level `_pop_step_feedback(step, context)` and have BOTH
      handlers call it** (R/B T1 — reaching into `DraftSpecHandler`'s private staticmethod from a
      sibling class is the wrong shape). Keep `DraftSpecHandler._pop_feedback` as a thin delegate:
      four existing tests call it directly (`test_draft_handler.py:199-213`) and must stay green.
      Give the new module-level helper its own direct tests.
      *src*: `draft.py` · *test*: same + `test_draft_handler.py`
- [x] **T1.5** — Drafting path, full `DraftSpecHandler` parity (R-10 items 5–6):
      - resolve the render profile via `resolve_profile(step.params.get("render_profile"),
        default=INTERACTIVE)`; `ValueError` → `_error_result` (R/B T4 — missing from the first draft)
      - build the required `base_prompt` via `_build_base_prompt` (R/B T5 — `FeatureDrafter`'s
        constructor requires it; without this the handler cannot be built at all)
      - construct `FeatureDrafter` with **keyword args only** (R-9 — its positional order differs
        from `Drafter`)
      - assert the returned path `== context.spec_path` → ERROR on mismatch
      - uuid tag if absent; `log_artifact_event(event_type="drafted_feature_spec")` when
        `context.db` is set
      - wrap the drafter call so an exception becomes an ERROR result, never propagates
      *src*: `draft.py` · *test*: same
- [x] **T1.6** — Registry rows: `(DRAFT, FEATURE) -> DraftFeatureHandler()` and
      `(VALIDATE, FEATURE) -> ValidateSpecHandler()` (the latter is a registry line only — R-11).
      *src*: `core/flow/handlers/registry.py` · *test*: `tests/unit/core/flow/handlers/test_handlers.py`
- [x] **T1.7** — Boundary bookkeeping: add `FeatureDrafter` to `workflows/drafting/context.yaml`
      `exposes:`; add the new `forbids: specweaver/drafting` row to
      `docs/architecture/known_boundary_violations.md` (D8 — a **new** row cross-referencing the
      existing inline-import row, not an amendment to it).
      *src*: both files · *test*: n/a (docs + manifest; verified by reading)

### Gate
- [x] Full suite green (5548 passed / 21 skipped), `ruff` clean, `mypy` clean (304 files), `tach check` OK
- Pre-commit skill:
  - [x] Phase 1 — Architecture verification (no new violations; AD-3 ledgered)
  - [x] Phase 2 — Test gap analysis (12 stories, HITL approved)
  - [x] Phase 3 — Implement missing tests (12 added + 1 inherited defect fixed)
  - [x] Phase 4 — Full test suite
  - [x] Phase 5 — Code quality
  - [x] Phase 6 — Documentation
  - [x] Phase 7 — Walkthrough
  - [x] Phase 7.5 — Red/Blue on code changes
- [ ] **HITL commit stop**

---

## CB-2 — `RunContext.decomposition` + shared hydration (FR-2)

- [ ] **T2.1** — Add `decomposition: str | None` to `RunContext`; correct `plan`'s comment to name
      the implementation PlanArtifact (AD-1).
- [ ] **T2.2** — Hydration helper in `runner.py`: PASSED-only; `decompose+feature` →
      `context.decomposition`; `plan+spec` → read `plan_path` → `context.plan`; missing key/file →
      WARNING + leave untouched; INFO log with `run_id`.
- [ ] **T2.3** — Call it at the **join point before `router = step_def.router`** (`runner.py:491`),
      reached by both the gate-advance and no-gate paths (R/B C1.1 — NOT inside the gate block).
- [ ] **T2.4** — Migrate `OrchestrateComponentsHandler` to `context.decomposition`
      (`decompose.py:119,127`); update the error message. Fan-out mechanics below `:130` are DMZ.
- [ ] Gate + **HITL commit stop**

## CB-3 — Cross-session rehydration (FR-3)

- [ ] **T3.1** — In `resume()`, before `execute_run`, walk `step_records`; hydrate from records
      where `result is not None and result.status is PASSED` (NOT `record.status`).
- [ ] **T3.2** — Pair-guard on **both** length and `step_name` identity; skip + warn on either
      mismatch (R/B C2.3 — a reordered YAML keeps the same length).
- [ ] Gate + **HITL commit stop**

## CB-4 — Approve-on-resume + NFR-1 re-assertions (FR-4)

- [ ] **T4.1** — Explicit approval kwarg on `_execute_loop`, forwarded through `execute_run`;
      `resume()` passes `True`, `run()` unchanged (D1).
- [ ] **T4.2** — Approval branch at the **very top of the loop body** (after
      `attempts.setdefault`) — before the handler lookup, the staleness bypass, and
      `mark_step_running` (R/B C1.2 + R-1).
- [ ] **T4.3** — Four-condition check (record `WAITING_FOR_INPUT` + stored result `PASSED` + HITL
      gate + signal live); hydrate, complete, persist, `gate_approved_on_resume`, emit with the
      `approved_on_resume` marker (D3).
- [ ] **T4.4** — Re-assert INT-US-02 E6/E7 as **three-session** journeys asserting COMPLETED from
      the persisted record + a drained verdict queue (D2).
- [ ] **T4.5** — Refresh `test_pipeline_state_persistence.py:79-80` (the `gate = None` workaround
      is obsolete); add the REST gate-approve regression test (D7).
- [ ] Gate + **HITL commit stop**
- [ ] Design-doc tracker: `Dev ✅`, `Pre-Commit ✅`, `Committed ✅`; Session Handoff updated
