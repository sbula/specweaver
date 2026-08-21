# Topic 06: Execution Sandbox (Safety)

This document tracks all capabilities related to process isolation, execution boundaries, and zero-trust environments.

## DAL-E: Prototyping
* **`E-EXEC-01` 🔜: Standard Local Execution**
* **`E-EXEC-02` 🔜: Air-Gapped Network Egress Control**
  > _(new)_ | Hardened execution boundary preventing malicious dependencies from establishing outward network connections during the validation and execution phases.

## DAL-D: Internal Tooling
* **`D-EXEC-01` ✅: Podman/Docker Integration** (Legacy: 3.9)<br>
  > _(new)_ | `Containerfile` bundling Python + `sw` CLI + SQLite + `sw serve`. Volume-mount `/projects` for host file access with strict path boundaries. Port: 8000 (unified). One-command deployment:
  > `podman run --env-file .env -v ./myproject:/projects -p 8000:8000 ghcr.io/sbula/specweaver`. Centralized `config/paths.py` with `SPECWEAVER_DATA_DIR` env var. `CORS_ORIGINS` env var for remote
  > dashboard access. CI/CD via GitHub Actions → GHCR. **Complete:** 3160 tests.
* **`D-EXEC-02` ✅: Git Worktree Bouncer** (Legacy: 3.26)<br>
  > [Design ✅](phase_3/feature_3.26/feature_3.26_design.md) | Provides dictatorial validation while fully supporting native IDEs. Clones current target to a `git worktree` for the Agentic IDE.
  > Mathematical diff striping auto-rejects and deletes LLM hallucinations to forbidden files before merge. **Complete**: 3884 tests.

## DAL-C: Enterprise Standard
* **`C-EXEC-01` ✅: Internal Layer Enforcement** (Legacy: 3.20a)<br>
  > _(split from 3.20)_ | Installed and configured Tach to enforce strict Domain-Driven layer isolation inside SpecWeaver's internal architecture, deleting `__init__.py` boilerplate and stopping L3
  > capabilities from importing L1 CLI dependencies. **Complete**: Replaced Ruff TID252, globally enforced implicitly bound namespaces, and subsumed legacy C05 rules to use Tach.
* **`C-EXEC-02` ✅: Native CLI Nodes** (Legacy: 3.40)<br>
  > _(inspired by Archon)_ | Augments 3.40 to introduce declarative `action: bash` pipeline steps. Mandates that all referenced hooks physically reside in the `FolderGrant`-protected
  > `.specweaver/scripts/` directory to prevent Agent RCE. Pipes deterministic `stdout` cleanly into downstream pipeline states, enabling robust terminal orchestration between AI loops. **Complete**:
  > SF-01 (BashActionAtom Core Execution), SF-02 (Pipeline Engine Integration — `BashActionHandler`, router branching on `exit_code`, `step_records` propagation), and SF-03 (Scaffold, Boundary Config,
  > and Docs) all done.
* **`C-EXEC-03` ✅: Domain-Driven Module Consolidation** (Legacy: 3.26a)<br>
  > _(from 3.26 discussion)_ | Massive architectural refactoring of flat directories into strict DDD boundaries. Moves L1-L5 phases to `workflows/` (drafting, review, implementation, planning),
  > pure-logic discovery to `assurance/` (standards, validation), physical state to `workspace/` (project, context), and external endpoints to `interfaces/` (api, cli). Fixes all absolute Python
  > imports across 3800 tests.
* **`C-EXEC-04` 🔜: Concurrent Git Merge Orchestration**<br>
  > _(new)_ | Advanced flow-engine capability for Multi-Spec Pipeline Fan-Out. Uses 3-way AST semantic merging (rather than text-line merging) to automatically resolve non-overlapping AST conflicts
  > from parallel agent worktrees. Halts and flags AST collisions for HITL.
* **`C-EXEC-05` ⚰️ RETIRED:** *(Issue Tracker Atoms — absorbed into `B-INTL-09` Agent Memory Bank; see topic_04. ID is dead — do NOT reuse; the gap to `C-EXEC-06` is intentional.)*
* **`C-EXEC-06` ✅: Per-Run (Session) Worktree Isolation**<br>
  > [Description](../features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_design.md) | _(Origin: INT-US-03 SF-03 spike; resolves `TECH-012`.)_ | A **session-scoped** isolation mode: a whole untrusted span of
  > steps runs inside one ephemeral git worktree with a single end-of-run reconcile, instead of `D-EXEC-02`'s per-step cycle. **DAL-C rather than DAL-D** because it accumulates a whole run's untrusted
  > mutations behind a single authorization gate — the `allowed_paths` strip-merge is the sole decision on what reaches the real repo.
* **`C-EXEC-07` 🔜: DAL-Escalated Isolation for Pipeline Runs**<br>
  > [Description](../features/topic_06_sandbox/C-EXEC-07/C-EXEC-07_design.md) | _(2026-07-24 — minted from INT-US-24 SF-03 intake.)_ | Extends the shipped `AD-8` escalation from the `sw implement`
  > root to `sw run`/`sw resume`, so any journey executing generated code auto-escalates into `C-EXEC-06` session isolation. Closes the asymmetry where the most untrusted surface has the weakest
  > default. **Not a one-line flip:** `_derive_allowed_paths` is implement-shaped, so scenario artifacts would be silently dropped by the reconcile gate. Integrated by `INT-US-09-SF06`.


## DAL-B: High-Assurance
* **`B-EXEC-01` ✅: Ephemeral Podman Sub-Containers** (Legacy: 3.45)<br>
  > [B-EXEC-01_design.md](../features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_design.md) | Resolves Agent RCE vulnerabilities. `QARunnerAtom`/`PythonQARunner` can route
  > test/lint/complexity/compile/architecture-check execution through a new `ContainerSubprocessExecutor` — an opt-in (`[sandbox] execution_mode = "container"`), fail-closed Podman/Docker sandbox with
  > a read-only source mount, a separate read-write scratch mount for test artifacts, `--network none` egress, non-root `--user`, and guaranteed container cleanup. Defaults to today's unsandboxed host
  > execution until explicitly enabled.
* **`B-EXEC-02` 🔜: Tiered Access Rights** (Legacy: 4.4)<br>
  > `future_capabilities_reference.md` §1 | Tiered access rights (zero-trust knowledge)
* **`B-EXEC-03` 🔜: Blast Radius Enforcement** (Legacy: 4.8)<br>
  > `future_capabilities_reference.md` §16 | Blast radius / locality enforcement.
  > **Data source** _(2026-08-21, [ADR-006](../../architecture/07_architectural_decision_records/adr_006_graphs_are_truth_vectors_are_discovery.md))_:
  > the `B-SENS-02` graph — symbol-level `CALLS`/`IMPORTS` closure, replacing the decomposer's LLM-guessed
  > blast radius. Sequenced behind `TECH-068`; honest on framework code only with `B-SENS-08`.

* **`B-EXEC-04` 🔜: Kernel-Enforced Resource Bounds (cgroups v2)**<br>
  > [Design](../features/topic_06_sandbox/B-EXEC-04/B-EXEC-04_design.md) | _(2026-08-12 — split out of `TECH-029`.)_ | `C-EXEC-02` FR-11 promises a fork-bombing script is capped by default; on Linux
  > the field maps to `RLIMIT_NPROC`, which is per-real-UID and counts tasks, so an idle machine already exceeds the cap. cgroups v2 `pids.max` is the mechanism that can scope to a process subtree.
  > **Supersedes `TECH-029`'s backstop — remove it rather than layering on top.**

## DAL-A: Mission-Critical
* **`A-EXEC-01` 🔜: Functional Sandboxing (Black Box Ledgers)** (Legacy: 3.46)<br>
  > _(new)_ | Completely disables continuous chat context. Hand-offs managed explicitly via disk ledger: `Request in` → `Context boots` → `Result out` → mechanically valid before next hydration.
  > Prioritizes state determinism over execution speed.
* **`A-EXEC-02` 🔜: Fuzzing Harnesses** (Legacy: 4.13)<br>
  > _(new)_ | Replaces parameterised scenarios with dynamically written `libFuzzer` logic loops against the generated AST for deep memory safety checks on C++/Rust targets.
  > **Gated** _(2026-08-20 [benefit review](../../analysis/benefit_chain_analysis_2026-08-20.md))_: sequenced behind `D-INTL-08` (polyglot implement loop) AND a
  > real native-code target — the trading system as planned is not one.
* **`A-EXEC-03` ⚰️ RETIRED:** *(Rust PyO3 AST & Sandbox C-Bindings — retired 2026-08-20 by the
  [benefit review](../../analysis/benefit_chain_analysis_2026-08-20.md): it speeds steps that are milliseconds beside the LLM calls dominating every run; no
  measured wait on the bouncer or extractor was ever recorded. ID is dead — do NOT reuse.)*
* **`A-EXEC-04` 🔜: Advanced Row-Level Task Locking**
  > _(new)_ | Advanced transactional concurrency beyond basic OCC. Pessimistic row-level locking (SELECT FOR UPDATE semantics), WAL2 mode evaluation, and multi-agent deadlock detection for fleets of
  > 20+ simultaneous agents. Builds on `B-INTL-09`'s basic heartbeat/OCC foundation.
