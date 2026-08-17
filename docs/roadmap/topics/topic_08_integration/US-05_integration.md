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

* **`INT-US-05-SF03` — Intelligent Code Exclusions:** the add-on's contract under `ADR-004`.

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | Per-language structural and binary exclusions; `.specweaverignore` with gitignore semantics; default scaffolding; interception before deep I/O | single feature | `C-SENS-02` | yes — **done** | — |
  | P-2 | Journey: a polyglot monorepo is scanned without build artefacts entering the token context | cross-feature | this contract, deferred | no | none — see below |

  **This entry was one of three marked `✅` while citing no test file**, reopened by `TECH-060` FR-3.
  It is now genuinely proven: `C-SENS-02`'s five FRs are cited and each is behind a killed mutant —
  `check_fr_coverage.py C-SENS-02` exits 0.

  **Getting there needed a filename fix, and that is the finding.** The capability has five
  implementation plans, and `check_fr_coverage.py` could not see any of them: they were named
  `C-SENS-02_sfNN_impl_plan.md` while the gate globs `*implementation_plan.md`. So a capability with
  five plans read as entirely unplanned. `TECH-044` had already noticed the naming drift — *"naming
  has
  already drifted three ways each (`sfN_implementation_plan` / `sfN_impl_plan` / …)"* — but recorded
  it
  as untidiness; its actual consequence, invisibility to the FR gate, was never stated. Measured
  across
  the whole tree, `C-SENS-02` was the only capability affected; the five files are renamed.

  P-2 has **no unbuilt blocker** — it is a journey this capability could carry alone, and it is
  deferred
  only because no e2e asserts it end to end today. That makes it the first deferred row in this
  migration that is a genuine test-writing task rather than a wait on someone else.

  **`INT-US-05-SF03-MIG` is discharged (2026-08-17); the contract stays open** on P-2.


* **`INT-US-05-SF04` — Framework Native Understanding:** the add-on's contract under `ADR-004`.

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | AST markers evaluated against declarative YAML schemas; the language gate; cascading `>>{...}<<` resolution under a depth cap | single feature | `B-INTL-02` | yes — **done** | — |
  | P-2 | Seam: an agent's `read_unrolled_symbol` intent reaches the evaluator through the code-structure atom, and the unrolled logic comes back attached to the symbol | cross-module | `B-INTL-02` | yes — **done** | — |
  | P-3 | Seam: a project's own `.specweaver/evaluators/*.yaml` are discovered by the loader and injected into the validation handler | cross-module | `B-INTL-02` | yes — **done** | — |
  | P-4 | Journey: an agent reading a Spring Boot or Actix codebase receives unrolled runtime behaviour in its prompt, not raw annotations | cross-feature | this contract, deferred | no | none — see below |

  **This entry was the second of three marked `✅` while citing no test file**, reopened by
  `TECH-060` FR-3. All five FRs are now cited and each is behind a killed mutant —
  `check_fr_coverage.py B-INTL-02` exits 0. FR-2 is genuinely multi-language: schemas ship for Spring
  Boot, Quarkus, NestJS, FastAPI and Actix.

  **FR-3 is the finding, and it is the same shape as `E-UI-02` FR-1.** Its test asserted only
  `res.status == "success"`, so swapping the tool's intent from `read_unrolled_symbol` to plain
  `read_symbol` passed the entire suite: a symbol came back, simply without its unrolled macro.
  **Success is not delegation.** A tool test that checks the envelope and not the payload cannot
  distinguish a tool that does the work from one that does something cheaper. The atom-level test
  already pinned the unrolled content; the tool path — the one an agent actually takes — did not.

  P-4 has **no unbuilt blocker.** Nothing in `src/` calls `read_unrolled_symbol`: it is reachable
  only when an agent chooses the intent, and no e2e drives an agent tool loop over a framework
  codebase. So the journey is deferred on a test nobody has written, not on a feature nobody has
  built — the second such row in this migration, after `INT-US-05-SF03` P-2.

  **`INT-US-05-SF04-MIG` is discharged (2026-08-17); the contract stays open** on P-4.
