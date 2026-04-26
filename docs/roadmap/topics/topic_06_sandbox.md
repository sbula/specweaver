# Topic 06: Execution Sandbox (Safety)

This document tracks all capabilities related to process isolation, execution boundaries, and zero-trust environments.

## DAL-E: Prototyping
* **`E-EXEC-01` 🔜: Standard Local Execution**

## DAL-D: Internal Tooling
* **`D-EXEC-01` ✅: Podman/Docker Integration** (Legacy: 3.9)<br>
  > _(new)_ | `Containerfile` bundling Python + `sw` CLI + SQLite + `sw serve`. Volume-mount `/projects` for host file access with strict path boundaries. Port: 8000 (unified). One-command deployment: `podman run --env-file .env -v ./myproject:/projects -p 8000:8000 ghcr.io/sbula/specweaver`. Centralized `config/paths.py` with `SPECWEAVER_DATA_DIR` env var. `CORS_ORIGINS` env var for remote dashboard access. CI/CD via GitHub Actions → GHCR. **Complete:** 3160 tests.
* **`D-EXEC-02` ✅: Git Worktree Bouncer** (Legacy: 3.26)<br>
  > [Design ✅](phase_3/feature_3.26/feature_3.26_design.md) | Provides dictatorial validation while fully supporting native IDEs. Clones current target to a `git worktree` for the Agentic IDE. Mathematical diff striping auto-rejects and deletes LLM hallucinations to forbidden files before merge. **Complete**: 3884 tests.

## DAL-C: Enterprise Standard
* **`C-EXEC-01` ✅: Internal Layer Enforcement** (Legacy: 3.20a)<br>
  > _(split from 3.20)_ | Installed and configured Tach to enforce strict Domain-Driven layer isolation inside SpecWeaver's internal architecture, deleting `__init__.py` boilerplate and stopping L3 capabilities from importing L1 CLI dependencies. **Complete**: Replaced Ruff TID252, globally enforced implicitly bound namespaces, and subsumed legacy C05 rules to use Tach.
* **`C-EXEC-02` 🔜: Native CLI Nodes** (Legacy: 3.40)<br>
  > _(inspired by Archon)_ | Augments 3.40 to introduce declarative `action: bash` pipeline steps. Mandates that all referenced hooks physically reside in the `FolderGrant`-protected `.specweaver/scripts/` directory to prevent Agent RCE. Pipes deterministic `stdout` cleanly into downstream pipeline states, enabling robust terminal orchestration between AI loops.

* **`C-EXEC-03` ✅: Domain-Driven Module Consolidation** (Legacy: 3.26a)<br>
  > _(from 3.26 discussion)_ | Massive architectural refactoring of flat directories into strict DDD boundaries. Moves L1-L5 phases to `workflows/` (drafting, review, implementation, planning), pure-logic discovery to `assurance/` (standards, validation), physical state to `workspace/` (project, context), and external endpoints to `interfaces/` (api, cli). Fixes all absolute Python imports across 3800 tests.
## DAL-B: High-Assurance
* **`B-EXEC-01` 🔜: Ephemeral Podman Sub-Containers** (Legacy: 3.45)<br>
  > _(new)_ | Resolves Agent RCE vulnerabilities. When `QARunner` executes LLM-generated tests (`pytest`), execution routes natively into ephemeral, headless Podman/Docker sub-containers instead of the host machine.
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
