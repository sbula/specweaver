# INT-US-21 SF-02 — Decomposition Artifacts & Frozen Seams

**Status**: APPROVED (user, 2026-07-25). Decisions D1–D7 approved. COMPLETE — committed 2026-07-26
(`4a42b87a`, `ce00be20`, `5aa20ffa`). · **FRs owned**: FR-5, FR-6, FR-7, FR-9 (FR-9 rescoped
2026-07-26 to the plan-bridge half only) · **Depends on**: SF-01 — COMPLETE (`f1de38f1`, `c4c1a109`,
`6811a943`, `5ebcc414`) · Design: [INT-US-21_design.md](INT-US-21_design.md) §Sub-features → SF-02

## Goal

Make the journey's output durable and PO-visible — `<stem>_decomposition.yaml` + lineage, stub
component specs, a DAL summary — and pin the plan→generate bridge to production wiring.

## Where it plugs in

Verified against `main` on 2026-07-25, after SF-01. Two findings (R-2, R-4) contradict the design
text; both are resolved by decisions and folded into the design's FR-5/FR-7 as `(SF-02 Phase-0)`
corrections.

### R-1 — The `DecompositionPlan` model (`workflows/planning/decomposition.py:28,72`)

`ComponentChange`: `component: str` · `exists: bool` · `change_nature: str` · `description: str` ·
**`proposed_dal: DALLevel` (REQUIRED, an enum)** · `dependencies: list[str]` ·
`target_modules: list[str]` · `confidence: int`.

`DecompositionPlan`: `feature_spec: str` · `components: list[ComponentChange]` ·
`integration_seams: list[IntegrationSeam]` · `build_sequence: list[str]` · `coverage_score: float`
· `alignment_notes: list[str]` · **`timestamp: str` (REQUIRED)**.

The component key is **`component`**, not `name` — `OrchestrateComponentsHandler` reads
`comp.get("component")` (`decompose.py:158`). A fixture using `name` tests nothing.

### R-2 — "Mirror `PlanSpecHandler`" would crash every run

`PlanSpecHandler` does `yaml.dump(plan_artifact.model_dump(), buf)` (`generation.py:397-399`).
Applied to a `DecompositionPlan`, measured:

| Serialization | `proposed_dal` becomes | `ruamel yaml.dump` |
|---|---|---|
| `model_dump()` (python mode) | `<enum 'DALLevel'>` | **`RepresenterError: cannot represent an object: <DALLevel.DAL_B>`** |
| `model_dump(mode="json")` | `str` | ✅ `proposed_dal: DAL_B` |

`PlanArtifact` has **no enum fields** (all `str`/`list`/`int`, `models.py:169-188`), so the pattern
does not transfer. `proposed_dal` is required on every component: python-mode fails on 100% of
real plans. FR-7 depends on this (D1).

### R-3 — The component template is **Jinja2**; `core/flow` had no Jinja

`.specweaver/templates/component_spec.md` (scaffolded from `_DEFAULT_COMPONENT_SPEC`,
`workspace/project/scaffold.py:81`) has placeholders `{{ component_name }}`, `{{ date }}`,
`{{ parent_feature | default("N/A") }}`,
`{{ purpose | default("TODO: Describe the single responsibility.") }}`.

- `jinja2` is used by `workflows/drafting/{drafter,feature_drafter}.py` (`from jinja2 import Template`);
  **`core/flow` imports it nowhere** (grep).
- "Pre-seeding Purpose from `description`" maps to `purpose` — the template must be **rendered**;
  copying writes literal `{{ component_name }}` into the user's spec.
- Read the template **file**; never import `_DEFAULT_COMPONENT_SPEC` (`core/flow/context.yaml`
  `consumes` lists only `workspace/memory`).

### R-4 — A park does NOT display step output

`RichPipelineDisplay._on_run_parked` (`engine/display.py:221-236`) prints the step name and
`Resume with: sw run --resume <id>`. `_on_step_parked` sets a status note only. **Nothing renders
`result.output`** — so FR-7's "shown at the HITL park" had no surface (D2).

### R-5 — Component-name validation exists — reuse it

`decompose.py:153`: `name_pattern = re.compile(r"^[a-zA-Z0-9_\-]+$")`, applied in the fan-out with
*"Invalid or malicious component name detected … Aborting fan_out to prevent path traversal."*
FR-6/NFR-5 need the same guard before any write — extract one module-level constant.

### R-6 — `PlanSpecHandler`'s persist/lineage sequence (the part that transfers)

`generation.py:387-411`:
1. `plan_path = context.spec_path.with_name(context.spec_path.stem + "_plan.yaml")`
2. uuid: `extract_artifact_uuid(existing content)` if the file exists, else `uuid4()`
3. `tag_str = wrap_artifact_tag(artifact_uuid, "yaml")` → `# sw-artifact: <uuid>`
   (`infrastructure/llm/lineage.py:50-52`), prepended to the dumped YAML
4. `plan_path.write_text(content)`, then `log_artifact_event(..., event_type="generated_plan")`
5. path returned in `StepResult.output["plan_path"]`

FR-5's analogues: `<stem>_decomposition.yaml`, `event_type="generated_decomposition"`.

### R-7 — FR-9a's seam: `run_fan_out(runner, sub_pipelines, parent_run_id)` — descoped 2026-07-26

Kept for `C-FLOW-12` to inherit, not built here: a pin against an undesigned consumer freezes a
guess and charges the suite permanently (design FR-9). `TECH-014` should land before `C-FLOW-12`.

`runner_utils.py:242`. `OrchestrateComponentsHandler` builds sub-pipelines from
`context.decomposition`, validates names, then fans out. `test_integration_physical_io_join_locks`
sets `ctx.pipeline_runner = runner` — the closest working example.

### R-8 — What SF-01 guarantees (do not re-implement)

`hydrate_plan_context` (`engine/hydration.py`) sets `context.decomposition` on any `PASSED`
`decompose+feature` step, serialized with `default=str` to match `StateStore`, cleared on
`FAILED`/`ERROR`, rebuilt on `resume()` from persisted records. FR-9(b) tests the consumer side
only — that `context.plan` reaches generation hook-driven rather than seeded.

No new external dependency; `jinja2` is already a project dependency (D3).

### Architecture check

Target: `specweaver/core/flow` — `archetype: orchestrator`; `consumes:` includes
`specweaver/planning`, `specweaver/llm`, `specweaver/config`; `forbids:` `specweaver/drafting`,
`specweaver/context`, `specweaver/sandbox/*/interfaces`.

| Mechanism | Where | Category | Constraint check | Verdict |
|---|---|---|---|---|
| Write `<stem>_decomposition.yaml` | `handlers/decompose.py` | I/O (file write) | orchestrator may do file I/O; `PlanSpecHandler` precedent | ✅ |
| Write `specs/<component>_spec.md` | `handlers/decompose.py` | I/O (file write) | same, plus NFR-5 name validation before any write | ✅ |
| Read `.specweaver/templates/component_spec.md` | `handlers/decompose.py` | I/O (file read) | a file read, not a `workspace/project` import | ✅ |
| Render Jinja template | `handlers/decompose.py` | Dependency (3rd-party) | `jinja2` is a project dep, not a `context.yaml` edge — but **new to `core/flow`** | ⚠️ D3 |
| `log_artifact_event` | `handlers/decompose.py` | I/O (DB) | `PlanSpecHandler`/`DraftFeatureHandler` precedent via `core/flow/store` | ✅ |
| Read `DecompositionPlan` model | `handlers/decompose.py` | Dependency | `consumes: specweaver/planning` already imported | ✅ |

Zero new tach edges, zero new `consumes`, no new cross-module import (no cycle), nothing added to a
stable module. No new boundary breach; AD-3's drafting seam is SF-01's.

## Changes

### CB-1 — Decomposition artifact persistence (FR-5, FR-7 data half)

Files: `[MODIFY] core/flow/handlers/decompose.py`,
`[NEW] tests/integration/core/flow/handlers/test_decomposition_artifacts_integration.py`,
`[NEW] tests/unit/core/flow/handlers/test_decompose_artifact.py`,
`[MODIFY] tests/unit/core/flow/handlers/test_decompose.py`

1. Derive `feature_name` from the spec stem when `step.params["feature_name"]` is absent (kills the
   `"unknown_feature"` fallback at `decompose.py:30`).
2. Persist `context.spec_path.with_name(stem + "_decomposition.yaml")` following R-6. **Serialize
   with `model_dump(mode="json")`** (D1) — never `model_dump()`.
3. uuid: extract-or-generate, prepend `wrap_artifact_tag(uuid, "yaml")`.
4. `log_artifact_event(event_type="generated_decomposition")` when `context.db` is set.
5. Return the artifact path in `StepResult.output` (D4) alongside the plan dump.
6. A persistence failure fails the step, plan kept in `output` (D6).

> [!IMPORTANT]
> **Tier corrected 2026-07-26 (`TECH-017`).** Planned and first built unit-only — 16 unit tests,
> zero integration. Unit tests build `DecomposeFeatureHandler()` by hand and mock `context.db`, so
> they cannot see the real registry row, runner hydration hook, SQLite, or a real filesystem
> failure. FR-5's central claim — on-disk artifact and in-memory `context.decomposition` agree — is
> only provable through production wiring.

### CB-2 — Stub component specs (FR-6)

Files: `[MODIFY] core/flow/handlers/decompose.py`,
`[MODIFY] tests/integration/core/flow/handlers/test_decomposition_artifacts_integration.py`,
`[MODIFY] tests/unit/core/flow/handlers/test_decompose.py` (unit only for the name-regex and
template-fallback branches)

1. Extract R-5's regex to a module-level constant; the fan-out and the stub writer share it.
2. Per `ComponentChange`: validate the name, resolve `specs/<component>_spec.md`, **skip if it
   exists** (never overwrite), else render with `component_name`, `date`, `parent_feature`,
   `purpose=description`.
3. Template: read `<project>/.specweaver/templates/component_spec.md`; if absent, a minimal skeleton
   defined in the handler (R-3). Never import from `workspace/project`.
4. Report created/skipped counts in the step output for the e2e inventory assertion.

Tier: integration-first (`TECH-017`) — FR-6 claims *real spec files on disk a user can carry into
`sw implement`*; a mocked filesystem cannot prove that.

> [!NOTE]
> **Why the stubs matter to the add-on (R/B C1.3).** `OrchestrateComponentsHandler` builds each
> sub-pipeline from `new_feature.yaml` with `params["component"] = <node>` and never checks that a
> component spec exists. The stubs are not a prerequisite for fan-out — they make each sub-run's
> `draft_spec` take the exists-skip path instead of parking for a human. That is the seam AD-4
> freezes, so FR-6 belongs in the base.

> [!CAUTION]
> **Stale stubs are out of scope but must not be silently wrong (R/B C1.2).** A re-decomposition
> that drops or renames a component leaves the old stub. SF-02 does not reconcile or delete it
> (hand-edit arbitration — `C-FLOW-05`/`B-INTL-07`); the report must show it was skipped, not
> authored.

### CB-3 — FR-9(b) plan-bridge seam pin + FR-7 summary

Files: `[NEW] tests/integration/core/flow/engine/test_seam_pins.py`

1. **FR-9(b)** — a custom `plan+spec → generate+code` pipeline proves `context.plan` reaches
   generation **hook-driven**. `test_planning_integration.py:441` seeds `ctx.plan` by hand, which
   proves nothing about production wiring.
2. FR-7 summary in the handler's own output (D2).

FR-9(a) — the decompose→orchestrate pin with a doubled sub-runner — was descoped 2026-07-26. CB-3
still owns FR-9(b) and FR-7.

### Design coverage

| Design item | Discharged by | Note |
|---|---|---|
| NFR-1 delivered-journey compat | CB-1/CB-2 regression tests | existing decompose tests stay green |
| NFR-2 cross-session honesty | CB-1 | **AD-8 holds: rehydration reads step records, NOT the artifact file.** No consumer may depend on the file existing |
| NFR-3 LLM economy | tests | persistence + stubs add ZERO LLM calls; assert handler call counts |
| NFR-4 fail-loud parity | D6 | write failure fails the step, plan retained in `output` |
| NFR-5 injection safety | CB-2 | R-5 regex before **any** write; hostile test asserts nothing written outside the target dir |
| NFR-6 boundary hygiene | architecture check | `jinja2` is 3rd-party (D3) |
| NFR-7 observability | CB-1/CB-2 + **R/B C1.1** | INFO with `run_id` on artifact write and stub creation. "Park messages name the artifact path" has FR-7's defect — no park surface renders output; same resolution (D2) |
| AD-4 freeze the add-on seams | CB-1/CB-2 | contracts defined and tested **as they stand**: artifact schema, stub paths, `proposed_dal` presence, `context.decomposition` shape; not pinned against the unbuilt fan-out |
| AD-6 DAL posture delegated | CB-1 | DAL **data** contract only; isolation is `C-EXEC-07`/`C-FLOW-12` |
| AD-7 / AD-8 | CB-1, D7 | stubs follow `spec_path.parent`; nothing reads the artifact back |
| RT stub writes collide with user files | CB-2 | never-overwrite; byte-identical after a second run |
| RT `context.decomposition` shape drifts | CB-1 + SF-01 CB-2 | artifact schema and hydration tests break on any JSON-contract change. **Accepted residual:** `C-FLOW-12` writes the fan-out pin as its first commit |

## Tests

| Bucket | Case |
|---|---|
| Happy | artifact next to the spec with the uuid tag; `proposed_dal` present and a **string** in the YAML; lineage event `generated_decomposition`; one stub per component with Purpose seeded; plan-bridge seam pin green |
| Boundary | zero-component plan (artifact, no stubs); existing component spec skipped and **byte-identical afterwards**; missing `.specweaver/templates/` → local fallback; spec stem already ending in `_decomposition`; `coverage_score` exactly 1.0; **re-run reuses the existing artifact's uuid** (R-6); a dropped component's old stub untouched and reported skipped (R/B C1.2) |
| Degradation | `context.db` unset (no lineage, still PASSES); `project_metadata` unset (existing `started_at` fallback); template unreadable (fallback, warning); specs dir missing; disk write failure mid-way must not corrupt the artifact |
| Hostile | component `../../etc/passwd` → rejected before any write, **nothing written outside `specs/`**; name with a path separator or NUL; `components` not a list; `proposed_dal` missing from the LLM payload (Pydantic rejects at parse — pinned); a spec path that is a directory |
| Regression | SF-01 hydration still fires after persistence (decompose output stays the source for `context.decomposition`) |

## Decisions (audit)

All seven approved by the user, 2026-07-25. Binding. Proposals Q1–Q7 became D1–D7 (Q5 proposed a
third copy + a TECH ticket; adopted as D5).

| # | Sev | Decision | Why |
|---|-----|----------|-----|
| D1 | HIGH | **Serialize the artifact with `model_dump(mode="json")`**, deviating from FR-5's "PlanSpecHandler parity" wording | `model_dump()` leaves `proposed_dal` a `DALLevel` enum and ruamel raises `RepresenterError` — **100%** of real plans. The modes differ in exactly two places (enum→str, tuple→list), both needed for YAML. `mode="json"` output is **byte-identical** to SF-01's `context.decomposition` (verified), so the on-disk and in-memory contracts of this AD-4 seam agree. Generalised by **`TECH-016`** |
| D2 | HIGH | **FR-7 = option (c):** the handler emits a human-readable summary (incl. `proposed_dal` per component) in its own `StepResult.output`. **No change to `engine/display.py`** | No park surface renders output (R-4); changing `_on_run_parked` touches display used by *every* pipeline. Rendering at the park belongs to SF-03's CLI journey (FR-8). Rejected: (a) data-only — FR-7 "done" while no human sees the DAL; (b) rendering in `_on_run_parked` now |
| D3 | MED | `core/flow` **may import `jinja2`** to render the template | Existing project dependency, not a `context.yaml` module edge. The template uses Jinja filters (`{{ purpose \| default(...) }}`), so `str.replace` would corrupt it; skipping the project template would ignore a user's customisation |
| D4 | MED | Artifact path in `StepResult.output["decomposition_path"]` | Mirrors `plan_path` without colliding (over `artifact_path`) — reusing `plan_path` would be picked up by FR-2's `plan+spec` hydration |
| D5 | MED | **Do NOT extract the shared persist helper in SF-02.** Write `mode="json"` inline; generalisation is **`TECH-016`** | Extracting refactors shipped `PlanSpecHandler`/`DraftFeatureHandler` inside a feature commit. TECH-016 makes it universal with an architecture-test guardrail |
| D6 | MED | Artifact write failure **fails the step loudly**, plan still in `output` | NFR-4. A resume re-persists without re-calling the LLM — a disk error costs no tokens |
| D7 | LOW | Stub specs go to `spec_path.parent` | AD-7; `project_path/"specs"` would split a feature from its components when the spec lives elsewhere |

**Spun off: `TECH-016` — Unified Artifact Writer & Serialization Format Enforcement.** Both existing
`yaml.dump(model_dump(), buf)` call sites (`generation.py:398`, `scenario.py:96`) are safe only
because their models have no enum fields, and `derive path → uuid → tag → write → lineage` is
hand-rolled five times; SF-02 adds a sixth.

## As built

| CB | Scope | FRs | Commit |
|----|-------|-----|--------|
| CB-1 | Decomposition artifact persistence | FR-5, FR-7 (data) | `4a42b87a` |
| CB-2 | Stub component specs | FR-6 | `ce00be20` |
| CB-3 | FR-9(b) plan-bridge seam pin + FR-7 summary | FR-9, FR-7 | `5aa20ffa` |

- Artifact, stub writer and `build_dal_summary()` live in `handlers/decomposition_artifacts.py`
  (split out of `decompose.py` at 586 lines); the stub report in
  `output["component_specs"]` has buckets `created`/`skipped`/`rejected`/`failed` (SF-03 CB-2 added `collided`).
- The plan dump sits nested under `DECOMPOSITION_PLAN_KEY` (defined in `engine/hydration.py`), so
  `decomposition_path` does not leak into `context.decomposition`.
- A lineage failure or a stub problem never fails the step — the decomposition is paid for and the
  artifact durable.
- Name guard uses `\Z`, not `$`; never-overwrite uses `is_file()`. Details in the CB walkthroughs.
