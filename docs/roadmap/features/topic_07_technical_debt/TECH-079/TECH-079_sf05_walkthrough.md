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
