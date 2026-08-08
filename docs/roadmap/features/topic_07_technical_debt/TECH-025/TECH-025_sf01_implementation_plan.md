# Implementation Plan: Registry IDs Leaking Into Proofs [SF-01: Gate Integrity]

- **Feature ID**: TECH-025
- **Sub-Feature**: SF-01 — Gate Integrity
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-025/TECH-025_sf01_implementation_plan.md
- **Status**: APPROVED (2026-08-08)

## Overview

`scripts/check_fr_coverage.py` counts an FR as proven when a file under `tests/` contains the story
ID **and** the literal `FR-N`, anywhere in the file. `tests/unit/scripts/test_check_fr_coverage.py`
is the checker's own test suite: it names `INT-US-21` in its module docstring (explaining the defect
the checker exists to catch) and contains `FR-1`…`FR-7`, `FR-10`, `FR-99` as **fixture inputs to the
function under test**. The gate therefore credits 8 of INT-US-21's 10 FRs to a file that asserts
nothing whatsoever about INT-US-21.

SF-01 teaches the scanner to skip files that declare themselves fixture data, and marks the one
file that qualifies. It must land before any ledger is closed against this gate (design AD-7):
closing three ledgers against a checker with this hole would certify exactly the fiction TECH-025
exists to remove.

**FRs**: FR-9 — *Stop the gate crediting fixture data.*

## Research Notes

Findings that constrain this plan. Each was verified against the live tree during planning.

**R1 — The false credit is real, and INT-US-21 does not depend on it.** Measured by re-running the
citation scan with the file excluded: every one of INT-US-21's ten FRs keeps at least two genuine
citing files. Counts fall (`FR-1: 6→5`, `FR-4: 8→7`, `FR-8: 3→3`, `FR-9: 2→2`) and the ledger stays
closed. If it does **not** stay closed after the change, the fix has over-reached — that is the
sub-feature's own regression check.

**R2 — The stricter "same-line" rule was evaluated and rejected, with measurements.** Requiring the
story ID and `FR-N` on one line would kill the false credit for free, but it reopens two ledgers
that currently pass: `INT-US-24` loses FR-5 and FR-6, `TECH-019` loses FR-2 and FR-3. The cause is
the `Proves:` convention itself — `Proves: TECH-019 FR-1, FR-4, FR-5.` names the story once while
that file's other FRs are cited on other lines. Repairing two unrelated delivered stories is not
this ticket's scope. **Do not revisit this without re-running the measurement.**

**R3 — Only one file qualifies today.** 54 test files name at least one story and contain FR
tokens, and naming several stories is *normal* here (cross-cutting regression notes). The
distinguishing trait is narrower: the FR strings are arguments to the checker under test. Only
`tests/unit/scripts/test_check_fr_coverage.py` meets it. The marker is a mechanism, not a list —
but it is applied to exactly one file in this sub-feature.

**R4 — Exact scanner surface.** `cited_frs_in_tests(tests_root, story) -> dict[str, list[str]]`
(`check_fr_coverage.py:104`) walks `tests_root.rglob("*.py")`, skips `_SKIP_DIRS`
(`{"__pycache__", ".pytest_cache", ".git"}`), reads via `_read()` (returns `None` on
`OSError`/`UnicodeDecodeError`), and `continue`s when `story not in text`. The skip belongs on that
same `continue` chain — one predicate, one call site.

**R5 — The script is loaded by path, not imported.** `scripts/` is not a package; the existing test
file loads it via `importlib.util.spec_from_file_location` and registers it in `sys.modules` under
`"check_fr_coverage"`. Any new test file must use the same loader shape. There is no `context.yaml`
for `scripts/` — it is not a `src/` module and no boundary rule applies.

**R6 — Blast radius is story closures only.** `check_fr_coverage.py` is invoked by the
`specweaver-feature` Phase 4 closure gate and by `specweaver-dev`/`pre-commit` documentation that
points at it. It is **not** part of `quality.py`, so no per-commit gate changes behaviour.

**R7 — Precedent for a header-scanned marker.** `check_conventions.py` reads only the first
`HEADER_SCAN_LINES = 5` lines when looking for the licence header, and its insertion-order comment
records that file-top pragmas (`# mypy:`, `# ruff:`) must stay at the very top. A marker in the
header region is consistent with how this repo already marks files for tooling.

## Proposed Changes

### 1. `[MODIFY] scripts/check_fr_coverage.py`

Add a fixture-data escape hatch to the citation scan.

**Settled at the Phase 4 gate (2026-08-08):**

| Decision | Value |
|---|---|
| Marker text | `# fr-coverage: fixture-data` |
| Scan window | first **10** lines (wider than `check_conventions.py`'s `HEADER_SCAN_LINES = 5`, because the marker sits below the two-line licence block and a blank line) |
| Predicate | `is_fixture_data(text: str) -> bool` |
| Test class | `TestIsFixtureData` — names the function under test, per the repo's unit-test class rule |

- A module constant holding the marker text, and one holding the scan window (lines from top).
- A small predicate — given file text, is this file declared fixture data? — checking the marker
  only within the window. Kept as a named function so it is directly testable rather than reachable
  only through the sweep.

> [!NOTE]
> The marker is deliberately **not** honoured by `planned_frs()`. Implementation plans are globbed
> per story (`*/TECH-001/TECH-001*implementation_plan.md`), so one story's plan can never credit
> another and there is nothing to leak. Considered and rejected at the Phase 4 gate; do not add it
> for symmetry.
- `cited_frs_in_tests` consults the predicate on the same `continue` chain that already skips
  undecodable files and files not naming the story.
- Extend the module docstring: state what the marker is for, that it can only ever *remove*
  citations and therefore is not an override in the sense the repo forbids, and record the
  measurement in R2 so the next person does not re-propose the same-line rule.

Pseudocode for the scan order inside `cited_frs_in_tests` — the order matters because each step is
cheaper than the next:

```
skip if path is under a _SKIP_DIRS component
text = _read(path); skip if None                  # undecodable
skip if story not in text                         # cheap substring reject, unchanged
skip if is_fixture_data(text)                     # NEW — before any FR collection
collect FRs and record the file
```

> [!CAUTION]
> The marker must be checked **after** `story not in text`, not before. Checking it first would
> read the header window of every Python file under `tests/` on every run, for a predicate that
> matters to roughly one file in a thousand.

### 2. `[MODIFY] tests/unit/scripts/test_check_fr_coverage.py`

Add the marker to the header region, above the existing module docstring's provenance paragraph, so
a reader sees immediately why this file is exempt. The docstring's `INT-US-21` / `D-INTL-02`
references **stay** — they are the legitimate, valuable record of why the checker exists, and the
marker is precisely what makes keeping them safe.

No test body changes. The `INT-US-21` strings inside `TestCitedFrsInTests` fixtures are left alone;
switching them to a synthetic ID would also work but is redundant once the file is marked, and
would churn eight assertions for no behavioural gain.

### 3. `[NEW] tests/unit/scripts/test_fr_coverage_fixture_exclusion.py`

The tests proving FR-9, plus this sub-feature's `Proves: TECH-025 FR-9.` tag.

> [!WARNING]
> These tests **cannot** live in `test_check_fr_coverage.py`. That file is about to be marked
> fixture data, so the scanner will skip it — and a `Proves: TECH-025 FR-9` tag inside a skipped
> file cites nothing, leaving TECH-025's own ledger short at closure. The split is forced by the
> mechanism, not stylistic.

> [!CAUTION]
> This new file must contain **no real story ID other than `TECH-025`**. It names `TECH-025` (for
> the `Proves:` tag) and would otherwise credit any story it mentioned with every `FR-N` token in
> it — reintroducing the defect one file over. All fixtures use synthetic IDs, following
> `TestMain`'s existing `TEST-US-1` convention in the sibling file.

> [!CAUTION]
> **The file must contain exactly one literal `FR-<digit>` token: the one in its own `Proves:` tag.**
> Found by this plan's Red/Blue review. The obvious way to write these tests scatters `"FR-1"`,
> `"FR-2"` … through the fixtures — and because the file also names `TECH-025`, the scanner would
> credit **TECH-025's own** FR-1, FR-2 and FR-3 from them. Those are the three ledger requirements
> that SF-04, SF-05 and SF-06 exist to satisfy, so TECH-025 could close its own ledger without
> them ever being done. That is a vacuous pass in the one ticket whose whole purpose is preventing
> vacuous passes.
>
> Build fixture tokens through a tiny module-level helper instead — `_fr(2)` returning `"FR-2"` —
> so no literal `FR-<digit>` appears in the source. `_FR_MENTION` requires a digit immediately
> after `FR-`, so an f-string with a placeholder does not match. This is not obfuscation: a
> formatting helper reads better than scattered string literals, and one comment explains why it
> exists. The rule is pinned by T9 below.
>
> This weakens nothing. The helper runs at test time, so the files written into `tmp_path` contain
> the real `FR-2` text and the scanner is exercised byte-for-byte as in production. Only the *test
> source* avoids the literal — which is the only thing the citation scan reads.

> [!NOTE]
> Placement: the licence header occupies lines 1–2 (`check_conventions.py` R2 scans the first 5
> lines and `tests/` is in `HEADER_TREES`), so the fixture-data marker goes on line 3 or 4 — inside
> both that window and the predicate's 10-line window — followed by the module docstring.

### 4. `[MODIFY] scripts/tests.py` — approved scope extension (2026-08-08)

Found at SF-01's Phase 2 gate, approved by the user before any code was written.

`_src_relative` (`scripts/tests.py:387`) returns `None` for anything outside `src/specweaver/`, and
the `tooling` profile's `cb` scope is `unit: module`, which consumes those relatives. A change
confined to `scripts/` therefore resolves to zero paths and the boundary gate blocks with *"selected
NO tests. You changed source that nothing mirrors"* — which is false here: `tests/unit/scripts/` is
that mirror and it exists.

This is not SF-01-specific. **No `scripts/`-only change in this repo can currently satisfy its own
commit gate**, and TECH-025's SF-02 and SF-03 both modify `scripts/check_conventions.py`.

- Teach `_src_relative` that a `scripts/*.py` path mirrors to `tests/unit/scripts/`, returning the
  path such that `rel.parent` is `scripts` — so `module` scope resolves to `tests/unit/scripts` and
  `touched` scope globs `test_<stem>*.py` inside it, with no change to `paths_for`.
- The `.py` suffix guard already excludes `scripts/baselines/*.json`.
- Add the case to the existing `tests/unit/scripts/test_tests_runner.py`.

## Test Plan

Adversarial matrix, per `tests/CLAUDE.md`. All unit tier — this is a script-level predicate with no
I/O beyond `tmp_path`, and TECH-025 is not an integration contract, so `TECH-017`'s
integration-tier rule does not apply.

| # | Bucket | Test | Asserts |
|---|--------|------|---------|
| T1 | Happy | marked file contributes nothing | A `tmp_path` file naming a synthetic story, containing `FR-N`, **plus** the marker → `cited_frs_in_tests` returns `{}` |
| T2 | Happy (control) | the marker is what does it | Byte-identical file **without** the marker → the same FR is collected. Without this pair, T1 could pass because of an unrelated bug |
| T3 | Boundary | marker inside the window | Marker on the last line of the scan window → skipped |
| T4 | Boundary | marker beyond the window | Marker one line past the window → **not** skipped. Pins the window as a real boundary rather than "somewhere near the top" |
| T5 | Boundary | predicate in isolation | The named predicate returns True/False directly for marked/unmarked text, including empty text |
| T6 | Degradation | marked **and** undecodable | An undecodable marked file still degrades gracefully — one bad file cannot abort the sweep (existing invariant, re-pinned because the new `continue` sits on that chain) |
| T7 | Hostile | marker as a prefix of a longer token | `# fr-coverage: fixture-database` must **not** count as marked. A naive `marker in line` check passes it, so the predicate matches the marker at a line boundary (end-of-line or trailing whitespace), not as a bare substring |
| T8 | Regression | mixed tree | A directory holding one marked and one unmarked file returns only the unmarked file's FRs — proves the skip is per-file, not per-sweep |
| T9 | Invariant | this file cannot credit TECH-025's ledger FRs | Read this module's own source and assert exactly one literal `FR-<digit>` token — the one in its `Proves:` tag. Guards the `_fr()` helper rule above against a future contributor "simplifying" it back to string literals |

**Not a pytest — a manifest entry.** "INT-US-21 still closes after the exclusion" cannot be a test
in this file: asserting it requires naming `INT-US-21`, and this file carries `FR-9` for its own
tag, so it would credit INT-US-21 FR-9 — the exact defect being fixed. Settled at the Phase 4 gate:
it is a verification command for **this** sub-feature, and **`INT-US-21` is added to SF-07's
manifest** so the guard covers it permanently once SF-07 lands. That amends design AD-5 (manifest
seeded with the three subject stories only); the amendment is recorded there, and its rationale is
that AD-5's reason — do not bind stories this ticket never audited — does not apply, because SF-01
audits INT-US-21 directly.

## Verification

```bash
PY=.venv/Scripts/python.exe

# 1. The new and existing script tests (module-scoped — serial on purpose)
$PY -m pytest tests/unit/scripts/ -v --tb=short

# 2. The fix does what it claims: this file no longer credits INT-US-21
$PY scripts/check_fr_coverage.py INT-US-21     # MUST still exit 0 — counts fall, ledger holds

# 3. No other ledger moved
$PY scripts/check_fr_coverage.py INT-US-24
$PY scripts/check_fr_coverage.py TECH-006
$PY scripts/check_fr_coverage.py TECH-019

# 4. Conventions + full suite
$PY scripts/quality.py cb
$PY -m pytest -n auto --tb=short -q

# 5. This sub-feature did not credit TECH-025's own ledger requirements.
#    Expect FR-9 present; FR-1/FR-2/FR-3 still absent (SF-04/05/06 have not run yet).
$PY scripts/check_fr_coverage.py TECH-025
```

Step 2 is the sub-feature's real proof. If INT-US-21 goes red, the predicate is over-matching —
fix the predicate, do not exempt the story.

## Commit Boundaries

**CB-1 (only)** — scanner predicate + skip, marker applied, new test file, docstring update.
The change is one predicate and one `continue`; splitting it would produce a commit where the
marker exists but does nothing, or one where tests reference a predicate that does not exist.

## What actually shipped (recorded 2026-08-08, post-implementation)

Delivered as planned, plus four things the plan did not foresee. All four were forced by gates, not
chosen:

1. **`scripts/tests.py` — `scripts/` now mirrors to `tests/unit/scripts/`** (plan §4, approved at
   the Phase 2 dev gate *before* any code). Without it no scripts-only change could satisfy its own
   commit boundary.
2. **The marker requires column 0** (`line.strip()` → `line.rstrip()`). Added at the pre-commit
   Phase 2 gate as stories U1/U2: an indented copy inside a docstring that merely *documents* the
   convention would otherwise have exempted the file, discarding a genuine proof **silently**.
3. **`tests/unit/scripts/test_tests_runner.py` split** into itself plus
   `test_refactor_diff_safety.py` (448 lines moved, 5 classes, pure move — 350 tests before and
   after). The file crossed its 900-line RED ceiling when this sub-feature's tests landed. It was a
   two-module grab-bag: those five classes used only the `rds` fixture and nothing from `tests.py`,
   so the split follows the seam that was already there and gives `scripts/_refactor_diff_safety.py`
   its proper mirror name.
4. **A dead section banner removed from `scripts/tests.py`** — a header for content that had moved
   out, immediately followed by another header. Needed because that file was sitting at *exactly*
   600/600 and this sub-feature's 13 lines tipped it to RED.

5. **`scripts/_story_resolution.py` extracted** (NEW, 108 lines). Trimming the dead banner had put
   `tests.py` back at *exactly* 600/600, and the mandated Phase 6 docstring correction — the file
   claimed `tests/<tier>/` mirrors `src/specweaver/`, which this sub-feature had just made false —
   immediately re-broke it. A file with zero headroom refuses every legitimate change, so the
   extraction stopped being optional. The roadmap-document parsing (`BASE_SECTION` …
   `integrated_capabilities`) is markdown archaeology over `topic_08_integration/`, a different
   concern from selecting and running pytest tiers, and `_refactor_diff_safety.py` is the
   precedent for splitting exactly this file. `tests.py`: 600 → **538**.

> [!CAUTION]
> **`UsageError` is defined in `_story_resolution.py` and re-exported by `tests.py` — never
> declared in both.** The first cut of the extraction did declare it twice, which is silent and
> nasty: two classes of the same name are two different exceptions, so `main`'s `except UsageError`
> would have missed everything the sibling raised and a usage error would have surfaced as a
> traceback instead of a message. The same applies to `CAPABILITY_ID`, which now lives in the
> sibling only.

## Backlog

Deferred, not lost — raised during this plan's audit and out of SF-01's scope:

- **Cross-story FR credit is systemic.** 54 test files name at least one story and contain FR
  tokens, and where a file names story A while carrying story B's FR numbers, A is credited for
  B's requirements. Example: `tests/unit/core/flow/handlers/test_base.py` names `INT-US-09`,
  `INT-US-21` and `TECH-006` and carries `FR-6`…`FR-12`. This inflates counts across many stories
  and can mask a genuine gap. Auditing it needs a per-story pass over all 54 files — a ticket of
  its own, not a rider on this one. Settled at the Phase 4 gate: **mint it via `specweaver-ticket`
  at TECH-025's closure**, not now, so it can reference what this ticket established rather than
  restating it.

- **Documentation stays in one place.** The marker convention is documented in
  `check_fr_coverage.py`'s module docstring **only** — not in `docs/dev_guides/testing_guide.md`
  and not in the `specweaver-pre-commit` phase-5 reference. Anyone who hits this reads the script
  first, and a convention written in three places drifts in two. Settled at the Phase 4 gate.
