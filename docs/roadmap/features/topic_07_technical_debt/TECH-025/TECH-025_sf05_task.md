# Task List: TECH-025 SF-05 — TECH-002 FR Ledger

- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf05_implementation_plan.md
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_design.md

> Bare `FR-N` is **TECH-025's**. TECH-002's are written qualified — `TECH-002 FR-5`.

## Phase 1 findings (verified live 2026-08-11, not inherited from the plan)

| # | Finding | Effect on the plan |
|---|---|---|
| P1 | All six TECH-002 FRs report `NO PLAN  NO TEST`; the gate resolves all four plans under their **new padded names** | Plan's premise intact; `TECH-027`'s rename did not break the glob |
| P2 | R3's absence claims still true — 0 sandbox imports under `assurance/validation/` and `interfaces/` | Safe to assert; not asserting a false claim |
| P3 | R6's NFR-5 violation live: `test_dispatcher_domain_conformance.py:5` names TECH-002 and carries **0** `FR-N` tokens | "Credits nothing yet" confirmed — fix before it can pay out |
| **P4** | **`tach` already enforces FR-5's absence half.** Probed: planting `from specweaver.sandbox.registry import ToolRegistry` into `validation/rules/code/c03_tests_pass.py` makes `tach check` fail | FR-5's new test is a **second** proof, not the only one. Its value is being a *citable* test — `test_tach_architectural_boundaries` carries no FR tag and shells out to a bare `tach` that is invisible unless `.venv/bin` is on `PATH` |
| **P5** | **`specweaver.interfaces` is NOT a declared tach module.** FR-6 is enforced by **nothing** today | FR-6's test is genuinely additive and is the only guard. This is the higher-value half of CB-1 |
| **P6** | The SF-04 guard `test_the_invariants_below_are_reading_the_real_tree` asserts **specific paths** — `sandbox/`, `core/config/*.py`, `llm/factory.py`, `llm/router.py` | Plan R4's "a new absence proof inherits the guard" is **false as written**. The guard must be *extended* to the two new roots, or both new invariants are vacuous-proof pattern 8 |

## Decisions (user, 2026-08-11)

- **Q1** → generalise the scanner; `config_orchestration_offenders` stays as a thin caller.
- **Q2** → FR-5 injection citation on `test_validation_hydrator.py` only; rule tests untagged.
- **Q3** → per-class citations in `test_sandbox_registry.py`, matching `TECH-006`'s precedent.

---

## Red/Blue corrections (2026-08-11) — see `TECH-025_sf05_redblue_review.md`

> [!CAUTION]
> **The plan's chosen file would have created a live false credit.** `tests/unit/test_architecture.py`
> already names `TECH-001`, and `check_fr_coverage` attributes **whole-file**. Simulated: appending
> only `Proves: TECH-002 FR-5.` and `FR-6.` credits TECH-002 with **FR-4** as well, borrowed from
> TECH-001's `test_cli_commands_live_in_their_own_domains`. That is the third appearance of the
> defect class SF-01 exists to prevent. The invariants move to a new file naming only `TECH-002`.

| # | Correction | From |
|---|---|---|
| C1 | New file `tests/unit/test_layer_import_isolation.py`, naming **only** `TECH-002` | BLUE-1.1 |
| C2 | That file writes its **own** real-tree guard — plan R4's "inherits the guard" is false (P6) | BLUE-1.3 |
| C3 | ~~Scanner stays in `test_architecture.py` and is **imported**~~ — **superseded by A2 at the pre-commit gate**: it moved to `tests/fixtures/arch_scanners.py`, which satisfies BLUE-1.1 equally (a fixtures module names no story) *and* follows the `db_utils.py` precedent, 4 of 4 | BLUE-1.1 → A2 |
| C4 | CB-2 verification reads the **file list** per FR, not the count — a count cannot distinguish a borrowed citation from a real one | BLUE-1.2 |
| C5 | Docstrings state the tach asymmetry (P4/P5) so neither test is later deleted as duplicate | BLUE-1.4 |
| C6 | **No `TECH-025` tag** in the new file — it would credit TECH-025 FR-5/FR-6 from TECH-002's tokens. Recorded as a constraint on SF-07 | BLUE-2.1 |
| C7 | The new file asserts it contains **exactly two** `FR-<digit>` tokens, following SF-01's T9 | BLUE-2.2 |

## CB-1 — The two absence invariants

*Ledger stays RED through this boundary. It answers: is the claim true?*

- [x] **T1 — Red: the real-tree guard, in the NEW file.** `tests/unit/test_layer_import_isolation.py`.
      Assert `assurance/validation/` and `interfaces/` exist and contain `.py` modules *recursively*.
      Demonstrate pattern 8 first: point the scanner at a deliberately wrong root and watch it report
      clean. Per C2 this is not inherited from SF-04's guard, which asserts other paths.
- [x] **T2 — Generalise the scanner.** `tests/unit/test_architecture.py`.
      `_import_offenders(root, prefixes, *, recursive)`; `config_orchestration_offenders` becomes a
      thin caller with `recursive=False` and `DOMAIN_PREFIXES`. FR-7's four synthetic probes
      (lines 413, 477, 485) must pass **untouched** — that is the regression check on this refactor.
- [x] **T2a — Self-guard the new file (C7).** It reads its own source and asserts exactly two literal
      `FR-<digit>` tokens, and that it names no registry ID other than `TECH-002`.
- [x] **T3 — Red: the eight test stories.** Write all of T1–T8 from the plan's Test Plan as failing
      tests before any scanner code. Matrix coverage:
      - *Happy*: validation imports no sandbox (FR-5) · interfaces imports no sandbox (FR-6)
      - *Boundary*: recursion **is** used for the new roots (planted import in nested `rules/code/`
        is found) · recursion is **not** used for `core/config/` (`bootstrap/` stays out of scope)
      - *Hostile*: planted `specweaver.sandbox` import detected in a validation module, and in an
        interfaces module
      - *Degradation*: an unparseable module raises rather than being silently skipped
- [x] **T4 — Green.** Implement the generalised scanner and the two invariants.
- [x] **T5 — Record P4/P5 in the test docstrings.** FR-5's test says tach is the primary guard and
      this is the citable second one; FR-6's says nothing else enforces it. Without this a later
      reader deletes FR-5's test as duplicate and never notices FR-6's is load-bearing.

**Gate:** ✅ `tests.py cb TECH-025 --kind tooling` (5582 passed / 6 accepted-delta) → pre-commit
Phases 1–7 complete (`TECH-025_sf05_precommit_review_cb1.md`, `TECH-025_sf05_walkthrough_cb1.md`)
→ **awaiting commit**.

> Pre-commit Phase 2 HITL added: A2 (scanner moved to `tests/fixtures/arch_scanners.py`, following
> the `db_utils.py` precedent) and gaps G1–G4 (multi-prefix, empty tuple, relative import,
> non-UTF-8). 15 tests in the new file, 37 with the sibling module.

## CB-2 — Citations and the NFR-5 repairs

*Turns the ledger green. It answers: is it linked?*

- [ ] **T6 — Plan-side citations.** 4 plans, no scope added, dated note naming TECH-025 as author
      under AD-4: `sf01` → `FR-1`, `FR-2` · `sf02` → `FR-4` · `sf03` → `FR-3` · `sf04` → `FR-5`, `FR-6`.
- [ ] **T7 — Test-side citations.** Per-class in `test_sandbox_registry.py` (`TestBaseTool` → FR-1,
      `TestToolRegistry` → FR-2, `TestBaseToolConformance` + `TestFacadeConformance` → FR-4);
      module-level on `test_dispatcher_registry_delegation.py` → FR-3; `test_validation_hydrator.py`
      → FR-5.
- [ ] **T8 — NFR-5 repairs.** Remove the registry ID from
      `test_dispatcher_domain_conformance.py`'s docstring; reword the stale `"TDD red-phase marker
      for SF-2"` in `test_sandbox_registry.py:162`, which describes a state that stopped being true
      when SF-2 shipped.
- [ ] **T9 — Ledger verification, by file list not by count (C4).** `TECH-002` → 0 · `TECH-001`
      stays 0 · `TECH-005` stays 1 · `TECH-022` stays 1 · `INT-US-21` stays 0. **Plus the positive
      attribution check the plan lacked:** each TECH-002 FR must resolve to the file that genuinely
      proves it — `FR-4` → `test_sandbox_registry.py`, and **not** `test_architecture.py`. A count
      cannot tell a borrowed citation from a real one, which is exactly how RED-1.1 would have
      shipped green.

**Gate:** `tests.py cb TECH-025 --kind tooling` → pre-commit skill → **HITL stop**.

## Out of scope

- TECH-005's ledger (SF-06) and the regression manifest (SF-07).
- Adding `specweaver.interfaces` to `tach.toml` — P5 is a real gap but closing it is a tach-config
  change to a shipped boundary file, not this sub-feature's traceability work. Record it; do not fix it here.
