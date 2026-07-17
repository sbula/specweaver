# Design: Zero-Trust Sandbox — Base Integration Contract (INT-US-09)

- **Feature ID**: INT-US-09
- **Phase**: 6
- **Status**: APPROVED — approved by Steve Bula on 2026-07-16 (amended 2026-07-16 during impl-planning: rebind scope narrowed to surfaces that *execute* untrusted content — `action: bash` and `run_tests`/pytest — explicitly excluding static-analysis QA like `lint_fix`/ruff, which parses but never executes code)
- **Design Doc**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_design.md

## Feature Overview

Feature INT-US-09 adds the **base integration layer** for US-9 ("The Zero-Trust Sandbox") to
SpecWeaver's flow-execution engine. It solves the problem that the three already-built
Core-Required (MVS) capabilities — **US-5 Core** (Git Worktree Bouncer / `D-EXEC-02`),
**E-EXEC-01** (Standard Local Execution / `SubprocessExecutor`), and **C-EXEC-02** (Native CLI
Action Nodes / `BashActionAtom`) — currently operate as three *independent, uncoordinated*
boundaries: worktree isolation rebinds only `RunContext.output_dir` while every process spawner
anchors its execution boundary to the unchanged `project_path`, and nothing enforces isolation for
untrusted steps. INT-US-09 wires them into one coherent, enforceable host-execution flow — a
boundary hand-off that binds process execution to the worktree, an opt-in enablement policy, and a
combined end-to-end proof. It interacts with `core.flow.engine` (runner / runner_utils / handlers),
`sandbox.execution.core` (`BashActionAtom` + `SubprocessExecutor`), `sandbox.git.core` (`GitAtom`
worktree intents), `core.config` (`SandboxSettings`), and the composition root
(`interfaces.cli` / `interfaces.api`), and does **NOT** touch containerization (`B-EXEC-01`,
`D-EXEC-01`, Podman/Docker, `ContainerSubprocessExecutor`) or any of the four INT-US-09 sub-story
add-on slots (SF01–SF04). Key constraints: **strictly container-free**; zero regression to existing
host execution; backward-compatible (isolation off by default); wiring lives only in the flow
orchestration layer / composition root using atom surfaces, never inside `sandbox/*`; respects
`tach.toml` / `context.yaml` boundaries and ADR-002 (generic engine, config frozen at the
composition root).

> **Scope note — this is an integration contract, not a capability build.** It wires *already-built*
> capabilities together on US-9's behalf. It invents no new execution mechanism. Containerization is
> a separate, explicitly-excluded concern owned by the INT-US-09 **sub-story add-ons** (see
> Sub-Feature Breakdown → *Out-of-Scope Add-On Sub-Stories*), not by this Base Contract.

## Research Findings

### Codebase Patterns

**The coordination gap (confirmed in code).** The three capabilities are three parallel,
independently-anchored boundaries:

- **Worktree isolation communicates only via `output_dir`.** `execute_in_sandbox(...)`
  (`src/specweaver/core/flow/engine/runner_utils.py:136-194`) clones the run context and sets **only**
  `isolated_context.output_dir = context.project_path / wt_path`, then calls the inner handler. It
  does not rebind any execution boundary. Triggered per-step by `PipelineStep.use_worktree`
  (`src/specweaver/core/flow/engine/models.py:221`), gated at `runner.py:320`
  (`if getattr(step_def, "use_worktree", False):`). A grep shows **no pipeline YAML ever sets it** —
  worktree isolation is reachable only by manual step authoring.
- **The executor boundary is its constructor `cwd`, fixed at construction**
  (`src/specweaver/sandbox/execution/executor.py:61`), and `SubprocessExecutor` is constructed
  **per-caller** at ~18 sites, each keying `cwd` off `context.project_path`. There is **no central
  executor factory** whose boundary the worktree flow could rebind — this is the structural reason
  the gap exists.
- **`BashActionAtom` runs against the project root even inside a sandboxed step.**
  `BashActionHandler._get_atom` (`src/specweaver/core/flow/handlers/bash_action.py:64-68`) builds
  `BashActionAtom(cwd=context.project_path)`; the atom resolves scripts against
  `<project>/.specweaver/scripts/` and constructs `SubprocessExecutor(cwd=self._cwd)` with
  `_cwd = project_path` (`src/specweaver/sandbox/execution/core/atom.py:65-67,106`). It never reads
  `output_dir`, so a `use_worktree: true` bash step still executes against the real repo root.

**Reuse (nothing is rebuilt).** The integration delegates entirely to existing atoms and mechanisms:
`GitAtom` worktree intents (`worktree_add` / `worktree_sync` / `strip_merge` / `worktree_teardown`,
`src/specweaver/sandbox/git/core/atom.py`), `BashActionAtom.run(context)`, `SubprocessExecutor`
(security boundary), and `execute_in_sandbox` (the existing US-5 orchestration seam). The
"Main-Branch Wins" strip-merge (out-of-bounds hunks erased per `context.yaml`, then
`git apply --strategy-option=ours`; shared docs like `README.md`/`docs/*` hard-forbidden) is
existing US-5 behavior the integration must preserve.

**Boundary rules that constrain the design** (authoritative: `tach.toml` + `context.yaml`):

- `core.flow` **may** consume `sandbox.execution.core` and `sandbox.git.core` (`tach.toml:41-42,156-158`;
  `core/flow/context.yaml:26-30`) — one-way, `flow → sandbox` only. The reverse is forbidden
  (`sandbox/execution/context.yaml:10-12` → `forbids: [sandbox.qa_runner.*, core.flow.*]`).
- `core.flow` **forbids** `sandbox/*/interfaces` (`core/flow/context.yaml:34-35`) — the engine must use
  **atom** surfaces (`GitAtom`, `BashActionAtom`), not agent-facing tools.
- `core.config` is **pure-logic** and forbids `sandbox/*` — subprocess/worktree config must surface as
  a passive `SandboxSettings` object injected into flow, not a sandbox import.
- **ADR-002** (`docs/architecture/07_architectural_decision_records/adr_002_composition_root_vs_factories.md`):
  the flow engine must remain a **generic orchestrator**; SpecWeaver-specific config is frozen at the
  **composition root** (`interfaces.cli` / `interfaces.api`) and passed in pre-hydrated — never welded
  into the engine, never fetched via atoms mid-pipeline (blocks the event loop / breaks snapshot
  isolation). **ADR-001** confirms the Git Worktree Sandbox *is* the chosen isolation model.
- Anti-patterns to avoid: raw `subprocess`/`os`/`git` in the engine (route through atoms — Feature 3.32
  SF-4 precedent); inline/lazy imports to dodge `tach`; parallel security mechanisms.

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Git CLI | system (already required) | `git worktree add/remove`, `git apply --strategy-option=ours` (via `GitAtom`) | existing US-5 / `D-EXEC-02` |
| SubprocessExecutor | in-repo (E-EXEC-01) | `execute()` with constructor-time `cwd` boundary, credential stripping, resource limits | `src/specweaver/sandbox/execution/executor.py` |

No new external library or service is introduced.

### Blueprint References

`docs/ORIGINS.md:170-191` — **Archon** ("Workflow Orchestration & Isolation … deterministic and
repeatable through YAML DAGs and git worktrees"; Bash/Script DAG Nodes → SpecWeaver's `action: bash`
steps resolving bare script names against `.specweaver/scripts/`) and **Cavekit** (Work Packet
Bundling clustering components into shared Git Worktrees). These are the origin patterns for the
worktree-sandbox + bash-node model this contract integrates.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Execution-boundary hand-off | PipelineRunner | When an **in-scope untrusted-*execution* surface** — a `action: bash` step (`BashActionAtom`) or a test run (`ValidateTestsHandler` → `run_tests` / pytest) — runs under worktree isolation, the system SHALL bind the process-execution boundary (the `SubprocessExecutor` `cwd`) to the worktree **source-tree** path rather than `project_path`. Static-analysis QA (lint/complexity/architecture, which parse but never execute the code) and all other handlers remain project-root-bound (documented limitation; see AD-2). | In-scope processes that *execute* LLM-authored content read/write within the worktree source tree, not the real source root. |
| FR-2 | Bash worktree containment | BashActionHandler / BashActionAtom | A `action: bash` step running under isolation SHALL resolve its script and `working_dir` against the worktree source tree, preserving canonical-path containment and fail-closed validation. | Bash scripts execute worktree-bounded; the real source tree is not directly mutated. (Intentionally-shared symlinked caches — `.specweaver/`, dep caches — are outside the isolation boundary by US-5 design; see AD-4.) |
| FR-3 | Isolation enablement policy | Composition root (CLI/API) | The system SHALL expose a US-9 isolation policy as a `SandboxSettings` field, resolved at the composition root and carried into `RunContext`, that when enabled makes worktree isolation the **default** for pipeline steps; a step MAY still explicitly opt out. When the policy is disabled or absent, behavior is identical to today (per-step opt-in only). | Operators enforce host-sandbox isolation via config, without editing pipelines, with no behavior change when off and an explicit per-step escape hatch. |
| FR-4 | Unified security boundary | SubprocessExecutor | Every isolated execution (bash script; `run_tests`/pytest) SHALL retain E-EXEC-01's guarantees: credential stripping, env allowlist, resource limits, timeout escalation, and `cwd` containment. | No untrusted-execution path bypasses the executor's security boundary when isolation is active. |
| FR-5 | Strip-merge preservation | GitAtom | Changes produced inside the worktree SHALL be reconciled back via the existing "Main-Branch Wins" `strip_merge` (out-of-bounds hunks stripped per `context.yaml`; shared docs forbidden). | Only allowed paths merge back to the source tree; the integration does not weaken US-5. |
| FR-6 | Verifiable proof | Test suite | The system SHALL provide an end-to-end test whose primary proven surface is a real `action: bash` step running inside a real git worktree, asserting its writes land in the worktree source tree and the real source root is not directly mutated; a `run_tests`/pytest execution under isolation is asserted as an additional case where a test step runs isolated. | The contract's "Verifiable Proof" is satisfied by a runnable, unmocked e2e test. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Backward compatibility | With the isolation policy absent/disabled and no per-step `use_worktree`, execution is byte-identical to today; no existing pipeline definition changes. |
| NFR-2 | Architecture compliance | All wiring in `core.flow` (engine/handlers) + composition root; atom surfaces only (`GitAtom`, `BashActionAtom`); no raw `subprocess`/`os`/`git` in the engine; config as passive `SandboxSettings` (ADR-002); imports declared at module top and registered in `tach.toml` (no lazy-import boundary dodges). |
| NFR-3 | Security | Credential stripping + env allowlist + `cwd` containment preserved on every isolated path; `.specweaver/scripts/` canonical containment fail-closed (checked at load and immediately pre-exec); `bash` resolved to an absolute path via `shutil.which()` (never the bare string). |
| NFR-4 | Platform | Works on Windows + Linux; reuse US-5's resilient worktree-teardown backoff for Windows file locks; no OS-specific regression. |
| NFR-5 | Observability | DEBUG-level lazy `%s` logging of command / cwd / timeout / exit_code / duration; handlers surface `files_touched`. |
| NFR-6 | Performance | Worktree add/teardown overhead is incurred only when isolation is active; the default (non-isolated) path adds zero overhead. |
| NFR-7 | Proof tier | Verifiable Proof is a real e2e test using real git worktrees + at least one real unmocked execution; if any optional prerequisite is unavailable, skip cleanly at collection time (no exclusion marker) — none is expected since git is always present. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Git CLI | already required by US-5 | `git worktree` lifecycle + `git apply --strategy-option=ours` via `GitAtom` | Y | No new version; reuses existing worktree ops. |
| SubprocessExecutor (E-EXEC-01) | in-repo | `execute()`, constructor-time `cwd` boundary | Y | Boundary is fixed at construction; rebinding = constructing an executor bound to the worktree path. |

No new third-party dependency. **No API incompatibility → no dependency gate.**

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | All integration/wiring lives in `core.flow` (engine + handlers) and the composition root; the engine drives `GitAtom` / `BashActionAtom` via the uniform `Atom.run(context)` contract — never raw `subprocess`/`os`/`git`. | `tach.toml`/`context.yaml` permit one-way `flow → sandbox.core` only; sandbox must stay engine-agnostic; SF-4 precedent forbids raw filesystem/process ops in the engine. | No |
| AD-2 | Introduce a generic **execution-root** on `RunContext` (default = `project_path`); `execute_in_sandbox` sets it to the worktree source-tree path, and the **in-scope untrusted-*execution* surfaces — `BashActionHandler` → `BashActionAtom` and `ValidateTestsHandler` → `QARunnerAtom` for the `run_tests` (pytest) path** — construct their atom/executor `cwd` from it instead of `project_path`. Static-analysis QA (`LintFixHandler`/ruff, complexity, architecture — parse but do not execute) and every other process-spawning site remain project-root-bound for now (documented limitation, incremental adoption — not a regression, since their default is unchanged). | The executor boundary is a constructor-fixed `cwd`; propagating `output_dir` alone cannot rebind execution. An engine-generic "where processes run" field keeps atoms ignorant of the engine. Scoping to surfaces that *execute* untrusted content (a trusted tool — `pytest`/`bash` — running LLM-authored files) bounds the change; static analysis (`ruff`/`tach`) never executes the code, so isolating it adds risk without security benefit. | No |
| AD-3 | The US-9 isolation policy is a `SandboxSettings` field resolved at the **composition root** (where `RunContext` is assembled for a run — `interfaces.cli` / `interfaces.api` pipeline invocation; exact call site pinned in the impl plan, consistent with how `SpecWeaverSettings.sandbox` already reaches the run) and carried into `RunContext`. The step flag becomes **tri-state** (`use_worktree: bool \| None`): `None` → policy decides; `True`/`False` → explicitly honored over the policy. The runner gate resolves `explicit-step-value ?? context.enforce_isolation`. Default (policy off, flag `None`) → today's behavior. | ADR-002: config frozen at the composition root, engine reads a passive flag (no step classification). Tri-state is required to distinguish an explicit opt-out from "unset" (a plain `bool=False` cannot). Preserves backward compatibility (NFR-1); existing explicit `True` steps stay valid. | No |
| AD-4 | Scope the isolation guarantee to the **worktree source tree**. Preserve `.specweaver/scripts/` canonical containment under the rebind (fail-closed `WorkspaceBoundary` at load + pre-exec, `shutil.which()` bash resolution unchanged). Intentionally-shared, symlinked paths (`.specweaver/` caches, dep caches, `reservations.db`) are **outside** the isolation boundary by existing US-5 design — the e2e proof (FR-6) asserts *source-tree* isolation specifically, not shared-cache isolation. | C-EXEC-02 security invariants + the path-containment (CVE-2025-54794) lesson must survive the boundary move; honesty about the shared-cache seam prevents a false isolation claim. Broadening isolation to shared caches is a separate, later concern (and partly what the container add-on SF01 addresses). | No |
| AD-5 | Verifiable Proof is a real-worktree, unmocked e2e test under `tests/e2e/sandbox/`, using the collection-time clean-skip pattern for any optional prerequisite. | `testing_guide` conventions; the roadmap Proof Mandate; the §23 corollary that a mocked unit test cannot catch host-path assumptions — pair with a real execution. | No |

*No decision constitutes an Architectural Switch — the integration fits entirely within existing
`consumes`/`forbids` rules, archetypes, and ADRs. No HITL architectural sign-off is required on
these grounds.*

## ROI Analysis

### Investment Cost

| Item | Effort | Risk |
|------|--------|------|
| Execution-root propagation in `execute_in_sandbox` + `RunContext` | S | Low — additive field, default preserves behavior |
| Handler rebind (`bash_action`, QA handlers) to execution-root | S–M | Low–Med — must keep `.specweaver/scripts` containment exact |
| `SandboxSettings` isolation-policy field + composition-root resolution | S | Low — mirrors existing `execution_mode` settings plumbing |
| Runner gate `OR context.enforce_isolation` | XS | Low |
| Real-worktree e2e proof test | M | Med — needs real worktree + real execution, Windows lock handling |

### Returns

| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| US-9 (Zero-Trust Sandbox) | Its Base Integration Contract is satisfiable — the three MVS capabilities finally cooperate as one enforceable flow. | High |
| Operators / CI | Can enforce host-sandbox isolation for untrusted execution via one config switch, no pipeline edits. | High |
| Every pipeline running LLM-authored bash/QA | Untrusted execution is filesystem-bounded to a worktree, with source changes gated by strip-merge. | High |
| Future INT-US-09 sub-story add-ons (SF01–SF04) | Inherit a coherent enforced-isolation seam to build on. | Medium |

### Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Rebind silently breaks `.specweaver/scripts` containment | Med | High | AD-4: keep `WorkspaceBoundary` fail-closed (load + pre-exec); e2e asserts containment; unit tests for path resolution under worktree. |
| Handlers other than bash/QA still anchor to `project_path` | Med | Med | Document execution-root as the canonical spawn root; audit all process-spawning handlers; leave non-audited paths on default (project_path) = no regression. |
| Windows worktree teardown file-lock flakiness | Med | Low | Reuse US-5's progressive-backoff teardown in a `finally`. |
| Enforcement-by-default surprises an existing pipeline | Low | Med | NFR-1: policy defaults off; enabling is an explicit operator action. |

### Refactoring Opportunities

| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| ~18 per-caller `SubprocessExecutor` constructions | No shared boundary; each keys `cwd` off `project_path` | An execution-root convention gives a single, worktree-aware source of truth for spawn `cwd` (incremental adoption) | M (out of scope here; noted) |
| `use_worktree` per-step literal | Set by no pipeline; isolation effectively dormant | The policy makes isolation reachable/enforceable centrally | S (in scope, FR-3) |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Guide-1 | Update `pipeline_engine_guide.md` §7 (Worktree Bouncer) to document that isolation now rebinds the **execution boundary** (execution-root), not just `output_dir`, and how the US-9 isolation policy enables it. | ⬜ To be written during Pre-commit |
| Guide-2 | Update `subprocess_execution.md` to describe the execution-root convention for `cwd` under isolation. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

**Single feature — no decomposition.**

The six FRs form one tightly-coupled, atomic integration: FR-3 (policy) and FR-6 (proof) are inert
without FR-1/FR-2/FR-4 (the boundary hand-off), and no FR subset ships independent value — so
splitting would violate the self-containment rule and collapse into a single dependency chain.
Delivered as one cohesive integration feature with an **un-suffixed** implementation plan
(`INT-US-09_implementation_plan.md`, following the `D-EXEC-01` single-feature precedent), organized
internally by commit boundaries during the implementation-plan phase.

- **Scope**: Wire US-5 (Worktree Bouncer) + E-EXEC-01 (SubprocessExecutor) + C-EXEC-02
  (BashActionAtom) into one enforceable host-execution flow: boundary hand-off, isolation policy,
  strip-merge preservation, and the e2e proof.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6]
- **Inputs**: `RunContext` (project_path, output_dir, env), `SandboxSettings` (new isolation
  policy) from the composition root, `PipelineStep.use_worktree`, existing `GitAtom` / `BashActionAtom`.
- **Outputs**: Worktree-bounded process execution; a config-driven isolation policy; a passing
  real-worktree e2e proof; updated dev guides.
- **Depends on**: none (US-5 Core, E-EXEC-01, C-EXEC-02 are all committed).
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-09/INT-US-09_implementation_plan.md

### Out-of-Scope Add-On Sub-Stories (documented, NOT designed here)

The roadmap reserves `INT-US-09-SF01..SF04` for **sub-story add-ons** layered on top of this Base
Contract. They are separate integration contracts, each blocked on (or deferring integration of)
its own capability, and are **explicitly out of scope** for this design:

| Slot | Add-on | Underlying capability | Status |
|------|--------|-----------------------|--------|
| INT-US-09-SF01 | Containerized Isolation | `D-EXEC-01` ✅ + `B-EXEC-01` ✅ (built) | Integration Pending Design — separate contract, container-scoped |
| INT-US-09-SF02 | Security Defenses | `E-EXEC-02` (unbuilt) | Blocked on capability |
| INT-US-09-SF03 | Extreme Execution Paranoia | `A-EXEC-01` (unbuilt) | Blocked on capability |
| INT-US-09-SF04 | Mathematical Speed & Security (Rust) | `A-EXEC-03` (unbuilt) | Blocked on capability |

## Execution Order

**Single feature — no decomposition.** One build unit; start the implementation-plan skill
immediately after design approval. Internal commit boundaries are defined in the implementation plan.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Core Zero-Trust Host-Execution Integration (single feature) | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: COMPLETE (2026-07-17). Implemented across 4 commit boundaries: CB-1 config
surface + composition-root policy wiring (`85d02be4`), CB-2 execution-root + tri-state gate
(`f4077870`), CB-3 boundary hand-off in the untrusted handlers (`bd6913c6`), CB-4 real-worktree
e2e proof + fail-closed + docs (this commit). Container-neutrality guard applied (does not activate
B-EXEC-01 container QA on `sw run`). API-run policy wiring deferred to Backlog (documented).
**Scope reminder**: STRICTLY CONTAINER-FREE. Integrates US-5 + E-EXEC-01 + C-EXEC-02 only. Excludes
B-EXEC-01, D-EXEC-01, Podman/Docker, and the INT-US-09-SF01..SF04 add-on sub-stories.
**Next step**: Trigger the `dev` skill for the single feature, starting at Commit Boundary CB-1
(config surface + composition-root wiring) in `INT-US-09_implementation_plan.md` — proceed CB-1 → CB-4.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ and resume with the
appropriate skill. Companion doc `docs/roadmap/topics/topic_08_integration/US-09_integration.md`
carries the reframed (non-container) Base Story Contract text this design corresponds to.
