# INT-US-21 SF-01 — Flow-Engine Substrate (registry, plan bridge, approve-on-resume)

**Status**: APPROVED (user, 2026-07-25). Decisions D1–D8 approved as written. COMPLETE — committed
2026-07-25 (`f1de38f1`, `c4c1a109`, `6811a943`, `5ebcc414`). · **FRs owned**: FR-1, FR-2, FR-3, FR-4 ·
**Depends on**: — · Design: [INT-US-21_design.md](INT-US-21_design.md) §Sub-features → SF-01

## Goal

Make the engine able to run the journey: close the four inherited engine gaps. Scope is the engine
substrate only — artifacts, stubs and seam pins are SF-02; the CLI journey, e2e proof and registry
closure are SF-03.

## Where it plugs in

Verified against `main` on 2026-07-25. Re-read the file:line refs before editing (Critical Rule 5).

**Since moved** (2026-08-12): `eeab8c53` extracted the loop body of `_execute_loop` into
`core/flow/engine/step_execution.py` (`TECH-020`); `c3f36d54` retired `runner_utils` — `execute_run`
→ `core/flow/engine/session.py`, `run_fan_out` → `core/flow/engine/fan_out.py`. `_resolve_spec_path`
became `resolve_spec_path` in `core/flow/interfaces/spec_path_resolution.py` (SF-03 CB-1). Line refs
below are as of the plan's date.

### The four gaps, at the code

1. **Unrunnable shipped pipeline.** `feature_decomposition.yaml` steps 1–2 use `draft+feature` /
   `validate+feature` — valid in `VALID_STEP_COMBINATIONS` (`engine/models.py:116-117`) but never
   mapped in `StepHandlerRegistry` (`handlers/registry.py:97-117`) → runner errors "No handler
   registered for draft+feature" at step 1. `FeatureDrafter` exists
   (`workflows/drafting/feature_drafter.py:178`, interview-driven, template Done Definition demands
   a DAL declaration) but is unexposed (`drafting/context.yaml` exposes only `Drafter`).
   `ValidateSpecHandler` already routes `kind=="feature"` → `validation_spec_feature` battery
   (`handlers/validation.py:82-92,155-156`).
2. **`context.plan` populated nowhere.** `RunContext.plan` promises "(set by runner hook)"
   (`handlers/base.py:63`) — zero writes in `src/`; no hook in `engine/runner.py`. Readers:
   `OrchestrateComponentsHandler` (`decompose.py:119,127`, expects a JSON string of a
   DecompositionPlan) and `GenerateCode/TestsHandler` (`generation.py:159-160,265-266`, `add_plan`
   prompt enrichment expecting a PlanArtifact). Two plan concepts collide on one field — the
   decomposition plan (feature→components) vs. the implementation plan (spec→file-layout, persisted
   by `PlanSpecHandler` as `<stem>_plan.yaml`).
3. **Resume re-parks forever.** `gates.py:54-58` parks HITL gates unconditionally;
   `park_current_step` keeps `current_step` at the parked step (`state.py:190-199`);
   `PipelineRunner.resume()` only flips status to RUNNING → the loop re-executes the step and the gate
   re-parks. Proven empirically (INT-US-02 E7 run with logs: session 2 re-parks at `draft_spec` with
   `result_status=passed`; the scripted DENY/ACCEPT verdicts are never consumed).
4. **No decomposition artifact.** `DecomposeFeatureHandler` returns `plan.model_dump()` only into the
   step record. `feature_name` falls back to `"unknown_feature"` (`decompose.py:30`; the bundled YAML
   passes no params). (SF-02's gap.)

Other anchors: step records persisted as JSON in SQLite (`store.py:132-133`); fan-out shares one
`RunContext` (`decompose.py:230-236`); `PlanSpecHandler` persist+lineage+uuid-tag pattern
(`generation.py:387-411,478-487`); `tach.toml:42` already lists `specweaver.workflows.drafting`
under `specweaver.core.flow`; inline-import debt row at `known_boundary_violations.md:9`.

### R-1 — Loop body order in `_execute_loop` (`engine/runner.py:212-557`)

The single most important constraint on FR-4. Per iteration:

1. `step_idx = run.current_step`; `attempts.setdefault(step_idx, 0)` (`:213-215`)
2. Handler lookup; `None` → ERROR result + `fail_current_step` + return (`:217-247`)
3. Staleness bypass (3.32 SF-04) — may `complete_current_step` and `continue` (`:263-293`)
4. **`run.mark_step_running()`** (`:295`) — sets `record.status = RUNNING`
5. Context injection: `run_id`, `step_records`, `pipeline_runner` (`:317-320`)
6. Handler execution, optionally sandboxed (`:326-333`)
7. `result.status == WAITING_FOR_INPUT` → `park_current_step` + return (**handler-park**, `:347-366`)
8. Gate evaluation (`:368-458`) → `park` returns; `stop` returns; `retry`/`loop_back` `continue`
9. Router or `run.complete_current_step(result)` (`:491-544`)
10. Persist + `_log("step_completed")` + `_emit("step_completed")` (`:546-557`)

The FR-4 approval branch MUST go **before step 4**: `mark_step_running()` overwrites
`record.status` from `WAITING_FOR_INPUT` to `RUNNING`, destroying the evidence AD-2 keys on. After
step 4 it is silently broken.

### R-2 — Park/complete transitions (`engine/state.py:151-199`)

- `complete_current_step(result)` → `record.status = result.status`; `record.result = result`;
  `current_step += 1`; COMPLETED when past the end.
- `park_current_step(result)` → `record.status = WAITING_FOR_INPUT`; `record.result = result`
  (**the original result object, unmodified**); `run.status = PARKED`; `current_step` unchanged.

So a gate-park leaves `record.status == WAITING_FOR_INPUT` while `record.result.status == PASSED`.
No schema change, no approval store.

### R-3 — HITL parks unconditionally (`engine/gates.py:54-58`)

```python
if gate.type == GateType.HITL:
    run.park_current_step(result)
    return "park"
```

`gates.py:55` is the **only** `GateType.HITL` reference in `src/` (grep) — no bypass, short-circuit
or interactive-mode exception exists. FR-4 must skip gate evaluation for the approved step; skipping
only the handler re-parks (design R/B C1.6).

### R-4 — The park flavours in persisted state

| Flavour | `record.status` | `record.result.status` | Set at | FR-4 verdict |
|---|---|---|---|---|
| Gate-park (HITL) | `WAITING_FOR_INPUT` | `PASSED` | `gates.py:57` | **APPROVE** — advance |
| Gate-park (HITL on failure) | `WAITING_FOR_INPUT` | `FAILED` / `ERROR` | `gates.py:57` | re-execute |
| Handler-park | `WAITING_FOR_INPUT` | `WAITING_FOR_INPUT` | `runner.py:354` | re-execute |
| RESERVE-park | `WAITING_FOR_INPUT` | `PENDING` (overwritten `gates.py:121`) | `gates.py:123` | re-execute |

`evaluate_reserve` sets `result.status = StepStatus.PENDING` before parking (`gates.py:121`), so
RESERVE can never be mistaken for an approval.

### R-5 — Blast radius of FR-4 is small

The design rated SF-01 "Medium risk — approve-on-resume touches every HITL pipeline". Measured:

- **Bundled pipelines with HITL gates: exactly two.** `new_feature.yaml:17` (`draft_spec`) and
  `feature_decomposition.yaml:16,37` (`draft_feature`, `decompose`). `scenario_integration.yaml:50`
  matches "hitl" but is `max_retries_hitl`, an unrelated AUTO-gate knob.
- **Existing tests that resume a parked run: 4** — `test_runner.py:279` (`test_resume_parked_run`),
  `test_runner.py:674`/`:715` (telemetry/cqrs), `test_pipeline_state_persistence.py:84`. Every one
  parks via a handler (`ParkHandler` returns `WAITING_FOR_INPUT`, `test_runner.py:60-66`;
  `FakeHitlHandler` likewise, `test_pipeline_state_persistence.py:27-34`) on a pipeline with no gate
  (`_make_pipeline`, `test_runner.py:97-107`).
- **Zero existing tests exercise the gate-park resume path.** `test_pipeline_state_persistence.py:80`
  works *around* the defect (`pipeline2.steps[1].gate = None  # Remove HITL gate so it progresses`).

Residual risk sits in `new_feature` runs via `sw run`/`sw resume` — INT-US-02's E6/E7, which NFR-1
targets.

### R-6 — FR-4 repairs the shipped REST gate endpoint

`POST /runs/{run_id}/gate` with `action: "approve"` calls `runner.resume(run_id)`
(`interfaces/api/v1/pipelines.py:264-337`) — it re-parked forever too. FR-4 fixes it via the shared
`resume()` path. `action: "reject"` sets `RunStatus.FAILED` directly (`:305-311`), no engine change.
Not named in the design; gets a regression test (D7).

### R-7 — `resume()` and the `execute_run` seam (`runner.py:138-183`, `runner_utils.py:141-150`)

`resume()` loads the run, flips `status = RUNNING`, then calls `execute_run(self, run, logger)`,
which calls `runner._execute_loop(run)` directly (`runner_utils.py:150`) or wraps it in a C-EXEC-06
session worktree. `run()` and `resume()` share that signature, so FR-3 and FR-4 need a deliberate
seam (D1). `execute_run` shallow-copies the context for session isolation (`copy.copy`,
`runner_utils.py:174`) and restores the original in `finally`: runner attributes survive; context
attributes set before the copy are carried into it.

### R-8 — NFR-8 is exact

`runner_utils.py:183-189`: after `_execute_loop`, `if run.status == RunStatus.PARKED: raise
RuntimeError("C-EXEC-06 session isolation does not support HITL parking (v1)…")`.
`feature_decomposition` must run with `session_isolation` OFF — a host-posture fact, not worked around.

### R-9 — `FeatureDrafter` API (`workflows/drafting/feature_drafter.py:178-262`)

- `__init__(self, base_prompt: PromptBuilder, llm: LLMAdapter, context_provider: ContextProvider,
  config: GenerationConfig | None = None)` — **positional order differs from `Drafter`**; call with
  keywords only.
- `async draft(self, name: str, output_dir: Path, *, topology_contexts: list[TopologyContext] | None
  = None, project_metadata: ProjectMetadata | None = None) -> Path`
- Writes `output_dir / f"{name}_feature_spec.md"` (`:260`) and returns that path.
- Interview driven by `FEATURE_SECTIONS`; a skipped answer yields a `*TODO: …*` placeholder
  (`:228-230`).

The `DraftSpecHandler` round-trip idiom FR-1 mirrors (`draft.py:162-168`):

```python
name = context.spec_path.stem.removesuffix("_spec")   # foo_spec.md -> "foo"
specs_dir = context.spec_path.parent
result_path = await drafter.draft(name, specs_dir, ...)  # writes foo_spec.md — round-trips
```

For features: `removesuffix("_feature_spec")` against `f"{name}_feature_spec.md"`. **Trap:**
`str.removesuffix` is a silent no-op when the suffix is absent — `foo.md` yields `name="foo"` and
writes `foo_feature_spec.md` ≠ `context.spec_path`. The loud ERROR must be an explicit membership
check; the post-call `result_path == context.spec_path` assertion is the backstop.

### R-10 — `DraftSpecHandler` parity checklist (`draft.py:23-208`)

In the order the shipped handler applies them:

1. `_pop_feedback` FIRST (`:31`) — pops exactly once, tolerates malformed entries, returns `None`
   when absent (`:95-108`). Must precede exists-skip or the loop_back rejection path is dead.
2. Feedback + interactive provider → re-draft; feedback + headless → park carrying
   `reviewer_findings` in the output (`:33-57`).
3. Exists-skip → `PASSED` with `artifact_uuid` extracted from the file (`:60-73`).
4. No provider / no llm → park with a "create it and resume" message (`:79-93`).
5. Drafting → uuid tag if absent, `log_artifact_event(event_type="drafted_spec")` when `context.db`
   is set, `PASSED` with `{"message", "path"}` output (`:167-206`).
6. Profile resolution defaults to `INTERACTIVE` for drafting (`:135`); `DecomposeFeatureHandler`
   uses `MINIMAL` (`decompose.py:50`).

### R-11 — `ValidateSpecHandler` already routes `kind` (`handlers/validation.py:81,155-156`)

`kind_str = step.params.get("kind")`; `kind_str == "feature"` → `pipeline_name =
"validation_spec_feature"`. `feature_decomposition.yaml:22-23` passes `params: {kind: feature}`.
FR-1's `(VALIDATE, FEATURE)` half is a registry row only. `validation_spec_feature.yaml` is bundled.

### R-12 — `context.plan` readers (FR-2)

- `decompose.py:119,127` — `if not context.plan` then `json.loads(context.plan)`: a
  **DecompositionPlan** JSON string.
- `generation.py:159-160,265-266` — `base_prompt.add_plan(context.plan)`: an **implementation
  PlanArtifact** body.

Keeping `decomposition` a **JSON string** makes `decompose.py:127`'s migration a one-attribute rename.

### R-13 — Step records fully persisted (`engine/store.py:132-133`)

`json.dumps([r.model_dump() for r in run.step_records], default=str)` — the nested `StepResult`,
including `output`, round-trips. FR-3 is honest; `context.feedback` is never persisted (INT-US-24
FR-2 correction). Confirms AD-8.

### R-14 — `attempts` resets per loop entry (`runner.py:210`)

`attempts: dict[int, int] = {}` is re-initialised on every `_execute_loop` call, so
`validate_feature`'s `max_retries: 3` restarts each session. Named in NFR-2 as NOT fixed here — do
not "fix" it by accident. (Now `TECH-033`.)

### R-15 — `_resolve_spec_path` special-cases `new_feature` only (`flow/interfaces/cli.py:101-127`)

Existing file path used as-is (`:113`); a bare module name derives `specs/{name}_spec.md` **only when
`pipeline_name == "new_feature"`** (`:117-119`); otherwise the literal path. So
`sw run feature_decomposition greeter` resolves to `Path("greeter")`. FR-8/SF-03 territory (D6), but
it constrains FR-1's filename convention.

### R-16 — Binding guides

- `pipeline_engine_guide.md:113-118` **WARNING**: `fan_out` loop limits / error bounds /
  `StepTarget.SPEC` validation inside `OrchestrateComponentsHandler` are DMZ. FR-2 touches only the
  field being read.
- `pipeline_engine_guide.md:119-123` **CAUTION**: the `coverage_score >= 1.0` 3-strike loop is
  deliberate. Untouched.
- `tests/CLAUDE.md`: all 4 adversarial buckets (happy, boundary, degradation, hostile).
- `user_guides/4_interactive_hitl_gates.md:32-38` describes resume as "boot it back up where it
  failed" — no approval semantics. Guide-2 updates it.

No external research: no new dependency; `pyproject.toml` untouched.

### Architecture check

Target: `specweaver/core/flow` — `archetype: orchestrator`; `consumes:` includes
`specweaver/planning`, `specweaver/validation`, `specweaver/llm`, `specweaver/config`; `forbids:`
`specweaver/sandbox/*/interfaces`, **`specweaver/drafting`**, `specweaver/context`.

| Mechanism | Where | Category | Constraint check | Verdict |
|---|---|---|---|---|
| Read/write `RunContext` fields | `handlers/base.py` | I/O & State (in-memory) | orchestrator may hold run state | ✅ |
| Read persisted step records | `engine/runner.py` via `run.step_records` | I/O & State | already the runner's job (`:319`) | ✅ |
| Read `plan_path` file content at hydration | `engine/runner.py` | I/O (file read) | orchestrator permits file I/O; `PlanSpecHandler` already writes there | ✅ |
| Import `FeatureDrafter` | `handlers/draft.py` (inline) | Dependencies | **`forbids: specweaver/drafting`** | ⚠️ **AD-3 — approved switch** |
| LLM call via `FeatureDrafter` | `handlers/draft.py` | LLM/AI | `consumes: specweaver/llm` | ✅ |
| Gate/approval decision | `engine/runner.py` + `engine/gates.py` | Domain topic | `purpose:` names "gates … and the pipeline runner" | ✅ |
| `json.loads`/`dumps` for `decomposition` | `handlers/decompose.py`, `engine/runner.py` | I/O (serialization) | `specweaver.commons.json` already used at `decompose.py` | ✅ |

- **Zero new tach edges, zero new `consumes`** (`tach.toml:42` already has the edge in `depends_on`);
  no new dependency on `config/`, `context/`, or `validation/`. `tach check` passes unchanged, which is why the
  `context.yaml` `forbids` breach must be ledgered by hand (NFR-6).
- **`DraftFeatureHandler`** beside `DraftSpecHandler`, not a `kind` param on it: different
  constructors, output suffixes and section sets, and `(DRAFT, SPEC)`/`(DRAFT, FEATURE)` are distinct
  registry keys (`models.py:115-117`).
- **Hydration** belongs to the runner — the only component that sees both the stored result and the
  context. No precedent exists.
- **Approval** lives in the loop, not `GateEvaluator`: the evaluator is handed a fresh result
  *after* execution; approval reads a *persisted record* *before* it.
- **No cycle**: `core.flow.handlers.draft` → `workflows.drafting.feature_drafter` is a lazy
  (in-function) import, like `draft.py:121`'s `Drafter`; `workflows/drafting` consumes only `llm`,
  `config`, `context` and never imports `core.flow`. Orchestrator → workflow is the right direction.
- **Closure**: 6 files across `core/flow/{engine,handlers}` + one line in
  `workflows/drafting/context.yaml`.
- **The one violation** is AD-3: breaches `forbids: specweaver/drafting` (`core/flow/context.yaml:36`)
  in `src/specweaver/core/flow/handlers/draft.py`. Pre-existing (`draft.py:121`); user-approved
  switch (D3a, 2026-07-24). `known_boundary_violations.md` recorded only the inline-import
  anti-pattern (line 9), not this `forbids` breach — SF-01 adds a DEFERRED row pointing at the
  DI/monolith-purge ticket.

## Changes

Strictly linear commit boundaries; each green (full suite + `ruff` + `mypy` + `tach check`) before
the next. No new source files planned — `DraftFeatureHandler` lives in `draft.py` (D5).

### CB-1 — Registry completeness (FR-1)

Files: `[MODIFY] core/flow/handlers/draft.py`, `[MODIFY] core/flow/handlers/registry.py`,
`[MODIFY] workflows/drafting/context.yaml`, `[MODIFY] docs/architecture/known_boundary_violations.md`

1. `DraftFeatureHandler` in `draft.py`, mirroring the R-10 order: pop-feedback → feedback branches →
   exists-skip → headless park → draft.
2. Name derivation as an explicit guard, not a bare `removesuffix` (R-9), **before** any LLM setup:
   - `context.spec_path.name` not ending with `_feature_spec.md` → `_error_result` naming the
     convention.
   - else `name = context.spec_path.name[: -len("_feature_spec.md")]`,
     `output_dir = context.spec_path.parent`.
   - **derived `name` must be non-empty** (R/B C1.3): a spec called `_feature_spec.md` yields
     `name = ""` and would round-trip cleanly through step 4. Same loud ERROR.
3. Construct `FeatureDrafter` with **keyword arguments only** (R-9).
4. After `draft()`, assert `result_path == context.spec_path`; mismatch → `_error_result`.
5. Lineage parity: uuid tag if absent + `log_artifact_event(event_type="drafted_feature_spec")` when
   `context.db` is set.
6. Register `(DRAFT, FEATURE) -> DraftFeatureHandler()` and `(VALIDATE, FEATURE) ->
   ValidateSpecHandler()` in `registry.py:97-117` — the validate row is a registry line only (R-11).
7. Add `FeatureDrafter` to `drafting/context.yaml`'s `exposes:`.
8. Add the `forbids: specweaver/drafting` row to `known_boundary_violations.md`.

> [!CAUTION]
> **Cross-SF constraint (D6).** This handler enforces `*_feature_spec.md`. When SF-03 extends
> `_resolve_spec_path` (`flow/interfaces/cli.py:101-127`, R-15) for `feature_decomposition` it MUST
> derive `specs/{name}_feature_spec.md` — `{name}_spec.md` would make **every drafting run error on
> the step-2 guard** and kill FR-8's journey.

### CB-2 — `RunContext.decomposition` + shared hydration (FR-2)

Files: `[MODIFY] core/flow/handlers/base.py`, `[MODIFY] core/flow/engine/runner.py`,
`[MODIFY] core/flow/handlers/decompose.py`

1. Add `decomposition: str | None = None` to `RunContext` (`base.py`, beside `plan` at `:63`),
   documented "DecompositionPlan JSON (set by runner hydration)". Correct `plan`'s comment to name
   the implementation PlanArtifact.
2. One helper — the single hydration point FR-2 and FR-3 both call (design R/B C2.3):
   - given `(step_def, result, context)`; return early unless `result.status is PASSED`
   - `decompose+feature` → `context.decomposition = json.dumps(result.output)`
   - `plan+spec` → read `result.output["plan_path"]`; missing key or file → `logger.warning`, leave
     `context.plan` untouched; else `context.plan = path.read_text()`
   - INFO log with `run_id` on every hydration (NFR-7)
3. Call it at the **join point both advance paths reach**: immediately before
   `router = step_def.router` (`runner.py:491`) — after the gate block's `advance` fall-through
   (`runner.py:457-458`) AND after the no-gate `else` branch (`:459-481`). Plus from the FR-4
   approval branch, which `continue`s past the join.
4. Migrate `OrchestrateComponentsHandler`: `context.plan` → `context.decomposition` at
   `decompose.py:119` and `:127`; update the "No DecompositionPlan found in context." message to
   name the new field. **Do not touch** the fan-out mechanics below `:130` (R-16 DMZ).

> [!WARNING]
> **Not inside the gate block (R/B C1.1).** A gateless `plan+spec` step returning PASSED — the shape
> FR-9's seam pin uses — would be silently skipped there.

### CB-3 — Cross-session rehydration (FR-3)

Files: `[MODIFY] core/flow/engine/runner.py`

1. In `resume()`, after `load_run` and before `execute_run` (`runner.py:159-178`), walk
   `run.step_records` in index order; for each record where **`record.result is not None` and
   `record.result.status is PASSED`** (NOT `record.status` — design R/B R2), pair it with
   `self._pipeline.steps[idx]` and feed the CB-2 helper. The `is not None` guard is mandatory:
   `_handle_loop_back` resets a target record to `result = None` (`gates.py:216-217`), so
   `record.result.status` would raise `AttributeError` after any loop-back (R/B C1.5).
2. Later index wins by construction (forward iteration overwrites).
3. Guard pairing on **both length and identity** (R/B C2.3): skip indices beyond
   `len(self._pipeline.steps)` and any index where `record.step_name != self._pipeline.steps[idx].name`,
   warning rather than raising. A *reordered* YAML keeps the same length and would hydrate the
   wrong field.
4. Missing plan file → WARNING + skip is CB-2's behaviour already.

### CB-4 — Approve-on-resume (FR-4) + NFR-1 re-assertions

Files: `[MODIFY] core/flow/engine/runner.py`, `[MODIFY] core/flow/engine/runner_utils.py`,
`[MODIFY] tests/e2e/capabilities/workflows/test_drafter_loop_e2e.py`,
`[MODIFY] tests/integration/core/flow/engine/test_pipeline_state_persistence.py`,
`[MODIFY] tests/unit/interfaces/api/v1/test_pipelines.py`

1. **D1**: an explicit keyword argument on `_execute_loop` (default `False`), forwarded through
   `execute_run`. `resume()` passes `True`; `run()` passes nothing. One-shot — consumed on the first
   loop iteration whether or not it approves.
2. At the **very top of the loop body**, immediately after `attempts.setdefault(step_idx, 0)`
   (`runner.py:215`), while the signal is live for `step_idx == run.current_step`:
   - the record exists and `record.status is WAITING_FOR_INPUT`
   - and `record.result is not None and record.result.status is PASSED`
   - and `step_def.gate is not None and step_def.gate.type is GateType.HITL`
   - → all true: INFO log with `run_id`; CB-2 hydration with the stored result;
     `run.complete_current_step(record.result)`; persist;
     `_log(run, "gate_approved_on_resume", step_def.name)`; `_emit("step_completed", …)` with the
     `approved_on_resume` marker (NFR-7 / R/B C2.2); consume the signal; `continue`.
   - → any false: consume the signal, fall through to normal execution.
3. **D2**: re-assert INT-US-02 E6/E7 — final run status COMPLETED from the persisted record, not
   `exit_code == 0` (PARKED and COMPLETED both exit 0), and the scripted verdict queue drained. Add
   the third `runner.invoke(app, ["resume"])` to each and assert COMPLETED only after it.
4. Refresh `test_pipeline_state_persistence.py:79-80`: drop the obsolete `gate = None` workaround;
   keep a gate-bearing variant that flows through.
5. **D7**: unit regression test — `POST /runs/{id}/gate` `action: "approve"` advances a gate-parked
   run (R-6). No endpoint code change.

> [!CAUTION]
> **The insertion point is a correctness constraint.** Two hazards precede the handler call:
> 1. `mark_step_running()` (`runner.py:295`) overwrites the `WAITING_FOR_INPUT` value AD-2 reads.
>    Placed after it, FR-4 compiles, type-checks, and is dead (R-1).
> 2. The **staleness-bypass block** (`runner.py:263-293`) can `complete_current_step(SKIPPED)` and
>    `continue` (R/B C1.2) — a parked step whose target is pristine would be bypassed as SKIPPED,
>    discarding the approval *and* the stored PASSED result.

> [!NOTE]
> **Accepted consequence (R/B C2.1).** Approving before the handler lookup (`runner.py:217-247`)
> means a resumed run whose YAML no longer registers the approved step's handler advances past it
> and fails at the *next* step. Correct — the step already succeeded in a prior session — but it
> moves which step name appears in the error.

### Design coverage

| Design item | Discharged by | Evidence |
|---|---|---|
| NFR-1 delivered-journey compatibility | CB-4 steps 3–4 + R-5 | 2 HITL pipelines, 0 existing gate-park tests |
| NFR-2 cross-session honesty | CB-3 | persisted state only; R-14 names the one inherited limit |
| NFR-3 LLM economy | Tests (happy + hostile) | exists-skip: zero LLM calls; approval: handler call count 0; hydration is a pure read |
| NFR-4 fail-loud parity | Tests (degradation) | malformed stored JSON still raises at the consumer; 3-strike loop untouched (R-16) |
| NFR-5 injection safety | Tests (hostile) | traversal-shaped `spec_path` rejected by the CB-1 guard before any write. (Component names are FR-6 → SF-02) |
| NFR-6 boundary hygiene | CB-1 step 8 | the ledger row exists because `tach check` cannot catch this |
| NFR-7 observability | D3 + CB-2 step 2 + CB-4 step 2 | INFO with `run_id` on every hydration; `gate_approved_on_resume` audit event |
| NFR-8 session-isolation posture | none | R-8 verbatim; do not weaken the `RuntimeError`; dev-guide note is SF-03/Guide-1 |
| AD-1 / AD-2 / AD-3 / AD-8 | CB-2 step 1 / CB-4 + R-4 / CB-1 steps 1, 8 (D8) / CB-3 | — |
| RT "approve-on-resume changes a flow someone relied on" | R-5 + CB-4 steps 3–4 | re-measured **low**, not medium |
| RT "gate-park vs handler-park misclassification" | Tests (hostile) | handler-park, FAILED, RESERVE/PENDING, AUTO gate |
| RT "plan file deleted between park and resume" | CB-2 step 2 + tests (degradation) | WARNING + skip |
| RT "`context.decomposition` shape drifts" | partially — SF-02 owns FR-9 | D4 freezes the type as `str` |

## Tests

Direct-branch testing: extract a helper rather than rely on transitive coverage.

| Bucket | Case |
|---|---|
| Happy | `DraftFeatureHandler`: spec exists → PASSED + `artifact_uuid`, no LLM call |
| | spec absent + provider + llm → drafts, returns `context.spec_path`, PASSED |
| | registry: `(DRAFT, FEATURE)` and `(VALIDATE, FEATURE)` resolve to non-`None` handlers |
| | hydration: `decompose+feature` PASSED → `context.decomposition` is the plan JSON; `plan+spec` PASSED → `context.plan` is the file body |
| | rehydration: stored PASSED decompose record → `context.decomposition` set on resume |
| | approve-on-resume: gate-park with PASSED → advances, handler call count stays 0, emits `gate_approved_on_resume` |
| | full 3-session `feature_decomposition` walk at unit/integration level (CLI proof is SF-03) |
| Boundary | zero-step and single-step pipelines with the signal live; approval at the **last** step → COMPLETED |
| | `step_records` longer than `steps` → warning, no raise |
| | **reordered YAML** — same length, `step_name` mismatch → skipped with a warning, wrong field NOT hydrated (R/B C2.3) |
| | **run that has looped back** — record reset to `result = None` → skipped, no `AttributeError` (R/B C1.5) |
| | **gateless `plan+spec` PASSED** → `context.plan` hydrates (call site at the join, R/B C1.1) |
| | **parked step whose target is "pristine"** (`stale_nodes` set) → approval wins, NOT bypassed as SKIPPED (R/B C1.2) |
| | decompose output `{}` / zero components → valid JSON, no crash |
| | spec named exactly `_feature_spec.md` → loud ERROR (R/B C1.3; only the non-empty guard catches it) |
| | `plan_path` → zero-byte file → `context.plan == ""` |
| Degradation | `plan_path` key missing → WARNING, `context.plan` untouched |
| | plan file deleted between park and resume → WARNING + skip; consumer fails loudly (NFR-2/FR-3) |
| | `record.result is None` on a `WAITING_FOR_INPUT` record → no approval |
| | `context.db` unset → lineage skipped, drafting PASSES (R-10) |
| | malformed JSON in a stored decompose output → hydration stores the string; consumer's `json.loads` raises (NFR-4) |
| Hostile | **handler-park NOT approved**: stored `WAITING_FOR_INPUT` under a HITL gate → re-executes (the most important negative test) |
| | HITL gate on a FAILED result → re-executes; RESERVE-park (stored `PENDING`) → re-executes (R-4); AUTO gate with PASSED → normal execution |
| | **`run()` never approves**, even against approvable-looking records |
| | approval fires **at most once per resume** |
| | `spec_path` with a traversal segment (`../../etc/passwd_feature_spec.md`, `../../x_feature_spec.md`) → guard before any write; no write outside `spec_path.parent` |
| | `spec_path` without the `_feature_spec.md` suffix → loud ERROR naming the convention |
| Regression | API `POST /runs/{id}/gate` `approve` advances a gate-parked run (R-6); all 4 existing resume tests green unmodified (R-5) |

## Decisions (audit)

All eight approved by the user, 2026-07-25, as written. Binding.

| # | Sev | Decision | Why |
|---|-----|----------|-----|
| D1 | HIGH | The one-shot approval signal is an **explicit keyword argument** on `_execute_loop`, forwarded through `execute_run`, default `False`. `run()` never sets it | An unconditional record check risks a **stale approval** — a future router/loop_back leaving a `WAITING_FOR_INPUT` record *ahead* of `current_step` would skip a real step. A kwarg makes that structurally impossible. A runner instance attribute is invisible in the signature and can survive a re-entrant call |
| D2 | HIGH | **INT-US-02 E6 and E7 become three-session journeys**: session 1 handler-parks → session 2 re-executes, PASSES, gate-parks → session 3 approves and flows through | Treating "handler-park that re-executes and immediately gate-parks" as one act would break AD-2's PASSED-only rule. The extra `sw resume` is the gate asking the human to approve the spec they just wrote. **Guide-2 must state this** |
| D3 | MED | The approval path logs audit event **`gate_approved_on_resume`** AND emits `step_completed` with an `approved_on_resume` marker | Otherwise the advance is invisible in the CLI and unassertable in e2e (FR-10, NFR-7) |
| D4 | MED | `RunContext.decomposition` is **`str \| None`** (canonical JSON), not a dict | Mirrors `context.plan`; keeps the `decompose.py` migration a rename; freezes the FR-9 seam as a string contract |
| D5 | MED | `DraftFeatureHandler` lives in **`handlers/draft.py`** | A separate module fragments a cohesive 208-line file and forces duplicating `_pop_feedback` or a cross-import |
| D6 | MED | The `_resolve_spec_path` gap (R-15) is **deferred to SF-03/FR-8**, with the CB-1 cross-SF constraint | The CLI journey is FR-8's scope; the two conventions MUST agree |
| D7 | MED | The REST gate endpoint (R-6) **gets a regression test in SF-01** | The behaviour changes either way; an untested silent fix invites a regression |
| D8 | LOW | `known_boundary_violations.md` gets a **new row**, cross-referencing the inline-import row (line 9) | Amending line 9 would conflate two rules in one entry |

## Deferred

| Item | Owner | Note |
|------|-------|------|
| `_resolve_spec_path` for `feature_decomposition` | SF-03 / FR-8 (D6) — done, `8fff2470` | MUST derive `specs/{name}_feature_spec.md` and **import `FEATURE_SPEC_SUFFIX` from `core/flow/handlers/draft.py`** — CB-1 made it a public module constant so the CLI and the guard cannot drift |
| `4_interactive_hitl_gates.md` approve-on-resume, incl. the D2 three-session journey | SF-03 / Guide-2 — pulled into CB-4 | §3 said only "boot it back up where it failed" (R-16) |
| `pipeline_engine_guide.md` journey block | SF-03 / Guide-1 — done, §13 in CB-5 | — |
| `domain_flow_engine.md` registry table missing handler rows | SF-03 docs pass — done in CB-1 | — |
| Retry counters do not survive resume (R-14) | not scheduled here — **do not "fix" it here**; now `TECH-033` | Planned as `C-FLOW-07` territory; design NFR-2 records why that was wrong |
| Shared mutable `RunContext` across concurrent fan-out sub-runners | **`TECH-014`** (filed 2026-07-25) — **NOT** the add-on | The runner writes `run_id`/`step_records`/`pipeline_runner` to the shared context every step (`runner.py:404-406`), so lineage and telemetry are **already mis-attributed** in shipped `C-FLOW-03` fan-out, independent of FR-2 (which widened it to the plan fields). A defect in delivered code, not gated on `C-FLOW-12`. **Should land before `C-FLOW-12`** |
| DI inversion of the `core/flow` → `workflows/drafting` seam | existing monolith-purge ticket | AD-3; SF-01 only ledgers the debt (D8) |

## As built

| CB | Scope | FRs | Commit |
|----|-------|-----|--------|
| CB-1 | Registry completeness | FR-1 | `f1de38f1` |
| CB-2 | `decomposition` field + shared hydration | FR-2 | `c4c1a109` |
| CB-3 | Cross-session rehydration | FR-3 | `6811a943` |
| CB-4 | Approve-on-resume + NFR-1 re-assertions | FR-4 | `5ebcc414` |

Deviations from the plan:

- **CB-1 handler order**: pop feedback → name guard (suffix + non-empty) → feedback branches →
  path-kind guard → exists-skip (`is_file()`) → headless park → draft. The name guard moved ahead of
  the feedback branches: an unusable spec path is fatal regardless of reviewer findings. The pop
  still runs first, so the once-only contract holds.
- **CB-1 drafting path**: render profile via `resolve_profile(step.params.get("render_profile"),
  default=INTERACTIVE)` (`ValueError` → `_error_result`); `base_prompt` via `_build_base_prompt`
  (`FeatureDrafter` requires it); a drafter exception becomes an ERROR result, never propagates;
  no `llm`/`context_provider` → park.
- **CB-1 path-kind guard**: a `spec_path` that exists but is not a file ERRORs, rather than
  `read_text()`-ing a directory (`DraftSpecHandler`'s behaviour) or falling through to drafting.
- **CB-1 `_pop_feedback`** → module-level `_pop_step_feedback`; `DraftSpecHandler._pop_feedback`
  stays a thin delegate — four shipped tests call it (`test_draft_handler.py:199-213`).
- **CB-1** also completed the `domain_flow_engine.md` registry table (9 missing handlers, every
  module path stale — `flow/_draft.py` no longer exists) and added dev-guide pattern 24 in
  `special_patterns_and_adaptations.md` (Round-Trip Name Derivation for Self-Naming Writers).
- **CB-2** hydration lives in new **`engine/hydration.py`** (`hydrate_plan_context`), and router-target
  resolution moved to **`engine/routers.py`** (`resolve_route_target()`): `runner.py` was at 598/600
  lines; now 593.
- **CB-2** serializes with `default=str`, matching `StateStore` (`store.py:132-133`), so live and
  resume hydration are byte-equal; catches `UnicodeDecodeError` (a `ValueError`, not `OSError`)
  from a corrupt plan artifact.
- **CB-2** clears the field a combo owns on a `FAILED`/`ERROR` result (user decision F4-b), so
  `decompose passes → hydrates → loop_back → decompose re-runs and fails` does not leave a superseded
  plan for orchestrate. Scope addition beyond FR-2's text.
- **CB-4** approval is `engine/approval.py`; it also requires `record.step_name == step_def.name`.
  E6/E7 drive to terminal with a bounded loop instead of a fixed three sessions (see the CB-4
  walkthrough).
