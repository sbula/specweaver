# US-03 Integration - Integration Contracts

## Base Story Contract (`INT-US-03`)
* **Status:** ✅ Done (2026-07-21) —
  [design APPROVED 2026-07-17](../../features/topic_08_integration/INT-US-03/INT-US-03_design.md);
  SF-01 (generation→QA loop), SF-02 (lint-fix reflection loop), SF-03 (zero-trust isolation +
  verifiable proof, `64d44a71`) all committed. `sw implement` runs the full autonomous loop, with
  untrusted high-assurance (DAL_A/B) code executed worktree-bounded via DAL-driven auto-escalation
  (consumes `C-EXEC-06`). **US-3 base contract closed.**
* **Integration Description:** The Implementation Generator (`D-INTL-01`) must pipe natively into
  the QA Runner (`D-VAL-01`) and the Code Validation Rules (`D-VAL-05`), so `sw implement` generates
  code + tests, runs the tests, runs C01–C08, and auto-fixes lint in one autonomous loop. QA/test
  execution MUST run exclusively inside the **US-9 Core zero-trust worktree sandbox** (`INT-US-09`,
  container-free; `enforce_isolation` / worktree rebind). **Container/Podman execution (`D-EXEC-01`
  / `B-EXEC-01`) is explicitly OUT of scope for this base contract** — it belongs to the US-9
  sub-story `INT-US-09-SF01` (Containerized Isolation), and a future `INT-US-03` sub-story would
  layer it on once that lands.
* **Verifiable Proof (delivered by SF-03, `64d44a71`):**
  `tests/e2e/sandbox/test_implement_loop_worktree_isolation_e2e.py` +
  `tests/integration/interfaces/cli/test_cli_implement_isolation.py` — the full
  `implement → run_tests → lint_fix → validate_code` loop with freshly **generated** code running
  pytest worktree-bounded (cwd inside `.worktrees/`, real source root unmutated), paired un-isolated
  control, and `C-EXEC-06` per-run isolation under DAL-driven auto-escalation (high-assurance code
  auto-sandboxes; small/non-git projects stay on host).

## Sub-Story Add-Ons

*(Mirrored from the master roadmap 2026-07-24 — every add-on group carries its own integration story.)*

* **`INT-US-03-SF01` — Multi-Language Test Support:** *Pending Design.* Integrates `D-VAL-03` (Polyglot QA Runner, built ✅) into the `sw implement` loop for non-Python targets.

  > **UN-RETIRED.** Ships `D-VAL-03` ✅, and this story owns its integration and e2e proof: a
  > target project's manifest selects that language's runner (`sandbox/qa_runner/core/factory.py`)
  > and the real toolchain runs. `D-INTL-08` is unbuilt and owns its own — `sw implement` being
  > Python-only is that missing feature, not a defect in a delivered one.

  ### Path Inventory

  | # | Path | Span | Owner | Runnable today | Blocker |
  |---|---|---|---|---|---|
  | P-1 | Each of five runners issues the right command per intent and parses what comes back — pytest/ruff, cargo, Gradle+Maven, detekt, tsc/eslint | single feature | `D-VAL-03` | yes — **done** | — |
  | P-2 | Seam: a project directory resolves to its language's runner, and every runner satisfies all five intents or cannot be instantiated | cross-module | `D-VAL-03` | yes — **done** | — |
  | P-3 | Seam: an agent reaches `run_compiler` / `run_debugger` through the Loom sandbox, and is refused when its role does not carry the intent | cross-module | `D-VAL-03` | yes — **done** | — |
  | P-4 | Journey: a real non-Python toolchain executes inside the sandbox | cross-feature | this contract, deferred | no | the container path is proven for **Python only**; nothing has exercised a non-Python toolchain inside it |
  | P-5 | Journey: `sw implement` drives a non-Python target end to end | cross-feature | `D-INTL-08` | retired | `ADR-003` — owned by `D-INTL-08`, which declares this seam as its own FR |
  | P-6 | A lint finding carries the URI of the rule it violated | cross-feature | this contract, deferred | no | needs a scope decision — see below |

  **All seven surviving FRs are cited and each is behind a killed mutant** —
  `check_fr_coverage.py D-VAL-03` exits 0. Every mutant is a *command* substitution rather than a
  deletion, which is the sharper test at this tier: `cargo check` for `cargo build`, `gradlew build`
  for `compileJava`, `tsc` without `--noEmit`, `unittest` for `pytest`. Each substitute is a real tool
  that really runs and really succeeds. A test asserting only that the runner returned without error
  would accept all four.

  **FR-1's mutant fails 228 tests and 11 collections** — the widest in this migration by an order of
  magnitude. Renaming `run_compiler` on the abstract base makes all five runners abstract and
  un-instantiable, and the QA surface is reached from nearly every pipeline. That is what an interface
  being load-bearing looks like when you measure it.

  **FR-2's mutant is the one to remember.** Forcing the `ROLE_INTENTS` membership test false leaves the
  tool completely functional: every intent dispatches, every result returns. What disappears is the
  *refusal* — any role may now compile and debug. Three tests catch it. A boundary whose refusal is
  untested is not a boundary, it is a habit.

  ### Two rows changed on contact

  **FR-8 (E2E Testing) is deleted.** It required that every runner "must be rigorously tested" — a
  statement about the test suite, not about the product. Its negation is an absent test, not a broken
  capability, and that is what `check_fr_coverage.py` already refuses at closure for every other row.
  The FR table had become partly a checklist of itself.

  **FR-1's data-model clause is struck, and that one is a finding.** It claimed the models were
  "expanded to support `stacktrace: str`, `rule_uri: str`". The fields exist on `TestFailure`,
  `LintError` and `DebugRunResult`. **Nothing writes them** — there is no `stacktrace=` or `rule_uri=`
  assignment anywhere in `src/` or `tests/`, and `arbiter.py` reads `f.get("stacktrace", "")` and so
  always reads the empty string.

  P-6 is the substantive half. FR-5, FR-6 and FR-7 all promise SARIF, and `language/core/sarif.py`
  genuinely parses it — `ruleId`, message, physical location, per finding. It never reads the rule
  descriptor's `helpUri`, which in SARIF is the field that makes a finding *actionable*: the link
  saying what the rule is and how to satisfy it. So the pipeline asks its linters for SARIF, is handed
  the URI, and drops it. Declared-but-never-written fields cannot be falsified by any mutant — deleting
  one breaks no caller, because there are none — which is precisely why a struck clause plus a deferred
  row is more honest than a green FR.

  Not ticketed: filling `rule_uri` changes what an agent receives in a lint report, which is a scope
  decision, and filing a ticket is not the same as taking it.

  P-4's blocker was `TECH-031`, held with `INT-US-09-SF01-MIG`. **`TECH-031` closed on 2026-08-18 and
  P-4 is no closer.** Everything it delivered is Python-specific — `uv`, PEP 735 groups, pytest — and
  `resolve_runner` still warns that "container sandboxing is validated for Python projects only". A
  blocker naming finished work reads as unblocked, which is why the row now names the gap itself
  rather than a ticket.

  What is missing is a non-Python toolchain executing inside the container: `cargo`, `gradlew` or
  `tsc` present in an image, resolved and run. Mocked executors prove the command and the parse, which
  is the whole contract at unit tier; whether those binaries exist in the sandbox is a container
  question, and it is open, not forgotten.

  **`INT-US-03-SF01-MIG` is discharged, and every path blocked on another ticket now names it.**
  The contract stays open on P-4 and P-6, which no other ticket owns — both need a scope decision.

* **`INT-US-03-SF02` — Visual UI Drift Detection:** *Pending Design.* Blocked on `A-VAL-05` (Multi-Modal Visual Quality Gates, unbuilt).

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `A-VAL-05`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.

* **`INT-US-03-SF03` — Graduated Autonomy (the "middle way" dial):** *Pending Design (minted
  2026-07-24 audit).* Integrates `C-FLOW-11` (unbuilt): the `mode: oneshot | agentic` dial into the
  `sw implement` inner loop (its named pilot consumer). **Add-on ID — distinct from the base
  contract's internal "INT-US-03 SF-03" sub-feature, which is committed** (SF vs sub-story numbering
  live in different namespaces; stated per the SF/CB terminology rule).

  > **RETIRED 2026-08-13 by `ADR-003`.** Never designed; its roadmap placeholder is gone.
  > The scope above is NOT descoped — it moves to `C-FLOW-11`, which owns its own
  > integration and e2e proof as FRs rather than a separate add-on restating them.

