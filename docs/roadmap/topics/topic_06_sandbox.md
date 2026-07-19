# Topic 06: Execution Sandbox (Safety)

This document tracks all capabilities related to process isolation, execution boundaries, and zero-trust environments.

## DAL-E: Prototyping
* **`E-EXEC-01` 🔜: Standard Local Execution**
* **`E-EXEC-02` 🔜: Air-Gapped Network Egress Control**
  > _(new)_ | Hardened execution boundary preventing malicious dependencies from establishing outward network connections during the validation and execution phases.

## DAL-D: Internal Tooling
* **`D-EXEC-01` ✅: Podman/Docker Integration** (Legacy: 3.9)<br>
  > _(new)_ | `Containerfile` bundling Python + `sw` CLI + SQLite + `sw serve`. Volume-mount `/projects` for host file access with strict path boundaries. Port: 8000 (unified). One-command deployment: `podman run --env-file .env -v ./myproject:/projects -p 8000:8000 ghcr.io/sbula/specweaver`. Centralized `config/paths.py` with `SPECWEAVER_DATA_DIR` env var. `CORS_ORIGINS` env var for remote dashboard access. CI/CD via GitHub Actions → GHCR. **Complete:** 3160 tests.
* **`D-EXEC-02` ✅: Git Worktree Bouncer** (Legacy: 3.26)<br>
  > [Design ✅](phase_3/feature_3.26/feature_3.26_design.md) | Provides dictatorial validation while fully supporting native IDEs. Clones current target to a `git worktree` for the Agentic IDE. Mathematical diff striping auto-rejects and deletes LLM hallucinations to forbidden files before merge. **Complete**: 3884 tests.

## DAL-C: Enterprise Standard
* **`C-EXEC-01` ✅: Internal Layer Enforcement** (Legacy: 3.20a)<br>
  > _(split from 3.20)_ | Installed and configured Tach to enforce strict Domain-Driven layer isolation inside SpecWeaver's internal architecture, deleting `__init__.py` boilerplate and stopping L3 capabilities from importing L1 CLI dependencies. **Complete**: Replaced Ruff TID252, globally enforced implicitly bound namespaces, and subsumed legacy C05 rules to use Tach.
* **`C-EXEC-02` ✅: Native CLI Nodes** (Legacy: 3.40)<br>
  > _(inspired by Archon)_ | Augments 3.40 to introduce declarative `action: bash` pipeline steps. Mandates that all referenced hooks physically reside in the `FolderGrant`-protected `.specweaver/scripts/` directory to prevent Agent RCE. Pipes deterministic `stdout` cleanly into downstream pipeline states, enabling robust terminal orchestration between AI loops. **Complete**: SF-1 (BashActionAtom Core Execution), SF-2 (Pipeline Engine Integration — `BashActionHandler`, router branching on `exit_code`, `step_records` propagation), and SF-3 (Scaffold, Boundary Config, and Docs) all done.
* **`C-EXEC-03` ✅: Domain-Driven Module Consolidation** (Legacy: 3.26a)<br>
  > _(from 3.26 discussion)_ | Massive architectural refactoring of flat directories into strict DDD boundaries. Moves L1-L5 phases to `workflows/` (drafting, review, implementation, planning), pure-logic discovery to `assurance/` (standards, validation), physical state to `workspace/` (project, context), and external endpoints to `interfaces/` (api, cli). Fixes all absolute Python imports across 3800 tests.
* **`C-EXEC-04` 🔜: Concurrent Git Merge Orchestration**<br>
  > _(new)_ | Advanced flow-engine capability for Multi-Spec Pipeline Fan-Out. Uses 3-way AST semantic merging (rather than text-line merging) to automatically resolve non-overlapping AST conflicts from parallel agent worktrees. Halts and flags AST collisions for HITL.
* **`C-EXEC-05` ⚰️ RETIRED:** *(Issue Tracker Atoms — absorbed into `B-INTL-09` Agent Memory Bank; see topic_04. ID is dead — do NOT reuse; the gap to `C-EXEC-06` is intentional.)*
* **`C-EXEC-06` 🟡: Per-Run (Session) Worktree Isolation**<br>
  > _(new; origin: INT-US-03 SF-03 spike, resolves `TECH-012`)_ | A **session-scoped** isolation mode for the flow engine: run a whole untrusted **span** of steps inside **one** ephemeral git worktree with a **single** end-of-run reconcile — instead of `D-EXEC-02`'s per-step create/reconcile/teardown. Generated code persists in the worktree across steps (generate → lint-fix → run tests → validate all see it), then the final diff is strip-merged back once. **Why DAL-C, not DAL-D like its `D-EXEC-02` sibling:** it accumulates a whole run's untrusted mutations behind a single authorization gate (the `allowed_paths` strip-merge is the sole decision on what lands in the user's *real* repo), it is the enabler of *fully autonomous* untrusted execution, and it is the merge/worktree-orchestration risk class of `C-EXEC-04`. Improper implementation → sandbox escape (generated pytest runs against the real source tree), unauthorized write-back to the user's branch, silent data loss, or false-safety. **Scope:** (a) session-worktree lifecycle (create-once/reconcile-once/teardown-once, unique branch, no orphaned branches); (b) a real `RunContext.allowed_paths` field, populated at the composition root; (c) commit-the-worktree-tree-before-reconcile so generated files actually survive; (d) stop swallowing `worktree_sync` failures; (e) a multi-step, freshly-generated-file e2e proof (the coverage gap that hid `TECH-012`). Extends the Git Worktree Bouncer (`D-EXEC-02`); integrated into the US-9 policy by `INT-US-09-SF05`; consumed by `INT-US-03 SF-03`. **Design APPROVED (2026-07-19); SF-01 (session lifecycle) in progress; SF-02 (reconcile) + SF-03 (policy + e2e) pending.**


## DAL-B: High-Assurance
* **`B-EXEC-01` ✅: Ephemeral Podman Sub-Containers** (Legacy: 3.45)<br>
  > [B-EXEC-01_design.md](../features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_design.md) | Resolves Agent RCE vulnerabilities. `QARunnerAtom`/`PythonQARunner` can route test/lint/complexity/compile/architecture-check execution through a new `ContainerSubprocessExecutor` — an opt-in (`[sandbox] execution_mode = "container"`), fail-closed Podman/Docker sandbox with a read-only source mount, a separate read-write scratch mount for test artifacts, `--network none` egress, non-root `--user`, and guaranteed container cleanup. Defaults to today's unsandboxed host execution until explicitly enabled.
* **`B-EXEC-02` 🔜: Tiered Access Rights** (Legacy: 4.4)<br>
  > `future_capabilities_reference.md` §1 | Tiered access rights (zero-trust knowledge)
* **`B-EXEC-03` 🔜: Blast Radius Enforcement** (Legacy: 4.8)<br>
  > `future_capabilities_reference.md` §16 | Blast radius / locality enforcement

## DAL-A: Mission-Critical
* **`A-EXEC-01` 🔜: Functional Sandboxing (Black Box Ledgers)** (Legacy: 3.46)<br>
  > _(new)_ | Completely disables continuous chat context. Hand-offs managed explicitly via disk ledger: `Request in` → `Context boots` → `Result out` → mechanically valid before next hydration. Prioritizes state determinism over execution speed.
* **`A-EXEC-02` 🔜: Fuzzing Harnesses** (Legacy: 4.13)<br>
  > _(new)_ | Replaces parameterised scenarios with dynamically written `libFuzzer` logic loops against the generated AST for deep memory safety checks on C++/Rust targets.
* **`A-EXEC-03` 🔜: Rust PyO3 AST & Sandbox C-Bindings** (Legacy: Backlog)<br>
  > _(new)_ | Polyglot AST Skeleton Extractor & Macro Evaluator natively in Rust (using Rayon for C-level concurrency). Git Worktree Bouncer Sandbox: Replace the OS-level `subprocess.run(["git"])` Python diff-striping mechanics with native Rust `libgit2` C-bindings.
* **`A-EXEC-04` 🔜: Advanced Row-Level Task Locking**
  > _(new)_ | Advanced transactional concurrency beyond basic OCC. Pessimistic row-level locking (SELECT FOR UPDATE semantics), WAL2 mode evaluation, and multi-agent deadlock detection for fleets of 20+ simultaneous agents. Builds on `B-INTL-09`'s basic heartbeat/OCC foundation.
