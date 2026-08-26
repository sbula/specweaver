# Topic 06: Execution Sandbox (Safety)

Capabilities for process isolation, execution boundaries, and zero-trust environments.

Seven keyed fields per entry, plus optional `Limits:` and `Note:` — no prose (`R-ENTRY`). Values are written plainly.
**🟡 marks a guess** · **🔴 marks nothing found**. Markers are the exception.

## DAL-E: Prototyping

* **`E-EXEC-01` 🔜: Standard Local Execution**
  > - **Purpose:** 🔴 nothing anywhere says what this is for. The superseded entry was a title and no body
  > - **Trigger:** 🔴
  > - **Precondition:** 🔴
  > - **Reads:** 🔴
  > - **Produces:** 🔴
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`E-EXEC-02` 🔜: Air-Gapped Network Egress Control**
  > - **Purpose:** Stop a malicious dependency phoning out while its code is being validated or run
  > - **Trigger:** While generated or third-party code executes
  > - **Precondition:** 🟡 `B-EXEC-01` → the container boundary to enforce it in
  > - **Reads:** —
  > - **Produces:** 🟡 a refused outbound connection
  > - **Enables:** 🔴
  > - **Done when:** 🔴

## DAL-D: Internal Tooling

* **`D-EXEC-01` ✅: Podman/Docker Integration** (Legacy: 3.9)
  > - **Purpose:** Run the whole product from one command, without installing a Python toolchain on the host
  > - **Trigger:** When the container is started
  > - **Precondition:** —
  > - **Reads:** a volume-mounted `/projects` with strict path boundaries · `.env`
  > - **Produces:** a running `sw serve` on port 8000, with `SPECWEAVER_DATA_DIR` and `CORS_ORIGINS`
  > - **Enables:** remote dashboard access · CI/CD publishing to GHCR
  > - **Done when:** `podman run … ghcr.io/sbula/specweaver` serves a mounted project

* **`D-EXEC-02` ✅: Git Worktree Bouncer** (Legacy: 3.26)
  > - **Purpose:** Let an agent write freely without letting it write anywhere — work happens in a throwaway worktree, and only permitted paths come back
  > - **Trigger:** Per step, when an agent may modify files
  > - **Precondition:** —
  > - **Reads:** the target repository and the step's allowed paths
  > - **Produces:** a git worktree · a striped diff, rejecting writes to forbidden files before merge
  > - **Enables:** agentic IDEs working against the real repo safely
  > - **Done when:** a write outside the allowed paths is deleted rather than merged

## DAL-C: Enterprise Standard

* **`C-EXEC-01` ✅: Internal Layer Enforcement** (Legacy: 3.20a)
  > - **Purpose:** Keep SpecWeaver's own layers from collapsing into each other, mechanically rather than by review
  > - **Trigger:** When `tach check` runs
  > - **Precondition:** —
  > - **Reads:** `tach.toml` and the import graph
  > - **Produces:** a boundary violation report
  > - **Enables:** DDD layering that cannot quietly erode
  > - **Done when:** an L3 capability importing an L1 CLI dependency fails the check

* **`C-EXEC-02` ✅: Native CLI Nodes** (Legacy: 3.40)
  > - **Purpose:** Let a pipeline run a shell step — while making agent-authored commands impossible, since the script must already exist in a protected directory
  > - **Trigger:** When a pipeline step declares `action: bash`
  > - **Precondition:** `E-SENS-03` → the `FolderGrant` that protects the script directory
  > - **Reads:** hooks in `.specweaver/scripts/` — and nowhere else
  > - **Produces:** deterministic `stdout` piped into downstream steps · an `exit_code` the router can branch on
  > - **Enables:** terminal orchestration between AI loops
  > - **Done when:** a script outside the protected directory cannot be invoked
  > - **Note:** `FR-11` promises a fork-bombing script is capped. That promise rests on a backstop `B-EXEC-04` supersedes

* **`C-EXEC-03` ✅: Domain-Driven Module Consolidation** (Legacy: 3.26a)
  > - **Purpose:** Give every kind of thing one home — workflows, assurance, workspace, interfaces — so where code belongs is a rule rather than a habit
  > - **Trigger:** Always — a structural property of the tree
  > - **Precondition:** —
  > - **Reads:** —
  > - **Produces:** the `workflows/` · `assurance/` · `workspace/` · `interfaces/` layout
  > - **Enables:** `C-EXEC-01` → boundaries worth enforcing
  > - **Done when:** every module sits in the layer its archetype names

* **`C-EXEC-04` 🔜: Concurrent Git Merge Orchestration**
  > - **Purpose:** Merge parallel agents' work by meaning rather than by line, so two edits to one file need not collide
  > - **Trigger:** When parallel worktrees are reconciled
  > - **Precondition:** `C-FLOW-03` → the fan-out that produces them · `D-SENS-02` → the ASTs to merge
  > - **Reads:** the ASTs of the competing worktrees
  > - **Produces:** 🟡 a 3-way semantic merge · a halt and HITL flag on a true AST collision
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`C-EXEC-05` ⚰️ RETIRED:** *(Issue Tracker Atoms — absorbed into `B-INTL-09` Agent Memory Bank;
  see topic 04. ID is dead — do NOT reuse; the gap to `C-EXEC-06` is intentional.)*

* **`C-EXEC-06` ✅: Per-Run (Session) Worktree Isolation**
  > - **Purpose:** Isolate a whole untrusted run behind one authorization gate, instead of paying the per-step worktree cycle
  > - **Trigger:** When a run contains untrusted execution
  > - **Precondition:** `D-EXEC-02` → the worktree machinery
  > - **Reads:** the run's `allowed_paths`
  > - **Produces:** one ephemeral worktree per run · a single end-of-run strip-merge
  > - **Enables:** `C-EXEC-07` → the escalation that routes runs into it
  > - **Done when:** a whole run's mutations reach the repo only through one reconcile
  > - **Note:** it accumulates a whole run's untrusted mutations behind a single gate, so the `allowed_paths` strip-merge is the only decision protecting the real repo

* **`C-EXEC-07` 🔜: DAL-Escalated Isolation for Pipeline Runs**
  > - **Purpose:** Close the asymmetry where the most untrusted surface has the weakest default — `sw run` executes LLM-written tests over LLM-written code with less isolation than `sw implement`
  > - **Trigger:** When `sw run` or `sw resume` executes generated code
  > - **Precondition:** `C-EXEC-06` → the session isolation it escalates into
  > - **Reads:** the pipeline's derived allowed paths
  > - **Produces:** 🟡 an auto-escalated run inside session isolation
  > - **Enables:** `C-FLOW-12` → sequenced behind this
  > - **Done when:** 🔴
  > - **Limits:** not a one-line flip — `_derive_allowed_paths` is implement-shaped, so scenario artifacts would be silently dropped by the reconcile gate

## DAL-B: High-Assurance

* **`B-EXEC-01` ✅: Ephemeral Podman Sub-Containers** (Legacy: 3.45)
  > - **Purpose:** Run generated code where it cannot reach the host, the network, or anything but a scratch directory
  > - **Trigger:** When tests, lint, complexity, compile or architecture checks run — with `[sandbox] execution_mode = "container"`
  > - **Precondition:** `D-VAL-01` → the QA runner it routes through
  > - **Reads:** the source, mounted read-only
  > - **Produces:** results from a fail-closed container — `--network none`, non-root, read-write scratch only, guaranteed cleanup
  > - **Enables:** running untrusted generated code at all
  > - **Done when:** an opt-in container executes the checks and is always cleaned up
  > - **Limits:** defaults to unsandboxed host execution until explicitly enabled

* **`B-EXEC-02` 🔜: Tiered Access Rights** (Legacy: 4.4)
  > - **Purpose:** 🟡 Give each agent only the knowledge its tier permits, rather than the whole workspace
  > - **Trigger:** 🔴
  > - **Precondition:** `E-SENS-03` → the grant model to tier
  > - **Reads:** 🔴
  > - **Produces:** 🔴
  > - **Enables:** 🔴
  > - **Done when:** 🔴

* **`B-EXEC-03` 🔜: Blast Radius Enforcement** (Legacy: 4.8)
  > - **Purpose:** Bound what a change may touch using what the code actually calls, replacing the decomposer's LLM-guessed blast radius
  > - **Trigger:** 🟡 Before a change is applied
  > - **Precondition:** `B-SENS-02` → the graph · `TECH-068` → real edges · `B-SENS-08` → honest on framework code
  > - **Reads:** symbol-level `CALLS` and `IMPORTS` closure
  > - **Produces:** 🟡 an enforced locality bound
  > - **Enables:** `A-FLOW-04` → the circuit breaker on the same seam
  > - **Done when:** 🔴

* **`B-EXEC-04` 🔜: Kernel-Enforced Resource Bounds (cgroups v2)**
  > - **Purpose:** Actually cap a fork bomb. Today's backstop is `RLIMIT_NPROC`, which is **per-real-UID** — so it bounds the machine's user, and an idle machine already exceeds it
  > - **Trigger:** When a sandboxed process subtree runs
  > - **Precondition:** `B-EXEC-01` → the container boundary · Linux cgroups v2 delegation
  > - **Reads:** —
  > - **Produces:** `pids.max` scoped to a process subtree
  > - **Enables:** `C-EXEC-02` `FR-11` → a promise that currently rests on a mechanism that cannot keep it
  > - **Done when:** 🔴
  > - **Note:** supersedes `TECH-029`'s backstop — **remove it rather than layering on top**

## DAL-A: Mission-Critical

* **`A-EXEC-01` 🔜: Functional Sandboxing (Black Box Ledgers)** (Legacy: 3.46)
  > - **Purpose:** 🟡 Make every hand-off explicit on disk, so state is deterministic rather than carried in a conversation
  > - **Trigger:** 🟡 At every hand-off between steps
  > - **Precondition:** 🔴
  > - **Reads:** 🟡 a disk ledger
  > - **Produces:** 🟡 request in → context boots → result out, mechanically valid before the next hydration
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Limits:** trades execution speed for state determinism. Continuous chat context is disabled entirely

* **`A-EXEC-02` 🔜: Fuzzing Harnesses** (Legacy: 4.13)
  > - **Purpose:** 🟡 Find memory-safety defects by fuzzing generated native code, rather than by fixed scenarios
  > - **Trigger:** 🔴
  > - **Precondition:** `D-INTL-08` → the polyglot implement loop · a real native-code target
  > - **Reads:** the generated AST, for C++ / Rust targets
  > - **Produces:** 🟡 `libFuzzer` loops
  > - **Enables:** 🔴
  > - **Done when:** 🔴
  > - **Limits:** the trading system as planned is not a native-code target

* **`A-EXEC-03` ⚰️ RETIRED:** *(Rust PyO3 AST & Sandbox C-Bindings — retired 2026-08-20 by the
  [benefit review](../../analysis/benefit_chain_analysis_2026-08-20.md): it speeds steps that are
  milliseconds beside the LLM calls dominating every run, and no measured wait on the bouncer or
  extractor was ever recorded. ID is dead — do NOT reuse.)*

* **`A-EXEC-04` 🔜: Advanced Row-Level Task Locking**
  > - **Purpose:** 🟡 Keep many agents from corrupting shared task state, beyond what optimistic concurrency can hold
  > - **Trigger:** 🟡 When 20+ agents contend for task rows
  > - **Precondition:** `B-INTL-09` → its heartbeat and OCC foundation
  > - **Reads:** 🟡 task rows
  > - **Produces:** 🟡 pessimistic row locks · WAL2 evaluation · deadlock detection
  > - **Enables:** 🔴
  > - **Done when:** 🔴
