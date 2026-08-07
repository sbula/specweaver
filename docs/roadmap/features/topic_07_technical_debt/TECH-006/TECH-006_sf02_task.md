# Task Breakdown: TECH-006 SF-02 — Reduce `RunContext` God Object

Implementation Plan: `TECH-006_sf02_implementation_plan.md`
Design Document: `TECH-006_design.md` (SF-02, FR-6…FR-12, AD-5…AD-8, NFR-6/7/8)
Story kind: TECH (refactor) → `python scripts/tests.py cb TECH-006 --kind refactor`

**5 commit boundaries** (design AD-7 / RED-1.2 — per-group-atomic: each commit adds ONE sub-model,
migrates EVERY consumer of that group's fields, and DELETES the old flat fields in the SAME commit.
Never leave an old and a new field alive for the same data across a commit boundary.)

| CB | Group | Fields moved | Status |
|----|-------|--------------|--------|
| 1 | `IsolationPolicy` | `enforce_isolation`, `execution_root`, `session_isolation`, `allowed_paths`, `dal_level` | ✅ `4e23171b` |
| 2 | `PlanContext` | `plan`, `decomposition` | ✅ |
| 3 | `RunHandle` + `AnalysisContext` + `ModelAccess` | `run_id`, `pipeline_runner`, `task_id`, `analyzer_factory`, `parsers`, `llm`, `config`, `llm_router` | ✅ |
| 4 | `GraphContext` | `topology`, `stale_nodes`, `workspace_roots`, `api_contract_paths` | ✅ |
| 5 | Dead-field cleanup + `model_post_init` split + `GuidanceContent` | deletes `env_vars`, `pipeline_name`; RELOCATES `step_records` | ✅ |

Field-count ledger (NFR-7): 32 today → 32−5+1 = 28 (CB1) → 27 (CB2) → 22 (CB3) → 19 (CB4) → 16 (CB5). ✅ ≤16.

---

## Commit Boundary 1 — `IsolationPolicy`

### Scope discovered during task planning (beyond the plan's own file list)

The impl plan's Commit-1 file table names `base.py`, `runner_utils.py`, `core/flow/interfaces/cli.py`,
`runner.py`, `validation.py`, `bash_action.py`. Grepping every real call site found **three more**
that the plan's table does not name. All three are mechanical consequences of the same move, not new
design decisions — recorded here so the diff is not a surprise at review:

1. **`resolve_should_isolate` (`runner_utils.py:20-32`)** reads `getattr(context, "enforce_isolation", False)`.
   Its docstring and its 19 direct unit tests (`test_isolation_gate.py`) make the *defensive* read a
   documented contract: `context` may be `None` or a partially-populated object and must never raise.
   The read moves to the nested path but the defensive contract is **preserved exactly**:
   `bool(getattr(getattr(context, "isolation", None), "enforce_isolation", False))`. Every one of the
   19 tests keeps its exact assertion; only the `SimpleNamespace` shape changes to match the new path.
   This is NOT a silent-failure hole in the sense of NFR-6 — `resolve_should_isolate` takes `Any`, is
   duck-typed by design, and its "missing attribute ⇒ host mode" fallback is the pre-existing,
   deliberately-tested behavior. Changing it to fail loudly would be a behavior change outside SF-02.
2. **`test_run_context_session_fields.py`** (6 tests) — not named in D-4's test inventory, but every
   one of its tests constructs or asserts on `allowed_paths`/`session_isolation`. Migrated in place.
3. **The two defensive `getattr` reads inside `runner_utils` itself** (`session_isolation` at :162,
   `dal_level` at :121, `allowed_paths` at :398) operate on a real `RunContext`, not a duck type.
   These become **direct attribute access** (`context.isolation.session_isolation`) — per NFR-6 a
   missed migration here MUST fail loudly, and a `getattr` default would be exactly the silent-`None`
   the design forbids. Behavior is identical for a real `RunContext` (the attribute always exists).
4. **`tests/unit/core/flow/engine/test_runner_handover.py::MockContext`** (RED-1.1) — a hand-rolled
   duck type (not a `RunContext`) whose `dal_level = "DAL_A"` exists *specifically* to make
   `runner.py:91`'s `getattr(..., "dal_level", None) is None` False so the `DALResolver` block is
   skipped. After T1.3 it has no `isolation` attribute → `AttributeError` inside
   `PipelineRunner.__init__` → **every test in that file breaks**. Migrated in T1.3.
5. **Frozen does NOT freeze `allowed_paths`'s contents** (RED-1.6) — empirically verified:
   `iso.allowed_paths.append("x")` on a `frozen=True` model succeeds (frozen blocks attribute
   *reassignment*, not mutation of a mutable field's value). AD-8 therefore closes the reassignment
   bug class, not the in-place-list-mutation one. No live exposure: nothing in `src/` appends to
   `allowed_paths` (verified — only whole-list assignment at `runner_utils.py:96`). Recorded so a
   future reader does not over-trust `frozen=True`; the per-instance-independence test is kept.

### Empirically verified before writing any code (`.tmp/rb_check.py`)

`copy.copy(ctx)` shares the sub-model instance (`c.isolation is o.isolation` → True); reassigning
`c.isolation = c.isolation.model_copy(update={...})` leaves the original's value untouched and makes
the instances distinct; frozen mutation raises `ValidationError`; an old flat kwarg raises
`ValidationError`; an old flat attribute read raises `AttributeError`. Every mechanism CB1 depends on
is confirmed, not assumed.

### T1.0 — Blast-radius reconnaissance (RED-2.4)

`extra="forbid"` makes `RunContext` reject *any* unknown kwarg, not only the 5 being moved — 86 test
files construct `RunContext(`, and a pre-existing typo'd or obsolete kwarg that Pydantic silently
dropped under the default `extra="ignore"` becomes a hard `ValidationError`. That is the intended
effect of FR-12, but it is unbudgeted discovery. Immediately after T1.1's green, run
`python -m pytest tests/unit/core/flow tests/integration/core/flow -x --tb=line -q 2>&1 | tail -40`
purely to **enumerate** the full failure set before migrating file-by-file. Record anything that is
NOT one of the 5 moved fields here — an unknown-kwarg failure is a real pre-existing defect this
commit surfaces, and per the standing rule inherited failures get fixed, not deferred.

**RESULT (executed).** Baseline before any change: **1189 passed, 0 failed** — no inherited failures
in scope, so every subsequent failure is attributable to this commit. After T1.1's green:
**243 failed, 959 passed**, and every failure classifies into one of the 5 moved fields:

| count | signature |
|---|---|
| 175 | `ValueError: "RunContext" object has no field "dal_level"` |
| 19 | `ValueError: ... no field "session_isolation"` |
| 19 | `AttributeError: ... no attribute 'session_isolation'` |
| 9 | `AttributeError: ... no attribute 'enforce_isolation'` |
| 5 + 4 | `execution_root` (read + assign) |
| 2 | `AttributeError: ... no attribute 'allowed_paths'` |
| 8 | `ValidationError for RunContext` (old flat kwarg at a construction site) |

**RED-2.4's feared discovery did not materialise**: zero failures from a pre-existing typo'd or
obsolete kwarg — `extra="forbid"` surfaced no latent defect. Recorded as a cleared risk, not a
skipped check.

**The 243 is not 243 problems.** 175 of them — 72% — are one unmigrated production line
(`runner.py:98`, `self._context.dal_level = ...`), which raises inside `PipelineRunner.__init__` and
therefore takes down every test that constructs a runner. Migrating T1.3 collapses the bulk of the
list. This is exactly why the enumeration runs before the file-by-file migration: the naive reading
("243 tests need editing") is off by an order of magnitude.

### T1.1 — `IsolationPolicy` sub-model + `extra="forbid"` on `RunContext`

- **Red**: extend `tests/unit/core/flow/handlers/test_base.py` with `TestIsolationPolicy`:
  1. *[Happy]* `IsolationPolicy()` defaults match today's flat defaults exactly
     (`enforce_isolation is False`, `execution_root is None`, `session_isolation is False`,
     `allowed_paths == []`, `dal_level is None`); `RunContext(project_path=…, spec_path=…)` gets a
     default `isolation` instance without passing one.
  2. *[Boundary]* `allowed_paths`'s `default_factory` list is independent per `IsolationPolicy`
     instance (the guarantee `test_run_context_session_fields.py::test_allowed_paths_is_independent_per_instance`
     currently makes about the flat field).
  3. *[Boundary]* `.model_copy(update={"execution_root": p})` returns a NEW instance; the original's
     `execution_root` is untouched (the mechanism AD-8/NFR-8 depends on).
  4. *[Hostile]* direct mutation `ctx.isolation.execution_root = Path("x")` raises `ValidationError`
     (frozen, AD-8 — the RED-2.1 bug class).
  5. *[Hostile]* `IsolationPolicy(bogus=1)` and `RunContext(project_path=…, spec_path=…, bogus=1)`
     both raise `ValidationError` (FR-12 `extra="forbid"`).
  6. *[Hostile]* wrong types still rejected at the new path: `IsolationPolicy(session_isolation="yes-please")`,
     `IsolationPolicy(allowed_paths="src/foo.py")` → `ValidationError` (preserves the two hostile-input
     tests `test_run_context_session_fields.py` has today).
  7. *[Hostile]* the old flat path is GONE, not shadowed: `RunContext(…, enforce_isolation=True)`
     raises `ValidationError` and `ctx.enforce_isolation` raises `AttributeError` (NFR-6, both halves).
  Run — fails (`IsolationPolicy` does not exist).
- **Green**: in `core/flow/handlers/base.py` add `IsolationPolicy(BaseModel)` with
  `model_config = ConfigDict(frozen=True, extra="forbid")` and the 5 fields at their exact current
  defaults (D-3). Add `RunContext.isolation: IsolationPolicy = Field(default_factory=IsolationPolicy)`.
  Delete the 5 flat fields. Add `extra="forbid"` to `RunContext.model_config` (keeping its existing
  `arbitrary_types_allowed=True` untouched, per RED-1.2).
- **Sequencing note (RED-1.4)**: T1.1's green leaves the rest of `src/` broken by design
  (`AttributeError`/`ValidationError` at every unmigrated site) — that is the loud failure NFR-6 asks
  for, and T1.2–T1.5 close it. **There is therefore no honest suite-wide green until T1.5 completes.**
  Verify each intermediate task with its own targeted command only
  (`python -m pytest tests/unit/core/flow/handlers/test_base.py -v`), and do not read the broken
  suite in between as a regression. The commit boundary is the atomic unit, not the individual task.

### T1.2 — `runner_utils.py` migration (the NFR-8 core)

- **Red**: `tests/integration/core/flow/engine/test_runner_sandbox.py::test_execute_in_sandbox_rebinds_execution_root`
  already asserts the exact NFR-8 property (isolated copy's `execution_root` set, ORIGINAL's still
  `None`) through a real `execute_in_sandbox` call. Update it to the nested path and confirm it FAILS
  first against the T1.1 tree.
  **Anti-vacuity guard (RED-1.3)**: as written, that red is weak — the test fails with
  `AttributeError` because the *field* doesn't exist yet, and goes green the moment the field exists,
  proving nothing about instance independence. Add two structural assertions that only pass if the
  `model_copy` discipline is actually followed:
  1. `seen["isolation_obj"] is not context.isolation` — the handler received a DIFFERENT
     `IsolationPolicy` instance than the original context holds (a shared instance is the RED-1.3 bug).
  2. `context.isolation.execution_root is None` after the call — the original is untouched.
  Add the *[Boundary]* case at 0/1/N `allowed_paths` entries surviving the isolated copy.
- **Green**: migrate all 5 fields' reads/writes in `runner_utils.py`:
  - `resolve_should_isolate` → nested defensive read (see Scope note 1).
  - `apply_session_policy` (:91, :95, :96) → `context.isolation = context.isolation.model_copy(update={…})`.
    **RED-1.5 — mandatory shape**: the on-path MUST be ONE `model_copy` carrying BOTH
    `session_isolation=True` and `allowed_paths=allowed`, issued AFTER `allowed` is computed. Two
    sequential `model_copy` calls would reintroduce exactly the "session on, allow-list empty" window
    that C2's no-half-apply guarantee exists to prevent — the same bug in a new shape. Collapsing to
    one write strengthens C2; splitting it silently repeals it.
  - `_dal_requires_isolation` (:121, :125) → `context.isolation.dal_level` read + `model_copy` cache write.
  - `execute_run` (:162, :189, :191, :213) → nested reads; the isolated copy's `execution_root` +
    `enforce_isolation` set via ONE `model_copy(update={…})` on the copy's `isolation` attribute.
  - `execute_in_sandbox` (:383, :398) → same `model_copy` pattern for `execution_root`; nested
    `allowed_paths` read.
- **Refactor**: verify no `getattr(context, "<old flat name>", …)` survives anywhere (grep).

### T1.3 — `runner.py` DAL injection

- **Red**: `tests/integration/core/flow/engine/test_runner_dal_injection.py` (3 tests) asserts
  `context.dal_level`. Update to `context.isolation.dal_level`; run — fails.
  **Plus (RED-1.1)**: `tests/unit/core/flow/engine/test_runner_handover.py::MockContext` — give the
  duck type an `isolation` stand-in (`SimpleNamespace(dal_level="DAL_A")` or a real `IsolationPolicy`)
  so `PipelineRunner.__init__` still skips the resolver. Run the whole file: it must go from
  all-erroring back to all-passing. This file is NOT in the impl plan's Commit-1 table — it was found
  by grepping for duck-typed context stand-ins, not by trusting the table.
- **Green**: `runner.py:91` `getattr(self._context, "dal_level", None)` → `self._context.isolation.dal_level`;
  `:98` assignment → `self._context.isolation = self._context.isolation.model_copy(update={"dal_level": …})`.

### T1.4 — Handler read sites + CLI composition root

- **Red**: update `test_bash_action_handler.py` (3 tests), `test_validate_tests_handler.py` (3 tests),
  `test_flow_cli_pipelines.py` (3 assertions), `test_cli_config_integration.py`,
  `test_cli_implement_isolation.py`, `test_session_policy.py`, `test_session_isolation.py`,
  `test_session_reconcile.py`, `test_session_policy_fullchain.py` to the nested path. Run — fails.
- **Green**: `bash_action.py:74`, `validation.py:469` → `context.isolation.execution_root`.
  `core/flow/interfaces/cli.py:319` and `:524` → `context.isolation = context.isolation.model_copy(update={"enforce_isolation": …})`.

### T1.5 — Remaining test-suite + e2e migration

- **Red/Green** (mechanical): `test_isolation_gate.py` (19 tests, `SimpleNamespace` reshape),
  `test_run_context_session_fields.py` (6 tests), `test_base.py::test_run_context_isolation_fields_default`,
  `tests/e2e/sandbox/test_c_exec_06_session_isolation_e2e.py`, `test_int_us_03_isolation_e2e.py`,
  `test_int_us_09_isolation_e2e.py`. Every post-construction `ctx.<field> = v` becomes
  `ctx.isolation = ctx.isolation.model_copy(update={…})`.
- **RED-1.8 — consecutive assignments must collapse, not chain-off-stale**: several call sites set two
  fields back to back (e.g. `test_c_exec_06_session_isolation_e2e.py:130-131` sets `session_isolation`
  then `allowed_paths`). Each pair becomes ONE `model_copy` with both keys. Translating them as two
  independent `model_copy` calls both derived from the *original* `ctx.isolation` silently discards
  the first write — a green-looking test that no longer tests what its name says.
- **RED-1.2 — `test_isolation_gate.py` is NOT a pure reshape.** The old suite had exactly one
  "attribute absent ⇒ host mode" case (`test_context_missing_enforce_isolation_defaults_host`). At the
  nested path that single case splits into **three structurally distinct absence shapes**, and a
  mechanical reshape covers only the third — dropping coverage while staying green:
  1. `SimpleNamespace()` — no `isolation` attribute at all → host.
  2. `SimpleNamespace(isolation=None)` — attribute present but `None` → host (newly reachable for a
     duck type; `getattr(None, "enforce_isolation", False)` must be the thing that saves it).
  3. `SimpleNamespace(isolation=SimpleNamespace())` — sub-object present, field absent → host.
  All three get their own test. **Plus** the more valuable half (RED-2.3): assert in `test_base.py`
  that `RunContext(project_path=…, spec_path=…, isolation=None)` raises `ValidationError` — proving
  shape 2 is unreachable for a real `RunContext`, so the duck-type tolerance is a defensive
  belt-and-braces rather than a live production path.

### T1.6 — Update the dev guides that document the flat path (RED-2.1)

Two **live** guides state the old contract as the way to write new code — a new handler author
following them today would write `context.execution_root` and get an `AttributeError`:
- `docs/dev_guides/pipeline_engine_guide.md:180, 183, 190`
- `docs/dev_guides/subprocess_execution.md:94, 96`

Both updated to `context.isolation.execution_root` / `RunContext.isolation.enforce_isolation` in this
commit — not deferred to the pre-commit skill's documentation phase.

**Deliberately NOT touched**: `docs/roadmap/features/topic_06_sandbox/C-EXEC-06/*` (delivered story —
finished-stories-immutable; those docs are a record of what was built then, not a live contract) and
`docs/roadmap/features/topic_07_technical_debt/TECH-013/TECH-013_design.md` (unstarted ticket; it
carries its own line-number research that will be re-done when TECH-013 starts).
- **Out of scope, verified**: `dal_level=` kwargs in `assurance/validation/interfaces/cli.py:273`,
  `validation_hydrator.py:219`, `api/v1/validation.py:78` are `execute_validation_flow` **function
  parameters**, not `RunContext` fields — confirmed by reading each. `allowed_paths`/`dal_level` in
  `sandbox/git/core/worktree_ops.py` and `sandbox/qa_runner/core/atom.py` are **dict** keys on the
  atom-intent payload, a different object entirely. None of these move.

### Commit-1 gate
`python scripts/tests.py cb TECH-006 --kind refactor` → pre-commit skill (all 7 phases) → **HITL stop**.
Expect the refactor-safety gate to flag construction-site value-wrapping (impl plan RED-2.1, accepted
risk). Resolve it for real when it fires — extend the gate or surface for human review; do NOT
reclassify `--kind` to dodge it.

---

## Commit Boundary 2 — `PlanContext`  🟡 in progress
Per impl plan Commit 2. Tasks detailed at the start of CB2 (after CB1 is committed).
Writers: `hydration.py` (set-on-success + clear-on-`FAILED`/`ERROR`, → `model_copy`, FR-10/AD-8).
Readers: `generation.py`, `decompose.py`. New `TestPlanContext` in `test_base.py`.

## Commit Boundary 3 — `RunHandle` + `AnalysisContext` + `ModelAccess`  ⬜
Per impl plan Commit 3 — widest fan-out (9 handlers read `llm`/`config`; 5 CLI construction sites).
`model_post_init`'s parser injection moves onto `self.analysis`. Updates
`test_base.py::test_run_context_builds_project_metadata`, `::test_run_context_graceful_degradation`,
`test_base_analyzer_factory.py`.

## Commit Boundary 4 — `GraphContext`  ⬜
Per impl plan Commit 4. The one non-rename change: `generation.py`'s
`context.api_contract_paths.append(...)` becomes read-modify-`model_copy`-write. D-5 docstring.

## Commit Boundary 5 — Dead fields (FR-8) + `model_post_init` split (FR-9)  ⬜
Per impl plan Commit 5. Deletes `env_vars`/`step_records`/`pipeline_name`; `gates.py:110` and
`runner_utils.py:359,384` fallbacks become literals; `test_base.py::test_run_context_env_vars`
deliberately removed (its entire subject is deleted). New `TestModelPostInitExtraction`.
Final NFR-7 assertion (`RunContext` top-level attribute count ≤16) lands here.

---
# Red/Blue Team Review Report — SF-02 Task Breakdown (Commit Boundary 1)

## Summary
- **Target**: this task breakdown (CB1 in detail). The design and impl plan were already Red/Blue
  reviewed and APPROVED — their decisions (frozen sub-models, `extra="forbid"`, per-group-atomic
  commits) were explicitly out of scope and not re-litigated.
- **Cycles**: 2
- **Findings**: 6 (Cycle 1) + 3 (Cycle 2) = 9
- **Critical/High fixes applied**: 2 HIGH, both by finding real call sites the impl plan's own file
  table does not name.

## Corrections Made
- **RED-1.1 (HIGH)** — `test_runner_handover.py::MockContext` is a hand-rolled duck type, not a
  `RunContext`, and sets `dal_level = "DAL_A"` *specifically* to make `runner.py:91`'s
  `getattr(..., "dal_level", None) is None` False so the `DALResolver` block is skipped. After T1.3
  it has no `isolation` attribute → `AttributeError` inside `PipelineRunner.__init__` → every test
  in the file breaks. Not in the impl plan's Commit-1 table (that table lists production files;
  duck-typed test stand-ins are invisible to a field grep). Added to T1.3.
- **RED-1.2 (HIGH)** — `test_isolation_gate.py`'s reshape looked mechanical but is a coverage
  regression in disguise: the one existing "attribute absent ⇒ host" case splits into three
  structurally distinct absence shapes at the nested path (`isolation` missing / `isolation=None` /
  field missing on the sub-object). A mechanical reshape covers only the third and stays green.
  T1.5 now requires all three, plus a `RunContext(isolation=None)` → `ValidationError` assertion.
- **RED-1.3 (MEDIUM)** — T1.2's red was weak by construction: updating the NFR-8 test to the nested
  path makes it fail with `AttributeError` (field missing), and it goes green the instant the field
  exists — proving nothing about instance independence. Added two structural assertions that only
  pass if the `model_copy` discipline is genuinely followed.
- **RED-1.4 (MEDIUM)** — the task list implied per-task greens were achievable. They are not: T1.1's
  green intentionally breaks every unmigrated site, so no honest suite-wide green exists until T1.5.
  Made explicit, with the per-task targeted command, so a broken intermediate suite is not misread.
- **RED-1.5 (MEDIUM)** — `apply_session_policy`'s two sequential writes collapsing into `model_copy`
  is only safe as ONE call carrying both keys. Two sequential `model_copy` calls would reintroduce
  the exact "session on, allow-list empty" window C2's no-half-apply guarantee prevents. Made a
  mandatory shape, not an incidental one.
- **RED-1.6 (MEDIUM)** — verified empirically that `frozen=True` does NOT prevent in-place mutation
  of a mutable field's contents (`iso.allowed_paths.append("x")` succeeds). AD-8 closes the
  reassignment bug class only. No live exposure (nothing in `src/` appends to `allowed_paths`), but
  recorded so a future reader does not over-trust `frozen=True`.
- **RED-2.1 (MEDIUM)** — two **live** dev guides document the flat path as the contract for writing
  new handlers (`pipeline_engine_guide.md:180,183,190`, `subprocess_execution.md:94,96`). Left
  stale, the next handler author follows them into an `AttributeError`. Added T1.6, in this commit
  rather than deferred to the pre-commit documentation phase. Delivered-story docs
  (`topic_06_sandbox/C-EXEC-06/*`) deliberately excluded — finished-stories-immutable.
- **RED-2.4 (MEDIUM)** — `extra="forbid"` rejects *any* unknown kwarg, not just the 5 moved fields,
  across 86 `RunContext(`-constructing test files. A pre-existing typo'd kwarg silently dropped
  today becomes a hard failure — intended (FR-12), but unbudgeted. Added T1.0: enumerate the whole
  failure set immediately after T1.1's green, before migrating file-by-file.

## Cleared / Verified (not defects)
- **Design RED-1.4 re-verified, and it holds** — the design cleared "nothing serializes `RunContext`
  as a whole" by grepping `src/` only. Re-ran it across `tests/` too: the three
  `ctx.model_dump_json()` hits (`test_handover.py:371,408`, `test_memory_integration.py:562`) are on
  **`HandoverContext`**, a different model — `handover.py` builds a small explicit DTO and never
  serializes the run context. The only whole-`RunContext` `model_dump()` anywhere is
  `test_base.py:70`, which CB5 deletes along with the fields it inspects. Clearance stands.
- **`RunContext(**kwargs)` dynamic construction** — re-grepped `src/` AND `tests/`: zero hits.
  `extra="forbid"` is safe to add.
- **`sandbox/security.py`, `api/v1/pipelines.py`** — read/construct only fields outside CB1
  (`workspace_roots`/`api_contract_paths` → CB4; the API passes just `project_path`/`spec_path`/
  `output_dir`). No CB1 change.
- **`dal_level=` at `assurance/validation/interfaces/cli.py:273`, `validation_hydrator.py:219`,
  `api/v1/validation.py:78`** — read each: they are `execute_validation_flow` **function
  parameters**, not `RunContext` fields. `allowed_paths`/`dal_level` in `sandbox/git/core/
  worktree_ops.py` and `sandbox/qa_runner/core/atom.py` are **dict** keys on an atom-intent payload.
  None move. (Named explicitly because a naive field-name grep flags all five as call sites.)
- **`test_runner_gates.py::MockContext`** — exercises `inject_feedback` only; `feedback` stays flat.

## Accepted Risks
- **RED-2.3 (MEDIUM, accepted with a refinement)**: testing the `isolation=None` duck-type shape is
  arguably YAGNI, since Pydantic makes it unreachable for a real `RunContext` (the field is typed
  `IsolationPolicy`, not `| None`). Accepted and kept: `resolve_should_isolate` takes `context: Any`
  with a documented never-raise contract and its entire existing test class is built on
  `SimpleNamespace` stand-ins, so the case costs one line and guards the contract as written. The
  refinement is the more valuable half — asserting `RunContext(isolation=None)` raises
  `ValidationError`, which proves the shape is unreachable in production.
- **Impl plan RED-2.1 (carried forward, unresolved by design)**: the refactor-safety gate cannot
  classify construction-site value-wrapping (`RunContext(enforce_isolation=X)` →
  `RunContext(isolation=IsolationPolicy(enforce_isolation=X))`) as a safe rename. Resolved for real
  when the gate fires at the CB1 commit gate — by extending the gate or surfacing for human review,
  never by reclassifying `--kind` to dodge it.

**Cycle 2** produced 0 CRITICAL, 0 HIGH, 3 MEDIUM — below every continuation threshold. Review
complete at the 2-cycle minimum.

*(End of Red/Blue Team Review Report)*

---
# CB1 Execution Record (T1.0 – T1.6)

## Outcome
`RunContext`: 33 → 29 counted attributes. Flow scope 1189 → **1206 passed, 0 failed** (+17 tests).
Full suite before the final re-verify: 6157 passed, 1 failed — that one failure being the
god-object canary described below, which is a witness this SF is meant to retire.

## Things found during execution that the plan did not predict

1. **Three kwargs that were never `RunContext` fields.** `workspace_dir`
   (`test_runner_profiles.py`, since `e2ac7e6e`), `test_path` and `code_path`
   (`test_flow_metadata_injection.py`, since `3f550e9c`). Pydantic's default `extra="ignore"`
   discarded all three silently for months. FR-12's `extra="forbid"` surfaced them. Verified
   nothing in `src/` reads any of them, then removed the kwargs — rather than inventing fields to
   match. This is RED-2.4's predicted risk actually materialising, having been (wrongly) recorded
   as cleared after the first enumeration pass missed them inside the `ValidationError` bucket.

2. **A canary test asserting `RunContext` is STILL a god object.**
   `test_check_class_health.py::test_the_real_run_context_is_still_a_god_object` asserted
   `len(attributes) > 30` — written deliberately to witness that "TECH-006 set out to cut it from
   23 fields; it grew instead, with every gate green". SF-02 is the work that repays that debt, so
   the witness was **inverted into a ratchet**, not relaxed: an exact expected count per commit
   boundary (`33 → 29 → 28 → 23 → 20 → 17`), plus a test asserting the class-health gate still
   blocks until CB5, plus one asserting the newly-extracted `IsolationPolicy` is not itself
   oversized. The replacement is strictly stronger than `> 30`: adding a field fails, and so does a
   boundary that silently fails to delete the flat fields it claimed to.

3. **`runner.py` crossed its RED file-size threshold — caused by this commit.** 600 → 602 (limit
   600). Fixed structurally, not by squeezing prose (the exact anti-pattern `TECH-020`'s entry
   warns about): the DAL resolve-and-cache block was extracted to `runner_utils.seed_dal_level`,
   beside the isolation policy it feeds, collapsing a real duplication with
   `_dal_requires_isolation`, which carried its own copy of the same rule. `runner.py` now **593** —
   7 lines of headroom returned to `TECH-020` rather than consumed. `runner_utils.py` was trimmed
   back under its own 450-line warning.

4. **`resolve_should_isolate`'s defensive contract splits three ways** (RED-1.2, predicted) and
   **`test_runner_handover.py::MockContext`** breaks at `PipelineRunner.__init__` (RED-1.1,
   predicted). Both confirmed real during execution.

## Pre-existing, verified NOT caused by this commit
- Cognitive complexity `_execute_run 19`, `resume 25`, `get_run_status 16` — identical numbers at
  `HEAD` (measured against `git show HEAD:` copies, not assumed). Untouched by this commit.
- `check_class_health` BLOCKS on `base.py` both before (33 attributes) and after (29). The finding
  is pre-existing and improving; it clears at CB5 — see the open question below.

## OPEN — must be resolved before CB5 can close
**NFR-7's target does not clear the project's own god-object gate.** NFR-7 says `RunContext` drops
to "≤16 top-level attributes"; `check_class_health.MAX_ATTRIBUTES` is **15**, and the analyser also
counts `model_config`, making the CB5 endpoint **17**. So even a fully successful SF-02 leaves
`base.py` blocking the class-health gate by 2. Options are (a) push further than the design's
grouping, (b) raise/《exempt》the threshold with justification, or (c) accept and file a follow-up.
Not decided here — flagged now so CB5 does not discover it at the finish line.

## Refactor-safety gate (impl plan RED-2.1 — fired, as predicted)
`python scripts/tests.py cb TECH-006 --kind refactor` → tiers pass (unit ok, integration ok), then
**BLOCKED: a refactor modified 16 test file(s)**. The gate cleared 6 of the 22 changed test files
and blocked 16.

Not dodged by reclassifying `--kind` (the standing instruction), and not "fixed" by extending the
gate, because an extension would not honestly cover this diff: the gate infers *one-token
substitutions*, whereas this migration is an *attribute-path deepening* (`X.field` →
`X.group.field`) that changes token-list length, plus construction-site value-wrapping, plus
genuinely new tests, plus one deliberately inverted assertion. No inference rule should
auto-clear that last one.

**Evidence prepared for the human review instead** — of **96 removed assertions, 94 have an exact
nested-path counterpart** among the 123 added. The 2 outliers:
- `assert resolve_should_isolate(None, SimpleNamespace(enforce_isolation=True)) is True` — intact,
  merely reflowed by `ruff format` (verified by reading it).
- `assert len(run_context.attributes) > 30` — the deliberate canary inversion in item 2 above.

So exactly ONE assertion changed meaning in this commit, deliberately and with its reasoning
recorded at the site. That is the finding the gate exists to surface, and it is the one thing a
reviewer needs to look at.


---
# CB2 Execution Record — `PlanContext`

`RunContext`: 29 → **28** counted attributes. Flow scope **1215 passed, 0 failed** (+9 tests).

`plan` and `decomposition` moved into a frozen `PlanContext`. INT-US-21 AD-1's rule — that these
are two DISTINCT concepts that must never be reconflated — was previously a comment above the two
fields; it is now carried by the sub-model's own docstring AND pinned by a test asserting that
setting one leaves the other untouched, plus one asserting a `model_copy` clear of one field does
not reset its sibling (the exact shape `hydration.py`'s clear-on-FAILED/ERROR takes under AD-8).

## Found during execution
**mypy caught a narrowing loss that the plan did not anticipate.** `context.decomposition =
json.dumps(...)` used to narrow the field to `str` for the `len(...)` in the very next log call.
Routing the write through `model_copy` erases that narrowing (the field is declared `str | None`),
so `mypy src/` failed on `len()`. Fixed by binding the serialised JSON to a local and using it for
both the update and the log — which is clearer than the original anyway. Worth carrying into CB3-5:
**every `model_copy` conversion is a potential narrowing regression at the following read**, and
mypy is the only gate that catches it (the tests all passed).

## Verification
- Assertion-integrity audit (same method as CB1): 73 removed assertions, 82 added. Four had no
  literal counterpart; all four verified by reading them — three were reflowed onto multiple lines
  by `ruff format`, and the fourth is the class-health sub-model test deliberately parametrised to
  cover `PlanContext` as well as `IsolationPolicy`, which is strictly broader than what it replaced.
  **Zero assertions weakened.**
- `ruff` / `mypy` (312 files) / `tach` clean. File sizes 0 errors — `generation.py`'s 589-line
  YELLOW is pre-existing (589 at HEAD, unchanged by this commit).
- NFR-7 ratchet updated 29 → 28; the class-health sub-model test parametrised over both sub-models
  so a later boundary cannot add an oversized one unnoticed.
- Refactor-safety gate blocks on 8 test files (down from CB1's 16 — this migration is more purely
  mechanical). Same disposition as CB1: surfaced for review, not dodged.


---
# CB3 Execution Record — `ModelAccess` + `RunHandle` + `AnalysisContext`

`RunContext`: 28 → **23** counted attributes (exactly the ledger's prediction). Flow scope
**1233 passed**; full suite **6191 passed, 0 failed**. The widest boundary of the five: 8 fields,
~106 production call sites, 45 test files.

## Verified before designing around it
`model` is a legal Pydantic v2 field name — the framework reserves the `model_` PREFIX, not the
bare word. Checked under `-W error::UserWarning` (no warning, `model_dump()` round-trips) rather
than assumed, because a namespace clash here would have surfaced far from its cause.

## Three defects the mechanical passes introduced, each caught by reading rather than by tests
1. **40+ `getattr(context, "run_id", ...)` string-based reads.** Post-move these would have
   silently returned the default — the exact silent-`None` class NFR-6 exists to forbid, and
   completely invisible to a regex over attribute access. All converted to direct nested reads so
   a miss fails loudly. This is the single biggest hazard in the whole SF and it was not in the
   plan; a later boundary should grep for `getattr(context, "<field>"` FIRST, before any rename.
2. **A regex turned a multi-line assignment into a frozen-model mutation**
   (`context.model.llm_router = ModelRouter(...)`, ×2 in `core/flow/interfaces/cli.py` and ×2 in
   tests), which raises at runtime. Caught because AD-8 made the sub-models frozen — the design
   decision doing precisely the job it was chosen for.
3. **A compound `getattr(context, "task_id", getattr(context, "run_id", "default"))` silently
   changed meaning** once the inner call was rewritten: `task_id` stopped resolving to the (always
   present, possibly `None`) attribute and started falling through to `run_id`. Exact prior
   semantics restored — `context.run.task_id`. CB5 still owns the documented widening to
   `task_id or run_id or "default"`; smuggling it in here would have hidden a behaviour change
   inside a relocation commit.

Also: four test files had to be reverted and redone after a merge helper wrongly combined
assignments across different functions, producing duplicate kwargs. Caught by ruff's
duplicate-keyword error, not by tests.

## `MagicMock(spec=RunContext)` exposes NO Pydantic v2 fields
Verified directly: `spec=RunContext` permits *setting* any attribute but *reading* none of the
model fields. So `ctx.run = ctx.run.model_copy(...)` fails at the read. Every spec'd-mock fixture
now holds REAL sub-model instances, which is both correct and more honest than a mocked stand-in.
Same fix for a bare `MagicMock()` fixture in `test_arbiter.py`, where `model_copy` returned another
MagicMock and the `AsyncMock` llm never actually landed.

## Verification
- Assertion-integrity audit: **38 removed, all 38 with an exact nested-path counterpart, zero
  outliers** — cleaner than CB1/CB2 because CB3 is a purer rename.
- One failure escaped the flow-scoped runs entirely and was caught only by the full suite:
  `tests/integration/engine/` (note: NOT `tests/integration/core/flow/`) uses a fixture named
  `mock_run_context`, which no var-name allowlist matched. Module-scoped greens are not evidence
  for a rename this wide.
- NFR-7 ratchet 28 → 23; the sub-model health test now parametrises over all five extracted models.

## Tooling fix made during this boundary (not part of SF-02's scope, but caused by it)
`CLAUDE.md`'s Test Commands prescribed a bare serial `python -m pytest`, and the system interpreter
has no `pytest-xdist` — so four full-suite runs were made at ~13 min each before this was noticed.
Measured on 16 cores: one module 12.5s serial vs 15.2s parallel (serial wins); `tests/unit` 5m02 vs
1m37; full suite ~13m vs 4m26. `CLAUDE.md` and `specweaver-dev/SKILL.md` now state the interpreter
and the crossover. (`scripts/tests.py` already passed `-n auto` — using it would have avoided this.)
Incidental discovery: `.claude/skills/` and `.agents/skills/` are **hard-linked** (same inode), not
merely kept in sync as an older working note claims; one edit updates both, and an editor that
replaces rather than truncates would silently break the link.


---
# CB4 Execution Record — `GraphContext`

`RunContext`: 22 → **19** counted attributes. Full suite **6206 passed, 0 failed**.

## CB3's lesson applied up front
Grepped for `getattr(context, "<field>", ...)` BEFORE renaming anything, per CB3's record. Found
two (`staleness.py:44`, `context_assembler.py:48`) that would otherwise have started silently
returning their defaults. Cost: one grep. In CB3 the same class of site was 40-odd and was only
caught by reading the diff.

## The append that had to stop being an append
`generation.py` did `context.api_contract_paths.append(...)` after a `None` guard. Frozen makes
that a rebuild-and-replace. Tested at 0, 1, N *and* unset starting points, because the unset and
empty cases are the ones where a careless rewrite silently drops the value.

## Two mock traps, both already seen in CB3
- `MagicMock(spec=RunContext)` fixtures needed a real `GraphContext`; six were seeded.
- `test_contract_handler.py` held a bare `MagicMock` whose `graph.model_copy()` returned another
  mock, so the test asserted against a mock rather than the list the handler built. Real object.

## The var-name gap bit twice
`mock_run_context` escaped the migration again — the same name that escaped CB3 and was caught
only by the full suite. A word-boundary match on `run_context` does not match inside
`mock_run_context`. Any future rename over this codebase should enumerate context variable names
from the fixtures first rather than assuming a list.

## Verification
- Assertion-integrity audit: 4 removed, all with exact nested-path counterparts, **zero outliers**.
- Ratchet 22 → 19; the sub-model health test now covers all six extracted models.
- One self-inflicted defect worth recording: the assignment rewriter swallowed a trailing `#`
  comment into a `model_copy(...)` call, producing invalid syntax. Ruff caught it immediately.
  Line-based rewriting must split trailing comments off before touching the expression.


---
# CB5 Execution Record — the step that finished the job

`RunContext`: 19 → **15**. `scripts/check_class_health.py` now reports
`handlers/base.py` as "all within limits" and exits 0 — the first time since that check existed.
Full suite **6216 passed, 0 failed**.

## FR-8's premise was wrong, and the three fields needed three different answers

The requirement said "delete `env_vars`, `step_records`, `pipeline_name` — confirmed zero
production readers". Asked the right question of each ("is this dead because it is not needed, or
because a feature was never finished?"), the answers diverged completely:

- **`env_vars` — not needed.** Born dead in `17ee01f5` (2026-04-12) with a written plan to inject
  it into spawned processes; that half was never built. `C-EXEC-02` later shipped an explicit
  per-step `env:` map that *deliberately refuses* this field so secrets cannot leak into
  `stdout`/`step_records`. Superseded by a better design → deleted as clutter.

- **`pipeline_name` — a BUG, not clutter.** Two real readers, no writer anywhere, so both always
  took their fallback. The consequence was not cosmetic: the RESERVE gate's resource key was
  `f"pipeline:{pipeline_target}"` with the target always `"default_pipeline"`, so **every pipeline
  in a project queued behind one shared lock** — global serialisation from a gate whose entire
  purpose was per-pipeline serialisation. Both readers now take the name from
  `PipelineRun.pipeline_name`, which is always populated and was already in scope at both sites.
  The original instruction (substitute the literal) would have cemented the defect and destroyed
  the evidence that a pipeline name ever belonged there.

  **A vacuous test had been hiding it.** `test_reserve_gate_acquires_lock` asserted
  `resource_id == "pipeline:test_pipe"` — and passed only because the test itself set
  `context.pipeline_name = "test_pipe"`. It proved a path production never took. Rewritten to
  assert against the pipeline definition with nothing seeded, plus a new
  `test_two_pipelines_reserve_different_resources` that would have caught this from the start.

- **`step_records` — not dead at all.** It is the delivered mechanism of `C-EXEC-02` FR-6/AD-4,
  with `test_downstream_step_reads_step_records` as its acceptance test. No *shipped handler*
  reads it — which is what the original research saw — but a completed story chose it as its
  state-propagation channel precisely because it needed no new plumbing. Deleting it would have
  withdrawn a delivered FR. Relocated to `RunHandle` (`context.run.step_records`): capability and
  tests intact, and `RunContext` still loses the top-level attribute.

## Reaching 15 needed two things the design never accounted for
NFR-7 said ≤16, a number derived from the grouping without ever being checked against the
project's own limit of 15. Closing the gap took the `model_config` metric fix (separate commit)
and `GuidanceContent` (AD-9), pairing `constitution`/`standards` — justified on AD-6's own
criterion, which simply had never been applied to that pair: all 7 construction sites set both,
on adjacent lines, and none sets one alone.

## Collateral
`test_planning_integration.py` crossed its 900-line limit (885 → 907) because of this work's
construction-site rewrites. A first attempt to compact them made it *worse* (914) — line-golfing
is the same anti-pattern as condensing comments to duck a size gate. Split instead at a real seam:
`TestDagOrchestratorIntegration` moved to `test_dag_orchestration_integration.py` (688 + 241).

## Still failing at the `cb` gate, all pre-existing and none in files touched here
`complexipy` and `cycles` report long-standing violations across `assurance/standards`,
`workspace/ast`, `graph/` and others — the debt already tracked as TECH-023/TECH-024. Verified
none of the reported functions live in any file this sub-feature changed.
