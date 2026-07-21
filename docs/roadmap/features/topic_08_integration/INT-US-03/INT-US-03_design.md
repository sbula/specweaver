# Design: Autonomous Implementation Integration (INT-US-03)

- **Feature ID**: INT-US-03
- **Phase**: 6
- **Status**: APPROVED — approved by Steve Bula on 2026-07-17 (AD-5, AD-6, AD-7 all resolved "yes").
- **Design Doc**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_design.md

## Feature Overview

Feature INT-US-03 adds the autonomous-implementation integration layer that pipes the
Implementation Generator (`D-INTL-01`) output natively into the QA Runner (`D-VAL-01`) and
the Code Validation Rules (`D-VAL-05`), closing the flagship US-3 loop: *hand an approved
spec → generate code, generate tests, run the tests, run C01–C08 code validation, and
auto-fix linting errors.* Today `sw implement` stops after writing `src/<stem>.py` and
`tests/test_<stem>.py` and merely prints "now run `sw check` manually"; this feature makes
QA a native, in-pipeline stage. All QA/test execution runs under the **already-built US-9
Core zero-trust worktree isolation** (`INT-US-09`, `enforce_isolation` / `execution_root`),
so untrusted generated code is exercised worktree-bounded, never against the real source
root. It touches only `workflows/implementation` (the `sw implement` pipeline + its
`RunContext`) plus a new e2e proof test, and does **NOT** add any new capability.

> [!IMPORTANT]
> **Container-free scope — `D-EXEC-01` is explicitly OUT.** The `US-03_integration.md`
> contract prose says "Zero-Trust **Podman** Sandbox (`D-EXEC-01`)". That is a **defect**:
> per the capability registry and `US-09_integration.md`, Podman/container execution
> (`D-EXEC-01` Podman/Docker Integration + `B-EXEC-01` Ephemeral Podman Sub-Containers) is
> **not** part of US-9 *Core*; it is the separate, still-**Pending-Design** US-9 add-on
> `INT-US-09-SF01` (Containerized Isolation). US-3's declared Core dependency is **US-9
> *Core*** = container-free git-worktree isolation. This base contract therefore integrates
> against worktree isolation only. Podman-exclusive QA for the implement loop is deferred to
> a future `INT-US-03` sub-story that depends on `INT-US-09-SF01`. **Recommended follow-up:**
> correct the prose in `US-03_integration.md` (see Architectural Decision AD-6).

## Research Findings

### Codebase Patterns

**What already exists (all US-3 Core deps are ✅ built and wired-ready — this is integration-only):**

- **`sw implement` (`D-INTL-01`)** — `src/specweaver/workflows/implementation/interfaces/cli.py:120-151`.
  Builds an **inline** `PipelineDefinition(name="implement_spec", ...)` with exactly two steps:
  `generate_code` (`GENERATE`/`CODE`) and `generate_tests` (`GENERATE`/`TESTS`), then runs it via
  `PipelineRunner`. Derives output paths `src/<stem>.py` / `tests/test_<stem>.py` where
  `stem = spec.stem − "_spec"` (`cli.py:99-104`). Its `RunContext` (`cli.py:137-147`) sets `config`
  but **never sets `enforce_isolation`** (defaults `False`). Ends by printing "Next steps: `sw check
  --level=code …`" (`cli.py:165-170`) — i.e. QA is a **manual, disconnected** follow-up today.
- **QA Runner (`D-VAL-01`)** — `QARunnerAtom` (`src/specweaver/sandbox/qa_runner/core/atom.py:71`),
  invoked by `ValidateTestsHandler` (`src/specweaver/core/flow/handlers/validation.py:335`) on a
  `VALIDATE`/`TESTS` step. Input contract: `{intent:"run_tests", target:"<rel path>", kind, coverage,
  coverage_threshold}`; exports `{passed, failed, errors, skipped, total, duration_seconds,
  coverage_pct, failures[]}`.
- **Lint-Fix Reflection Loop (`D-VAL-01`)** — `LintFixHandler` (`src/specweaver/core/flow/handlers/lint_fix.py:23`),
  handler key `lint_fix+code`. Phase 1 = `ruff format` + `ruff check --fix`; Phase 2 = LLM reflection
  loop up to `max_reflections` (default 3). Returns `{reflections_used, lint_errors_remaining, auto_fixed}`.
  Already passes `sandbox_settings=context.config.sandbox` to its atom (`lint_fix.py:215-216`).
- **Code Validation Rules (`D-VAL-05`)** — `VALIDATE`/`CODE` step → `ValidateCodeHandler`
  (`validation.py:200`), runs C01–C08 (tests-pass, coverage, type hints, architecture).
- **US-9 Core zero-trust worktree isolation (`INT-US-09`, ✅ Done 2026-07-17)** — the sandbox
  plumbing is **already built**. `RunContext.enforce_isolation` (`src/specweaver/core/flow/handlers/base.py:56`,
  default `False`) + `execution_root` (`base.py:57`) rebind untrusted-process cwd to an ephemeral git
  worktree. `PipelineStep.use_worktree` (`True`=force, `False`=off, `None`=defer to policy). Proven by
  `tests/e2e/sandbox/test_int_us_09_isolation_e2e.py`: a `VALIDATE`/`TESTS` step with
  `use_worktree=None` + `enforce_isolation=True` runs `QARunnerAtom`→pytest **worktree-bounded**, with
  a paired un-isolated control guarding against a 0-collected vacuous pass. Container-free; needs only
  git+bash; skips cleanly otherwise.
- **`new_feature.yaml` (`src/specweaver/workflows/pipelines/new_feature.yaml`)** — already chains
  `generate_code → generate_tests → run_tests (validate/tests, coverage, loop_back→generate_code,
  max_retries 2) → validate_code (validate/code, C01–C08) → review_code`. This is the exact QA chain
  INT-US-03 needs, **minus** the spec draft/validate/review + HITL stages (out of scope: the spec is
  already approved) and **minus** the `lint_fix` step. It is the structural template for the wiring.

**Which modules will be touched:** only `workflows/implementation` (`interfaces/cli.py`: extend the
inline pipeline + thread the isolation policy into `RunContext` + report QA results) and `tests/e2e/`
(new proof). The generator, QA runner, lint-fix loop, validation handlers and worktree isolation are
all pre-existing and dispatched by the flow engine — none are imported directly by the CLI.

**Boundary rules that constrain the design:** `workflows/implementation/context.yaml` is an
`orchestrator` with `consumes: [llm, config, validation]`, `forbids: []`. The CLI already imports the
needed flow symbols (`StepAction`, `StepTarget`, `PipelineDefinition`, `PipelineStep`, `RunContext`,
`PipelineRunner`). Adding `VALIDATE`/`LINT_FIX` steps to the inline pipeline and reading
`settings.sandbox` uses only already-consumed dependencies → **no new import, no boundary change, no
architectural switch.** (`tach check` must stay green.)

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| git | any | ephemeral worktree add/remove (US-9 isolation, already wired) | host |
| bash | any | shell for `action: bash` / test invocation (already wired) | host |
| pytest | stack | test execution via `QARunnerAtom.run_tests` (already wired) | `pyproject.toml` |
| ruff | stack | `ruff format` + `ruff check --fix` in the lint-fix loop (already wired) | `pyproject.toml` |

No new external tool is introduced. Podman/Docker is **explicitly excluded** from this base contract.

### Blueprint References

None. This feature is driven entirely by the existing SpecWeaver Flow + Sandbox architecture and the
`INT-US-09` isolation pattern (`test_int_us_09_isolation_e2e.py`).

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Native test run | `implement` pipeline | SHALL append a `run_tests` step (`VALIDATE`/`TESTS`) after `generate_tests`, executing the generated tests via `QARunnerAtom.run_tests` with `coverage=true`. | Generated tests are run automatically; step exports `{passed, failed, coverage_pct, …}`. |
| FR-2 | Auto-fix linting | `implement` pipeline | SHALL append a `lint_fix` step (`LINT_FIX`/`CODE`) running `ruff` auto-fix then the LLM reflection loop (`max_reflections` default 3) over the generated code. | Lint errors are auto-corrected; step exports `{reflections_used, lint_errors_remaining, auto_fixed}`. |
| FR-3 | Code validation rules | `implement` pipeline | SHALL append a `validate_code` step (`VALIDATE`/`CODE`) running `D-VAL-05` rules C01–C08 over the generated code. | Generated code is validated (tests-pass, coverage, type hints, architecture) — the declared US-3 Core `D-VAL-05` dependency is exercised. |
| FR-4 | Generated-target resolution | `implement` pipeline | SHALL resolve each QA step's `target` to this run's generated files (`src/<stem>.py`, `tests/test_<stem>.py`, `stem = spec.stem − "_spec"`). | QA runs against the freshly generated artifacts, not stale or unrelated paths. |
| FR-5 | Zero-trust QA execution | `implement` `RunContext` | SHALL resolve `enforce_isolation` from `SandboxSettings` and set `use_worktree=None` on all QA/lint steps, so that under the US-9 policy every QA/test/lint process runs **worktree-bounded** (container-free), never against the real source root. | Untrusted generated code is executed exclusively inside the US-9 zero-trust worktree sandbox; the real source root is never mutated by generated tests. |
| FR-6 | Failure loop-back | `implement` pipeline | SHALL gate `run_tests` with `on_fail: loop_back → generate_code`, `max_retries: 2` (mirroring `new_feature.yaml`). | On test failure the loop attempts bounded regeneration before surfacing failure. |
| FR-7 | Inline QA reporting | `implement` command | SHALL report QA + lint outcomes inline (pass/fail, coverage %, reflections used, lint errors remaining) and remove the stale "run `sw check` manually" next-steps message. | The user sees the full autonomous result from one command; no manual follow-up implied. |
| FR-8 | Verifiable proof | test suite | SHALL provide an e2e test driving the full `implement → run_tests → lint_fix → validate_code` loop with `enforce_isolation=True`, proving generated tests run pytest **worktree-bounded** (cwd inside `.worktrees/`, source root unmutated) and lint-fix auto-corrects, plus an **un-isolated control** proving the probe actually runs (no 0-collected false pass). | The contract's "Verifiable Proof" is a real, unmocked, CI-runnable (git+bash, skip-clean) e2e test. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Container-free | The base contract MUST NOT introduce any Podman/Docker code path (`execution_mode="container"`, `ContainerSubprocessExecutor`). Isolation is worktree-only (US-9 Core). |
| NFR-2 | Backward compatibility | With the US-9 isolation policy **off**, `sw implement` MUST still succeed on hosts without git worktrees; QA runs on host as a normal in-pipeline step (existing default-off `INT-US-09` behavior preserved). |
| NFR-3 | Architecture compliance | All changes confined to `workflows/implementation` + `tests/`; no new cross-layer import; `tach check`, `ruff`, `mypy --strict` MUST stay green. |
| NFR-4 | Graceful degradation | If git/bash are unavailable, the isolation path MUST skip cleanly (proof test skips, matching `INT-US-09` NFR-7); QA still runs on host. LLM-unavailable → `lint_fix` degrades to ruff-only (existing `LintFixHandler` behavior). |
| NFR-5 | Bounded cost | `run_tests` loop-back `max_retries ≤ 2`; `lint_fix max_reflections` default 3 — no unbounded LLM/token spend in the autonomous loop. |
| NFR-6 | Determinism of proof | The proof test MUST include the paired un-isolated control asserting `failed == 1` (probe ran) to prevent a vacuous 0-collected pass, per the `INT-US-09` proof pattern. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| git | any | worktree add/remove | Y | Already used by US-9 isolation (`INT-US-09` ✅). |
| bash | any | shell execution | Y | Already used by `BashActionAtom` / test invocation. |
| pytest / ruff | current stack | test + lint execution | Y | Already invoked by `QARunnerAtom` / `LintFixHandler`. |

No dependency upgrade required. No Podman/Docker dependency added.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Extend the **existing inline** `implement_spec` pipeline in `cli.py` rather than switching `sw implement` to load `new_feature.yaml`. | `new_feature.yaml` also runs spec draft/validate/review + HITL — wrong for an already-approved spec. Appending QA steps to the inline definition is minimal, in-module, and adds no import. | No |
| AD-2 | QA steps use `use_worktree=None` (defer to policy) + thread `enforce_isolation` into `RunContext` from `settings.sandbox`. | Reuses the shipped `INT-US-09` isolation mechanism verbatim; zero new sandbox code. | No |
| AD-3 | Include `validate_code` (C01–C08 / `D-VAL-05`) in the base loop. | `D-VAL-05` is a **declared US-3 Core dependency**; integrating it is the base contract's job (contrast `D-EXEC-01`, which is a US-9 *sub-story* dep and thus excluded). | No |
| AD-4 | Resolve QA `target` to the generated `src/<stem>.py` / `tests/test_<stem>.py` via the existing stem convention. | Matches how `sw implement` already derives paths (`cli.py:99-104`) and how `validation_hydrator` derives `test_<stem>.py`; no new state-passing machinery needed. | No |
| AD-5 | **[SUPERSEDED by AD-8, 2026-07-21]** Originally (approved 2026-07-17): `sw implement` forces isolation **on** by default. Superseded because blanket default-on imposes worktree/reconcile friction (clean-tree requirement, `chore(sandbox)` commit) on *all* implement runs incl. small/interactive projects. AD-8 replaces it with **DAL-driven auto-escalation** — off by default, auto-on only for high-assurance (DAL_B+) code — which delivers the same zero-trust intent exactly where it is warranted, with zero friction for small projects. | *(historical)* The contract says QA "MUST execute exclusively inside the sandbox," and LLM-generated code is untrusted. | Superseded. |
| AD-8 | **[RESOLVED — approved by Steve Bula 2026-07-21]** `sw implement` isolation policy = **opt-in default + DAL-driven auto-escalation (Option C).** Per-run session isolation stays off by default; the shared `apply_session_policy` **auto-enables it when the touched code's resolved DAL is `DAL_B` or stricter** (`is_strict`). Overridable: `[sandbox] enforce_session_isolation` forces always-on; `[sandbox] auto_isolate_min_dal` sets/disables the threshold. Non-git under escalation degrades to host (never breaks the command). Folded into `INT-US-03 SF-03` as a small enhancement to the shared `apply_session_policy`, **opt-in per caller** (`dal_auto_escalate` param): **`sw implement` opts in; `sw run`/`sw resume` do not** — so escalation fires only where untrusted code is generated, never on benign `sw run` pipelines (e.g. `validate_only`). | Reuses the existing `DALResolver` + `DALLevel` risk machinery: isolation cost (ephemeral worktree, reconcile commit, clean-tree requirement) then falls **only** on code whose assurance level justifies it, and never on small/low-DAL projects. Zero config for the common case. | No (policy enhancement to the shipped `C-EXEC-06` session policy; no new capability). |
| AD-6 | **[RESOLVED — approved 2026-07-17]** Correct `US-03_integration.md` prose: replace "Zero-Trust Podman Sandbox (`D-EXEC-01`)" with "US-9 Core zero-trust **worktree** sandbox (container-free; Podman = `INT-US-09-SF01`, out of scope)". *(Applied 2026-07-17.)* | The current prose repeatedly drags a US-9 *sub-story* capability (`D-EXEC-01`) into base contracts, contradicting the declared dependency graph. | No — doc edit. |
| AD-7 | **[SUPERSEDED — 2026-07-21]** The per-step crux below is now MOOT. The SF-03 spike proved the per-step model cannot carry freshly-generated code across worktrees (`TECH-012`); the approved resolution was the **per-run (session) worktree mode**, built as capability **`C-EXEC-06`** (SF-01/02/03 committed) and integrated by **`INT-US-09-SF05`** (✅). In session mode the WHOLE implement loop runs in ONE worktree, so generated files persist in-tree across steps (generate → run_tests → lint_fix → validate) with a **single** end-of-run authorized reconcile against `allowed_paths` — no per-step `strip_merge` carry, no per-step `allowed_paths` threading, no spike. **SF-03 re-scopes to *consume* `C-EXEC-06`:** one `apply_session_policy(context, settings, logger)` call in the implement CLI (`PipelineRunner.run()` already routes through `execute_run`), the AD-5 default-on decision, and the FR-8 proof. *(Original per-step rationale retained below for history.)* | *(historical)* `execute_in_sandbox` is **per-step**: each step gets a fresh worktree checked out from branch HEAD, torn down after, with inter-step data flowing only via the real repo through `strip_merge`. A clean HEAD checkout does **not** carry uncommitted working-tree files, and `strip_merge` discards any path not in `allowed_paths`. | **Resolved via the approved per-run architectural switch (`C-EXEC-06`, AD-5).** |

> [!WARNING]
> **Crux integration risk (AD-7) — the isolated loop is NOT "just flip a flag".** Because US-9
> isolation is per-step (fresh worktree per step, torn down after; inter-step state travels through
> the real repo via allow-listed `strip_merge`), the freshly generated, **uncommitted** code will be
> **absent** from the `run_tests` worktree unless the generate steps are themselves isolated and their
> output paths are in `context.allowed_paths`. The existing `test_int_us_09_isolation_e2e.py` sidesteps
> this by committing its probe test up front — a luxury the autonomous loop does not have. SF-03 must
> resolve this explicitly (recommended path in AD-7) and its proof (FR-8) must exercise **generated**
> code, not pre-committed code. If validation shows the per-step model can't cleanly carry generated
> artifacts, the fallback is to keep SF-01/SF-02 (host-mode loop) shipping value while SF-03 is
> escalated (possible `INT-US-09` enhancement for a per-*run* worktree — which would be a separate,
> approved architectural change, not silently absorbed here).

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Extend inline pipeline (run_tests + lint_fix + validate_code) + target resolution | Low (single file) | Low — steps/handlers already exist |
| Thread US-9 isolation policy into `implement` `RunContext` | Low | Low — field already exists (`base.py:56`) |
| Inline QA reporting + remove stale message | Trivial | Low |
| e2e verifiable-proof test (+ control) | Medium | Low — mirrors shipped `test_int_us_09_isolation_e2e.py` |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| End user (Success Criterion #4) | "hand an approved spec → code + tests + auto-fixed lint" works from one command | High — closes flagship US-3 |
| US-17 (SWE-Bench), US-19 (Fleet), US-22 (Contracts), US-24 (Scenarios) | All build on autonomous implementation; unblocked by closing US-3 | High — cascading epic unlock |
| Zero-trust posture | Autonomously generated (untrusted) code is executed sandboxed by default | High (security) |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| QA loop-back causes long autonomous runs / token burn | Medium | Medium | `max_retries ≤ 2`, `max_reflections = 3` (NFR-5) |
| Generated tests are flaky/fail → pipeline aborts | Medium | Low | Loop-back then surface a clear failure report (FR-6, FR-7) |
| Isolation default-on breaks hosts lacking git | Low | Medium | Clean skip/host-fallback (NFR-4); AD-5 keeps it configurable |
| Scope creep pulling in Podman (`D-EXEC-01`) | — | — | Explicitly excluded (NFR-1); documented in Feature Overview + AD-6 |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `new_feature.yaml` | Duplicates a generate→QA chain but lacks `lint_fix` | Could add `lint_fix` step for consistency once INT-US-03 lands | Low (follow-up) |
| `api/v1/implement.py` | Stale `Generator` signature (`# type: ignore[call-arg]`) — would fail at runtime | Should be fixed/aligned when REST-side autonomous implement is wired | Low (separate) |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Autonomous Implement Loop | How `sw implement` now runs QA + lint-fix in-pipeline, and how US-9 isolation bounds it | ⬜ To be written during Pre-commit (optional — small surface) |

## Sub-Feature Breakdown

### SF-01: Generation → QA Test Loop
- **Scope**: Extend the inline `implement_spec` pipeline so generated code+tests are validated in-pipeline — append `run_tests` (`VALIDATE`/`TESTS`, coverage) and `validate_code` (`VALIDATE`/`CODE`, C01–C08), resolve QA targets to the generated files, add the loop-back-on-fail gate, and report QA results inline.
- **FRs**: [FR-1, FR-3, FR-4, FR-6, FR-7]
- **Inputs**: Approved spec path; generator outputs `src/<stem>.py`, `tests/test_<stem>.py`; `RunContext` (llm, config, db).
- **Outputs**: `implement_spec` pipeline that runs tests + C01–C08 and surfaces `{passed, failed, coverage_pct, …}` inline.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf01_implementation_plan.md

### SF-02: Lint-Fix Reflection Loop Integration
- **Scope**: Append the `lint_fix` step (`LINT_FIX`/`CODE`, `ruff` auto-fix + LLM reflection loop) to the loop and extend inline reporting with `{reflections_used, lint_errors_remaining, auto_fixed}`.
- **FRs**: [FR-2]
- **Inputs**: The extended pipeline from SF-01; generated `src/<stem>.py`; `RunContext.llm` + `config`.
- **Outputs**: Autonomously lint-corrected code; lint outcome reported inline.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf02_implementation_plan.md

### SF-03: Zero-Trust Isolation + Verifiable Proof
- **Scope**: Thread the US-9 worktree-isolation policy into the `implement` `RunContext` (`enforce_isolation` from `SandboxSettings`; `use_worktree=None` on **all** steps incl. generate), thread the generated `src`/`tests` paths into `context.allowed_paths` so `strip_merge` preserves them (**AD-7 crux**), and deliver the e2e proof that **freshly generated** code runs QA worktree-bounded, plus the paired un-isolated control. **May require a short spike to confirm the per-step model carries generated artifacts (AD-7).**
- **FRs**: [FR-5, FR-8]
- **Inputs**: The full loop from SF-01 + SF-02; `SandboxSettings`; `allowed_paths`; git+bash.
- **Outputs**: Sandboxed autonomous implement loop; `tests/e2e/.../test_int_us_03_*_e2e.py` proving worktree-bounded QA on **generated** (not pre-committed) code + control.
- **Depends on**: [SF-01, SF-02]
- **Risk**: Highest of the three (AD-7). SF-01/SF-02 deliver the host-mode loop independently, so value ships even if SF-03 needs escalation.
- **Impl Plan**: docs/roadmap/features/topic_08_integration/INT-US-03/INT-US-03_sf03_implementation_plan.md

## Execution Order

1. **SF-01** — Generation → QA Test Loop (no deps — start immediately)
2. **SF-02** — Lint-Fix Reflection Loop Integration (depends on SF-01)
3. **SF-03** — Zero-Trust Isolation + Verifiable Proof (depends on SF-01, SF-02)

Linear DAG (SF-01 → SF-02 → SF-03); no parallelism (all three edit the same inline pipeline and its
`RunContext`, so serial execution avoids merge conflicts). Acyclic — verified.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Generation → QA Test Loop | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Lint-Fix Reflection Loop Integration | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Zero-Trust Isolation + Verifiable Proof | SF-01, SF-02, **INT-US-09-SF05** ✅ | ✅ | ✅ | ✅ | 🟡 | ⬜ |

## Session Handoff

**Current status**: Design **APPROVED**. **SF-01 committed to `main` (`cc1cec22`, 2026-07-18)** — the
generation→QA loop is live (host mode); full suite green (5271 passed).
**SF-01 + SF-02 committed to `main`** — the autonomous generation→QA→lint loop is live (host mode).
**SF-03 is UNBLOCKED (2026-07-21):** its dependency — per-run (session) worktree isolation — is delivered
(**`C-EXEC-06`** SF-01/02/03 committed; **`INT-US-09-SF05`** ✅; `TECH-012` resolved). AD-7's per-step crux is
**superseded** by session mode (generated code persists in one worktree; single end-of-run reconcile). SF-03
re-scopes to *consume* `C-EXEC-06`: thread the per-run policy into the implement `RunContext`
(`apply_session_policy`), apply the AD-5 default-on decision, and ship the FR-8 proof.
**Next step**: finalize the re-scoped `INT-US-03_sf03_implementation_plan.md`, then `/specweaver-dev` — closes
the US-3 base contract.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume
from there using the appropriate skill.
