# Implementation Plan: Autonomous Feature Decomposition [SF-02: Decomposition Artifacts & Frozen Seams]

- **Feature ID**: INT-US-21
- **Sub-Feature**: SF-02 — Decomposition Artifacts & Frozen Seams
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-21/INT-US-21_sf02_implementation_plan.md
- **Status**: APPROVED (user, 2026-07-25)
- **FRs in scope**: FR-5, FR-6, FR-7, FR-9
- **Depends on**: SF-01 — COMPLETE (`f1de38f1`, `c4c1a109`, `6811a943`, `5ebcc414`)

---

## Research Notes

Verified against `main` on 2026-07-25, after SF-01 landed. Several findings contradict instructions
in the design; those are called out explicitly.

### R-1 — The `DecompositionPlan` model (`workflows/planning/decomposition.py:28,72`)

`ComponentChange`: `component: str` · `exists: bool` · `change_nature: str` · `description: str` ·
**`proposed_dal: DALLevel` (REQUIRED, an enum)** · `dependencies: list[str]` ·
`target_modules: list[str]` · `confidence: int`.

`DecompositionPlan`: `feature_spec: str` · `components: list[ComponentChange]` ·
`integration_seams: list[IntegrationSeam]` · `build_sequence: list[str]` · `coverage_score: float`
· `alignment_notes: list[str]` · **`timestamp: str` (REQUIRED)**.

> The component key is **`component`**, not `name` — `OrchestrateComponentsHandler` reads
> `comp.get("component")` (`decompose.py:158`). Any fixture using `name` is testing nothing.

### R-2 — ⚠️ The design's "mirror `PlanSpecHandler`" instruction would crash every run

FR-5 says to persist "PlanSpecHandler parity". `PlanSpecHandler` does
`yaml.dump(plan_artifact.model_dump(), buf)` (`generation.py:397-399`). Applied to a
`DecompositionPlan` that **raises**, measured:

| Serialization | `proposed_dal` becomes | `ruamel yaml.dump` |
|---|---|---|
| `model_dump()` (python mode) | `<enum 'DALLevel'>` | **`RepresenterError: cannot represent an object: <DALLevel.DAL_B>`** |
| `model_dump(mode="json")` | `str` | ✅ `proposed_dal: DAL_B` |

`PlanSpecHandler` gets away with it only because `PlanArtifact` has **no enum fields** (all
`str`/`list`/`int`, `models.py:169-188`). The pattern does not transfer.

> **SF-02 MUST use `model_dump(mode="json")` for the artifact.** `proposed_dal` is required on every
> component, so the python-mode dump fails on 100% of real plans — this is not an edge case.
> FR-7 ("`proposed_dal` survives serialization to the persisted artifact") depends on exactly this.

### R-3 — The component template is **Jinja2**, and `core/flow` has no Jinja today

`.specweaver/templates/component_spec.md` (scaffolded from `_DEFAULT_COMPONENT_SPEC`,
`workspace/project/scaffold.py:81`) contains Jinja placeholders:
`{{ component_name }}`, `{{ date }}`, `{{ parent_feature | default("N/A") }}`,
`{{ purpose | default("TODO: Describe the single responsibility.") }}`.

- `jinja2` is used by `workflows/drafting/{drafter,feature_drafter}.py` (`from jinja2 import Template`).
- **`core/flow` imports jinja2 nowhere.** Verified by grep.
- FR-6's "pre-seeding Purpose from `description`" maps to the `purpose` variable — which means the
  template must be **rendered**, not copied. Copying verbatim writes literal `{{ component_name }}`
  into the user's spec file.
- Per SF-01 CB-1's decision, the handler must **read the template file**, never import
  `_DEFAULT_COMPONENT_SPEC` (`core/flow/context.yaml` `consumes` lists only `workspace/memory`).

### R-4 — ⚠️ A park does NOT display step output, so FR-7 is not free

`RichPipelineDisplay._on_run_parked` (`engine/display.py:221-236`) prints exactly two things: the
step name and `Resume with: sw run --resume <id>`. `_on_step_parked` sets a status note only.
**Nothing renders `result.output`.**

FR-7 says `proposed_dal` is "surfaced in the decompose step's output summary shown at the HITL
park". No such surface exists today — the data reaching `result.output` is necessary but **not
sufficient**. See Q2.

### R-5 — Component-name validation already exists (reuse, don't reinvent)

`decompose.py:153`: `name_pattern = re.compile(r"^[a-zA-Z0-9_\-]+$")`, applied in the fan-out with
the message *"Invalid or malicious component name detected … Aborting fan_out to prevent path
traversal."* FR-6/NFR-5 require the same guard before any filesystem write. Extract it to one
module-level constant rather than a second copy.

### R-6 — `PlanSpecHandler`'s persist/lineage pattern (the parts that DO transfer)

`generation.py:387-411`:
1. `plan_path = context.spec_path.with_name(context.spec_path.stem + "_plan.yaml")`
2. uuid: `extract_artifact_uuid(existing content)` if the file exists, else `uuid4()`
3. `tag_str = wrap_artifact_tag(artifact_uuid, "yaml")` → `# sw-artifact: <uuid>` (verified in
   `infrastructure/llm/lineage.py:50-52`), prepended to the dumped YAML
4. `plan_path.write_text(content)`, then `log_artifact_event(..., event_type="generated_plan")`
5. The path is returned in `StepResult.output["plan_path"]`

FR-5's analogues: `<stem>_decomposition.yaml`, `event_type="generated_decomposition"`.

### R-7 — FR-9a's seam: `run_fan_out(runner, sub_pipelines, parent_run_id)`

`runner_utils.py:242`. `OrchestrateComponentsHandler` builds sub-pipelines from
`context.decomposition` (SF-01 CB-2 migrated it off `context.plan`), validates names, then fans out.
The existing `test_integration_physical_io_join_locks` sets `ctx.pipeline_runner = runner` and is
the closest working example.

> **`TECH-014` applies here.** The fan-out hands the *same* `RunContext` to every sub-runner. FR-9a
> only needs to prove the hydrated field *reaches* the fan-out and the DAG is enumerated — it must
> NOT try to fix or work around the race, which is a separate ticket.

### R-8 — What SF-01 already guarantees (do not re-implement)

`context.decomposition` is populated by `hydrate_plan_context` (`engine/hydration.py`) on any
`PASSED` `decompose+feature` step, serialized with `default=str` to match `StateStore`, cleared on
`FAILED`/`ERROR`, and rebuilt on `resume()` from persisted records. FR-9a's pin therefore tests the
*consumer* side only.

### External research

None required — no new external dependency beyond `jinja2`, which is already a project dependency
(used by `workflows/drafting`). See Q3 for whether `core/flow` should import it.

---

## Architecture Verification (Phase 3)

### 3.1 Mechanism vs. Constraint Matrix

Target module: `specweaver/core/flow` — `archetype: orchestrator`; `consumes:` includes
`specweaver/planning`, `specweaver/llm`, `specweaver/config`; `forbids:` `specweaver/drafting`,
`specweaver/context`, `specweaver/sandbox/*/interfaces`.

| Mechanism | Where | Category | Constraint check | Verdict |
|---|---|---|---|---|
| Write `<stem>_decomposition.yaml` | `handlers/decompose.py` | I/O (file write) | orchestrator may do file I/O; `PlanSpecHandler` precedent | ✅ |
| Write `specs/<component>_spec.md` | `handlers/decompose.py` | I/O (file write) | same, plus NFR-5 name validation before any write | ✅ |
| Read `.specweaver/templates/component_spec.md` | `handlers/decompose.py` | I/O (file read) | a *file read*, not a `workspace/project` import — deliberate (SF-01 CB-1) | ✅ |
| Render Jinja template | `handlers/decompose.py` | Dependency (3rd-party) | `jinja2` is a project dep, not governed by `context.yaml` (which lists internal modules) — but it is **new to `core/flow`** | ⚠️ Q3 |
| `log_artifact_event` | `handlers/decompose.py` | I/O (DB) | `PlanSpecHandler`/`DraftFeatureHandler` precedent via `core/flow/store` | ✅ |
| Read `DecompositionPlan` model | `handlers/decompose.py` | Dependency | `consumes: specweaver/planning` ✅ already imported | ✅ |

**Zero new tach edges. Zero new `consumes` entries.**

### 3.2 Zoom-out test

- **Artifact persistence** — `PlanSpecHandler` already does the equivalent for a different artifact.
  Rather than a third copy, the shared shape (derive path → uuid → tag → write → lineage) is a
  candidate for one helper. See Q5.
- **Stub spec writing** — no existing capability writes component specs; genuinely new.
- **Seam pins** — pure tests, no production code.

### 3.3–3.5 Cycles / closure / stability

No new imports between `specweaver` modules, so no new cycle is possible. Changes are confined to
`handlers/decompose.py` plus tests (and possibly `engine/display.py` — Q2). Nothing is added to a
stable module.

### 3.6 Architectural violations

**None new.** SF-02 introduces no boundary breach; the AD-3 drafting seam is SF-01's and is
untouched here.

---

## Design Coverage Map (Phase 5.0 pre-check)

Every FR, NFR, AD and Risk-Table entry from the design that touches SF-02, and where this plan
discharges it.

| Design item | Discharged by | Note |
|---|---|---|
| FR-5 artifact persistence | CB-1 | `mode="json"` per D1 — see R-2 |
| FR-6 stub component specs | CB-2 | never-overwrite + name guard + Jinja render |
| FR-7 DAL contract | CB-1 (data) + CB-2 (summary) | D2: handler-owned summary, no display change |
| FR-9 seam pins | CB-3 | (a) decompose→orchestrate, (b) hook-driven plan→generate |
| NFR-1 delivered-journey compat | CB-1/CB-2 regression tests | decompose gains writes; existing decompose tests must stay green |
| NFR-2 cross-session honesty | CB-1 | **AD-8 holds: rehydration reads step records, NOT the artifact file.** SF-02 must not make any consumer depend on the file existing |
| NFR-3 LLM economy | Test plan | persistence + stubs add ZERO LLM calls; assert handler call counts |
| NFR-4 fail-loud parity | D6 | artifact write failure fails the step, plan retained in `output` |
| NFR-5 injection safety | CB-2 | R-5 regex before **any** filesystem write; hostile test asserts nothing written outside the target dir |
| NFR-6 boundary hygiene | §3.1 | zero new tach edges, zero new `consumes`; `jinja2` is 3rd-party (D3) |
| NFR-7 observability | CB-1/CB-2 + **R/B C1.1** | INFO with `run_id` on artifact write and stub creation. **The design's "park messages name the artifact path" clause has the same defect as FR-7** — no park surface renders output. Same resolution as D2: the handler puts the path in its summary; rendering is SF-03 |
| AD-4 freeze the add-on seams | CB-1/CB-2/CB-3 | SF-02 *is* the freezing: artifact schema, stub paths, `proposed_dal` presence, `context.decomposition` contract |
| AD-6 DAL posture delegated | CB-1 | SF-02 guarantees the DAL **data** contract only; per-component isolation is `C-EXEC-07`/`C-FLOW-12` |
| AD-7 artifact next to the spec | CB-1, D7 | stubs follow the same rule (`spec_path.parent`) |
| AD-8 rehydration from records | CB-1 | the artifact is the human-facing copy; nothing reads it back |
| RT stub writes collide with user files | CB-2 | never-overwrite; asserted byte-identical after a second run |
| RT `context.decomposition` shape drifts | CB-3 (FR-9a) | the pin fails if the contract breaks |

## Work Breakdown — Commit Boundaries

### CB-1 — Decomposition artifact persistence (FR-5, FR-7 data half)

**Files**: `[MODIFY] core/flow/handlers/decompose.py`, `[MODIFY] tests/unit/core/flow/handlers/test_decompose.py`

1. Derive `feature_name` from the spec stem when `step.params["feature_name"]` is absent
   (kills the `"unknown_feature"` fallback at `decompose.py:30`).
2. Persist `context.spec_path.with_name(stem + "_decomposition.yaml")` following R-6's sequence.
   **Serialize with `model_dump(mode="json")`** — R-2. Never `model_dump()`.
3. uuid: extract-or-generate, prepend `wrap_artifact_tag(uuid, "yaml")`.
4. `log_artifact_event(event_type="generated_decomposition")` when `context.db` is set.
5. Return the artifact path in `StepResult.output` (key name — Q4) alongside the existing plan dump.
6. Persistence failure must NOT lose the plan: the step's `output` still carries the decomposition
   so SF-01's hydration bridge keeps working. Decide fail-loud vs. warn — Q6.

### CB-2 — Stub component specs (FR-6)

**Files**: `[MODIFY] core/flow/handlers/decompose.py`, `[MODIFY] tests/unit/core/flow/handlers/test_decompose.py`

1. Extract R-5's name regex to a module-level constant; reuse it in both the fan-out and here.
2. For each `ComponentChange`: validate the name, resolve `specs/<component>_spec.md`, **skip if it
   exists** (never overwrite), else render the template with `component_name`, `date`,
   `parent_feature`, `purpose=description`.
3. Template source: read `<project>/.specweaver/templates/component_spec.md`; if absent, a minimal
   skeleton defined locally in the handler (R-3). Never import from `workspace/project`.
4. Report created/skipped counts in the step output so the e2e inventory assertion has something to
   read.

> [!NOTE]
> **Why the stubs matter to the add-on (R/B C1.3).** `OrchestrateComponentsHandler` builds each
> sub-pipeline from `new_feature.yaml` with `params["component"] = <node>`; it never checks that a
> component spec exists. So the stubs are **not** a prerequisite for fan-out to start — they are
> what makes each sub-run's `draft_spec` take the exists-skip path instead of parking for a human.
> That is precisely the seam AD-4 freezes, and it is why FR-6 belongs in the base contract rather
> than the add-on.

> [!CAUTION]
> **Stale stubs are out of scope but must not be silently wrong (R/B C1.2).** Never-overwrite means
> a re-decomposition that drops or renames a component leaves the old stub on disk. SF-02 does NOT
> reconcile or delete them (that is hand-edit arbitration — `C-FLOW-05`/`B-INTL-07` territory), but
> the created/skipped report must make it visible that a stub was skipped rather than authored.

### CB-3 — FR-9 seam pins (+ FR-7 surfacing, pending Q2)

**Files**: `[NEW] tests/integration/core/flow/engine/test_seam_pins.py`, possibly
`[MODIFY] core/flow/engine/display.py`

1. **FR-9a** — a custom `decompose → orchestrate` pipeline with a doubled sub-runner proves the
   hydrated `context.decomposition` feeds the fan-out: DAG ordering reached, components enumerated.
   **Do not** add an orchestrate step to `feature_decomposition.yaml`.
2. **FR-9b** — a custom `plan+spec → generate+code` pipeline proves `context.plan` reaches
   generation **hook-driven**. Today's `test_planning_integration.py:441` seeds `ctx.plan` by hand,
   which proves nothing about production wiring.
3. FR-7 park surfacing, scope per Q2.

---

## Test Plan (4 adversarial buckets)

**Happy** — artifact written next to the spec with the uuid tag; `proposed_dal` present and a
**string** in the YAML; lineage event logged with `generated_decomposition`; stub spec created per
component with Purpose seeded; both seam pins green.

**Boundary** — zero-component plan (artifact written, no stubs); a component whose spec already
exists (skipped, **byte-identical afterwards**); missing `.specweaver/templates/` (local fallback
used); spec stem that already ends in `_decomposition`; `coverage_score` exactly 1.0;
**re-running decompose reuses the existing artifact's uuid** rather than minting a new lineage
identity (R-6's extract-or-generate); a re-decomposition that drops a component leaves the old
stub untouched and reports it as skipped (R/B C1.2).

**Degradation** — `context.db` unset (no lineage, still PASSES); template file unreadable (fallback,
warning); specs dir missing (created or loud failure — Q7); disk write failure mid-way (partial
stubs must not corrupt the artifact).

**Hostile** — component name `../../etc/passwd` → rejected before any write, and **assert nothing
was written outside `specs/`**; name with a path separator or NUL; a plan whose `components` is not
a list; `proposed_dal` missing from the LLM payload (Pydantic rejects at parse — pin it).

**Regression** — SF-01's hydration still fires after the new persistence code (the decompose output
must remain the source for `context.decomposition`).

---

## Resolved Decisions (Phase 4 audit — user, 2026-07-25)

All seven approved. Binding on the implementation; do not re-litigate.

| # | Sev | Decision | Rationale |
|---|-----|----------|-----------|
| D1 | HIGH | **Serialize the artifact with `model_dump(mode="json")`**, deviating from FR-5's "PlanSpecHandler parity" wording | Measured: `model_dump()` leaves `proposed_dal` a `DALLevel` enum and ruamel raises `RepresenterError`; `proposed_dal` is required on every component, so python-mode fails on **100%** of real plans. The two modes differ in exactly two places (enum→str, tuple→list), both needed for YAML. Decisive extra: `mode="json"` output is **byte-identical** to what SF-01 already puts in `context.decomposition` (verified), so the on-disk artifact and the in-memory contract are the same shape — which matters because AD-4 freezes this artifact as a seam `C-FLOW-12` builds on. Generalised by **`TECH-016`** |
| D2 | HIGH | **FR-7 = option (c):** the handler emits a human-readable summary (including `proposed_dal` per component) in its own `StepResult.output`. **No change to `engine/display.py`** | No park surface renders step output today (R-4). Modifying `_on_run_parked` would touch shipped display used by *every* pipeline — wider than SF-02's remit. Rich rendering at the park belongs to SF-03's CLI journey, which owns FR-8 |
| D3 | MED | `core/flow` **may import `jinja2`** to render the component template | It is an existing project dependency, not a `context.yaml`-governed module edge. The shipped template genuinely uses Jinja filters (`{{ purpose \| default(...) }}`), so `str.replace` would corrupt it |
| D4 | MED | Artifact path goes in `StepResult.output["decomposition_path"]` | Mirrors `plan_path` without colliding with it — reusing `plan_path` would be picked up by FR-2's `plan+spec` hydration branch, which is actively dangerous |
| D5 | MED | **Do NOT extract the shared persist helper in SF-02.** Write `mode="json"` inline; the generalisation is **`TECH-016`** | Extracting would refactor shipped `PlanSpecHandler`/`DraftFeatureHandler` inside a feature commit — the exact bundling this repo ticketed against. SF-02 needs correct behaviour now; TECH-016 makes it universal, with an architecture-test guardrail so bypassing the helper fails the build |
| D6 | MED | Artifact write failure **fails the step loudly**, with the plan still in `output` | NFR-4 fail-loud parity. Keeping the plan in `output` means a resume re-persists without re-calling the LLM, so a disk error costs no tokens |
| D7 | LOW | Stub specs are written to `spec_path.parent` | Consistent with AD-7 (the artifact lands next to the spec); `project_path/"specs"` would split a feature from its components whenever the spec lives elsewhere |

### Spun off during this plan

**`TECH-016` — Unified Artifact Writer & Serialization Format Enforcement.** Phase 0 found that
*both* existing `yaml.dump(model_dump(), buf)` call sites (`generation.py:398`, `scenario.py:96`)
are safe only because their models happen to have no enum fields, and that the
`derive path → uuid → tag → write → lineage` sequence is hand-rolled five times. SF-02 adds a sixth.
Filed rather than fixed here, per D5.

<details>
<summary>Original audit questions (superseded by the decisions above)</summary>

Sorted by severity.

| # | Sev | Question | Options | Impact | Proposal |
|---|---|---|---|---|---|
| Q1 | **HIGH** | R-2 proves the design's "PlanSpecHandler parity" instruction crashes on every real plan. Confirm SF-02 deviates and uses `model_dump(mode="json")` | (a) deviate, document it; (b) follow the design literally | (b) is a guaranteed 100% failure rate — `proposed_dal` is required on every component | **(a)**. It is a design-text defect, not a judgement call; the walkthrough records the deviation |
| Q2 | **HIGH** | FR-7 says `proposed_dal` is "surfaced … at the HITL park", but no park surface renders step output (R-4). How far does SF-02 go? | (a) data-only: guarantee it in artifact + `result.output`, defer rendering to SF-03's CLI journey; (b) add output rendering to `_on_run_parked` now; (c) put a human-readable summary in the park message the handler controls | (b) touches shipped display used by every pipeline — wider blast radius than SF-02's remit; (a) risks FR-7 being "done" while a human still cannot see the DAL at the gate | **(c)** — the handler owns its own summary string, no display change, and SF-03 can render it richly later. Confirm |
| Q3 | MED | Should `core/flow` import `jinja2` to render the component template (R-3)? | (a) yes — `jinja2` is already a project dep; (b) plain `str.replace` for the four placeholders; (c) ship a non-Jinja fallback and skip the project template | (b) breaks on `{{ x \| default(...) }}` filters, which the shipped template uses; (c) silently ignores a template the user customised | **(a)**. It is a third-party dep, not a `context.yaml`-governed module edge, and the template is genuinely Jinja |
| Q4 | MED | `StepResult.output` key for the artifact path | (a) `decomposition_path` (mirrors `plan_path`); (b) `artifact_path`; (c) reuse `plan_path` | (c) collides with FR-2's `plan+spec` hydration, which reads `plan_path` — actively dangerous | **(a)** |
| Q5 | MED | Three handlers now do derive-path → uuid → tag → write → lineage. Extract a shared helper? | (a) extract now; (b) third copy, extract later; (c) leave duplicated | (a) touches shipped `PlanSpecHandler`/`DraftFeatureHandler` inside a feature commit — the exact bundling this repo just ticketed against | **(b)**, and file it as a TECH ticket via `specweaver-ticket` rather than doing it here |
| Q6 | MED | Artifact write fails (disk full / permission). Fail the step, or warn and pass? | (a) fail loud — the artifact is FR-5's deliverable; (b) warn, keep the plan in `output` so the run continues | NFR-4 says fail-loud parity; but (a) discards a successful, expensive LLM decomposition over a disk error | **(a)** with the plan still in `output`, so a resume re-persists without re-calling the LLM. Confirm |
| Q7 | LOW | Stub specs go in `specs/` — relative to `project_path` or `spec_path.parent`? | (a) `project_path/"specs"`; (b) `spec_path.parent` | They differ whenever the feature spec is not in `specs/`. (b) co-locates components with their parent feature | **(b)** — consistent with the artifact landing next to the spec (AD-7) |

</details>

---

## Progress

| CB | Scope | FRs | Status |
|----|-------|-----|--------|
| CB-1 | Decomposition artifact persistence | FR-5, FR-7 (data) | ⬜ |
| CB-2 | Stub component specs | FR-6 | ⬜ |
| CB-3 | FR-9 seam pins (+ FR-7 surfacing) | FR-9, FR-7 | ⬜ |
