---
description: Run a pre-commit test gap analysis for the current feature before marking it done.
---

# Pre-Commit Test Gap Analysis

Before we commit, run a pre-commit test gap analysis for the feature we just built.

Rules:

1. Read EVERY source file that was created or modified for this feature.
2. For each file, go line-by-line and identify EVERY branch, guard clause,
   error path, boundary condition, edge case, and fallback. Reference
   the source line numbers.
3. Read EVERY existing test file that covers these modules (unit, integration,
   e2e). Do NOT guess — actually read the test files and list what scenarios
   they already cover.
4. Produce a gap table per source module with columns:
   `[#, Scenario, Why It Matters, Source Line, Layer (Unit/Integ/E2E), Status (✅ covered / ❌ missing)]`
5. Propose integration tests that exercise the seams between modules
   (e.g., CLI → service → DB round-trip, service → prompt builder → adapter).
6. Propose e2e tests for the user-facing workflows this feature enables.
7. Do NOT invent arbitrary test counts. Every scenario must trace to real code.
8. Update `docs/test_coverage_matrix.md` with the corrected entries.
9. Present the FULL list — do NOT limit to 10 items.
