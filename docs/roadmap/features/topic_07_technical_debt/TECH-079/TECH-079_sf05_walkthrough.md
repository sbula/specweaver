# Walkthrough: TECH-079 SF-05 — Analyzers on one base

## CB-1: pin the Python style results, one style base (FR-16)

**What changed**
- `assurance/standards/tree_sitter_base.py`: the style base `TreeSitterAnalyzer` is now
  `TreeSitterStyleAnalyzer`; no alias (NFR-3). The module holds the helpers every style analyzer
  shares, once (Q3 `[agreed 2026-11-06]`): `classify_name`, `compute_confidence`, `file_weight`, and
  `vote_result(category, sample_size, **votes)`, which turns vote counts into a `CategoryResult`.
- The Python, JavaScript and TypeScript analyzers use them. Their own copies are gone, and so is
  the JavaScript analyzer's import of the Python analyzer's private `_classify_name`.

**What a user sees.** Nothing: `sw standards scan` gives the same results.

**Tests**
- Pinned first: `tests/integration/assurance/standards/test_python_style_results_pinned.py` scans
  real files through `StandardsScanner` and compares each of the six Python categories with values
  worked out by hand from the fixtures. It is green on the old parser by design; CB-3 must keep it
  green.
- Red first: `test_the_old_base_name_is_gone` (`ImportError`).
- Moved (NFR-1): the tests of `_classify_name`, `_compute_confidence` and `_file_weight` moved from
  `test_python_analyzer.py` to `test_tree_sitter_base.py`, against the shared helpers; same cases.
  New: two tests of `vote_result`.

**Mutants.** Run, not yet in the corpus (CB-3 adds the FR-17 set): confidence taken from the last
vote, and a `snake_case` pattern that admits capitals — the pin objected to both.

**Red/blue (2 cycles).** No finding above threshold. Checked: each replaced block computed the
confidence from its first counter, or 0 when empty, as `vote_result` does; the order of the
`dominant` keys is unchanged; `vote_result` with no vote would fail, and no caller passes none.

**Gate.** The duplication check found the old repeated vote blocks once the helpers moved; they are
now one helper, and the baseline is re-frozen at 89 clones, none new.

## CB-2: the code rules read a leading BOM (FR-18)

**What changed**
- `assurance/validation/rules/code/_python_only.py`: new `parse_python(text)` drops one byte order
  mark at the very start, as Python does for a file on disk, then calls `ast.parse`. C01 and
  `python_tree` (C06, C08) use it. One place covers every door (`sw check`, `POST /api/v1/check`,
  the validate steps), because each hands the rules the text it read (Q6 `[agreed 2026-11-06]`).

**What a user sees.** `sw check --level code` on a Python file saved with a BOM: C01 passes, and C06
and C08 judge the file. Before, C01 failed with "invalid non-printable character U+FEFF" and C06
and C08 skipped it.

**Tests.** Red first: `tests/integration/assurance/validation/test_check_reads_a_bom.py` through the
real CLI (red: 3 of 4; the BOM-in-the-middle case was already right and stays a failure on line 2).

**Mutants.** TECH-079 FR-18 `bom-kept` (objected by 3 tests). TECH-093 FR-1 `c01-skips-the-check`
re-pinned after C01 changed, re-run on its scope and objected. `stale_mutants.py`: 0.

**Red/blue (2 cycles).** No finding above threshold. Checked: only one leading mark is dropped, so
line numbers stay right; a file of only a BOM parses as empty, as in Python; the rules never see
bytes, so a BOM in another encoding is not this rule's case.
