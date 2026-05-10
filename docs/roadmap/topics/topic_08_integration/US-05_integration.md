# US-05 Integration - Integration Contracts

## Base Story Contract (`INT-US-05`)
* **Status:** ✅ Complete
* **Integration Description:** The AST Skeleton Extractor (`D-SENS-02`) must natively resolve edges against the Git Worktree Bouncer (`D-EXEC-02`) to ensure extracted context accurately reflects the current filesystem state without hallucinatory paths.
* **Verifiable Proof:** `tests/e2e/capabilities/core/test_lineage_e2e.py`

## Sub-Story Add-Ons

* **Intelligent Code Exclusions (`INT-US-05-SUB`)**
  * **Status:** ✅ Complete
  * **Integration Description:** The `.specweaverignore` engine (`C-SENS-02`) provides deterministic exclusions directly into the Extractor.
  * **Verifiable Proof:** Covered by E2E tests in `tests/e2e/capabilities/core/` and integration tests suite `pytest -m integration`.

* **Framework Native Understanding (`INT-US-05-SUB`)**
  * **Status:** ✅ Complete
  * **Integration Description:** The Macro Evaluator (`B-INTL-02`) integrates to detect context boundaries for Frameworks natively.
  * **Verifiable Proof:** Covered by E2E tests in `tests/e2e/capabilities/intelligence/` and `tests/integration/` suites.
