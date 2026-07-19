# US-09 Integration - Integration Contracts

## Base Story Contract (`INT-US-09`)
* **Status:** ✅ Done (2026-07-17) for the **single-step** case — implemented across 4 commit boundaries (`85d02be4`, `f4077870`, `bd6913c6`, `474490ae`). ⚠️ **Known defect (2026-07-19, `TECH-012`):** the per-step reconcile is non-functional for **multi-step** isolated pipelines — the second isolated step crashes on a branch-name collision, and generated (uncommitted) files never survive between steps (`worktree_sync` swallows its rebase failure; `allowed_paths` field is absent). Masked because every isolation test drives a single step over pre-committed files. Fix = **`INT-US-09-SF05`** (below). **Backlog (deferred, documented):** API-run policy wiring (`interfaces/api/v1/pipelines.py`); container add-on = `INT-US-09-SF01`.
* **Design:** [INT-US-09_design.md](../../features/topic_08_integration/INT-US-09/INT-US-09_design.md)
* **Integration Description:** The three already-built Core-Required (MVS) capabilities — **US-5 Core** (Git Worktree Bouncer / `D-EXEC-02`), **E-EXEC-01** (Standard Local Execution / `SubprocessExecutor`), and **C-EXEC-02** (Native CLI Action Nodes / `BashActionAtom`) — must be wired into one enforceable, **container-free** host-execution flow. Untrusted execution runs inside an ephemeral git-worktree sandbox with the `SubprocessExecutor` security boundary (credential stripping, resource limits, `cwd` containment) rebound to the worktree path — so bash actions and QA execution operate worktree-bounded rather than against the real source root — and source changes are reconciled back via the existing "Main-Branch Wins" strip-merge (out-of-bounds hunks stripped per `context.yaml`). Isolation is enabled by an opt-in US-9 policy (`SandboxSettings`, resolved at the composition root); default-off preserves today's behavior exactly.
* **Verifiable Proof:** `tests/e2e/sandbox/test_int_us_09_isolation_e2e.py` — a real-worktree, unmocked e2e suite (5 scenarios): a real `action: bash` step and a real `run_tests`/pytest step each run bounded to an ephemeral git worktree under the opt-in US-9 policy (process `pwd`/`cwd` inside `.worktrees/`, real source root not mutated), with un-isolated controls proving the rebind is gated.

> [!NOTE]
> **Container-free scope.** This Base Contract is **strictly the non-container host-execution
> integration** of `US-5 Core` + `E-EXEC-01` + `C-EXEC-02`. Containerization
> (`B-EXEC-01` Ephemeral Podman Sub-Containers, `D-EXEC-01` Podman/Docker Integration) is **NOT**
> part of it — it belongs to the separate **`INT-US-09-SF01` (Containerized Isolation)** add-on
> sub-story below. `B-EXEC-01`'s `ContainerSubprocessExecutor` is built and complete
> ([design](../../features/topic_06_sandbox/B-EXEC-01/B-EXEC-01_design.md)); wiring it in as an
> enforced default is that add-on's job, not this Base Contract's.

## Sub-Story Add-Ons

Layered on top of the Base Contract; each is a separate integration contract (Pending Design).

* **`INT-US-09-SF01` — Containerized Isolation:** integrate `B-EXEC-01` (Ephemeral Podman
  Sub-Containers, built ✅) + `D-EXEC-01` (Podman/Docker Integration, built ✅) so container
  execution can become an enforced US-9 default. *Pending Design — container-scoped, out of scope
  for the Base Contract.*
* **`INT-US-09-SF02` — Security Defenses:** blocked on `E-EXEC-02` (Air-Gapped Network Egress
  Control, unbuilt).
* **`INT-US-09-SF03` — Extreme Execution Paranoia:** blocked on `A-EXEC-01` (Functional Agent
  Sandboxing / Black Box Ledgers, unbuilt).
* **`INT-US-09-SF04` — Mathematical Speed & Security (Rust):** blocked on `A-EXEC-03` (Git Worktree
  Bouncer C-Bindings / Rust PyO3, unbuilt).
* **`INT-US-09-SF05` — Per-Run (Session) Worktree Isolation:** *Pending Design.* **Integrates the new
  capability `C-EXEC-06`** (Per-Run/Session Worktree Isolation — the actual build) into the US-9 policy:
  wires it at the composition root, threads `RunContext.allowed_paths`, and delivers a real multi-step,
  freshly-generated-file e2e proof. Like every US-9 add-on, the SF is **integration only** — the build
  lives in the capability:
  * **`C-EXEC-06` (capability, `🔜` to build):** run a whole untrusted **span** of steps in **one**
    ephemeral worktree with a **single** end-of-run reconcile (instead of per-step
    create/reconcile/teardown). Generated code persists in the worktree across steps, lint fixes it in
    place, pytest runs on it in place, then the final diff is strip-merged back once. Adds the missing
    `allowed_paths` field + a commit-before-reconcile step; **resolves the `TECH-012` defect**. Extends the
    Git Worktree Bouncer family (`D-EXEC-02`).
  * **Critical path:** this is what `INT-US-03 SF-03` consumes to run `sw implement` worktree-bounded — so
    building `C-EXEC-06` + `INT-US-09-SF05` is the blocker for closing the US-3 flagship epic.
