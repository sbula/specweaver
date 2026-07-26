# Design: INT-US-21 — Autonomous Feature Decomposition (Base Integration Contract)

- **Feature ID**: INT-US-21
- **Phase**: Integration (Topic 08)
- **Status**: APPROVED (user, 2026-07-25)
- **Design Doc**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_design.md

## Feature Overview

INT-US-21 turns the already-built decomposition capabilities into a working epic journey: a user
hands an epic-level (feature-kind) spec to `sw run feature_decomposition <spec>` and the system
validates it at feature thresholds, decomposes it into a DAG of small, DAL-rated, testable
sub-components, persists the reviewed DecompositionPlan as a durable artifact (plus stub component
specs), and completes through the HITL review gates via `sw resume`. It solves the
"built-but-not-integrated" problem: `D-INTL-02` (SpecKind, DecomposeFeatureHandler,
`feature_decomposition.yaml`) and `D-INTL-03` (PlanSpecHandler) exist as capabilities, but the
shipped pipeline is unrunnable (unregistered handlers), `context.plan` is populated nowhere, the
flow engine has no HITL approval semantics (resume re-parks forever — proven empirically), and the
plan artifact is never persisted. It interacts with the flow engine (runner, gates, registry,
handlers), `workflows/drafting` (FeatureDrafter exposure), and the pipeline YAML/state store; it
does NOT touch recursive decomposition (`C-INTL-01`/`INT-US-21-SF01`, delivered), autonomous DAG
*execution* (delegated to the new `C-FLOW-12` + `INT-US-21-SF02` add-on), or DAL-escalated run
isolation (`C-EXEC-07`/`INT-US-09-SF06`). Key constraints: base contract = Core-Required MVS only;
INT-US-02/03/24 structural precedent (verifiable proof on the real CLI, standard display/exit-code
contract); the add-on seams MUST be frozen forward-compatible so `C-FLOW-12` integrates on top of
the base without rework (user mandate, 2026-07-24).

## Research Findings

### Codebase Patterns

**The four verified gaps (all inherited):**

1. **Unrunnable shipped pipeline.** `feature_decomposition.yaml` steps 1–2 use `draft+feature` /
   `validate+feature` — valid in `VALID_STEP_COMBINATIONS` (`engine/models.py:116-117`) but never
   mapped in `StepHandlerRegistry` (`handlers/registry.py:97-117`) → runner errors "No handler
   registered for draft+feature" at step 1. `FeatureDrafter` exists
   (`workflows/drafting/feature_drafter.py:178`, interview-driven, template Done Definition demands
   a DAL declaration) but is unexposed (`drafting/context.yaml` exposes only `Drafter`) and has no
   handler. `ValidateSpecHandler` already routes `kind=="feature"` → `validation_spec_feature`
   battery (`handlers/validation.py:82-92,155-156`).
2. **`context.plan` populated nowhere.** `RunContext.plan` promises "(set by runner hook)"
   (`handlers/base.py:63`) — zero writes in `src/`; no hook exists in `engine/runner.py`. Readers:
   `OrchestrateComponentsHandler` (`decompose.py:119,127`, expects a JSON string of a
   DecompositionPlan) and `GenerateCode/TestsHandler` (`generation.py:159-160,265-266`,
   `add_plan` prompt enrichment expecting a PlanArtifact). **Two colliding plan concepts on one
   field** — the decomposition plan (feature→components) vs. the implementation plan
   (spec→file-layout, persisted by `PlanSpecHandler` as `<stem>_plan.yaml`). INT-US-24 AD-5
   explicitly bequeathed this gap here.
3. **No HITL approval semantics — resume re-parks forever.** `gates.py:54-58` parks HITL gates
   unconditionally; `park_current_step` keeps `current_step` at the parked step
   (`state.py:190-199`); `PipelineRunner.resume()` only flips status to RUNNING → the loop
   re-executes the step and the gate re-parks. Proven empirically (INT-US-02 E7 run with logs:
   session 2 re-parks at `draft_spec` with `result_status=passed`; the scripted DENY/ACCEPT
   verdicts are never consumed). INT-US-02's E6/E7 are vacuously green because PARKED and
   COMPLETED both exit 0. No test in the suite drives a bundled pipeline THROUGH a HITL gate.
4. **No decomposition artifact.** `DecomposeFeatureHandler` returns `plan.model_dump()` only into
   the step record; D-INTL-02's original plan (§6.2) promised writing
   `<name>_decomposition.yaml` + stub Component Specs — never shipped. `feature_name` falls back
   to `"unknown_feature"` (`decompose.py:30`; the bundled YAML passes no params).

**Adjacent facts constraining the design:** step records ARE fully persisted (JSON in SQLite,
`store.py:132-133`) → resume-time rehydration can be honest, unlike `context.feedback`
(NOT persisted — INT-US-24 FR-2 correction). `context.workspace_roots` ("set by decomposition")
is likewise never set; consumed by sandbox security + review — deliberately deferred to the
add-on (per-component boundary scoping is an execution concern). The orchestrate fan-out shares
ONE mutable `RunContext` across concurrent sub-runners (`decompose.py:230-236`) — latent race,
never exercised; owned by the add-on. D-INTL-02 §Decision #1 moved fan-out out of scope ("2C →
Feature 3.14"), confirming the decompose→orchestrate bridge was never designed end-to-end.
`pipeline_engine_guide.md` §5 CAUTIONs: coverage `< 1.0` → rigid 3-strike loop → FAILED;
orchestrate loop/error bounds are DMZ assumptions — don't touch in the base. Reuse anchors:
`PlanSpecHandler`'s persist+lineage+uuid-tag pattern (`generation.py:387-411,478-487`);
`DraftSpecHandler`'s exists-skip + pop-once feedback + headless-park contract (`draft.py`);
INT-US-24's e2e harness pattern (scripted adapter, real CLI, persisted-run-record assertions,
fresh CliRunner per session).

**Boundary rules:** tach already allows `core.flow → workflows.drafting/planning` (no new edge).
`core/flow/context.yaml` `forbids: specweaver/drafting` — already bent by `DraftSpecHandler` via
inline import (acknowledged DEFERRED debt, `known_boundary_violations.md:9`); AD-3 extends the
existing seam, approved. `workflows/pipelines` is data-only. `drafting/context.yaml` exposes list
gains `FeatureDrafter`.

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| — (pure internal integration) | — | `graphlib`, `ruamel.yaml`, SQLite via existing store — all in use | pyproject.toml |

### Blueprint References

Planner→DAG-executor with persisted plan artifact, explicit state-machine HITL pauses, and a
replanner loop is the standard shape (Planner-Executor Agentic Framework, emergentmind.com;
skywork.ai 2025 workflow patterns; zylos.ai long-running agents 2026-01). SpecWeaver has all the
pieces; this contract wires them honestly. Grill-style authoring (D-INTL-04/D-INTL-07) is
deliberately upstream and decoupled — gates stay authoring-agnostic (draft.py carries the
"D-INTL-07 supersession target — do not invest in prompt shaping" marker).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Registry completeness | Flow engine | Register `(DRAFT, FEATURE)` → new thin `DraftFeatureHandler` (wraps `FeatureDrafter`; exists-skip, pop-once feedback, headless-park — full `DraftSpecHandler` parity) and `(VALIDATE, FEATURE)` → the existing `ValidateSpecHandler` (kind param passthrough); expose `FeatureDrafter` in `drafting/context.yaml`. **Path reconciliation (R/B C1.1):** `FeatureDrafter.draft()` self-derives its output as `output_dir/<name>_feature_spec.md` (`feature_drafter.py:260`) while every downstream step reads `context.spec_path`. The handler therefore derives `name` by stripping the `_feature_spec.md` suffix from `context.spec_path.name` and passes `output_dir=context.spec_path.parent`, so the drafter's return value is `context.spec_path` by construction; a `spec_path` not matching `*_feature_spec.md` → loud `ERROR` naming the required convention (zero drafting-UX investment, per AD-5). The returned path is asserted equal to `context.spec_path` before `PASSED` | The bundled `feature_decomposition.yaml` executes past steps 1–2 with real handlers, and an in-session draft is guaranteed to be the file validate/decompose read |
| FR-2 | Plan hydration hook (both plan concepts) | Runner post-step hook | After a step's stored result is `PASSED`: `decompose+feature` → set new field `context.decomposition` = canonical JSON string of the step's `DecompositionPlan` output; `plan+spec` → set `context.plan` = content read from the step's `plan_path` output (implementation PlanArtifact for `add_plan` consumers). `OrchestrateComponentsHandler` migrates to consume `context.decomposition`. **The hook fires on every path that stores a `PASSED` result — including FR-4's approve-on-resume completion, which never executes a handler (R/B C2.3); FR-3 rehydration and this hook share one hydration function so the two can never drift** | Both bridges work with zero field collision (D1a); D-INTL-03 becomes integrable-by-YAML in any pipeline without touching delivered YAML (R/B R11 fix) |
| FR-3 | Cross-session rehydration | Runner resume path | On `resume()`, before the loop starts, rehydrate from persisted step records keyed on the **stored RESULT status `PASSED`** (a gate-parked step's record status is `WAITING_FOR_INPUT` while its stored result is `PASSED` — R/B R2 fix); latest matching record by step index wins; a missing/deleted plan file at rehydration → WARNING + skip (consumers fail with their own loud message) | A parked-then-resumed journey retains both plans honestly (no `context.feedback`-style myth) |
| FR-4 | HITL approve-on-resume | Flow engine (gates + runner) | On resume, a step whose record is `WAITING_FOR_INPUT` with a stored result status `PASSED` and a HITL gate ⇒ human resumed = approved → complete the step from the stored result and advance. **The approval path MUST bypass BOTH the handler execution AND the gate evaluation for that step (R/B C1.6):** `GateEvaluator.evaluate` parks HITL unconditionally (`gates.py:53-57`) and the loop returns on `verdict == "park"` (`runner.py:402`), so skipping only the handler re-parks and the defect survives verbatim. The approved step is completed and `current_step` advanced before the gate block is reached; approval applies to the resumed step only (once per park), never to later steps. Handler-parks (stored result status `WAITING_FOR_INPUT`) re-execute as today | `sw resume` advances past reviewed HITL gates engine-wide; INT-US-02 E6/E7 re-asserted to genuinely prove flow-through (adapter consumption asserted) per the inherited-failures rule |
| FR-5 | Decomposition artifact persistence | `DecomposeFeatureHandler` | Persist the validated plan as `<spec_stem>_decomposition.yaml` next to the spec (uuid artifact tag, `generated_decomposition` lineage event — `PlanSpecHandler` parity **for the sequence**: derive path → extract-or-generate uuid → tag → write → lineage). **Correction (SF-02 Phase-0, 2026-07-25): the serialization call is NOT parity.** `PlanSpecHandler` uses `model_dump()`, which is safe only because `PlanArtifact` has no enum fields; `DecompositionPlan.components[].proposed_dal` is a required `DALLevel`, and ruamel raises `RepresenterError` on it — a 100% failure rate. Use **`model_dump(mode="json")`**, which also makes the artifact byte-identical to SF-01's hydrated `context.decomposition` (verified), so the on-disk and in-memory contracts of this AD-4-frozen seam agree. Generalised by `TECH-016`; derive `feature_name` from the spec stem when the step param is absent | The reviewed plan is a durable, lineage-tracked artifact; no more `"unknown_feature"` |
| FR-6 | Stub component specs | `DecomposeFeatureHandler` (post-persist) | For each `ComponentChange` with a name-validated component (reuse the fan-out's `^[a-zA-Z0-9_\-]+$` guard), write `specs/<component>_spec.md` IF absent (never overwrite), pre-seeding Purpose from `description`. **Template source (R/B C1.2):** read `<project>/.specweaver/templates/component_spec.md` as a FILE (the `sw init` scaffold, `scaffold.py:275`); if absent — unscaffolded projects have no such file — fall back to a minimal heading skeleton defined locally in the handler. Do NOT import `_DEFAULT_COMPONENT_SPEC` from `workspace/project/scaffold.py`: `core/flow/context.yaml` `consumes` lists only `specweaver/workspace/memory`, so the import would be a new boundary violation (tach permits `specweaver.workspace` wholesale — it would not be caught) | The DAG becomes tangible per-component spec files the user can carry into `sw implement` today (D-INTL-02 §6.2 promise delivered), with no new consumes edge |
| FR-7 | DAL artifact contract | Decompose output + artifact | `proposed_dal` per component survives serialization to the persisted artifact (see FR-5's correction — this is exactly what the `mode="json"` dump guarantees) and is carried in a human-readable summary the handler emits in its own `StepResult.output`. **Correction (SF-02 Phase-0, 2026-07-25):** no park surface renders step output today — `_on_run_parked` prints only the step name and the resume hint — so "shown at the HITL park" was not achievable as written. SF-02 guarantees the data and the summary; **rich rendering at the park belongs to SF-03's CLI journey (FR-8)**, which owns the display contract | The plan is the DAL source of truth downstream (C-FLOW-12's per-sub-run isolation and C-EXEC-07 consume it unchanged) |
| FR-8 | CLI journey | `sw run` / `sw resume` | `sw run feature_decomposition <spec>` (spec pre-exists → draft skips) → gate-park #1 (draft HITL) → resume → validate (feature thresholds) → decompose → gate-park #2 (review) → resume → COMPLETED; display/exit-code parity with INT-US-02 (COMPLETED→0, FAILED→1, PARKED→0 + resume hint) | The full epic journey works end-to-end on the real CLI across three sessions |
| FR-9 | Plan-bridge seam pin (hook-driven) | Integration tests | A custom `plan+spec → generate+code` pipeline proves `context.plan` reaches generation **hook-driven**; today's `test_planning_integration.py` seeds the field manually, so it proves nothing about production wiring. **Descoped 2026-07-26 (user, scope re-cut):** the original FR-9 also demanded *(a)* a decompose→orchestrate pin with a doubled sub-runner to freeze the fan-out seam for `C-FLOW-12`. `C-FLOW-12` does not exist — SF-03 *mints* it, and it is sequenced behind `C-EXEC-07` — so that half was a regression pin for a capability two stories away from being designed: speculative generality with a permanent suite cost. Dropped. The add-on writes its own pin when it lands, against a contract it can actually see | The D-INTL-03 plan bridge is proven in production wiring rather than in a fixture |
| FR-10 | Verifiable proof | e2e suite (real CLI, scripted adapter) | Scenarios: happy 3-session journey (both approve-on-resume advances asserted at ZERO LLM calls + artifact/stub inventory + no strays); coverage<1.0 → HITL park with the coverage failure surfaced in the park message → resume re-executes decompose (fresh LLM round; human-bounded — the bundled gate is HITL, so the auto 3-strike loop is custom-pipeline territory, already pinned in `test_decomposition_loop_integration.py`); garbage LLM JSON → loud ValueError; headless park when spec missing; cross-session rehydration (fresh CliRunner per session, persisted-run-record assertions); zero-component plan; stub-spec no-overwrite | The contract is proven the INT-US-24 way; the first test in the suite to drive a bundled pipeline THROUGH a HITL gate |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Delivered-journey compatibility | `new_feature`, `scenario_integration`, `sw implement` behavior unchanged EXCEPT FR-4, which makes INT-US-02's already-claimed park→resume semantics true (documented inherited-defect fix; E6/E7 re-asserted, full suite green) |
| NFR-2 | Cross-session honesty | Rehydration reads ONLY persisted state (step records / artifact file); no in-memory field is assumed to survive a session (INT-US-24 lesson). **Named inherited limit (R/B C1.5):** `_execute_loop` re-initializes `attempts: dict[int,int] = {}` on every entry (`runner.py:210`), so `validate_feature`'s `max_retries: 3` budget resets per session — a resumed run gets a fresh 3 strikes. Inherited, NOT fixed here (persisting attempt counters is a state-schema change; `C-FLOW-07` territory). Stated so no planner assumes retries accumulate across `sw resume` |
| NFR-3 | LLM economy | The journey costs exactly the decompose LLM call(s) (+ drafting only when the spec is authored in-session); persistence, hydration, approval and stubs add ZERO LLM calls |
| NFR-4 | Fail-loud parity | Coverage 3-strike loop, malformed LLM JSON, and missing handlers keep their existing loud failure semantics (pipeline_engine_guide DMZ CAUTIONs untouched) |
| NFR-5 | Injection safety | Component names are validated (`^[a-zA-Z0-9_\-]+$`) before any filesystem write (stub specs, artifact refs); LLM content never forms a path segment unvalidated |
| NFR-6 | Boundary hygiene | Zero new tach edges (`tach.toml:42` already lists `specweaver.workflows.drafting` under `specweaver.core.flow`); no new `consumes` edge in any `context.yaml` (see FR-6). **`known_boundary_violations.md` MUST gain an explicit row for the `core/flow` → `workflows/drafting` `forbids` breach in SF-01 (R/B C1.3)** — today's line 9 records only the *inline-import* anti-pattern for `core/flow/handlers/*`, NOT the `forbids: specweaver/drafting` rule itself, so AD-3's "already acknowledged" is only half-true and the debt would otherwise stay unrecorded; `tach check` + roadmap-sync green at every commit |
| NFR-7 | Observability | Hydration, approval-advance, artifact writes and stub creation each log at INFO with run_id; park messages name the artifact path so the human can review before resuming. **The approve-on-resume advance MUST emit a `step_completed` event carrying an `approved_on_resume` marker (R/B C2.2)** — a step completed with no handler execution is otherwise invisible in the CLI display, and FR-10's "both advances asserted" needs an observable to assert on |
| NFR-8 | Session-isolation posture | `feature_decomposition` requires `session_isolation` OFF: C-EXEC-06 v1 RAISES on any park inside a session worktree (by design, AD-4 of C-EXEC-06). Documented as a host-posture fact in the dev guide; not worked around here |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| — | — | — | — | Pure internal integration; stdlib `graphlib`, existing `ruamel.yaml`, existing SQLite store |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Split the plan field: new `RunContext.decomposition` (DecompositionPlan JSON string) vs. `context.plan` (implementation PlanArtifact) | Two colliding concepts on one field is a latent type bug; one small migration in `decompose.py` ends it forever | No — approved by user 2026-07-24 (D1a) |
| AD-2 | Approve-on-resume is derived from persisted state (gate-park = record `WAITING_FOR_INPUT` + stored result `PASSED` + HITL gate); everything else re-executes: handler-parks (stored result `WAITING_FOR_INPUT`), HITL-gate parks on FAILED/ERROR results (human resumed a failed step → fresh attempt, human-bounded retry), and RESERVE parks (stored result `PENDING` → reservation retried) | No schema change, no new approval store; the distinction already exists in persisted data; applies engine-wide so every HITL pipeline (incl. add-on's) inherits it; the `PASSED`-only rule makes misclassification structurally impossible | No — approved by user 2026-07-24 (D2) |
| AD-3 | `DraftFeatureHandler` follows the existing `DraftSpecHandler` inline-import seam into `workflows/drafting` (`draft.py:121`). **Correction (R/B C1.3):** the *inline-import* half is acknowledged debt (`known_boundary_violations.md:9`); the `forbids: specweaver/drafting` breach in `core/flow/context.yaml` is NOT recorded anywhere — SF-01 adds that row (NFR-6) | Extends an acknowledged DEFERRED debt item without creating a new violation *class*; DI-inversion belongs to the existing monolith-purge ticket. Recording the unrecorded half keeps the debt ledger honest rather than inheriting a silent breach | **Yes — approved by user 2026-07-24 (D3a)** |
| AD-4 | Base = decomposition journey only; autonomous DAG *execution* (per-component spec synthesis, race-hardened fan-out, `proposed_dal`-driven isolation) minted as **`C-FLOW-12` + `INT-US-21-SF02`**, sequenced behind `C-EXEC-07`. The base freezes the add-on's seams: `context.decomposition` contract (FR-2 hydration + FR-5 artifact schema), stub spec paths (FR-6), `proposed_dal` presence (FR-7), approve-on-resume (FR-4). **Amended 2026-07-26:** "frozen" here means *the contract is defined and tested as it stands*, NOT that the base ships a forward-compatibility pin for the fan-out — the original FR-9(a) attempted that and was descoped (see FR-9). A pin written against an undesigned consumer freezes guesswork | Delivers the stated US-21 benefit ("break it down BEFORE writing any code") and closes the epic honestly; execution needs capabilities nobody claimed built; user mandate: the add-on must integrate completely on top of the base without rework | No — approved by user 2026-07-24 (D4) |
| AD-5 | Authoring-agnostic gates: zero investment in feature-spec drafting UX; spec-pre-exists posture (INT-US-24 E6 precedent); `FeatureDrafter` wrapped as-is | Drafting is a D-INTL-07 supersession target (grill-style interview slots in behind unchanged gates, INT-US-02 precedent); D-INTL-04 outputs reach the decomposer via the existing profile system | No |
| AD-6 | DAL execution posture delegated: journey-level isolation escalation stays with `C-EXEC-07`/`INT-US-09-SF06`; the base only guarantees the DAL *data* contract (FR-7) | Plan production is LLM-only (no untrusted code execution); same delegation INT-US-24 made; per-component posture belongs to the add-on where code actually runs | No |
| AD-7 | Artifact lands next to the spec (`specs/<stem>_decomposition.yaml`), not a `features/` dir | `PlanSpecHandler` precedent (`<stem>_plan.yaml` next to spec); one convention for all plan-class artifacts | No |
| AD-8 | Rehydration source of truth = persisted step records; the artifact file is the human-facing copy | Step records are already transactional & load-bearing for resume; file could be hand-edited between sessions (re-arbitrating hand-edits is `C-FLOW-05`/`B-INTL-07` territory, out of scope) | No |
| AD-9 | **Delivered-add-on re-validation is `TECH-018`, not a clause of this feature.** The obligation stands unchanged in substance: audit the delivered `INT-US-21-SUB` / `C-INTL-01` (Iterative Decomposition) against the integrated base — claimed scope still valid, still covers what US-21 needs, cooperates with the new seams (`context.decomposition`, the persisted `<stem>_decomposition.yaml` schema, approve-on-resume, the `feature_decomposition` journey). **Audit + report only**; findings become NEW stories or tickets, never edits to `INT-US-21-SUB` (finished-stories-immutable). **Relocated 2026-07-26:** it is no longer a gate on US-21 going 🟢 | User mandate, 2026-07-25 — the *reasoning* was and is sound: `C-INTL-01` was proven against a decomposition path that was never runnable end-to-end (§Research gaps), so its integration claim was never exercised through a real journey. But as `AD-9` it made an audit of a **different, delivered** story block closure of this one, with unknown size, on the critical path. Auditing story A must not hold story B hostage. Sequenced after SF-03 commits, since the integrated base is what it audits against | No |

## ROI Analysis

### Investment Cost

| Item | Effort | Risk |
|------|--------|------|
| SF-01 engine substrate (registry, bridge, rehydration, approve-on-resume) | Medium | Medium — approve-on-resume touches every HITL pipeline; mitigated by NFR-1 re-assertions + full suite |
| SF-02 artifacts & seam (persistence, stubs, DAL surfacing, orchestrate pin) | Small-medium | Low — mirrors shipped PlanSpecHandler patterns |
| SF-03 CLI journey + proof + docs + registry closure | Medium | Low — INT-US-24 harness pattern is proven |

### Returns

| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| US-21 epic | Closes 🟢 with the last MVS item | High |
| EVERY HITL pipeline (US-2, US-24, future) | Park→resume finally works engine-wide; INT-US-02's vacuous proofs made honest | High |
| `C-FLOW-12` / `INT-US-21-SF02` add-on | Frozen, regression-pinned seams — integrates without rework | High (user mandate) |
| `C-EXEC-07`, DAL machinery | `proposed_dal` becomes a reliable, persisted per-component contract | Medium |
| D-INTL-04 / D-INTL-07 (grill-style) | Authoring-agnostic gates + `context.decomposition` substrate to ride on | Medium (future) |
| INT-US-24 dual-pipeline | Orchestrate dispatch cleanly separated from the decomposition-plan path | Low |

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Approve-on-resume changes behavior of a flow someone relied on parking forever | Low | Medium | It is the documented INT-US-02 contract made true; NFR-1 re-assertions; walkthrough + user-guide currency (4_interactive_hitl_gates.md) |
| Gate-park vs handler-park misclassification (e.g. ERROR result under HITL gate) | Medium | Medium | Approval requires stored result `PASSED` explicitly; everything else re-executes; hostile-input tests in the 4-bucket matrix |
| Stub spec writes collide with user files | Low | Medium | Never-overwrite rule + name validation (NFR-5); inventory-asserted in e2e |
| `context.decomposition` shape drifts from what the add-on later needs | Low | High for add-on | FR-2's hydration tests and FR-5's artifact schema pin the shape **as it stands** — any change to the JSON contract breaks them. **Accepted residual (2026-07-26):** nothing pins the shape against what the *unbuilt* fan-out will need, because that requirement does not exist yet; the descoped FR-9(a) claimed to and could only have frozen a guess. `C-FLOW-12` writes its own pin as its first commit |
| Two-park journey feels heavy in interactive terminals | Medium | Low | Same posture as shipped `new_feature`; interactive short-circuit of gate-parks is a future D-INTL-07-class enhancement, noted not built |
| Plan file deleted/moved between park and resume | Low | Low | Rehydration WARNING + skip; consuming step fails with its own loud message (NFR-2/FR-3); decomposition rehydrates from step records, not the file |

### Refactoring Opportunities

| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| INT-US-02 E6/E7 e2e | Vacuously green (exit-0 ambiguity) | Re-asserted to prove real flow-through | Small (in SF-01) |
| `OrchestrateComponentsHandler` | Reads the never-set `context.plan` | Migrates to `context.decomposition`; dual-pipeline dispatch untouched | Small (in SF-01) |
| `stale architecture doc` (domain_flow_engine.md registry table) | Missing 4 shipped handler rows | Currency update in SF-03 docs pass | Small |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Guide-1 | `feature_decomposition` journey currency block in `pipeline_engine_guide.md` (scenario_pipelines.md `[!IMPORTANT]` precedent: CLI journey, exit codes, artifact contract, approve-on-resume semantics, host-posture facts) | ⬜ To be written during SF-03 pre-commit |
| Guide-2 | `4_interactive_hitl_gates.md` user-guide update: approve-on-resume semantics (resume = approval of a gate-park) | ⬜ To be written during SF-03 pre-commit |

## Open Questions

**OQ-1 — RESOLVED (user, 2026-07-25): Option B.** Naming and structure stay exactly as they are:
`US-21_integration.md` keeps `INT-US-21-SUB` for the delivered Recursive-Planning add-on, and
SF-03 mints the new add-on as `INT-US-21-SF02` alongside it. No delivered entry is renamed
(finished-stories-immutable rule honoured). The ID divergence with `master_story_roadmap.md:521`
is an accepted, documented inconsistency — recorded here so no future session re-opens it as
"registry corruption".

**In its place the user mandated a re-validation obligation, now tracked as `TECH-018` — see AD-9.**
The original options analysis is retained below for the record.

<details>
<summary>Original OQ-1 analysis (superseded by the resolution above)</summary>

**OQ-1 (MEDIUM — needs a user decision; blocks SF-03 registry closure only, not SF-01/SF-02).**
The delivered Recursive-Planning add-on carries two different IDs in two places:
`master_story_roadmap.md:521` calls it **`INT-US-21-SF01`**; `US-21_integration.md:10` calls it
**`INT-US-21-SUB`**. SF-03 mints `INT-US-21-SF02` into `US-21_integration.md`, which would leave
that file showing `INT-US-21-SUB` + `INT-US-21-SF02` and no SF01 — a reader cannot tell whether
an SF01 is missing. The finished-stories-immutable rule forbids me from renaming a ✅ delivered
entry unilaterally.

| Option | Pros | Cons | Consequence |
|--------|------|------|-------------|
| **A. Rename `INT-US-21-SUB` → `INT-US-21-SF01` in `US-21_integration.md`** (recommended) | One ID per story across the whole registry; matches the master roadmap, which is already the SF01 spelling; matches every other topic_08 file's convention | Edits a delivered entry's *identifier* (immutability rule) | Registry self-consistent; the immutability rule is bent once, for an ID-correction only — no scope/description change |
| B. Mint the add-on as `INT-US-21-SF02` and leave `SUB` alone | Zero edits to delivered entries | Permanent SUB/SF01/SF02 inconsistency; every future reader re-asks this question | Cheapest now, confusing forever |
| C. Mint the add-on as `INT-US-21-SUB02` to match local convention | Internally consistent *within* `US-21_integration.md` | Contradicts `master_story_roadmap.md` and every other topic_08 file; propagates the wrong convention | Locks in the divergence |

**Recommendation: A.** The master roadmap already uses `SF01`, so this is correcting a stale
spelling to match the source of truth, not rewriting delivered scope. Deferring the choice does
not block SF-01 or SF-02.

</details>

## Sub-Feature Breakdown

### SF-01: Flow-Engine Substrate (registry, plan bridge, approve-on-resume)
- **Scope**: Make the engine able to run the journey — the four inherited engine gaps fixed.
- **FRs**: [FR-1, FR-2, FR-3, FR-4]
- **Inputs**: Shipped `feature_decomposition.yaml`; existing `FeatureDrafter`, `ValidateSpecHandler`, `DecomposeFeatureHandler`, `OrchestrateComponentsHandler`; persisted step records.
- **Outputs**: Registered `(DRAFT,FEATURE)`/`(VALIDATE,FEATURE)` (with FR-1's spec-path reconciliation); `RunContext.decomposition` + one shared hydration function driving both the post-step hook and resume rehydration (decompose→`context.decomposition`, plan→`context.plan`), keyed on stored-result status; approve-on-resume engine semantics bypassing handler AND gate, emitting `approved_on_resume`; the `known_boundary_violations.md` row for the `forbids: drafting` breach (NFR-6); honest INT-US-02 E6/E7; migrated orchestrate consumption.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_sf01_implementation_plan.md

### SF-02: Decomposition Artifacts & Frozen Seams
- **Scope**: Make the journey's output durable and PO-visible, and freeze the add-on's integration surface.
- **FRs**: [FR-5, FR-6, FR-7, FR-9]
- **Inputs**: SF-01's hydration bridge; `PlanSpecHandler` persist/lineage pattern; component spec template; DecompositionPlan model.
- **Outputs**: `<stem>_decomposition.yaml` + lineage; stub component specs (never-overwrite, `.specweaver/templates/component_spec.md` read as a file with a local skeleton fallback — no new consumes edge); DAL summary in the step output; hook-driven plan→generate seam pin (FR-9). The orchestrate/fan-out pin was descoped 2026-07-26 — see FR-9.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_sf02_implementation_plan.md

### SF-03: CLI Journey, Verifiable Proof & Registry Closure
- **Scope**: Prove the full journey on the real CLI, update docs, close the epic. (Delivered-add-on re-validation is `TECH-018`, sequenced after this — see AD-9.)
- **FRs**: [FR-8, FR-10]
- **Inputs**: SF-01 + SF-02 committed; INT-US-24 e2e harness pattern (scripted adapter, fresh CliRunner per session, persisted-run-record assertions).
- **Outputs**: e2e suite (first bundled-pipeline-through-HITL proof); dev/user guide currency (Guides 1–2); registry closure: US-21 🟢, `C-FLOW-12` minted in topic_03 (verified free — `C-FLOW-11` is the current maximum in `capability_matrix.md`), `INT-US-21-SF02` minted in US-21_integration.md alongside the untouched `INT-US-21-SUB` (both Pending Design; OQ-1 Option B). **Closure gate (2026-07-26):** `python scripts/check_fr_coverage.py INT-US-21` must exit 0 — every FR the design declares is owned by a plan and cited by a test — together with a green full suite, which carries the always-on handler-reachability invariants. The delivered-add-on re-validation is `TECH-018` and does **not** gate 🟢 (see AD-9).
- **Depends on**: SF-01, SF-02
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_sf03_implementation_plan.md

## Execution Order

1. SF-01 (no deps — start immediately)
2. SF-02 (depends on SF-01)
3. SF-03 (depends on SF-01, SF-02)

Strictly linear — no parallel sessions.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Flow-Engine Substrate | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Decomposition Artifacts & Frozen Seams | SF-01 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-03 | CLI Journey, Proof & Registry Closure | SF-01, SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design **APPROVED** (user, 2026-07-25). Phase 6 consistency check + Red/Blue
Cycles 1–2 complete; all four inherited gaps re-verified line-by-line against `main`; 9
corrections folded in (marked `R/B C1.x` / `C2.x` inline). OQ-1 resolved as Option B — naming
and structure stay as-is; the re-validation obligation (now `TECH-018`) replaces the rename.
**SF-01 is COMPLETE and committed** (2026-07-25), all four commit boundaries:

| CB | Scope | FR | Commit |
|----|-------|----|--------|
| CB-1 | Registry completeness (`DraftFeatureHandler`, `(VALIDATE,FEATURE)`) | FR-1 | `f1de38f1` |
| CB-2 | Plan hydration bridge (`engine/hydration.py`, `RunContext.decomposition`) | FR-2 | `c4c1a109` |
| CB-3 | Cross-session rehydration on `resume()` | FR-3 | `6811a943` |
| CB-4 | HITL approve-on-resume (`engine/approval.py`) | FR-4 | `5ebcc414` |

All four inherited engine gaps from §Research Findings are closed. Suite: 5646 passed / 19 skipped.

> [!IMPORTANT]
> **Scoping record (2026-07-26) — SF-01 was capability recovery, not integration. Do not copy this
> story's shape.** Classified by what they actually do, **8 of this contract's 10 FRs build missing
> capability** and only FR-8 and FR-10 integrate: FR-1 a new handler and registry rows, FR-2/FR-3/FR-4
> new flow-engine mechanisms, FR-5/FR-6 capabilities `D-INTL-02` §6.2 promised and never shipped.
> Two consequences worth naming, because both were mistaken for something else at the time:
>
> 1. **The unit-test weight in SF-01 was a symptom, not indiscipline.** You cannot integration-test
>    your way through building four new engine mechanisms; new code is TDD'd unit-first. The tier
>    mismatch that triggered `TECH-017` was the *story label* being wrong, not the tests. Had the
>    work been scoped as capability stories, `TECH-017`'s rule would have needed no enforcement here.
> 2. **The single highest-value thing delivered has nothing to do with feature decomposition.**
>    FR-4 fixed park→resume **engine-wide** — every HITL pipeline in SpecWeaver was theatre, and two
>    already-"delivered" stories (INT-US-02 E6/E7) were vacuously green. That belonged in its own
>    flow-engine story where it would be findable, not buried as a sub-clause here.
>
> The root cause is scoping capability work as horizontal *components* ("build the decomposer"),
> which structurally cannot own its own wiring — wiring lives between components and therefore in
> nobody's scope, so it falls to "the integration story". Prefer thin **vertical threads** ("a user
> can decompose a feature via `sw run feature_decomposition`, happy path"): registration, YAML
> execution and artifact persistence then cannot be skipped, because the thread fails without them.
> The guards committed in `f7a0f34f` (handler reachability + the FR ledger) detect both failure modes
> that produced this story; the scoping heuristic is what prevents them.

**Tickets spun off during SF-01** (registry repaired + both filed in `f0e1709a`):
`TECH-014` fan-out `RunContext` isolation (live defect in shipped `C-FLOW-03`; should land before
`C-FLOW-12`) and `TECH-015` retire grab-bag modules.

**SF-02 implementation plan APPROVED** (user, 2026-07-25). Decisions D1–D7 binding; FR-5 and FR-7
carry `(SF-02 Phase-0)` corrections. Three commit boundaries: CB-1 artifact persistence →
CB-2 stub component specs → CB-3 plan-bridge seam pin (FR-9) + FR-7 summary. **CB-3 was rescoped
2026-07-26:** FR-9(a)'s decompose→orchestrate fan-out pin is descoped (see FR-9), so CB-3 keeps
FR-9(b) and the FR-7 surfacing only. CB-3 is not deleted — it still owns FR-7.
**Next step**: SF-02 CB-1 (artifact persistence, FR-5 + FR-7 data) is implemented but **uncommitted**,
and carries unit tests only. Per `TECH-017` it needs integration coverage before it earns a commit.

> [!IMPORTANT]
> **Two hard constraints SF-03 inherits from SF-01.** (1) `_resolve_spec_path`
> (`core/flow/interfaces/cli.py`) still special-cases `new_feature` only, so
> `sw run feature_decomposition greeter` does not resolve a spec. When SF-03/FR-8 fixes it, it MUST
> derive `specs/{name}_feature_spec.md` and **import `FEATURE_SPEC_SUFFIX` from
> `core/flow/handlers/draft.py`** rather than re-hardcode the literal — otherwise every drafting run
> trips CB-1's convention guard. (2) SF-01 found **five** separate vacuous proofs in existing tests
> (exit-code-only assertions, `_AlwaysPassHandler` overwriting the registry, `PIPELINES_DIR`
> silently skipping two tests, a fixture that could not pass its own battery, and live API calls in
> a "mocked" test). Treat existing coverage as unverified until read.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and
resume from there using the appropriate skill. Phase-3 decisions D1a/D2/D3a/D4 were approved by
the user on 2026-07-24 (see Architectural Decisions); the add-on split (`C-FLOW-12` +
`INT-US-21-SF02`) is a user mandate — do not pull execution scope into the base. "Frozen seams"
means the contract is defined and tested as it stands, NOT that the base pins it against the
unbuilt fan-out (FR-9(a), descoped 2026-07-26).

Before writing `Status: COMPLETE`, run the closure gate — `python scripts/check_fr_coverage.py
INT-US-21` plus a green full suite. Delivered-add-on re-validation is **`TECH-018`**, sequenced
after SF-03; it is audit-only, findings become new stories never edits to `INT-US-21-SUB`, and it
does **not** gate US-21 going 🟢.
