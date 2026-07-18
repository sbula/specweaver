# US-03 Integration - Integration Contracts

## Base Story Contract (`INT-US-03`)
* **Status:** 🟡 In Progress — [design APPROVED 2026-07-17](../../features/topic_08_integration/INT-US-03/INT-US-03_design.md); SF-01 implementation plan in progress.
* **Integration Description:** The Implementation Generator (`D-INTL-01`) must pipe natively into the QA Runner (`D-VAL-01`) and the Code Validation Rules (`D-VAL-05`), so `sw implement` generates code + tests, runs the tests, runs C01–C08, and auto-fixes lint in one autonomous loop. QA/test execution MUST run exclusively inside the **US-9 Core zero-trust worktree sandbox** (`INT-US-09`, container-free; `enforce_isolation` / worktree rebind). **Container/Podman execution (`D-EXEC-01` / `B-EXEC-01`) is explicitly OUT of scope for this base contract** — it belongs to the US-9 sub-story `INT-US-09-SF01` (Containerized Isolation), and a future `INT-US-03` sub-story would layer it on once that lands.
* **Verifiable Proof:** e2e test driving the full `implement → run_tests → lint_fix → validate_code` loop under `enforce_isolation=True`, proving freshly **generated** code runs pytest worktree-bounded (cwd inside `.worktrees/`, real source root unmutated) with a paired un-isolated control. *(To be delivered in `INT-US-03` SF-03.)*

## Sub-Story Add-Ons

* No explicit sub-story contracts defined yet.
