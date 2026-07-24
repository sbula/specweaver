# US-03 Integration - Integration Contracts

## Base Story Contract (`INT-US-03`)
* **Status:** ✅ Done (2026-07-21) — [design APPROVED 2026-07-17](../../features/topic_08_integration/INT-US-03/INT-US-03_design.md); SF-01 (generation→QA loop), SF-02 (lint-fix reflection loop), SF-03 (zero-trust isolation + verifiable proof, `64d44a71`) all committed. `sw implement` runs the full autonomous loop, with untrusted high-assurance (DAL_A/B) code executed worktree-bounded via DAL-driven auto-escalation (consumes `C-EXEC-06`). **US-3 base contract closed.**
* **Integration Description:** The Implementation Generator (`D-INTL-01`) must pipe natively into the QA Runner (`D-VAL-01`) and the Code Validation Rules (`D-VAL-05`), so `sw implement` generates code + tests, runs the tests, runs C01–C08, and auto-fixes lint in one autonomous loop. QA/test execution MUST run exclusively inside the **US-9 Core zero-trust worktree sandbox** (`INT-US-09`, container-free; `enforce_isolation` / worktree rebind). **Container/Podman execution (`D-EXEC-01` / `B-EXEC-01`) is explicitly OUT of scope for this base contract** — it belongs to the US-9 sub-story `INT-US-09-SF01` (Containerized Isolation), and a future `INT-US-03` sub-story would layer it on once that lands.
* **Verifiable Proof:** e2e test driving the full `implement → run_tests → lint_fix → validate_code` loop under `enforce_isolation=True`, proving freshly **generated** code runs pytest worktree-bounded (cwd inside `.worktrees/`, real source root unmutated) with a paired un-isolated control. *(To be delivered in `INT-US-03` SF-03.)*

## Sub-Story Add-Ons

*(Mirrored from the master roadmap 2026-07-24 — every add-on group carries its own integration story.)*

* **`INT-US-03-SF01` — Multi-Language Test Support:** *Pending Design.* Integrates `D-VAL-03` (Polyglot QA Runner, built ✅) into the `sw implement` loop for non-Python targets.
* **`INT-US-03-SF02` — Visual UI Drift Detection:** *Pending Design.* Blocked on `A-VAL-05` (Multi-Modal Visual Quality Gates, unbuilt).
* **`INT-US-03-SF03` — Graduated Autonomy (the "middle way" dial):** *Pending Design (minted 2026-07-24 audit).* Integrates `C-FLOW-11` (unbuilt): the `mode: oneshot | agentic` dial into the `sw implement` inner loop (its named pilot consumer). **Add-on ID — distinct from the base contract's internal "INT-US-03 SF-03" sub-feature, which is committed** (SF vs sub-story numbering live in different namespaces; stated per the SF/CB terminology rule).
