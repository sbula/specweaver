# US-05 Integration - Integration Contracts

## Base Story Contract (`INT-US-05`)
* **Status:** ✅ Complete
* **Integration Description:** The AST Skeleton Extractor (`D-SENS-02`) must natively resolve edges
  against the Git Worktree Bouncer (`D-EXEC-02`) to ensure extracted context accurately reflects the
  current filesystem state without hallucinatory paths.
* **Verifiable Proof:** `tests/e2e/capabilities/core/test_lineage_e2e.py`

## Sub-Story Add-Ons

* **Intelligent Code Exclusions (`INT-US-05-SF03`)**
  * **Status:** ✅ Complete
  * **Integration Description:** The `.specweaverignore` engine (`C-SENS-02`) provides deterministic exclusions directly into the Extractor.
  * **Verifiable Proof:** Covered by E2E tests in `tests/e2e/capabilities/core/` and integration tests suite `pytest -m integration`.

* **Framework Native Understanding (`INT-US-05-SF04`)**
  * **Status:** ✅ Complete
  * **Integration Description:** The Macro Evaluator (`B-INTL-02`) integrates to detect context boundaries for Frameworks natively.
  * **Verifiable Proof:** Covered by E2E tests in `tests/e2e/capabilities/intelligence/` and `tests/integration/` suites.

---

> **Identifier repair, 2026-08-13 (`TECH-039`).** Both add-ons above were spelled `INT-US-05-SUB`
> — one identifier naming two different delivered sub-stories.
>
> **This was repair, not a rename, and the distinction is the whole decision.**
> `finished-stories-immutable` protects the record of what was delivered; it does not require
> preserving a token that cannot identify anything. `INT-US-05-SUB` was never a valid identifier:
> nothing reading this file could tell the two entries apart, `check_story_preconditions.py
> INT-US-05-SUB` resolved to whichever its regex reached first and could never check the other, and
> `check_proof_tier.py` had to key its ratchet on file+title instead of ID specifically to route
> around this entry.
>
> Nothing was minted. `master_story_roadmap.md` already declared these two add-ons as
> `INT-US-05-SF03` (Intelligent Code Exclusions, `C-SENS-02`) and `INT-US-05-SF04` (Framework
> Native Understanding, `B-INTL-02`), with titles matching this file word for word. This document
> was reconciled TO the registry.
>
> **Not the same as `OQ-1`**, and it must not be closed the same way. That accepted divergence
> (`INT-US-21-SUB` here vs `INT-US-21-SF01` in the roadmap) is two names for one thing — ugly but
> unambiguous, and left alone deliberately. This was one name for two things, which is ambiguous by
> construction. A guardrail now forbids the latter and permits the former.

