# Topic 07: Technical Debt & Architecture (TECH)

This document tracks all massive refactoring efforts, technical debt removal, and underlying
architectural epics required to ensure the platform remains stable, secure, and mathematically sound
as it scales to enterprise levels. These stories do not add new user-facing features but are
critical for long-term project viability.

## Domain-Driven Design (DDD)
* **`TECH-001` 🟢: Domain-Driven Design Unification**
  > [Description](../features/topic_07_technical_debt/TECH-001/TECH-001_design.md) | _(2026-07-13)_ | The codebase had drifted from its declared DDD/hexagonal structure, with domain logic reachable
  > from adapters. **DELIVERED:** unified across four sub-features; SF-04 landed 2026-08-02 (`346f64c3`), eliminating all three circular dependencies.

* **`TECH-025` 🟢: Registry IDs Leaking Into Proofs — FR Traceability Gap and Story-Named Tests (TECH-001 SF-01/02/03, TECH-002 SF-01..4, TECH-005 SF-01/2)**
  > [Description](../features/topic_07_technical_debt/TECH-025/TECH-025_design.md) | _(2026-08-02, widened three times.)_ | A registry ID leaking into something that outlives it: FR citations were
  > never made for three delivered stories, and nine test files plus three functions were named after the story that paid for them. **DELIVERED 2026-08-12** across seven sub-features; five FR ledgers
  > now exit 0 with a guard test against reopening.
* **`TECH-002` 🟢: BaseTool Registry Refactoring**
  > [Description](../features/topic_07_technical_debt/TECH-002/TECH-002_design.md) | Eliminates manual tool registration and automates dependency injection bindings for all sandbox tools via an
  > explicit `ToolRegistry` (`sandbox/registry.py`). Automatic registration via `__init_subclass__` was never implemented — the approved design deliberately rejected it (global import-time
  > auto-registration pollutes memory space and bypasses isolation limits) in favor of the explicit registry actually shipped. Status corrected because the mechanism this entry originally described
  > never existed.

## Architecture & Restructuring
* **`TECH-037` 🟢: Duplicated Code Is Found Only By Accident**
  > [Description](../features/topic_07_technical_debt/TECH-037/TECH-037_design.md) | _(2026-08-12 — raised by the user after `TECH-023` batch 7 and `TECH-035` each turned out to be duplication
  > findings wearing a complexity or cohesion label.)_ | **There was no duplicate-code check in this repo**, and `ruff` cannot provide one (`R0801` is not implemented). Every duplication fixed that
  > day was found *by accident*, two of them live defects rather than mere repetition. **DELIVERED 2026-08-12:** `jscpd` plus a content-keyed ratchet in the `cb` gate; clones reduced 148 → 123.

* **`TECH-020` 🟢: Extract the Step-Execution Loop from PipelineRunner**
  > [Description](../features/topic_07_technical_debt/TECH-020/TECH-020_design.md) | _(2026-07-27 — found by the INT-US-21 SF-03 CB-2 pre-commit gate.)_ | `runner.py` sat at exactly its 600-line RED
  > threshold, with `_execute_loop` spanning ~60% of the file behind a `# noqa: C901` — a suppression admitting the method was past the project's own bar. **DELIVERED 2026-08-12:** 599 → 292 lines,
  > `_execute_loop` 365 → 21, the `noqa` deleted.

* **`TECH-003` 🟢: Structural Refactoring of Workspace AST Module**
  > [Description](../features/topic_07_technical_debt/TECH-003/TECH-003_design.md) | To make the bounded context crystal clear, we want to introduce a dedicated `ast` boundary inside the workspace
  > module. This separates mechanical Tree-Sitter extraction (`parsers`) from output mapping (`adapters`).
* **`TECH-004` 🟢: Architectural Refactoring of `graph/` Bounded Context**
  > [Description](../features/topic_07_technical_debt/TECH-004/TECH-004_design.md) | Resolved: the standalone CLI command for graph building is **not** an architectural violation. Design doc `AD-2`
  > decided to keep the CLI as the Composition Root rather than centralize orchestration into a `GraphBuildAtom` or an autonomous `spinUp` workflow — no such Atom exists in `src/`, matching that
  > decision. _(2026-07-31: reworded — this previously read as an open question when the decision has been settled and shipped.)_

* **`TECH-016` 🟢: Unified Artifact Writer & Serialization Format Enforcement**
  > [Description](../features/topic_07_technical_debt/TECH-016/TECH-016_design.md) | _(Origin: INT-US-21 SF-02.)_ | Artifact writing and serialization were hand-rolled per site rather than going
  > through one writer, so format enforcement and lineage tagging drifted between them. **DELIVERED 2026-08-12** across both halves; §2's unified event tail also resolved `TECH-036` by construction,
  > since the shared helper carries the `None` guard and the never-raises contract.

* **`TECH-015` 🟢: Retire Grab-Bag Modules (Name-Says-Nothing Refactor)**
  > [Description](../features/topic_07_technical_debt/TECH-015/TECH-015_design.md) | _(Origin: INT-US-21.)_ | Grab-bag modules whose names promise nothing (`utils`, `helpers`, `commons` leaves)
  > accrete anything, and the dependency graph then routes around the accretion. **DELIVERED 2026-08-12:** three grab-bags split into eleven contract-named modules, with rule **R7** shipped so they
  > cannot regrow.

* **`TECH-034` 🟢: Split the AST Parser Hierarchy by Language Paradigm**
  > [Description](../features/topic_07_technical_debt/TECH-034/TECH-034_design.md) | _(2026-08-12)_ | The AST parser hierarchy put every language in one shape regardless of paradigm, so per-language
  > classes diverged silently. **DELIVERED 2026-08-12:** split by paradigm, with the shared reading and editing behaviour hoisted into mixins the base already modelled.

* **`TECH-035` 🟢: Chronically Failing Class-Health Gate**
  > [Description](../features/topic_07_technical_debt/TECH-035/TECH-035_design.md) | _(2026-08-12 — surfaced during `TECH-023` batch 2.)_ | `check_class_health.py` failed on a clean tree, 23 classes
  > of 397, and nobody had seen it because the gate's `changed` scope skipped it entirely unless a commit touched one of the 23. **DELIVERED 2026-08-12:** 19+1 → 4+0 without restructuring a single
  > class — all five reductions were measurement corrections.

* **`TECH-009` 🟢: Git & Filesystem Subprocess Migration to SubprocessExecutor**
  > [Description](../features/topic_07_technical_debt/TECH-009/TECH-009_design.md) | _(Origin: `C-EXEC-02` TID251 audit.)_ | Git and filesystem operations bypassed `SubprocessExecutor`, so they missed
  > its timeout escalation and credential stripping. **DELIVERED:** migrated behind the executor, leaving only the documented MCP exemption that `TECH-010` owns.

* **`TECH-010` 🔴: MCP Persistent-Process Executor Migration**
  > [Description](../features/topic_07_technical_debt/TECH-010/TECH-010_design.md) | _Status: STUB. Origin: `C-EXEC-02 SF-01` pre-commit `TID251` audit (2026-07-13)._ | `mcp/core/executor.py` keeps a
  > documented raw-`subprocess` exemption: its persistent, bidirectional process pattern is architecturally incompatible with `SubprocessExecutor.execute()`'s one-shot design. Needs a
  > long-lived-process executor abstraction rather than a mechanical migration.

* **`TECH-011` 🔴: Load-Time Params Validation for All Pipeline Step Types**
  > [Description](../features/topic_07_technical_debt/TECH-011/TECH-011_design.md) | _Status: STUB. Origin: `C-EXEC-02 SF-02` implementation-plan Phase 4, Q1 (2026-07-14)._ | `PipelineStep.params` is
  > opaque to `PipelineDefinition.validate_flow()`, so every step type's params are validated only when the step **executes** — potentially far into a long HITL-gated run. Combined with Pydantic
  > `extra="ignore"`, an author typo (e.g. `script:` at step level instead of under `params:`) surfaces as a confusing runtime handler error instead of an immediate load-time failure. Must apply to
  > **all** step types uniformly, not as a bash-specific special case.

* **`TECH-023` 🟢: Repo-Wide Cyclomatic Complexity Violations (complexipy)**
  > [Description](../features/topic_07_technical_debt/TECH-023/TECH-023_design.md) | _(2026-08-08)_ | Repo-wide cognitive complexity violations measured by `complexipy`, which replaced the C901
  > cyclomatic gate. **DELIVERED 2026-08-12/13: 98 → 0**, with the ratchet baseline empty. Several batches turned out to be duplication or cohesion findings wearing a complexity label, which is what
  > raised `TECH-037` and `TECH-035`.

* **`TECH-024` 🟢: Repo-Wide Dependency Cycles (check_coupling)**
  > [Description](../features/topic_07_technical_debt/TECH-024/TECH-024_design.md) | _(new, 2026-08-02 — found running `quality.py cb` for TECH-001 SF-04, confirmed chronic and unrelated via
  > `git stash`)_ | `check_coupling.py --cycles-only` reports 4 live import cycles: `assurance.validation.registry`/`rules.code.register`/`rules.spec.register` (3);
  > `core.flow.engine.runner`/`runner_utils`/`staleness`/`handlers.decompose`/`handlers.dual_pipeline`/`handlers.registry` (6, overlaps `TECH-020`/`TECH-015`'s files — coordinate sequencing, this
  > ticket owns only the import-direction defect); `infrastructure.llm.adapters._rate_limit`/`factory` (2); `interfaces.api.app`/`ui.htmx`/`v1.pipelines`/`v1.router`/`v1.ws` (5).

## Schema & Data Layer
* **`TECH-005` 🟢: Database Table Prefix Harmonization**
  > [Description](../features/topic_07_technical_debt/TECH-005/TECH-005_design.md) | _(2026-07-15)_ | Database tables were unprefixed, so separate bounded contexts collided in one SQLite file.
  > **DELIVERED:** all tables prefixed; SF-03 landed 2026-08-11 (`4ebb89cf`) covering the six raw-sqlite3 tables with a zero-data-loss migration path.

## Context Loading & RunContext Anti-Patterns
* **`TECH-036` 🟢: Lineage Telemetry Takes Down a Lint Fix That Already Succeeded**
  > [Description](../features/topic_07_technical_debt/TECH-036/TECH-036_design.md) | _(2026-08-12 — found while measuring `TECH-016` §2.)_ | `LintFixHandler._llm_fix` opened the telemetry DB with no
  > `None` guard, so a lint fix that had already written its corrected file was reported as a failed step. **RESOLVED 2026-08-12 by `TECH-016` §2** without its own implementation: unifying the event
  > tail gave every site the guard and the never-raises contract.

* **`TECH-021` 🟢: `loop_back` Discards the Failing Step's Result** — FIXED 2026-07-28
  > [Description](../features/topic_07_technical_debt/TECH-021/TECH-021_design.md) | _(2026-07-28 — found by the first test to drive a bundled pipeline through a HITL gate.)_ | When a gate's
  > `on_fail: loop_back` fired, the failing step's result was discarded, so the reason was never persisted and the user was parked at the wrong gate with nothing explaining why. **FIXED 2026-07-28:**
  > `_handle_loop_back` retains status and result before rewinding.

* **`TECH-006` 🟢: Context Loading Pipeline Refactoring**
  > [Description](../features/topic_07_technical_debt/TECH-006/TECH-006_design.md) | _(2026-07-21)_ | Context loading is spread across unrelated interface modules, and `RunContext` had grown into a
  > God Object — 23 fields and a 67-line `model_post_init`, one more field per feature. **DELIVERED:** SF-02 landed, `RunContext` 32 fields → 15 attributes. Sequencing for the remaining prompt-factory
  > move is a live decision under `C-INTL-06` / `C-FLOW-11` — see the design.

* **`TECH-014` 🟢: Fan-Out RunContext Isolation (Concurrent Sub-Run State Corruption)**
  > [Description](../features/topic_07_technical_debt/TECH-014/TECH-014_design.md) | _(Origin: INT-US-21.)_ | Concurrent sub-runs shared one `RunContext`, so fan-out could corrupt run state and
  > mis-attribute telemetry. **DELIVERED 2026-08-12:** fixed in `PipelineRunner.run`, covering all four fan-out sites rather than the one the ticket recorded.

## Security & Validation
* **`TECH-041` 🔴: The Code-Level DAL Override Is Unproven End to End (Needs a Scripted LLM)**
  > [Description](../features/topic_07_technical_debt/TECH-041/TECH-041_design.md) | _(2026-08-13 — found while fixing `TECH-017`'s vacuous-assertion findings.)_ | `C-VAL-03`'s DAL override is proven
  > at spec level and **not** at code level: every link is tested in isolation and the chain never. The test that appeared to prove it never executed `sw implement` at all. Needs a scripted LLM
  > adapter; the lenient-DAL control is the load-bearing half.

* **`TECH-007` 🟢: PromptBuilder Input Escaping & Pluggable Context Architecture**
  > [Description](../features/topic_07_technical_debt/TECH-007/TECH-007_design.md) | _(Origin: prompt-injection review.)_ | `PromptBuilder` interpolated caller-supplied content without escaping, so
  > analysed source could inject instructions into the prompt. **DELIVERED.** The longer-term shape — canonical on-disk files consumed by both `oneshot` slots and agentic work units — is a `C-INTL-06`
  > decision, recorded in the design.

* **`TECH-012` 🟢: Multi-Step Git-Worktree Isolation is Broken (Reconcile Never Commits; Crashes on Step 2)**
  > [Description](../features/topic_07_technical_debt/TECH-012/TECH-012_design.md) | _Origin: `INT-US-03 SF-03` implementation-plan Phase-0 spike (2026-07-19)._ | The per-step worktree model was
  > non-functional for multi-step untrusted loops: the reconcile never committed, and the second isolated step crashed. **✅ RESOLVED (2026-07-21) by `C-EXEC-06`** (per-run/session worktree isolation)
  > — retained as the record of the defect and of what fixed it.

* **`TECH-013` 🔴: API Composition Roots Do Not Resolve Worktree-Isolation Policy**
  > [Description](../features/topic_07_technical_debt/TECH-013/TECH-013_design.md) | _Status: STUB. Origin: recorded during `C-EXEC-06 SF-03` implementation-plan Phase 4 (2026-07-20)._ |
  > `C-EXEC-06 SF-03` wired session-isolation policy on the **CLI** composition root only. The API run sites (`interfaces/api/v1/pipelines.py`) resolve neither `enforce_isolation` nor the session
  > policy, so a run started through the REST API silently gets a different execution posture than the same run started from the CLI. `apply_session_policy` was written to be reusable verbatim here.

* **`TECH-017` 🔴: Integration-Contract Proof Audit (Test Tier Must Match Story Tier)**
  > [Description](../features/topic_07_technical_debt/TECH-017/TECH-017_design.md) | _(2026-07-26 — user mandate after INT-US-21 SF-02 CB-1 shipped 16 unit tests and **zero** integration/e2e.)_ | An
  > `INT-US-NN` story is an integration contract, so its proof must be integration and e2e tests. The valuable corollary: an integration story needing heavy unit testing means the capability stories
  > it integrates shipped incomplete. Deliverable is a per-story matrix of contract claims vs what a test proves, plus a tier-ratio guardrail at **planning** time. Evidence re-measured 2026-08-13 —
  > plan from the design's annotations, not its 2026-07-26 body, and take its cheapest-first phasing.

* **`TECH-018` 🟢: Delivered Add-On Re-Validation Against an Integrated Base (INT-US-21-SUB / C-INTL-01)**
  > [Description](../features/topic_07_technical_debt/TECH-018/TECH-018_design.md) | _(Origin: INT-US-21 design `AD-9`, user mandate 2026-07-25; relocated out of the feature 2026-07-26 so an audit of
  > a delivered story could not gate this epic.)_ | `INT-US-21-SUB` / `C-INTL-01` was delivered ✅ claiming coverage that was never exercised through a real `sw run feature_decomposition` journey — no
  > such journey could run. **AUDIT DELIVERED 2026-08-13**, audit-only: the claimed scope was never valid, the seams are proven by the base contract's own suite, and two findings were filed
  > (`TECH-038`, plus one handed to `TECH-017`).

* **`TECH-029` 🟢: Sandbox Process Cap Uses `RLIMIT_NPROC`, Which Bounds the User and Not the Sandbox**
  > [Description](../features/topic_07_technical_debt/TECH-029/TECH-029_design.md) | _(2026-08-12 — root cause of 18 of the 25 chronic Linux test failures.)_ | The sandbox process cap became
  > `setrlimit(RLIMIT_NPROC)`, which is per-real-UID and therefore bounded the **user** rather than the sandbox. **DELIVERED:** replaced by a best-effort backstop that is meant to be removed, not
  > extended, when `B-EXEC-04` lands kernel-enforced cgroups v2 `pids.max`.

* **`TECH-030` 🟢: An Empty `FolderGrant` Path Grants the Whole Project on POSIX and Nothing on Windows**
  > [Description](../features/topic_07_technical_debt/TECH-030/TECH-030_design.md) | _(2026-08-12)_ | An empty `FolderGrant` path granted the whole project on POSIX and nothing on Windows — the same
  > configuration meaning opposite things per platform, in a security primitive. **DELIVERED:** the empty path is now rejected rather than interpreted.

* **`TECH-032` 🟢: The Non-Python QA Runners Report an Absent Toolchain as Success**
  > [Description](../features/topic_07_technical_debt/TECH-032/TECH-032_design.md) | _(2026-08-12 — found during `TECH-031`.)_ | `run_tests`, `run_linter` and `run_architecture_check` all reported an
  > **absent toolchain as a clean run** — a vacuous proof inside the QA gate itself. **DELIVERED:** the runners now fail loudly; the discriminator is empty stdout rather than the exit code, since
  > pytest exits 4 for a missing `tests/` directory.

* **`TECH-033` 🟢: A Step's Retry Budget Resets on Every `sw resume`**
  > [Description](../features/topic_07_technical_debt/TECH-033/TECH-033_design.md) | _(2026-08-12)_ | `_execute_loop` re-initialised `attempts` on every entry, so each `sw resume` granted a fresh
  > three-strike budget and a failing step could retry indefinitely across sessions. **DELIVERED:** the budget is now inherited across resumes.

## Documentation & Knowledge Architecture
* **`TECH-047` 🔴: Nothing Runs the FR-Coverage Gate Across Delivered Work**
  > [Description](../features/topic_07_technical_debt/TECH-047/TECH-047_design.md) |
  > _(2026-08-13 — from `docs/analysis/test_coverage_audit_2026-08-13.md`.)_ |
  > `check_fr_coverage.py` works and takes a story ID, so it fires only when a human remembers a
  > story — and nobody remembers 47. **40 of 47 delivered capabilities exit `BLOCKED`.** Third
  > instance of one disease, after `check_story_preconditions` (INT-US-25) and `check_class_health`
  > ("nothing in scope" for a session). The hard part is not the sweep — it is that turning it on
  > produces 40 failures, and a ratchet nobody can act on says "40 unverified is fine".

* **`TECH-048` 🔴: A Design the FR Gate Cannot Parse Reports "Cannot Run", Not "Failed"**
  > [Description](../features/topic_07_technical_debt/TECH-048/TECH-048_design.md) |
  > _(2026-08-13 — same audit.)_ | `no FR rows parsed` collapses two different situations: a design
  > that states no requirements, and one whose requirements the parser **cannot read**.
  > `C-SENS-02` and `D-SENS-03` are the latter — from the outside indistinguishable from having
  > nothing to check. Small now; the failure mode scales, because every new design format silently
  > removes a capability from the gate's reach and nothing reports the reach shrinking. Must not
  > apply to `TECH` tickets, whose stub has no FR table by design.

* **`TECH-046` 🔴: `C-INTL-01` Shipped Without the Recursion It Was Designed For**
  > [Description](../features/topic_07_technical_debt/TECH-046/TECH-046_design.md) |
  > _(2026-08-13 — `TECH-038`'s follow-up, filed once the evidence said the scope was wrong.)_ |
  > `C-INTL-01`'s design is titled *"Automated iterative decomposition (multi-level)"* and specifies
  > recursion three ways — FR-3, AD-2 and an agent-sized split heuristic. None was built, and no
  > plan records a descope, while the entry says ✅. `check_fr_coverage.py C-INTL-01` has reported
  > `BLOCKED` since `TECH-025`; nothing ran it. Decide explicitly: build it, or delete the unbuilt
  > FR rows so the descoping is visible.

* **`TECH-044` 🟢: Registry Entries Carry Content Belonging Four Layers Down**
  > [Description](../features/topic_07_technical_debt/TECH-044/TECH-044_design.md) | _(2026-08-13 — raised by the user while reviewing `TECH-017`'s parser fix.)_ | `R-DEPTH` and `R-ENTRY` froze 2057
  > over-long lines and 41 over-long entries; this ticket is the backlog they froze. **"Move it to the design" is the wrong instruction** — the spine has four layers and one entry usually holds
  > content for three at once. Redistribution, never deletion.
* **`TECH-045` 🔴: Nothing Bounds a Document's Size**
  > [Description](../features/topic_07_technical_debt/TECH-045/TECH-045_design.md) |
  > _(2026-08-13 — raised by the user while reviewing `TECH-044`'s first redistribution.)_ |
  > `R-DEPTH` caps a line and `R-ENTRY` caps an entry; nothing caps a **file**, and
  > `check_file_sizes.py` covers `src tests scripts` only. Two documents already exceed 45 KB.
  > A single number will not fit — the same measurement that killed the entry-size cap applies —
  > so the design must decide whether to threshold per kind, catch only the tail, detect mixed
  > layers structurally, or accept that prose is unbounded.


* **`TECH-040` 🟢: `sw run --verbose` Showed No Handler Output**
  > [Description](../features/topic_07_technical_debt/TECH-040/TECH-040_design.md) | _(2026-08-13 — found while fixing `TECH-017`'s vacuous-assertion findings.)_ | `--verbose` is documented as *"Show
  > detailed handler output"*. Its traceback half always worked; the display half never did — `RichPipelineDisplay` stored `self._verbose` and nothing in `src/` read it, so a successful run looked
  > identical with and without the flag. **DELIVERED 2026-08-13:** step output now renders as a dimmed row under each step. The ticket's own headline overstated the defect as "does nothing" —
  > corrected in the design.

* **`TECH-039` 🟢: One Identifier Named Two Delivered Add-Ons (`INT-US-05-SUB` Collision)**
  > [Description](../features/topic_07_technical_debt/TECH-039/TECH-039_design.md) | _(2026-08-13 — found by `check_proof_tier.py` on its first run.)_ | `US-05_integration.md` gave **two different
  > delivered add-ons the same identifier**. **DELIVERED 2026-08-13:** repair, not a rename — the token never identified anything, and the master roadmap already declared both ids (`SF03`/`SF04`), so
  > the document was reconciled to the registry. Guardrail shipped: an identifier may name at most one entry, un-ratcheted. `OQ-1`'s divergence stays legal.

* **`TECH-038` 🟢: Registry Claims Recursive Decomposition the Capability Does Not Implement**
  > [Description](../features/topic_07_technical_debt/TECH-038/TECH-038_design.md) | _(2026-08-13 — `TECH-018` audit finding 1.)_ | `INT-US-21-SUB` is registered as *Recursive Planning*; the shipped
  > decomposer is one flat LLM call returning a non-nestable plan. **RESOLVED 2026-08-13: the scope is wrong, not the description.** `C-INTL-01` designed recursion three ways and never built it, so no
  > wording was changed — which wording is right depends on a scope decision, filed as `TECH-046`.

* **`TECH-026` 🟢: Roadmap Placement Contract — One Registry ID, One Line**
  > [Description](../features/topic_07_technical_debt/TECH-026/TECH-026_design.md) | _(2026-08-08 — found during `TECH-025` SF-02.)_ | No document stated what belongs in `master_story_roadmap.md`
  > versus a topic doc versus a design, so each agent derived the convention from whatever it grepped — and Topic 07 is where it grepped. **DELIVERED:** the contract written once as a shared
  > reference, plus `check_roadmap_placement.py` in the `doc` gate.

* **`TECH-027` 🟢: Sub-Feature Identifier Contract — Two Digits and an Explicit Owner**
  > [Description](../features/topic_07_technical_debt/TECH-027/TECH-027_design.md) | _(2026-08-11 — raised by the user while reviewing `TECH-026`.)_ | `SF-NN` is used project-wide and had never been
  > given a contract, producing two compounding defects: an unpadded/padded format split, and sub-features whose owner is not stated at all. **DELIVERED:** two digits and an explicit owner, enforced
  > by `check_conventions.py`.

* **`TECH-019` 🟢: Skill Instruction Integrity — Dangling Doc References and Contradictory Gate Orders**
  > [Description](../features/topic_07_technical_debt/TECH-019/TECH-019_design.md) | _(2026-07-26 — found by the INT-US-21 SF-02 CB-1 pre-commit gate.)_ | Skill instructions are never checked against
  > the repo they instruct on, so they rot silently and the agent absorbs the rot as truth. **DELIVERED 2026-08-08:** twelve dangling instruction sites repaired — six more than the ticket claimed —
  > two contradictory gate orders reconciled, and `check_skill_references.py` shipped into the `doc` gate.

* **`TECH-008` 🟢: Architectural Documentation Modularization**
  > [Description](../features/topic_07_technical_debt/TECH-008/TECH-008_design.md) | A severe structural refactoring of the monolithic `docs/architecture` directory. Slices the 46KB
  > `architecture_reference.md` and 17 loosely organized files into a visually-rich, GitHub-publishable static site structure perfectly aligned with Domain-Driven Design (Hexagonal Layers, Bounded
  > Contexts). Uses a Non-Destructive Copy-and-Verify strategy to guarantee zero data loss. Formalizes the Composition Root vs Factory debates into ADRs.


## Build & Packaging
* **`TECH-028` 🟢: Split `dev` Dependency Definitions — Broken Default Sync, Test Tooling in the Container Image**
  > [Description](../features/topic_07_technical_debt/TECH-028/TECH-028_design.md) | _(2026-08-11 — found while reproducing a fresh-clone setup.)_ | Two different definitions were both named `dev`, so
  > the default `uv sync` installed neither completely and test tooling leaked into the container image. **DELIVERED:** collapsed into one dependency-group, so plain `uv sync` now installs everything
  > the gates need.

* **`TECH-031` 🟡: The Container Prepare Phase Has Never Installed a Toolchain**
  > [Description](../features/topic_07_technical_debt/TECH-031/TECH-031_design.md) | _(2026-08-12 — found during `TECH-028`, re-scoped the same day once measured against live podman.)_ | Three chained
  > defects mean the container prepare phase has never installed a toolchain. **Latent, not live:** `execution_mode` defaults to `"host"`, and the fourth defect — QA runners reporting an absent
  > toolchain as a clean run — is fixed (`TECH-032`).
