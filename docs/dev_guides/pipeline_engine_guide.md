# Flow Pipelines

Use when: you add a pipeline, a step handler, a router or a gate, or you need to know how the flow
engine isolates, persists or guards a run.

A pipeline is YAML: an ordered list of steps, each with an optional gate (did it pass?) and router
(where next?). `PipelineRunner` executes it, checkpoints every step, and can `resume(run_id)`.

Section numbers are cited from roadmap docs (§5, §7, §9, §11, §12). Keep them stable.

---

## 1. Pipelines are YAML (`pipelines/*.yaml`)

```yaml
name: "security_audit_flow"
steps:
  - name: generate_audit_plan
    action: plan
    target: code
    gate:
      type: auto
      condition: completed

  - name: review_security_issues
    action: review
    target: code
    gate:
      type: hitl
      on_fail: loop_back
      loop_target: generate_audit_plan
      max_retries: 3
```

- **`action` + `target`** select the handler.
- **`gate`** stops the `PipelineRunner`. `auto` passes when static validation passes. `hitl` parks the
  run until a human approves it (the approval is persisted in the state DB).

---

## 2. Handlers

The runner looks up `action` + `target` (e.g. `review` + `code`) in the `StepHandlerRegistry` and runs
that handler.

- **Location**: `src/specweaver/flow/_<domain>.py`

```python
from specweaver.core.flow.engine.models import StepResult

class ReviewCodeHandler:
    def execute(self, context: RunContext) -> StepResult:
        # Load the configuration bounds
        # Spin up LLM / Exec Tools 
        # Evaluate Logic
        return StepResult(status="pass", artifacts={"feedback": result.feedback})
```

Since moved (2026-09-25): handlers live in `src/specweaver/core/flow/handlers/<domain>.py`, the
registry in `core/flow/handlers/registry.py`, and the protocol is
`async def execute(self, step: PipelineStep, context: RunContext) -> StepResult` (`handlers/base.py`).
`StepResult` is in `core/flow/engine/state.py`.

After the handler returns, `StateStore` checkpoints the step, so an interrupted run can
`resume(run_id)`.

---

## 3. Single-step pipelines

A one-off CLI command (e.g. `sw standards scan`) still runs through the flow engine, as a pipeline of
one step. It gets the same persistence, telemetry and handler path as a full pipeline.

```python
# Reusable helper from flow/runner.py
from specweaver.core.flow.engine.runner import create_single_step

# Dynamic runtime generation
pipe = create_single_step(action="scan", target="standards")
runner.execute(pipe)
```

Since moved (2026-09-25): it is the classmethod `PipelineDefinition.create_single_step(name, action,
target, gate=None, params=None, description="")` in `core/flow/engine/models.py`.

---

## 4. DAL-driven rule thresholds

Validation thresholds depend on the target's DAL (Fractal Resolution Engine, `C-VAL-03`).
`ValidateSpecHandler` and `ValidateCodeHandler` find the target module's `context.yaml`, read
`.operational.dal_level`, and deep-merge that DAL's entry from the DAL matrix over the global
thresholds. Global settings are not overridden.

Sketch:

```python
# Extract the target architecture baseline
dal = dal_resolver.resolve(target.path) or context.db.get_default_dal()

# Map bounding thresholds locally and merge
if dal_settings := context.settings.dal_matrix.matrix.get(dal):
    from pydantic.utils import deep_update # equivalent
    resolved = deep_merge_dict(base_config, dal_settings.dict(exclude_unset=True))
    
apply_settings_to_pipeline(pipeline, ValidationSettings(**resolved))
```

Real functions: `deep_merge_dict` (`core/config/settings.py`), `apply_settings_to_pipeline`
(`assurance/validation/executor.py`).

---

## 5. Sub-pipelines (fan-out)

Since Feature 3.24 a step (e.g. a feature decomposer) can fan out into independent sub-pipelines.

1. **Lineage**: every `PipelineRun` has a `parent_run_id` in `pipeline_state.db`.
2. **Waves**: sub-pipelines are ordered by a `graphlib.TopologicalSorter`, not a bulk
   `asyncio.gather`. `TopologyGraph.impact_of` finds components whose `context.yaml` footprints
   overlap; those never run in the same wave. Non-overlapping ones run in parallel.
3. **Spawn**: each wave node runs its own `PipelineRunner` with the parent run's UUID as
   `parent_run_id`.
4. **Join**: the parent waits for the whole DAG, then folds all child outputs into one `StepResult`.

The SQLite records hold the full parent/child lineage.

> [!WARNING]
> **Orchestrating sub-components (Feature 3.24)**
> `fan_out()` lives in `OrchestrateComponentsHandler`. Changing its loop limits, error handling or
> `StepTarget.SPEC` validation sequence breaks DMZ assumptions. The engine parses `new_feature.yaml`
> so the L3 component validations always run.

> [!CAUTION]
> **Coverage assertion**
> `DecomposeFeatureHandler` requires `coverage_score >= 1.0` across the resulting components. A
> failing LLM result loops up to `max_retries` (3 strikes) and then ends `FAILED`, without asking a
> human. Under a HITL gate this differs — see §13.

---

## 6. Routers (conditional branching)

Since Feature 3.25. A **gate** decides pass/fail; a **router** decides where to go *after* a pass.

- **Operators only**: `eq`, `neq`, `lt`, `gt`, `in`, `contains`, `is_empty`, `not_empty`. No
  `eval()` — YAML must not execute code.
- **Loop bound (NFR-4)**: a router may jump backwards. All backward jumps count against
  `max_total_loops` (default `20`); exceeding it ends the run with `ERROR`.
- **Telemetry (FR-5)**: every jump emits `"step_routed"`, so a dashboard can replay the path.

Example — skip decomposition when the `Planner`'s output says `{"complexity": "trivial"}`:

```yaml
name: "adaptive_feature_flow"
max_total_loops: 20
steps:
  - name: plan_architectural_impact
    action: plan
    target: feature
    router:
      default_target: decompose_structure
      rules:
        # Fast-Track Condition: The previous step payload yielded `{"complexity": "trivial"}`
        - field: "complexity"
          operator: "eq"
          value: "trivial"
          target: execute_quick_fix

  - name: decompose_structure
    action: decompose
    target: feature
    # Standard heavy-lifting fallback...
  
  - name: execute_quick_fix
    action: generate 
    target: code
```

---

## 7. Worktree isolation

Untrusted steps can run in an ephemeral git worktree instead of the real project root. Two modes,
mutually exclusive at runtime:

| | Per-step (`D-EXEC-02`, `INT-US-09`) | Per-run / session (`C-EXEC-06`) |
|---|---|---|
| Scope | one step | the whole run |
| Code | `execute_in_sandbox` (`core/flow/engine/sandboxed_execution.py`) | `execute_run` (`core/flow/engine/session.py`) |
| Worktree / branch | `.worktrees/<task_id>` / `sf-<pipeline>-<task_id>` | `.worktrees/session-<run_id>` / `sf-session-<run_id>` |
| Rebinds | `output_dir` + `isolation.execution_root` | `project_path` + `execution_root`, `output_dir=None` |
| Reconcile | `worktree_sync`, then `strip_merge` after every step | `worktree_commit` + one `strip_merge` at run end |
| Reconcile failure | logged as a warning | fails the run |
| Enable | `use_worktree`, or `[sandbox] enforce_worktree_isolation` | `[sandbox] enforce_session_isolation`, or DAL auto-escalation |

Both modes: container-free (git only); **fail closed** — if `git worktree add` fails (e.g. not a git
repo) the run raises an actionable error with GitAtom's real message and no step runs on the real
root; caches are symlinked into the worktree; teardown runs in a `finally`.

Per-step isolation cannot run a multi-step loop such as `sw implement`'s generate → lint-fix →
run-tests: nothing is committed in the worktree, so the merge brings nothing back, and the next step
collides on the branch name (`TECH-012`). Use per-run mode for that.

### 7.1 Shared mechanics

- **Caches (FR-2)**: `setup_sandbox_caches` symlinks `.pytest_cache`, `__pycache__`, `node_modules`,
  `.gradle`, `target`, `build`, `.venv`, `venv` and `.specweaver` into the worktree, so nothing is
  rebuilt or copied.
- **Strip-merge (FR-4)**: `strip_merge` (`sandbox/git/core/worktree_ops.py`) runs
  `git merge --no-commit --no-ff <branch> -X ours`, then restores or deletes every changed file that
  is not in `allowed_paths` (exact repo-relative match). `README.md` and `docs/` are hard-blocked even
  when allow-listed. `doc_updates.md` always survives. A merge that fails (e.g. a dirty real working
  tree) is `git merge --abort`ed and reported with "commit or stash them first".
- **Teardown**: `_intent_worktree_teardown` runs `git worktree remove --force`; if that fails (Windows
  file locks, e.g. Defender), it retries `shutil.rmtree` with a 5-step backoff (0.05 → 0.75 s, under
  2 s total), then `git worktree prune`. Given a `branch`, it also deletes it (`branch -D`).

### 7.2 Per-step mode (`INT-US-09`, the US-9 zero-trust contract)

- **Enable one step**: `use_worktree: true` in the step YAML. The flag is tri-state `bool | None`:
  `True` forces isolation on, `False` forces it off, **`None` (default) defers to the policy**.
- **Enable by policy**: `[sandbox] enforce_worktree_isolation = true` in `specweaver.toml`. The
  composition root (`sw run`/`sw resume`) resolves it onto `RunContext.isolation.enforce_isolation`;
  the runner then isolates every step whose `use_worktree` is unset. Default off ⇒ byte-identical
  behavior. Container QA is a separate opt-in (`execution_mode`) and is **not** activated by this.
- **Execution boundary**: `execute_in_sandbox` sets `RunContext.isolation.execution_root` to the
  worktree. The two untrusted-execution handlers — `BashActionHandler` (`action: bash`) and
  `ValidateTestsHandler` (`run_tests`/pytest) — build their atom/`SubprocessExecutor` `cwd` from
  `context.isolation.execution_root or context.project_path`, so an LLM-authored script or test runs
  inside the worktree.
- **Static QA stays on the project root**: `lint_fix`/ruff, complexity and `tach` parse code but never
  execute it.
- **Allow-list**: per-step reads the same `allowed_paths`. With the session policy off it is empty, so
  per-step write-back is limited to `doc_updates.md`.

### 7.3 Per-run (session) mode (`C-EXEC-06`)

One worktree for the whole run, one authorized reconcile at the end. Design:
[`C-EXEC-06_design.md`](../roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_design.md).

**Enable** in `specweaver.toml`:

```toml
[sandbox]
enforce_session_isolation = true
session_allowed_paths = []   # empty = derive from the spec (below); non-empty = used verbatim
auto_isolate_min_dal = "DAL_B"
```

Lifecycle (`execute_run`, when `context.isolation.session_isolation` is set):

1. **Create**: tear down any stale same-named worktree + branch left by a hard crash, then
   `worktree_add` `.worktrees/session-<run_id>` on branch `sf-session-<run_id>`.
2. **Rebind**: the session workspace root — `project_path` and `execution_root` — points at the
   worktree; `output_dir=None`. **All** steps run there, so generated code persists across steps and
   `run_tests` loop-backs iterate in the same worktree. Static QA lints the same copy that will be
   reconciled. Per-step isolation is suppressed inside the span (`enforce_isolation=False`): per-run
   wins when both policies are on.
3. **Reconcile — only on `RunStatus.COMPLETED`**: `worktree_commit` (`git add -A` + commit on the
   session branch; a clean tree is a no-op), then **one** `strip_merge` that writes back **only**
   `context.isolation.allowed_paths` (plus the README/docs hard-block). Any commit or merge failure
   raises — never swallowed. This is the DAL-C authorization gate for what generated code reaches the
   user's repo. A failed or parked run does **not** reconcile.
4. **Teardown** in `finally`: worktree **and** branch, once.

**`allowed_paths`** — populated at the composition root by `apply_session_policy`
(`core/flow/engine/isolation.py`), **only when the session policy is on**:

- `[sandbox] session_allowed_paths` non-empty ⇒ used verbatim. **Empty ⇒ derive.**
- Derived = the pipeline's generation targets: `src/<stem>.py` + `tests/test_<stem>.py`, where
  `<stem> = spec_path.stem.replace("_spec","")` — byte-matched to `generation.py` (`.replace`, not
  `.removesuffix`).
- **NFR-2 guard**: with the policy off, `allowed_paths` stays empty, so per-step `strip_merge` is
  unaffected.
- No half-apply: the list is computed before either field changes, so a failure leaves the session
  off rather than "on with an empty allow-list".

**DAL auto-escalation (`INT-US-03` SF-03)**: `apply_session_policy` takes an opt-in
`dal_auto_escalate` flag. Only **`sw implement`** passes it today. When set and
`enforce_session_isolation` is off, session isolation turns on if the touched code's resolved DAL is
**at or above `[sandbox] auto_isolate_min_dal`** (default `DAL_B`; `"off"` disables). High-assurance
(DAL_A/B) generated code is sandboxed automatically; low-DAL projects stay on host mode.
`sw run`/`sw resume` do **not** opt in. **Q3 degrade**: if escalation wants isolation but the project
is not a git repo, it logs a warning and stays on host. An explicit `enforce_session_isolation=true`
still fails closed.

**v1 limits**:

- Non-parking spans only (AD-4): a HITL park inside a session raises, because the worktree cannot
  survive a resume. Pipelines that park (e.g. §13) need session isolation OFF.
- API composition roots do not resolve the policy yet (`TECH-013`).

---

## 8. JOIN barriers

Some steps must wait until every parallel worker of a fan-out has finished. `GateType.JOIN` is that
barrier (Feature 3.27, SF-3).

- **Configure**: `gate: {type: join}` on the step in the YAML iteration block.
- **Deferred**: when `OrchestrateComponentsHandler` pushes `new_feature.yaml` onto a DAG fan-out, it
  removes every step with a `join` gate. Those steps do not run in the async loop.
- **Wave N**: the removed steps are collected across all DAG nodes (`deferred_joins`). After
  `fan_out()` succeeds, they run as `Wave N` — a synchronous sub-pipeline in the same UUID state
  tree, after all file handles and locks are released.

Use case: five components generating docs over one API contract in parallel collide on file locks
(`SQLITE_BUSY`, overlapping text). Put the documentation step under a `join` gate: generation runs in
parallel, one synthesis wave writes the result.

---

## 9. Incremental bypass (topology crawler)

Feature 3.32. Skips QA on modules that did not change.

- **Graph**: `TopologyGraph.from_project()` computes Merkle-tree hashes over the source directories.
- **Stale nodes**: `ValidateTestsHandler` and `LintFixHandler` read `context.graph.stale_nodes`.
- **Pristine short-circuit**: a module not in the stale set is skipped. If `stale_nodes` is an empty
  list for a target, the handler skips `pytest`/`ruff` and returns `SUCCESS` at once.
- **Tombstones**: if a dependency was deleted, `TopologyGraph` flags the consumer itself as stale, so
  the failure surfaces.

Current state: `GraphContext.stale_nodes` (`core/flow/handlers/run_context.py`) is read but written
by nothing, so it is always `None` in production and the short-circuit never fires.

---

## 10. Vault Binding Shield (Option D)

NFR-2 of Feature 3.32c (process isolation, credential security).

- **Pre-flight (FR-1)**: `PipelineRunner.run()` and `PipelineRunner.resume()` call
  `verify_vault_security` (`core/flow/engine/security.py`) before any step. If
  `.specweaver/vault.env` exists, it asks `GitAtom` (`_intent_is_tracked`,
  `git ls-files --error-unmatch`) whether the file is tracked.
- **Boundary**: the engine never calls `subprocess.run` from configuration code; git runs only through
  `GitAtom`.
- **Abort**: if `vault.env` is tracked, the runner raises `RuntimeError` before any state write or
  push. No loop, no HITL gate: a tracked vault means plaintext credentials are in version control.

---

## 11. Handover persistence (`files_touched`)

Feature D-INTL-06 (Context Hydration & Handover Engine).

- **Implicit**: handlers never save handover state. `PipelineRunner` calls `_save_handover` in the
  `finally` blocks of `run()` and `resume()`, so it runs even on `KeyboardInterrupt`.
- **Never raises**: the aggregation sits in a `try...except Exception`. A SQLite, Pydantic or
  filesystem error logs a `WARNING` and the pipeline ends normally.
- **`files_touched`**: to feed the memory bank, return the key in `StepResult.output`:
  ```python
  return StepResult(
      status=StepStatus.PASSED,
      output={"files_touched": ["src/my_module/new_file.py", "docs/my_doc.md"]}
  )
  ```
  The engine deduplicates and truncates the list. Malformed values are ignored.

---

## 12. Script steps (`action: bash`)

Since C-EXEC-02. Runs a script from `.specweaver/scripts/` with no LLM and no handler code.
`action: bash` + `target: script` goes to `BashActionHandler`, a thin wrapper around `BashActionAtom`
(containment and security rules: `docs/dev_guides/subprocess_execution.md`).

```yaml
name: "lint_then_bash_check"
steps:
  - name: run_custom_check
    action: bash
    target: script
    params:
      script: check_licenses.sh   # bare filename, resolved inside .specweaver/scripts/
      args: ["--strict"]
      timeout_seconds: 120
    router:
      default_target: on_failure
      rules:
        - field: exit_code
          operator: eq
          value: 0
          target: on_success
```

### Trap: inputs must sit under `params:`

`script`, `args`, `working_dir`, `timeout_seconds`, `env` — all **must** be under `params:`.
`PipelineStep` silently ignores unknown top-level keys (`extra="ignore"`):

```yaml
- name: run_custom_check
  action: bash
  target: script
  script: check_licenses.sh   # WRONG — silently dropped, params ends up {}
```

This parses to `params={}` and fails at runtime with `BashActionAtom`'s
`"Missing 'script' in context."` — far from the real mistake.

`BashActionHandler` passes `step.params` through untouched. All validation (bare filename, path
containment, timeout ceiling, `PATH`-override rejection) is in `BashActionAtom.run()`. Load-time
`params` validation for all step types: `TECH-011`.

### Output shape

On success or failure, `StepResult.output` is `BashActionAtom`'s `exports` dict, verbatim:

```python
{
    "exit_code": 0,
    "stdout": "...",       # truncated to 1 MiB
    "stderr": "...",       # truncated to 1 MiB
    "duration_seconds": 0.42,
}
```

A nonzero `exit_code` is `StepStatus.FAILED`, not an exception. To branch on it instead of aborting,
add `gate: {on_fail: continue}`. `exit_code` is top-level, so rules use `field: exit_code` directly.

### `validate` output shape

`validate+spec` and `validate+code` return the same payload, built by one helper
(`handlers/validation.py::_validation_output`). `run_tests` does **not** — it returns the QA runner's
`passed`/`failed`/`total`, with no `rule_id`.

```python
{
    "results": [
        {
            "rule_id": "S01",
            "status": "fail",              # Status.value
            "message": "...",              # the rule's summary
            "findings": [                  # ALWAYS present, [] when the rule found nothing
                {
                    "message": "...",      # quotes spec content -- treat as untrusted
                    "line": 12,            # None when the rule cannot locate it
                    "severity": "error",   # Severity.value -- error | warning | info
                    "suggestion": "...",   # None when the rule has none
                },
            ],
        },
    ],
    "total": 12,
    "passed": 11,      # everything that is not FAIL -- WARN and SKIP count as passed
    "failed": 1,
}
```

`findings` was added by `INT-US-04` SF-01 CB-1 (FR-1); before, this path discarded every `Finding`
(line, severity, suggestion) that the REST API (`interfaces/api/v1/validation.py::_rule_response`)
already returned.

- **`findings` is never absent** — no `.get` fallback needed.
- **`severity` is a value, not an enum repr.** `StateStore.save_run` persists this payload through
  `json.dumps(..., default=str)`, which would write `"Severity.ERROR"` for a plain `Enum`. `Severity`
  is a `StrEnum` today; a unit test pins that, because changing it would silently reshape every
  persisted record.
- **Size**: about **170 bytes per finding**, plus ~15 bytes per rule for the empty list. Measured
  worst case: a 3.1 KB step record (CB-1 measurement in `INT-US-04_sf01_implementation_plan.md`).

**Queryable table** (`INT-US-04` SF-01 CB-2): `StateStore` also writes `flow_validation_results`
(`core/flow/engine/store.py`, schema version 3). Grain: **one row per finding**; a rule with no
findings gets one row with NULL finding columns. Append-only — a retried step adds rows with its
`attempt` number.

---

## 13. The `feature_decomposition` journey (`INT-US-21`)

`feature_decomposition.yaml` turns an epic-level feature spec into a DAG of DAL-rated component
specs. It is the reference **multi-session HITL journey** and the only bundled pipeline with two
human gates.

```bash
sw run feature_decomposition specs/onboarding_feature_spec.md   # explicit path
sw run feature_decomposition onboarding                         # bare name, same spec
```

A bare name resolves to `specs/<name>_feature_spec.md`. The suffix is one constant
(`FEATURE_SPEC_SUFFIX` in `core/flow/handlers/draft.py`) that the resolver **imports**.
`DraftFeatureHandler` errors on a spec path that does not match it, so a second literal would break
every drafting run.

### Three sessions

| Session | What happens | Ends |
|---|---|---|
| 1 | `draft_feature` — an existing spec takes the exists-skip path | **PARK** at the draft gate |
| 2 | resume = approval → `validate_feature` (feature battery) → `decompose` (one LLM call) | **PARK** at the review gate |
| 3 | resume = approval | **COMPLETED** |

Each park costs one `sw resume`. Resuming a gate-parked step that **passed** approves it and moves on
without re-running it; anything else re-executes. See User Handbook 4.

> [!CAUTION]
> **`PARKED` and `COMPLETED` both exit `0`.**
> `FAILED` is the only non-zero outcome (`1`); an interrupt exits `130`. A script or test that
> branches on this journey MUST read the persisted run status from the state store, never the exit
> code. `INT-US-02`'s end-to-end proof stayed green for months without passing its first gate for
> this reason.

### What reaches disk

- **`specs/<stem>_decomposition.yaml`** — the reviewed plan, with a `# sw-artifact:` uuid tag and a
  `generated_decomposition` lineage event. A re-run reuses the existing uuid.
- **`specs/<component>_spec.md`** — one stub per component, from
  `.specweaver/templates/component_spec.md` (built-in skeleton if the project was never scaffolded).
  **Never overwritten.** The step reports five disjoint buckets: `created`, `skipped` (spec already
  there), `rejected` (name failed validation), `failed` (write error), `collided` (name would target
  the feature spec itself).

> [!IMPORTANT]
> **Serialize with `model_dump(mode="json")`, never `model_dump()`.**
> `DecompositionPlan.components[].proposed_dal` is a required `DALLevel` enum; `ruamel` raises
> `RepresenterError` on an enum, so python-mode dump fails on 100% of real plans. `mode="json"` also
> makes the file byte-identical to the hydrated `context.decomposition`. Generalised by `TECH-016`.

### Coverage failures park; they do not loop

§5's `coverage_score >= 1.0` 3-strike loop is the **auto-gate** behaviour — what a custom pipeline
gets. Here the decompose gate is **HITL**, and a HITL gate parks whatever the step returned. A
low-coverage plan is a *failed* step that parks for a human. Resuming a failed gate-park is **not**
an approval: the step re-executes, costing a new LLM round. Measured, not inferred.

The same holds for `validate_feature`: a spec that fails the battery loops back to `draft_feature`,
which parks. **The retry budget survives the resume**: `LoopState.for_run` seeds `attempts` from the
persisted `StepRecord.attempt`, so a step that used one of three retries resumes with two.
Fixed 2026-08-12 (`TECH-033`); before, every resume granted a fresh 3-strike budget.

One boundary, by decision: resuming a step whose budget is **fully** spent gives it one final attempt
before the gate stops the run. Refusing would make a retry-exhausted run unresumable even after the
root cause is fixed.

### Host posture

> [!WARNING]
> **This journey requires `session_isolation` OFF.**
> `C-EXEC-06` v1 raises on any park inside a session worktree, by design (§7.3). A pipeline that
> parks twice cannot run under session isolation.

### Resuming

Resuming a **completed** run is refused; `PipelineRunner.resume()` would otherwise set it back to
`RUNNING` and leave it reporting as in-flight forever. Parked and failed runs stay resumable. An
interrupt (`Ctrl-C`) exits `130` and prints the run id, so the resume command can be pasted.

---

## 14. Context skeletonization

Before an LLM step, background and dependency files are reduced to skeletons (signatures, no bodies)
by the **ContextAssembler**. Handlers call `evaluate_and_fetch_skeleton_context()` via
`asyncio.to_thread`, which runs `CodeStructureAtom` off the event loop and returns a
path → skeleton-string mapping for the prompt. Details:
[`code_structure_and_ast_editing.md`](code_structure_and_ast_editing.md).
