# US-09 Integration - Integration Contracts

## Base Story Contract (`INT-US-09`)
* **Status:** ✅ Done (2026-07-17) for the **single-step** case — implemented across 4 commit boundaries (`85d02be4`, `f4077870`, `bd6913c6`, `474490ae`). ✅ **Multi-step case resolved (2026-07-21, `TECH-012`):** the per-step reconcile was non-functional for **multi-step** isolated pipelines (second step crashed on a branch-name collision; generated uncommitted files never survived between steps). Resolved by the **per-run (session) worktree mode** (`C-EXEC-06`, integration `INT-US-09-SF05` — both ✅): a whole untrusted span runs in one worktree with a single authorized reconcile. The legacy **per-step** model remains single-step-only (multi-step per-step isolation is a documented limitation — use session mode). **Backlog (deferred, documented):** API-run policy wiring (`interfaces/api/v1/pipelines.py`, tracked as `TECH-013`); container add-on = `INT-US-09-SF01`.
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
* **`INT-US-09-SF05` — Per-Run (Session) Worktree Isolation:** ✅ **Done (delivered by `C-EXEC-06`,
  2026-07-21).** No separate design was needed — this SF's entire integration scope was absorbed by the
  capability's own sub-features. Details below.
  * **`C-EXEC-06` (capability, ✅ complete — SF-01/02/03 committed):** runs a whole untrusted **span** of
    steps in **one** ephemeral worktree with a **single** end-of-run reconcile (instead of per-step
    create/reconcile/teardown). Generated code persists in the worktree across steps, lint fixes it in
    place, pytest runs on it in place, then the final diff is strip-merged back once. Added the
    `allowed_paths` field + a commit-before-reconcile step; **resolves the `TECH-012` defect**. Extends the
    Git Worktree Bouncer family (`D-EXEC-02`).

  ### Why `INT-US-09-SF05` is already done (no design required)

  SF-05's three stated deliverables — *(1) wire the capability at the composition root, (2) thread
  `RunContext.allowed_paths`, (3) a multi-step freshly-generated-file e2e proof* — were each delivered by
  `C-EXEC-06`'s own sub-features. When `C-EXEC-06` was decomposed (2026-07-19), its **SF-03**
  (Composition-Root Policy + Allow-List + Verifiable Proof) was scoped to exactly this integration work, so a
  separate SF-05 landing became redundant:

  | SF-05 deliverable | Delivered by | Evidence |
  |---|---|---|
  | Wire the per-run policy at the composition root | `C-EXEC-06` SF-03 (`bd5cedd2`) | `[sandbox] enforce_session_isolation` opt-in knob resolved by `apply_session_policy` at the `sw run`/`sw resume` composition roots (`core/flow/interfaces/cli.py`); default-off ⇒ byte-identical behavior. |
  | Thread `RunContext.allowed_paths` | SF-01 (field, `aac3f126`) + SF-03 (populate) | `apply_session_policy` → `_derive_allowed_paths` populates the allow-list from the generation targets; the single end-of-run `strip_merge` authorizes against it. |
  | Multi-step, freshly-generated-file e2e proof | SF-03 (`bd5cedd2`) | `tests/e2e/sandbox/test_c_exec_06_session_isolation_e2e.py` (generate → bounded pytest → authorized reconcile lands only `allowed_paths`; `secret.py` stripped; un-isolated control; non-git fail-loud) + `tests/integration/core/flow/engine/test_session_policy_fullchain.py`. |

  As a US-9 add-on, SF-05 was **integration only** — and that integration is the composition-root policy
  wiring + allow-list threading + proof, all of which `C-EXEC-06` SF-03 shipped. **`TECH-012` is resolved**:
  per-run session mode is the working multi-step isolation path (the per-step model's multi-step crash
  remains a documented limitation — use session mode for multi-step untrusted spans).

  * **Remaining consumer work (NOT SF-05):** `INT-US-03 SF-03` still owns wiring the policy into the
    **`sw implement`** flow (one `apply_session_policy(context, settings, logger)` call in
    `workflows/implementation/interfaces/cli.py` — `settings` is already loaded there; `PipelineRunner.run()`
    already routes through `execute_run`, so no other change is needed) plus the implement-specific FR-8 proof.
    The API-run composition roots remain a separate deferred item (`TECH-013`).
  * **Critical path:** `INT-US-03 SF-03` consumes this to run `sw implement` worktree-bounded — the last step
    before closing the US-3 flagship epic.
