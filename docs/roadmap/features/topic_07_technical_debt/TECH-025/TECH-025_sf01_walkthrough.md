# Walkthrough: TECH-025 SF-01 — Gate Integrity (CB-1)

- **FR**: FR-9 — stop `check_fr_coverage.py` crediting fixture data
- **Commit boundary**: 1 of 1
- **Date**: 2026-08-08

## What changed and why

`check_fr_coverage.py` credits a requirement when a file under `tests/` contains the story id *and*
the literal `FR-N`, anywhere in the file. Its own test suite does both: it names a real story in the
docstring explaining why the checker exists, and it feeds requirement ids to the function under test
as inputs. **Eight of that story's ten requirements were being counted as proven by a file that
asserts nothing about it.**

That mattered here specifically: TECH-025's remaining sub-features close three ledgers *using this
gate*. Closing them against a checker with this hole would certify exactly the fiction the ticket
exists to remove — so this became SF-01 and a hard dependency of SF-04, SF-05 and SF-06.

| File | Change |
|---|---|
| `scripts/check_fr_coverage.py` | `FIXTURE_DATA_MARKER`, `_MARKER_SCAN_LINES`, `is_fixture_data()`; one `continue` in `cited_frs_in_tests`; docstring |
| `tests/unit/scripts/test_check_fr_coverage.py` | Marker applied on line 3; docstring explains the exemption |
| `tests/unit/scripts/test_fr_coverage_fixture_exclusion.py` | NEW — 16 tests, carries `Proves: TECH-025 FR-9.` |
| `scripts/tests.py` | `_src_relative` maps `scripts/` → `tests/unit/scripts/`; story-resolution extracted; dead banner removed; docstring corrected. **600 → 538** |
| `scripts/_story_resolution.py` | NEW — integration-doc parsing + `UsageError`, re-exported by `tests.py` |
| `tests/unit/scripts/test_tests_runner.py` | 4 scope tests added; 448 lines moved out. **906 → 453** |
| `tests/unit/scripts/test_refactor_diff_safety.py` | NEW — the 5 moved classes |

### Two design constraints worth knowing before editing these files

- **`test_fr_coverage_fixture_exclusion.py` may contain exactly one literal `FR-<digit>`** — the one
  in its own `Proves:` tag. It names `TECH-025`, so any other literal would credit TECH-025's own
  FR-1/FR-2/FR-3 — the ledger closures SF-04/05/06 exist to deliver — letting this ticket certify
  work nobody has done. Fixture ids are built by a `_fr(n)` helper; `TestProvesTagIsTheOnlyFrLiteral`
  pins it. The helper runs at test time, so files written to `tmp_path` still hold the real text.
- **The marker must sit at column 0.** An indented copy is inside something else — most dangerously
  a docstring documenting the convention, which would exempt that file and discard whatever it
  genuinely proves, silently, while the gate stayed green.

## Test results

| Tier | Scope | Result |
|---|---|---|
| unit | `tests/unit/scripts` (gate scope) | **350 passed** |
| integration | all | passed |
| e2e | all | **191 passed** |
| **Full suite** | `pytest -n auto` | **6265 passed, 19 skipped, 0 failed** (4m14) |

Gate: `scripts/tests.py cb TECH-025 --kind tooling` → ok, DAL-C (TECH default). Widened with `--all`
voluntarily, because this boundary changes the script that decides test selection for every story.

## Quality checks

| Check | Result |
|---|---|
| ruff · format · mypy · tach · conventions · suppressions · test_basenames · useless_asserts · file_sizes | **pass** |
| complexipy | **FAIL — pre-existing** |
| cycles | **FAIL — pre-existing** |

Attribution was **measured, not assumed**: `git stash` of this boundary's five files, then
`quality.py cb --only complexipy,cycles,file_sizes`. Result: complexipy and cycles failed *without*
the change; `file_sizes` **passed** without it. So both size REDs were mine and were fixed; the other
two are chronic.

They are also out of bounds by design: every complexipy offender is in
`src/specweaver/workspace/ast/parsers/` and `workspace/memory/hydrator.py`, and all three cycles are
inside `src/specweaver/` — while this sub-feature's **NFR-1 is zero `src/` changes**. They belong to
`TECH-023` (complexity) and `TECH-024` (cycles), which the roadmap ranks #7 and #6 and explicitly
forbids sharing a working tree, "so neither number stays attributable".

## HITL gate decisions

Every gate fired; none was bypassed or auto-approved.

| Gate | Presented | Decision |
|---|---|---|
| Design Phase 3 (scope) | Rename scope; proof shape; unit-class rule scope | All nine files + three functions; manifest + regression guard; apply-to-what-we-rename plus a ticketed sweep |
| Design Phase 6 | Consistency + 2-cycle Red/Blue (8 findings; FR-9 and the rule-ID exclusion added) | **Approved** |
| Plan Phase 4 | 6 audit questions | **All proposals accepted** |
| Plan Phase 5 | Consistency + 2-cycle Red/Blue | **Approved** |
| Dev Phase 2 | Task list **plus a blocker**: no `scripts/`-only change could pass its own commit gate | **Option A** — fix `tests.py` inside SF-01 |
| Pre-commit Phase 2 | Coverage matrix, vacuous-proof audit, 4 proposed stories | **All of them** |
| Pre-commit Phase 3 | The 4 implemented edge cases | **Approved** |

## Probe (mandatory)

Replaced the skip with `if False`. Exactly `test_marked_file_contributes_no_citations` and
`test_marker_skips_only_the_marked_file` went red; the other ten stayed green, including the
control. Restored; `grep` for `PROBE` / `if False` returns clean.

Two tests were found weak by their own probes and fixed before landing:
- `test_marker_quoted_in_a_docstring_does_not_exempt_the_file` first passed for the wrong reason —
  trailing text failed equality regardless of column, so it proved nothing about the column-0 rule
  it was named for. Rewritten as an indented, otherwise-exact marker.
- The `_fr()` rule was violated by my own explanatory comment on first write. `TestProvesTagIsTheOnlyFrLiteral` caught it.

## Ledger effects

| Story | Before | After |
|---|---|---|
| INT-US-21 | exit 0, inflated (`FR-1`: 6 files) | **exit 0**, honest (`FR-1`: 5 files) — every requirement still has ≥2 genuine citations |
| INT-US-24 · TECH-006 · TECH-019 | exit 0 | exit 0, unmoved |
| TECH-025 | no FRs cited | FR-9 cited; FR-1/2/3 still absent — correct, SF-04/05/06 have not run |

## Two defects this gate caught before they landed

- **`UsageError` declared twice.** The first cut of the extraction left one class in each module.
  Two classes of the same name are two different exceptions, so `main`'s `except UsageError` would
  have missed everything the sibling raised — every usage error surfacing as a traceback instead of
  a message. Now defined in `_story_resolution.py` and re-exported.
- **A regex silently mangled to a literal backspace byte.** Generating the new module through a
  shell heredoc turned `\\b` into `0x08`, so `CAPABILITY_ID` could never match and nine DAL-derivation
  tests went red. Invisible to `grep` and to file reads — it renders as nothing. Found only because
  the tests exercise the real integration docs. The file was rewritten directly rather than through
  a heredoc, and verified byte-wise to contain no control characters.

## Open items for the reviewer

1. **complexipy / cycles remain red repo-wide.** Pre-existing, proven by `git stash`; every offender
   is under `src/specweaver/`, which this sub-feature's NFR-1 forbids touching. Owned by TECH-023
   and TECH-024, which the roadmap ranks #7 and #6 and forbids sharing a working tree.
2. **No automated guard yet that INT-US-21's ledger stays closed.** It cannot be a test without
   naming that story beside an `FR-N` token. It lands in SF-07's manifest (design AD-5 as amended).
3. **Scope grew well beyond FR-9** — five files instead of three, plus two new modules. Every step
   was gate-forced and approved at a HITL gate, but it is worth a look as one diff.
