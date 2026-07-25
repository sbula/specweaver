# Implementation Plan: Autonomous Feature Decomposition [SF-01: Flow-Engine Substrate]

- **Feature ID**: INT-US-21
- **Sub-Feature**: SF-01 — Flow-Engine Substrate (registry, plan bridge, approve-on-resume)
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_sf01_implementation_plan.md
- **Status**: APPROVED (user, 2026-07-25)
- **FRs in scope**: FR-1, FR-2, FR-3, FR-4

---

## Research Notes

Every fact below was verified against `main` on 2026-07-25. File:line references are load-bearing —
the implementation must re-read them before editing (Critical Rule 5).

### R-1 — The loop body order in `_execute_loop` (`engine/runner.py:212-557`)

This ordering is the single most important constraint on FR-4. Per iteration:

1. `step_idx = run.current_step`; `attempts.setdefault(step_idx, 0)` (`:213-215`)
2. Handler lookup; `None` → ERROR result + `fail_current_step` + return (`:217-247`)
3. Staleness bypass (3.32 SF-4) — may `complete_current_step` and `continue` (`:263-293`)
4. **`run.mark_step_running()`** (`:295`) — sets `record.status = RUNNING`
5. Context injection: `run_id`, `step_records`, `pipeline_runner` (`:317-320`)
6. Handler execution, optionally sandboxed (`:326-333`)
7. `result.status == WAITING_FOR_INPUT` → `park_current_step` + return (**handler-park**, `:347-366`)
8. Gate evaluation (`:368-458`) → `park` returns; `stop` returns; `retry`/`loop_back` `continue`
9. Router or `run.complete_current_step(result)` (`:491-544`)
10. Persist + `_log("step_completed")` + `_emit("step_completed")` (`:546-557`)

> **Consequence:** the FR-4 approval branch MUST be inserted **before step 4**.
> `mark_step_running()` overwrites `record.status` from `WAITING_FOR_INPUT` to `RUNNING`,
> destroying the exact evidence AD-2 keys the approval decision on. Inserting after step 4
> is not a style choice — it is silently broken.

### R-2 — Park/complete state transitions (`engine/state.py:151-199`)

- `complete_current_step(result)` → `record.status = result.status`; `record.result = result`;
  `current_step += 1`; COMPLETED when past the end.
- `park_current_step(result)` → `record.status = WAITING_FOR_INPUT`; `record.result = result`
  (**the original result object, unmodified**); `run.status = PARKED`; `current_step` unchanged.

This is what makes AD-2's discriminator work and what makes it *cheap*: a gate-park leaves
`record.status == WAITING_FOR_INPUT` while `record.result.status == PASSED`. No schema change,
no approval store. Confirmed by reading both methods in full.

### R-3 — HITL parks unconditionally (`engine/gates.py:54-58`)

```python
if gate.type == GateType.HITL:
    run.park_current_step(result)
    return "park"
```

No condition check, no result inspection. `gates.py:55` is the **only** `GateType.HITL` reference
in all of `src/` (verified by grep) — there is no existing bypass, short-circuit, or
interactive-mode exception anywhere. So FR-4 must skip gate evaluation for the approved step;
skipping only the handler re-parks and the defect survives verbatim (design R/B C1.6).

### R-4 — The three park *flavours* are distinguishable in persisted state

| Flavour | `record.status` | `record.result.status` | Set at | FR-4 verdict |
|---|---|---|---|---|
| Gate-park (HITL) | `WAITING_FOR_INPUT` | `PASSED` | `gates.py:57` | **APPROVE** — advance |
| Gate-park (HITL on failure) | `WAITING_FOR_INPUT` | `FAILED` / `ERROR` | `gates.py:57` | re-execute |
| Handler-park | `WAITING_FOR_INPUT` | `WAITING_FOR_INPUT` | `runner.py:354` | re-execute |
| RESERVE-park | `WAITING_FOR_INPUT` | `PENDING` (overwritten `gates.py:121`) | `gates.py:123` | re-execute |

AD-2's "approve only on stored result `PASSED`" makes misclassification structurally impossible.
Verified: `evaluate_reserve` explicitly sets `result.status = StepStatus.PENDING` before parking
(`gates.py:121`), so RESERVE can never be mistaken for an approval.

### R-5 — Blast radius of FR-4 is far smaller than the design's ROI table assumed

The design rated SF-01 "Medium risk — approve-on-resume touches every HITL pipeline". Measured:

- **Bundled pipelines with HITL gates: exactly two.** `new_feature.yaml:17` (`draft_spec`) and
  `feature_decomposition.yaml:16,37` (`draft_feature`, `decompose`). `scenario_integration.yaml:50`
  matches a grep for "hitl" but it is `max_retries_hitl`, an unrelated AUTO-gate knob.
- **Existing tests that resume a parked run: 4** — `test_runner.py:279` (`test_resume_parked_run`),
  `test_runner.py:674`/`:715` (telemetry/cqrs), `test_pipeline_state_persistence.py:84`.
  **Every one of them parks via a handler** (`ParkHandler` returns `WAITING_FOR_INPUT`,
  `test_runner.py:60-66`; `FakeHitlHandler` likewise, `test_pipeline_state_persistence.py:27-34`)
  **on a pipeline whose steps carry no gate at all** (`_make_pipeline`, `test_runner.py:97-107`).
- **Therefore: zero existing tests exercise the gate-park resume path.** FR-4 is a no-op for all
  of them. `test_pipeline_state_persistence.py:80` even works *around* the defect
  (`pipeline2.steps[1].gate = None  # Remove HITL gate so it progresses`) — after FR-4 that
  workaround is obsolete and its comment becomes stale.

The residual risk is therefore concentrated entirely in `new_feature` runs driven through
`sw run`/`sw resume`, i.e. INT-US-02's E6/E7 — which is exactly what NFR-1 already targets.

### R-6 — FR-4 silently repairs the shipped REST gate endpoint

`POST /runs/{run_id}/gate` with `action: "approve"` calls `runner.resume(run_id)`
(`interfaces/api/v1/pipelines.py:264-337`). Today that re-executes and re-parks forever — the API's
"approve" is as broken as the CLI's. FR-4 fixes it for free via the shared `resume()` path.
`action: "reject"` sets `RunStatus.FAILED` directly without resuming (`:305-311`) and needs no
engine change. **This beneficiary is not named in the design's ROI table** — worth a regression
test so the newly-honest behaviour is pinned.

### R-7 — `resume()` and the `execute_run` seam (`runner.py:138-183`, `runner_utils.py:141-150`)

`resume()` loads the run, flips `status = RUNNING`, then calls `execute_run(self, run, logger)`,
which either calls `runner._execute_loop(run)` directly (`runner_utils.py:150`) or wraps it in a
C-EXEC-06 session worktree. Both `run()` and `resume()` funnel through `execute_run` with an
identical signature, so FR-3's rehydration and FR-4's approval flag need a deliberate seam —
see Q1/Q2.

`execute_run` shallow-copies the context for session isolation (`copy.copy`, `runner_utils.py:174`)
and restores the original in `finally`. Instance attributes on the *runner* survive that swap;
attributes on the *context* set before the copy are carried into the copy.

### R-8 — NFR-8's session-isolation claim is exact

`runner_utils.py:183-189`: after `_execute_loop`, `if run.status == RunStatus.PARKED: raise
RuntimeError("C-EXEC-06 session isolation does not support HITL parking (v1)…")`. The design's
NFR-8 is verbatim-accurate. `feature_decomposition` must run with `session_isolation` OFF; this is
a documented host-posture fact, not something SF-01 works around.

### R-9 — `FeatureDrafter` API surface (`workflows/drafting/feature_drafter.py:178-262`)

- `__init__(self, base_prompt: PromptBuilder, llm: LLMAdapter, context_provider: ContextProvider,
  config: GenerationConfig | None = None)` — **positional order differs from `Drafter`**; call with
  keywords only.
- `async draft(self, name: str, output_dir: Path, *, topology_contexts: list[TopologyContext] | None
  = None, project_metadata: ProjectMetadata | None = None) -> Path`
- Writes `output_dir / f"{name}_feature_spec.md"` (`:260`) and returns that path.
- The interview is driven by `FEATURE_SECTIONS`; a skipped answer yields a `*TODO: …*` placeholder
  rather than failing (`:228-230`).

**The `DraftSpecHandler` round-trip idiom that FR-1 must mirror** (`draft.py:162-168`):

```python
name = context.spec_path.stem.removesuffix("_spec")   # foo_spec.md -> "foo"
specs_dir = context.spec_path.parent
result_path = await drafter.draft(name, specs_dir, ...)  # writes foo_spec.md — round-trips
```

For features the equivalent is `removesuffix("_feature_spec")` against
`f"{name}_feature_spec.md"`. **Gotcha:** `str.removesuffix` is a silent no-op when the suffix is
absent, so `foo.md` would yield `name="foo"` and write `foo_feature_spec.md` ≠ `context.spec_path`.
FR-1's loud ERROR must be an explicit membership check, never an implicit reliance on
`removesuffix`. The post-call assertion `result_path == context.spec_path` is the backstop.

### R-10 — `DraftSpecHandler` parity checklist (`draft.py:23-208`)

The behaviours FR-1 calls "full parity", in the order the shipped handler applies them:

1. `_pop_feedback` FIRST (`:31`) — pops exactly once, tolerates malformed entries, returns `None`
   when absent (`:95-108`). Must precede exists-skip or the loop_back rejection path is dead.
2. Feedback + interactive provider → re-draft; feedback + headless → park carrying
   `reviewer_findings` in the output (`:33-57`).
3. Exists-skip → `PASSED` with `artifact_uuid` extracted from the file (`:60-73`).
4. No provider / no llm → park with a "create it and resume" message (`:79-93`).
5. Drafting → uuid tag if absent, `log_artifact_event(event_type="drafted_spec")` when
   `context.db` is set, `PASSED` with `{"message", "path"}` output (`:167-206`).
6. Profile resolution defaults to `INTERACTIVE` for drafting (`:135`); `DecomposeFeatureHandler`
   uses `MINIMAL` (`decompose.py:50`).

### R-11 — `ValidateSpecHandler` already routes `kind` (`handlers/validation.py:81,155-156`)

`kind_str = step.params.get("kind")`; `kind_str == "feature"` → `pipeline_name =
"validation_spec_feature"`. `feature_decomposition.yaml:22-23` already passes `params: {kind:
feature}`. **FR-1's `(VALIDATE, FEATURE)` half therefore needs a registry row and nothing else** —
no handler changes. `validation_spec_feature.yaml` exists in the bundled pipelines.

### R-12 — `context.plan` readers and the collision (FR-2)

Zero writes to `context.plan` anywhere in `src/` (verified by grep). Readers:
- `decompose.py:119,127` — `if not context.plan` then `json.loads(context.plan)`, expecting a
  **DecompositionPlan** JSON string.
- `generation.py:159-160,265-266` — `base_prompt.add_plan(context.plan)`, expecting an
  **implementation PlanArtifact** body.

Two incompatible types on one field, exactly as AD-1 describes. Keeping `decomposition` a **JSON
string** (not a dict) means `decompose.py:127`'s `json.loads` migrates by renaming one attribute.

### R-13 — Step records are fully persisted (`engine/store.py:132-133`)

`json.dumps([r.model_dump() for r in run.step_records], default=str)` — the nested `StepResult`,
including `output`, round-trips. FR-3's rehydration from step records is honest, unlike
`context.feedback` (never persisted — the INT-US-24 FR-2 correction). Confirms AD-8.

### R-14 — `attempts` resets per loop entry (`runner.py:210`)

`attempts: dict[int, int] = {}` is re-initialised on every `_execute_loop` call, so
`validate_feature`'s `max_retries: 3` budget restarts each session. Inherited; the design names it
under NFR-2 as explicitly NOT fixed here. No SF-01 work — listed so nobody "fixes" it by accident.

### R-15 — `_resolve_spec_path` special-cases `new_feature` only (`flow/interfaces/cli.py:101-127`)

An existing file path is used as-is (`:113`); a bare module name derives
`specs/{name}_spec.md` **only when `pipeline_name == "new_feature"`** (`:117-119`); otherwise it
falls through to the literal path. So `sw run feature_decomposition greeter` resolves to
`Path("greeter")`, not a spec. See Q6 — this is FR-8/SF-03 territory but it constrains the
filename convention FR-1 enforces here.

### R-16 — Guides and conventions that bind this work

- `pipeline_engine_guide.md:113-118` **WARNING**: `fan_out` loop limits / error bounds /
  `StepTarget.SPEC` validation sequence inside `OrchestrateComponentsHandler` are DMZ. FR-2's
  migration touches only the *field being read*, nothing in the fan-out mechanics.
- `pipeline_engine_guide.md:119-123` **CAUTION**: the `coverage_score >= 1.0` 3-strike loop is
  deliberate. Untouched by SF-01.
- `tests/CLAUDE.md`: every feature needs all 4 adversarial buckets (happy, boundary, degradation,
  hostile). Reflected in the test plan below.
- `user_guides/4_interactive_hitl_gates.md:32-38` describes resume as "boot it back up where it
  failed" — no approval semantics. SF-03's Guide-2 updates it; SF-01 must not leave it stale
  without that follow-up being recorded.

### External research

None required. SF-01 is a pure internal integration: no new dependency, no new external API.
`pyproject.toml` is untouched; `graphlib`, `ruamel.yaml` and the SQLite store are already in use.
The design's External Dependencies table (empty) is accurate.

---

## Architecture Verification (Phase 3)

### 3.1 Mechanism vs. Constraint Matrix

Target module for all engine work: `specweaver/core/flow` — `archetype: orchestrator`,
`consumes:` includes `specweaver/planning`, `specweaver/validation`, `specweaver/llm`,
`specweaver/config`; `forbids:` `specweaver/sandbox/*/interfaces`, **`specweaver/drafting`**,
`specweaver/context`.

| Mechanism | Where | Category | Constraint check | Verdict |
|---|---|---|---|---|
| Read/write `RunContext` fields | `handlers/base.py` | I/O & State (in-memory) | orchestrator may hold run state | ✅ |
| Read persisted step records | `engine/runner.py` via `run.step_records` | I/O & State | already the runner's job (`:319`) | ✅ |
| Read `plan_path` file content at hydration | `engine/runner.py` | I/O (file read) | orchestrator archetype permits file I/O; `PlanSpecHandler` already writes there | ✅ |
| Import `FeatureDrafter` | `handlers/draft.py` (inline) | Dependencies | **`forbids: specweaver/drafting`** | ⚠️ **AD-3 — approved switch**; see 3.6 |
| LLM call via `FeatureDrafter` | `handlers/draft.py` | LLM/AI | `consumes: specweaver/llm` | ✅ |
| Gate/approval decision | `engine/runner.py` + `engine/gates.py` | Domain topic | `purpose:` names "gates … and the pipeline runner" | ✅ |
| `json.loads`/`dumps` for `decomposition` | `handlers/decompose.py`, `engine/runner.py` | I/O (serialization) | `specweaver.commons.json` already used at `decompose.py` | ✅ |

`tach.toml:42` already lists `specweaver.workflows.drafting` in `specweaver.core.flow`'s
`depends_on`. **Zero new tach edges. Zero new `consumes` entries.** `tach check` will pass
unchanged — which is precisely why the `context.yaml`-level `forbids` breach must be ledgered
manually (NFR-6); the tooling cannot catch it.

### 3.2 Zoom-out test

- **`DraftFeatureHandler`** — does an equivalent exist? `DraftSpecHandler` is the same shape for a
  different target. Extending it via a `kind` param was considered and **rejected**: the two
  drafters have different constructors, different output suffixes, different section sets, and
  `(DRAFT, SPEC)`/`(DRAFT, FEATURE)` are already distinct registry keys by design
  (`models.py:115-117`). Two thin handlers beside each other in `draft.py` is the lower-coupling
  option. Named for what the code *is* (a draft handler for the feature target), not what an agent
  does. ✅
- **Hydration function** — no precedent exists (`context.plan` is written nowhere), so this is
  genuinely new capability, not a duplicate. It belongs to the runner because the runner is the
  only component that sees both the stored result and the context. ✅
- **Approval decision** — belongs in the runner loop, not `GateEvaluator`. `GateEvaluator.evaluate`
  is called *after* a step executes and is handed a fresh `result`; the approval decision happens
  *before* execution and reads a *persisted record*. Different inputs, different timing. Putting it
  in the evaluator would require passing the run's record state into a class whose whole contract
  is "given a fresh result, what next?". ✅ Keep it in `_execute_loop`.

### 3.3 Acyclic dependencies

`core.flow.handlers.draft` → `workflows.drafting.feature_drafter` is a **lazy (in-function)
import**, matching `draft.py:121`'s existing `Drafter` import. `workflows/drafting` consumes only
`llm`, `config`, `context` (`drafting/context.yaml`) and never imports `core.flow` — no cycle,
direct or transitive. The dependency points downward (orchestrator → workflow). ✅

### 3.4 Common closure

SF-01 modifies 6 files across 2 modules (`core/flow/{engine,handlers}`, plus one line in
`workflows/drafting/context.yaml`). The engine changes (FR-2/3/4) are tightly coupled and all live
in `engine/runner.py` + `handlers/base.py` — co-located. FR-1's handler work is separable and gets
its own commit boundary. No cross-module scatter. ✅

### 3.5 Stability direction

No new dependency is added to `config/`, `context/`, or `validation/`. `core/flow` (volatile
orchestrator) depends on `workflows/drafting` (less volatile workflow) — correct direction. ✅

### 3.6 Architectural violations → CRITICAL audit items

**One**, and it is the design's already-approved AD-3: the inline import from `core/flow/handlers`
into `workflows/drafting` breaches `core/flow/context.yaml`'s `forbids: specweaver/drafting`.

- **Rule broken**: `forbids: specweaver/drafting` (`core/flow/context.yaml:36`)
- **Affected**: `src/specweaver/core/flow/handlers/draft.py` (new `DraftFeatureHandler`)
- **Status**: pre-existing — `DraftSpecHandler` already does this at `draft.py:121`. AD-3 extends
  it; **user-approved architectural switch (D3a, 2026-07-24)**.
- **Fix required by NFR-6**: `known_boundary_violations.md` currently records only the
  *inline-import* anti-pattern for `core/flow/handlers/*` (line 9). It does **not** record this
  `forbids` breach. SF-01 must add an explicit row (DEFERRED, pointing at the DI/monolith-purge
  ticket as the destination). Without it the debt stays invisible and `tach check` gives false
  assurance.

---

## Work Breakdown — Commit Boundaries

Strictly linear. Each CB is independently green (full suite + `ruff` + `mypy` + `tach check`)
before the next begins, per the pre-commit gate.

### CB-1 — Registry completeness (FR-1)

**Files**: `[MODIFY] core/flow/handlers/draft.py`, `[MODIFY] core/flow/handlers/registry.py`,
`[MODIFY] workflows/drafting/context.yaml`, `[MODIFY] docs/architecture/known_boundary_violations.md`

**No new source files anywhere in SF-01** — `DraftFeatureHandler` lives in the existing `draft.py`
per D5, and every other change edits a shipped file.

Steps:
1. `DraftFeatureHandler` in `draft.py`, beside `DraftSpecHandler`, mirroring the R-10 order:
   pop-feedback → feedback branches → exists-skip → headless park → draft.
> [!CAUTION]
> **Cross-SF constraint (D6).** This handler enforces the `*_feature_spec.md` filename convention.
> `_resolve_spec_path` (`flow/interfaces/cli.py:101-127`) currently derives `specs/{name}_spec.md`
> for `new_feature` **only**, and falls through to a literal path for everything else (R-15).
> When SF-03 extends it for `feature_decomposition` it MUST derive `specs/{name}_feature_spec.md`.
> If it derives `{name}_spec.md` instead, **every drafting run errors on the guard in step 2** and
> FR-8's CLI journey is dead on arrival. This is the single tightest coupling between SF-01 and SF-03.

2. Name derivation, as an explicit guard rather than a bare `removesuffix` (R-9):
   - if `context.spec_path.name` does not end with `_feature_spec.md` → `_error_result` naming the
     required convention. Do this **before** any LLM setup so the failure costs nothing.
   - else `name = context.spec_path.name[: -len("_feature_spec.md")]`,
     `output_dir = context.spec_path.parent`.
   - **the derived `name` must be non-empty** (R/B C1.3): a spec literally called
     `_feature_spec.md` passes the suffix check, yields `name = ""`, and would round-trip cleanly
     through the step-4 assertion — silently drafting an unnamed feature spec. Reject it with the
     same loud ERROR. (The test plan's "empty stem → loud ERROR" case depends on this.)
3. Construct `FeatureDrafter` with **keyword arguments only** (R-9: its positional order differs
   from `Drafter`).
4. After `draft()` returns, assert `result_path == context.spec_path`; mismatch → `_error_result`.
   This is the backstop that makes FR-1's guarantee structural.
5. Lineage parity: uuid tag if absent + `log_artifact_event(event_type="drafted_feature_spec")`
   when `context.db` is set.
6. Register `(DRAFT, FEATURE) -> DraftFeatureHandler()` and
   `(VALIDATE, FEATURE) -> ValidateSpecHandler()` in `registry.py:97-117`.
   The validate row is a **registry line only** — no handler change (R-11).
7. Add `FeatureDrafter` to `drafting/context.yaml`'s `exposes:` list.
8. Add the `forbids: specweaver/drafting` row to `known_boundary_violations.md` (§3.6).

### CB-2 — `RunContext.decomposition` + shared hydration (FR-2)

**Files**: `[MODIFY] core/flow/handlers/base.py`, `[MODIFY] core/flow/engine/runner.py`,
`[MODIFY] core/flow/handlers/decompose.py`

Steps:
1. Add `decomposition: str | None = None` to `RunContext` (`base.py`, beside `plan` at `:63`),
   documented as "DecompositionPlan JSON (set by runner hydration)". Correct `plan`'s comment to
   name the implementation PlanArtifact so the two are never conflated again.
2. One module-level helper in `runner.py` — the single hydration point both FR-2 and FR-3 call, so
   they cannot drift (design R/B C2.3). Pseudocode:
   - given `(step_def, result, context)`; return early unless `result.status is PASSED`
   - `decompose+feature` → `context.decomposition = json.dumps(result.output)`
   - `plan+spec` → read `result.output["plan_path"]`; missing key or missing file → `logger.warning`
     and leave `context.plan` untouched; else `context.plan = path.read_text()`
   - log at INFO with `run_id` on every successful hydration (NFR-7)
3. Call it in `_execute_loop` at the **common join point both advance paths reach**: immediately
   before `router = step_def.router` (`runner.py:491`), i.e. after the gate block has fallen
   through to advance AND after the no-gate `else` branch (`:459-481`). Plus from the FR-4
   approval branch (CB-4), which `continue`s and never reaches the join.

> [!WARNING]
> **Do not place the hydration call inside the gate block (R/B C1.1).** Two distinct paths reach
> the advance point: the gate's `advance` fall-through (`runner.py:457-458`) *and* the no-gate
> `else` branch (`:459-481`). A gateless `plan+spec` step returning PASSED — exactly the shape
> FR-9's plan→generate seam pin will use — would be silently skipped if the call sits inside the
> gate block. The join point before `router` is the only site both paths cross.
4. Migrate `OrchestrateComponentsHandler`: `context.plan` → `context.decomposition` at
   `decompose.py:119` and `:127`. Update the "No DecompositionPlan found in context." message to
   name the new field. **Do not touch** the fan-out mechanics below `:130` (R-16 DMZ warning).

### CB-3 — Cross-session rehydration (FR-3)

**Files**: `[MODIFY] core/flow/engine/runner.py`

Steps:
1. In `resume()`, after `load_run` and before `execute_run` (`runner.py:159-178`), walk
   `run.step_records` in index order; for each record where **`record.result is not None` and
   `record.result.status is PASSED`** (NOT `record.status` — a gate-parked step's record status is
   `WAITING_FOR_INPUT`, design R/B R2), pair it with `self._pipeline.steps[idx]` and feed it to the
   CB-2 hydration helper. The `is not None` guard is mandatory: `_handle_loop_back` resets a target
   record to `result = None` (`gates.py:216-217`), so `record.result.status` would raise
   `AttributeError` on any pipeline that has looped back (R/B C1.5).
2. Later index wins by construction (forward iteration overwrites).
3. Guard the pairing on **both length and identity** (R/B C2.3): skip indices beyond
   `len(self._pipeline.steps)`, and skip any index where
   `record.step_name != self._pipeline.steps[idx].name`. Both emit a warning rather than raising.
   Length alone is insufficient — a YAML whose steps were *reordered* between sessions keeps the
   same length while silently pairing a stored result with the wrong action/target, hydrating the
   wrong context field.
4. Missing plan file → WARNING + skip is already CB-2's behaviour; nothing extra here.

### CB-4 — Approve-on-resume (FR-4) + NFR-1 re-assertions

**Files**: `[MODIFY] core/flow/engine/runner.py`, `[MODIFY] core/flow/engine/runner_utils.py`,
`[MODIFY] tests/e2e/capabilities/workflows/test_int_us_02_drafter_e2e.py`,
`[MODIFY] tests/integration/core/flow/engine/test_pipeline_state_persistence.py`,
`[MODIFY] tests/unit/interfaces/api/v1/test_pipelines.py`

Steps:
1. Per **D1**: add an explicit keyword argument to `_execute_loop` (default `False`) and forward it
   through `execute_run`. `resume()` passes `True`; `run()` passes nothing, so the fresh-run path
   stays byte-identical. The signal is one-shot — consumed on the first loop iteration whether or
   not it results in an approval.

> [!CAUTION]
> **The insertion point is a correctness constraint, not a style choice.** Two separate hazards sit
> between the top of the loop body and the handler call:
> 1. `mark_step_running()` (`runner.py:295`) sets `record.status = RUNNING`, overwriting the
>    `WAITING_FOR_INPUT` value AD-2's discriminator reads. Placed after it, FR-4 compiles, passes
>    type-checking, and is silently dead (R-1).
> 2. The **staleness-bypass block** (`runner.py:263-293`) also precedes `mark_step_running` and can
>    itself `complete_current_step(SKIPPED)` and `continue` (R/B C1.2). A parked step whose target
>    happens to be pristine would be bypassed as SKIPPED — discarding the human's approval *and*
>    the stored PASSED result.
>
> Therefore the approval check goes at the **very top of the loop body**, immediately after
> `attempts.setdefault(step_idx, 0)` (`runner.py:215`) — before the handler lookup and before the
> staleness block.

> [!NOTE]
> **Accepted consequence (R/B C2.1).** Checking before the handler lookup (`runner.py:217-247`)
> means a resumed run whose pipeline YAML no longer registers the approved step's handler will
> advance past it and fail at the *next* step instead. This is the more correct behaviour — the
> approved step genuinely already executed successfully in a prior session — but it does move
> which step name appears in the error. Deliberate, not an oversight.

2. In `_execute_loop`, at the top of the loop body per the CAUTION above, and only while the
   one-shot signal is live for `step_idx == run.current_step`:
   - the record exists and `record.status is WAITING_FOR_INPUT`
   - and `record.result is not None and record.result.status is PASSED`
   - and `step_def.gate is not None and step_def.gate.type is GateType.HITL`
   - → all four true: log the approval at INFO with `run_id`; call the CB-2 hydration helper with
     the stored result; `run.complete_current_step(record.result)`; persist;
     `_log(run, "gate_approved_on_resume", step_def.name)`; `_emit("step_completed", …)` with the
     `approved_on_resume` marker (NFR-7 / design R/B C2.2); consume the one-shot signal; `continue`.
   - → any false: consume the one-shot signal and fall through to normal execution.
3. Re-assert INT-US-02 E6/E7 honestly (**D2**): assert the **final run status is COMPLETED** from
   the persisted record, not merely `exit_code == 0` (both PARKED and COMPLETED exit 0 — the whole
   reason they were vacuous), and assert the scripted adapter's verdict queue was actually drained.
   **Both become three-session journeys**: session 1 handler-parks → session 2 re-executes, PASSES,
   gate-parks → session 3 approves and flows through. Add the third `runner.invoke(app, ["resume"])`
   to each and assert COMPLETED only after it.
4. Refresh `test_pipeline_state_persistence.py:79-80`: the `gate = None` workaround is obsolete.
   Keep a gate-bearing variant that proves flow-through without mutating the pipeline.
5. Per **D7**: add a unit regression test that `POST /runs/{id}/gate` with `action: "approve"`
   advances a gate-parked run (R-6). The endpoint needs no code change — the test pins the
   behaviour that FR-4 silently repairs.

---

## Design Coverage Map (Phase 5.0 pre-check)

Every FR, NFR, AD and Risk-Table entry from the design that touches SF-01, and where this plan
discharges it. Nothing in this table may be silently dropped during implementation.

| Design item | Discharged by | Evidence |
|---|---|---|
| FR-1 registry completeness + path reconciliation | CB-1 | R-9 round-trip idiom; R-11 (validate is a registry line only) |
| FR-2 hydration hook, both plan concepts | CB-2 | R-12 (two colliding readers); fires on the FR-4 path too (CB-4 step 2) |
| FR-3 cross-session rehydration | CB-3 | R-13 (step records fully persisted); keyed on `result.status`, not `record.status` |
| FR-4 approve-on-resume | CB-4 | R-1 insertion point; R-4 flavour table |
| NFR-1 delivered-journey compatibility | CB-4 steps 3–4 + R-5 | Measured blast radius: 2 HITL pipelines, 0 existing gate-park tests |
| NFR-2 cross-session honesty | CB-3 | Reads persisted state only; R-14 names the one inherited limit and forbids fixing it here |
| NFR-3 LLM economy | Test plan (happy + hostile) | Exists-skip asserts zero LLM calls; approval asserts handler call count stays 0; hydration and rehydration are pure reads |
| NFR-4 fail-loud parity | Test plan (degradation) | Malformed stored JSON still raises at the consumer; coverage 3-strike loop untouched (R-16) |
| NFR-5 injection safety | Test plan (hostile) | Traversal-shaped `spec_path` rejected by the CB-1 guard before any write. (Component-name validation is FR-6 → SF-02) |
| NFR-6 boundary hygiene | §3.6 + CB-1 step 8 | Zero new tach edges; the ledger row is mandatory precisely because `tach check` cannot catch this |
| NFR-7 observability | D3 + CB-2 step 2 + CB-4 step 2 | INFO with `run_id` on every hydration; `gate_approved_on_resume` audit event |
| NFR-8 session-isolation posture | No SF-01 action | R-8 verified verbatim. SF-01 must not weaken the `RuntimeError`; the dev-guide note is SF-03/Guide-1 |
| AD-1 split plan field | CB-2 step 1 | New `decomposition` field; `plan`'s comment corrected so the two are never reconflated |
| AD-2 approval derived from persisted state | CB-4 step 2 + R-4 | Four-flavour table; PASSED-only rule makes misclassification structurally impossible |
| AD-3 inline-import seam | §3.6 + CB-1 steps 1/8 | User-approved switch (D3a); the unrecorded half gets ledgered (D8) |
| AD-8 rehydration source = step records | CB-3 | Artifact file is the human-facing copy only |
| RT "approve-on-resume changes a flow someone relied on" | R-5 + CB-4 steps 3–4 | Risk re-measured as **low**, not medium — no existing test exercises the path |
| RT "gate-park vs handler-park misclassification" | Test plan (hostile) | Four explicit negative tests: handler-park, FAILED, RESERVE/PENDING, AUTO gate |
| RT "plan file deleted between park and resume" | CB-2 step 2 + test plan (degradation) | WARNING + skip; consumer fails with its own message |
| RT "`context.decomposition` shape drifts" | Partially — SF-02 owns FR-9 | D4 freezes the type as `str` here; the regression pin itself lands in SF-02 |

## Test Plan (4 adversarial buckets, per `tests/CLAUDE.md`)

Direct-branch testing per the standing rule — extract a helper rather than relying on transitive
coverage.

### Happy path
- `DraftFeatureHandler`: spec exists → PASSED + `artifact_uuid` (no LLM call).
- `DraftFeatureHandler`: spec absent + provider + llm → drafts, returns `context.spec_path`, PASSED.
- Registry: `(DRAFT, FEATURE)` and `(VALIDATE, FEATURE)` both resolve to non-`None` handlers.
- Hydration: `decompose+feature` PASSED → `context.decomposition` is the plan JSON.
- Hydration: `plan+spec` PASSED → `context.plan` is the file body.
- Rehydration: a run with a stored PASSED decompose record → `context.decomposition` set on resume.
- Approve-on-resume: gate-park with PASSED result → advances without re-executing (assert the
  handler's call count stays 0) and emits `gate_approved_on_resume`.
- Full 3-session `feature_decomposition` walk at unit/integration level (the CLI proof is SF-03).

### Boundary / edge
- Zero-step and single-step pipelines with the approval signal live.
- Approval at the **last** step → run reaches COMPLETED (`complete_current_step` past the end).
- `step_records` longer than the pipeline's `steps` (CB-3 step 3) → warning, no raise.
- **Reordered pipeline YAML between sessions** — same length, `step_name` mismatch at an index →
  that record is skipped with a warning, and the wrong context field is NOT hydrated (R/B C2.3).
- **Rehydrating a run that has looped back** — a target record reset to `result = None` → skipped,
  no `AttributeError` (R/B C1.5).
- **Gateless `plan+spec` step returning PASSED** → `context.plan` still hydrates, proving the call
  site is at the join and not inside the gate block (R/B C1.1).
- **Parked step whose target is "pristine"** (`stale_nodes` set) → approval wins; the step is NOT
  bypassed as SKIPPED (R/B C1.2).
- Decompose output `{}` / plan with zero components → hydrates to valid JSON, no crash.
- Spec named exactly `_feature_spec.md` (empty derived name) → loud ERROR, not an empty-name draft
  (R/B C1.3 — this case round-trips cleanly through the equality assertion, so only the explicit
  non-empty guard catches it).
- `plan_path` present but pointing at a zero-byte file → `context.plan` set to `""`, no crash.

### Graceful degradation
- `plan_path` key missing from the step output → WARNING, `context.plan` untouched, no raise.
- Plan file deleted between park and resume → WARNING + skip; the consuming step fails with its own
  loud message (NFR-2/FR-3).
- `record.result is None` on a `WAITING_FOR_INPUT` record → no approval, normal re-execution.
- `context.db` unset → lineage logging skipped, drafting still PASSES (R-10 parity).
- Malformed JSON already in a stored decompose output → hydration stores the string; the consumer's
  existing `json.loads` raises loudly (NFR-4 fail-loud parity preserved).

### Hostile / wrong input
- **Handler-park must NOT be approved**: stored result `WAITING_FOR_INPUT` under a HITL gate →
  re-executes. (The single most important negative test in this SF.)
- **HITL gate on a FAILED result must NOT be approved** → re-executes.
- **RESERVE-park must NOT be approved**: stored result `PENDING` → re-executes (R-4).
- **AUTO gate with a PASSED stored result must NOT be approved** → normal execution.
- **`run()` must never approve**, even against a run whose records look approvable.
- Approval must fire **at most once per resume** — a second parked-looking record later in the same
  pipeline is not auto-approved.
- `spec_path` with a traversal segment (`../../etc/passwd_feature_spec.md`) → the name guard runs
  before any filesystem write; assert no write outside `spec_path.parent`.
- `spec_path` whose name lacks the `_feature_spec.md` suffix → loud ERROR naming the convention.

### Regression pins
- API `POST /runs/{id}/gate` `approve` advances a gate-parked run (R-6).
- All 4 existing resume tests stay green unmodified (R-5) — proof the blast radius is contained.

---

## Resolved Decisions (Phase 4 audit — all approved by the user, 2026-07-25)

These were the Phase 2/3 audit questions. **All eight proposals were approved as written.** They are
binding on the implementation; a fresh agent must not re-litigate them.

| # | Sev | Decision | Rationale (why the alternatives lose) |
|---|-----|----------|----------------------------------------|
| D1 | HIGH | The one-shot approval signal is an **explicit keyword argument** on `_execute_loop`, forwarded through `execute_run`, defaulting to `False`. `run()` never sets it | An unconditional record check risks a **stale approval** — any future router/loop_back leaving a `WAITING_FOR_INPUT` record *ahead* of `current_step` would silently skip a real step. Today's invariants happen to prevent that; a kwarg makes it structurally impossible instead of accidentally true. A runner instance attribute is invisible in the signature and can survive a re-entrant call |
| D2 | HIGH | **INT-US-02 E6 and E7 become three-session journeys** and are re-asserted as such: session 1 handler-parks → session 2 re-executes, PASSES, gate-parks → session 3 approves and flows through | Special-casing "handler-park that re-executes and immediately gate-parks" as one continuous act would break AD-2's PASSED-only rule and re-open the misclassification hole the design closed. The extra `sw resume` is the gate doing its job: asking the human to approve the spec they just wrote. **SF-03's Guide-2 must state this explicitly** |
| D3 | MED | The approval path logs audit event **`gate_approved_on_resume`** AND emits `step_completed` carrying an `approved_on_resume` marker | Without an emitted event the advance is invisible in the CLI display and unassertable in e2e — FR-10's "both advances asserted" needs an observable. Design NFR-7 already requires this |
| D4 | MED | `RunContext.decomposition` is **`str \| None`** (canonical JSON), not a parsed dict | Mirrors `context.plan`'s shape, keeps the `decompose.py` migration a one-attribute rename, and freezes the FR-9 add-on seam as a string contract |
| D5 | MED | `DraftFeatureHandler` lives in **`handlers/draft.py`** beside `DraftSpecHandler` | A separate module fragments a cohesive 208-line file and forces either duplication of `_pop_feedback` or an awkward cross-import |
| D6 | MED | The `_resolve_spec_path` gap (R-15) is **deferred to SF-03/FR-8**, with a binding cross-SF constraint recorded below | The CLI journey is FR-8's scope. But see the CAUTION in CB-1 — the two conventions MUST agree or every drafting run trips the guard |
| D7 | MED | The newly-honest REST gate endpoint (R-6) **gets a regression test in SF-01** | The behaviour change is real whether or not it is tested; an untested silent fix invites a later regression |
| D8 | LOW | `known_boundary_violations.md` gets a **new row**, cross-referencing the existing inline-import row (line 9) | Amending line 9 would conflate two distinct rules in one entry |

---

## Backlog (deferred out of SF-01 — recorded so nothing is lost)

| Item | Owner | Note |
|------|-------|------|
| `_resolve_spec_path` support for `feature_decomposition` | **SF-03 / FR-8** (D6) | MUST derive `specs/{name}_feature_spec.md` — see the CAUTION in CB-1. **Import `FEATURE_SPEC_SUFFIX` from `core/flow/handlers/draft.py`** rather than re-hardcoding the literal; CB-1 deliberately made it a public module constant so the CLI and the handler guard cannot drift apart |
| `user_guides/4_interactive_hitl_gates.md` approve-on-resume semantics, incl. the D2 three-session drafting journey | **SF-03 / Guide-2** | §3 currently says only "boot it back up where it failed" (R-16) |
| `pipeline_engine_guide.md` `feature_decomposition` journey currency block | **SF-03 / Guide-1** | — |
| `domain_flow_engine.md` registry table missing shipped handler rows | **SF-03 docs pass** | Design §Refactoring Opportunities |
| Retry counters do not survive resume (`attempts` re-init, R-14) | **Not scheduled** — `C-FLOW-07` territory | Named in design NFR-2 as an accepted inherited limit. **Do not "fix" it here** |
| Shared mutable `RunContext` across concurrent fan-out sub-runners | **`TECH-014`** (filed 2026-07-25) — **NOT** the add-on | Re-scoped during CB-2 pre-commit. The runner writes `run_id`/`step_records`/`pipeline_runner` to the shared context on every step (`runner.py:404-406`), so lineage and telemetry are **already mis-attributed today** in shipped `C-FLOW-03` fan-out — independent of FR-2. It is a defect in delivered code, not a missing capability, so it must not be gated on `C-FLOW-12` (unbuilt, sequenced behind `C-EXEC-07`). FR-2 widened the blast radius to the plan fields but did not create it. **Should land before `C-FLOW-12`**, which ought to be able to assume context hygiene |
| DI inversion of the `core/flow` → `workflows/drafting` seam | Existing monolith-purge ticket | AD-3; SF-01 only ledgers the debt (D8) |

## Progress

| CB | Scope | FRs | Status |
|----|-------|-----|--------|
| CB-1 | Registry completeness | FR-1 | ✅ Pre-commit passed (see notes below) |
| CB-2 | `decomposition` field + shared hydration | FR-2 | ✅ Committed `c4c1a109` |
| CB-3 | Cross-session rehydration | FR-3 | ✅ Committed `6811a943` |
| CB-4 | Approve-on-resume + NFR-1 re-assertions | FR-4 | ✅ Pre-commit passed |

### CB-1 implementation notes (as built)

Deviations and discoveries worth carrying forward:

1. **Step order changed vs. the first task breakdown.** The name-derivation guard was moved *ahead
   of* the feedback branches. An unusable spec path is fatal regardless of reviewer findings; with
   the original order, feedback + interactive would have entered drafting with a name that cannot
   round-trip. The feedback pop still runs first, so the once-only contract holds.
2. **`_pop_feedback` extracted to a module-level `_pop_step_feedback`**, with
   `DraftSpecHandler._pop_feedback` kept as a thin delegate — four shipped tests
   (`test_draft_handler.py:199-213`) call it directly.
3. **Path-kind guard added** beyond the plan: a `spec_path` that exists but is not a file now
   ERRORs explicitly, rather than `read_text()`-ing a directory (today's `DraftSpecHandler`
   behaviour) or silently falling through to drafting.
4. **Inherited defect fixed** — `PIPELINES_DIR` in `test_feature_pipeline.py` used `parents[4]`
   (= `tests/`) instead of `parents[5]` (repo root). Both tests in that class are guarded by
   `if not path.exists(): pytest.skip(...)`, so they had **never executed**. Integration skips
   dropped 5 → 3 once corrected. This is the third vacuous-proof instance in this feature — after
   INT-US-02's E6/E7 and `_AlwaysPassHandler` overwriting the registry in the same file.
5. **Registry table in `domain_flow_engine.md` fully corrected** — it was missing 9 shipped
   handlers and every module path was stale (`flow/_draft.py` no longer exists). The design had
   assigned this to SF-03's docs pass; done here instead since CB-1 modifies that very registry.
6. **New dev-guide pattern 24** (`special_patterns_and_adaptations.md`): Round-Trip Name Derivation
   for Self-Naming Writers.

### CB-2 implementation notes (as built)

Four findings surfaced by the user's "unusual flows / edge cases / graceful teardown" challenge at
the Phase-2 gate — the first two were live bugs in CB-2's own new code:

1. **Serialization asymmetry, live vs. resume (FIXED).** `StateStore` persists step records with
   `json.dumps(..., default=str)` (`store.py:132-133`); the hydration hook used strict `dumps`.
   Verified: a decompose output carrying a `Path` or `set` raised on the **live** path (field left
   unset) but hydrated cleanly on the **resume** path, where the store had already stringified it.
   The same run behaved differently depending on whether it was interrupted — exactly the drift the
   shared hydration function was meant to prevent. **Sharing the function is only half the
   guarantee; the serialization semantics must match too.** Now uses `default=str`, pinned by a
   test that hydrates live and via a store round-trip and asserts byte-equality.
2. **`UnicodeDecodeError` escaped the guard (FIXED).** It subclasses `ValueError`, not `OSError`, so
   a corrupt/binary plan artifact propagated out of a function documented as never-raising — and
   did so *after* the gate had already decided to advance. Now caught.
3. **Fan-out shared-context race → `TECH-014`** (user decision: fix fully, as a TECH ticket rather
   than inside the add-on). See the Backlog row.
5. **Two refactors forced by the file-size gate.** `runner.py` was already at 598/600 lines before
   CB-2 — one line from the RED threshold. Rather than shave, two genuinely separable concerns were
   moved out: `hydrate_plan_context` → new **`engine/hydration.py`** (also where CB-3's resume
   rehydration will import it from), and the router-target resolution block → **`engine/routers.py`**
   as `resolve_route_target()`, putting router logic in the router module. `runner.py` is now 593.
4. **Stale hydration on a failed re-run (FIXED, user decision F4-b).** Hydration fired only on
   `PASSED` and never cleared, so `decompose passes → hydrates → loop_back → decompose re-runs and
   fails` left the **superseded** plan in `context.decomposition` for a downstream orchestrate step
   to consume silently. A non-`PASSED` result now clears the field **that combo owns** (and only
   that one). Scope addition beyond FR-2's literal text, approved by the user.
