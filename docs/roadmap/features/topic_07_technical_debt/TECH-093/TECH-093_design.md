# Design: Three Code Checks Read Every Language as Python

- **Feature ID**: TECH-093
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED
- **Kind**: `bugfix`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-093/TECH-093_design.md
- **Origin**: 2026-10-31, the `TECH-087` live demo (`sw check --level code Cart.kt`). A defect in
  delivered work: C01, C06 and C08 have run Python's `ast.parse` on every file since before
  `20a5a4e2`, and `TECH-078` (every language gets validation) narrowed only `sw implement`'s
  pipeline, not the rules. `finished-stories-immutable` bars editing those stories, so this ticket
  owns it. Chosen by the user over folding it into `TECH-089` `[agreed 2026-10-31]`.

## Feature Overview

TECH-093 makes the code checks C01 (Syntax Valid), C06 (No Bare Except) and C08 (Type Hints) judge
only Python files. It solves a false FAIL on valid Kotlin, Java and Rust, a SKIP reason that calls
valid code broken, and a false PASS on a TypeScript file that happens to parse as Python. For any
other language, or a file whose language is unknown, each of the three reports SKIP and says why.
It touches the three rule files in `assurance/validation/rules/code/` and reads the language from
`commons.languages.language_of`. It does not add real checks for other languages, and does not
change `sw implement`, which already runs only C02 and C03 for a non-Python file.

## The Defect (measured 2026-10-31)

Each rule's `check(spec_text, spec_path)` calls `ast.parse(spec_text)` whatever `spec_path` is.
Small valid files, run through the three rule classes:

| File | C01 | C06 | C08 |
|---|---|---|---|
| `Cart.kt`, `Main.java`, `lib.rs` | FAIL "Syntax error at line 1: invalid syntax" | SKIP "Cannot parse file (syntax error)" | SKIP, same |
| `app.ts` (`x = 1`) | PASS | PASS | PASS |

The live run on 2026-10-30 (`sw check --level code src/main/kotlin/shop/Cart.kt` in a Maven Kotlin
project) showed the C01 FAIL through the CLI.

## Path List (`ADR-005`)

| # | Path | Span | Owner | Status |
|---|---|---|---|---|
| P-1 | A rule judges one file (`Rule.check`) | this feature alone | TECH-093 (FR-1, FR-2) | ✅ |
| P-2 | `sw check --level code <file>` → `execute_validation_flow` → the rules → the printed table | CLI, hydrator, executor, rules | TECH-093 (FR-3) | ✅ |
| P-3 | `POST /api/v1/check` with `level: code` → `execute_validation_flow` → the response's rule rows | API, hydrator, executor, rules | TECH-093 (FR-4) | ✅ |
| — | `sw implement`'s `validate_code` step | not reached: `ValidateCodeHandler` narrows a non-Python file to C02 and C03 (`core/flow/handlers/validation.py`, `_test_rules_only`) | — | unchanged |

## Research Findings

### Codebase Patterns

- **The one language table**: `specweaver.commons.languages.language_of(path) -> str | None`
  (`commons/languages.py:39`). Its docstring: *"The one copy: prompts, parsers, rename, the
  archetype rules and the task's files all read it."* `.py` and `.pyi` are `python`; `.kt`, `.java`,
  `.rs`, `.ts` and others are named; any other ending is `None`.
- **SKIP with a reason** is the shape C05 already uses for a language it cannot check
  (`c05_import_direction.py:56`, `self._skip(str(exports["note"]))`), via `Rule._skip(message)`
  (`assurance/validation/models.py:172`).
- **Boundary**: `rules/code/context.yaml` is `pure-logic` and consumes
  `specweaver/assurance/validation`. `specweaver.commons` is a tach `utility = true` module
  (`tach.toml:172`), and `rules/spec/s12_archetype_spec_bounds.py` already imports it. No new
  dependency edge.
- **Callers**: `run_rules` (`runner.py:66`) and `execute_validation_pipeline` (`executor.py:206`)
  both call `rule.check(spec_text, spec_path)`. The CLI (`sw check`) and the API (`/check`) pass
  the file's path.
- **User guide**: `docs/user_guides/1_installation_and_setup.md:334` says the code rules are
  Python's and describes `sw implement` only.

### External Tools

None. Python's `ast` is already used; nothing new is called.

### Blueprint References

Linters choose files by type before they run: pre-commit's `types` filter tags each file through
the `identify` library, so a Python hook never sees a Kotlin file
([adamj.eu](https://adamj.eu/tech/2024/01/24/pre-commit-fail-hook/)). Here the rule makes the
same choice itself, because the CLI and API run the whole pipeline on any file.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | For a file whose ending `language_of` names as a language other than Python, C01, C06 and C08 SHALL each return SKIP, with a message naming that language; none SHALL return PASS, WARN or FAIL `[agreed 2026-10-31]` | C01, C06, C08 | check a `.kt`, `.java`, `.rs` or `.ts` file | SKIP, e.g. "C01 checks Python only; this file is kotlin" |
| FR-2 | When `spec_path` is `None`, or its ending names no language, C01, C06 and C08 SHALL each return SKIP saying the language is unknown; none SHALL parse the text as Python `[agreed 2026-10-31]` | C01, C06, C08 | check text with no path, or `bin/tool` | SKIP, "language unknown" |
| FR-3 | `sw check --level code <file>` on a Kotlin file SHALL print C01, C06 and C08 as SKIP with the language named, and none as FAIL (seam: CLI → `execute_validation_flow` → the rules) | `sw check` | run on a valid `.kt` file | the table shows three SKIP rows |
| FR-4 | `POST /api/v1/check` with `level: code` on a Kotlin file SHALL return C01, C06 and C08 with status `skip`, and none counted in `failed` (seam: API → `execute_validation_flow` → the rules) | the API | check a valid `.kt` file | three `skip` rows |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1, FR-2 | the file's language | `commons` · `language_of(path: str \| PurePath) -> str \| None` | read `commons/languages.py:39`; ran it on `.kt`, `.ts`, no ending |
| FR-1, FR-2 | a SKIP result | `assurance.validation` · `Rule._skip(message: str = "") -> RuleResult` | read `models.py:172` |
| FR-3 | the CLI's path to the rules | `sw check` → `execute_validation_flow(pipeline, content, path, …)` | the 2026-10-30 live run printed C01 FAIL for `Cart.kt` |
| FR-4 | the API's path to the rules | `run_check` → `execute_validation_flow(resolved, content, abs_path, …)` | read `interfaces/api/v1/validation.py:89-123` |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Python files keep today's results | Every existing C01, C06 and C08 case on a `.py` path gives the same status and message as before |
| NFR-2 | A Python file with a syntax error keeps today's results | C01 FAIL with the line; C06 and C08 SKIP "Cannot parse file (syntax error)" |

## External Dependencies

None.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | The language comes from `commons.languages.language_of`, never a new suffix check in the rules | The one copy (`TECH-079` records the cost of many); `.pyi` comes for free | No |
| AD-2 | Each rule decides for itself, before parsing; the CLI and API pipelines are not narrowed like `sw implement`'s | The user chose SKIP in the rule `[agreed 2026-10-31]`; it covers every caller, a custom `--pipeline` included | No |
| AD-3 | One small shared helper in `rules/code/` returns the SKIP result or `None`, used by all three rules | Three copies of the same two branches would drift | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Helper and three call sites | small | low |
| Tests that call these rules without a path | small | low: they gain a `.py` path |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| `sw check` and the API on Java, Kotlin, Rust, TypeScript | no false FAIL, no false PASS | high for those users |
| `TECH-087`'s promise | a check that did not run is never clean holds for code rules too | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A caller passes Python text with no path and now gets SKIP | low: every production caller passes a path | a check stops judging | FR-2 says so in the message; tests pin it |
| A Python file with an unusual ending (`.pyw`) is skipped | low | a check stops judging | `language_of` is the one place to add it |
| `sw check` prints `ALL PASSED` when nothing fails or warns, and does not count SKIP rows; a file where every other rule passes now reads `ALL PASSED` with C01, C06 and C08 skipped | low: on a Kotlin file C02 to C05 still judge (probe 2026-10-31) | the summary hides three skips | the SKIP rows stay in the table; the summary is not in scope (Non-Goals) |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `ValidateCodeHandler._test_rules_only` | narrows the pipeline for non-Python files | could later rely on rules that skip themselves | not in scope |

## Works For Real

Run 2026-10-31 in a scratch home: `HOME=<scratch> SPECWEAVER_DATA_DIR=<scratch>/data sw check
--level code src/main/kotlin/shop/Cart.kt` printed `C01 Syntax Valid SKIP kotlin: C01 checks Python
only`, and the same for C06 and C08. Before TECH-093 it printed `C01 FAIL Syntax error at line 1`.

## Non-Goals

- Real syntax, bare-except or type-hint checks for other languages `[agreed 2026-10-31]`.
- Moving the parsers (`TECH-089`).
- Changing `sw implement`'s narrowing.
- Changing how `sw check`'s summary line counts SKIP rows. It goes into the next TECH ticket that is started, not a new ticket `[agreed 2026-10-31]`.

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| User guide, code rules | `1_installation_and_setup.md:334`: `sw check` and the API report C01, C06 and C08 as SKIP for other languages | ✅ |

## Sub-Feature Breakdown

Single feature — no decomposition.

- **Scope**: C01, C06 and C08 judge Python only and say why they skip.
- **FRs**: [FR-1, FR-2, FR-3, FR-4]
- **Inputs**: the file text and path given to `Rule.check`.
- **Outputs**: SKIP results with a reason, seen in `sw check` and the API.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-093/TECH-093_implementation_plan.md

## Execution Order

Single feature — no decomposition.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Code checks judge Python only | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

### Red/Blue (Phase 6), 2 cycles
- R1 (MEDIUM) The summary line counts no SKIP, so `ALL PASSED` can stand over three skipped checks.
  Probed 2026-10-31 in a scratch home: `sw check --level code` on `Cart.kt` and on `bin/tool`
  both end `FAILED` today, from C01 and C05; after the fix C02 to C05 still judge a Kotlin file.
  Blue: a summary change is a new `T-POSTURE` question, put to the user at approval.
- R2 (LOW) FR-1's example message is not a contract. Blue: tests assert SKIP and that the language
  name appears, not the exact words.
- R3 (LOW) `.pyi` stubs: `language_of` says `python`, so they keep today's checks. No change.
- Cycle 2: challenged AD-2 (should the CLI narrow like `sw implement` instead?). No: the user chose
  the rule `[agreed 2026-10-31]`, and a rule that skips itself covers a custom `--pipeline` too.
  No new finding.

**Current status**: CB-1 committed 2026-10-31. The closure gate passed (`check_fr_coverage.py`, `tests.py feature --kind bugfix`); waiting for the user's sign-off.
**Next step**: The user's sign-off, then `Status: COMPLETE`.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate skill.
