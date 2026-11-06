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

## CB-3: Python style on tree-sitter (FR-17)

**What changed**
- `assurance/standards/languages/python/analyzer.py`: `PythonStandardsAnalyzer` extends
  `TreeSitterStyleAnalyzer` and parses with `PythonCodeStructure().parser`. The six extractors walk
  tree-sitter nodes and keep `ast`'s rules: only plain parameters count for type hints (after any
  `/`, before any `*`); a docstring is a plain string (no f-, t- or bytes prefix) first in the body
  that holds more than whitespace once its escapes are decoded; `from __future__` is absolute;
  the test framework is the import nearest the top, found breadth first as `ast.walk` did. `ast` is
  no longer imported.
- `tree_sitter_base.py`: a `_readable(tree)` hook, True by default. The Python analyzer skips a tree
  with `has_error` (Q2 `[agreed 2026-11-06]`); JavaScript and TypeScript count such trees, as before.

**What a user sees.** The same `sw standards scan` results, and a Python file saved with a BOM now
counts (Q1 `[agreed 2026-11-06]`); before, it was skipped.

**Tests**
- The CB-1 pin stays green unchanged, plus a BOM case (red first: the old parser skipped the file).
  Found at dev: tree-sitter keeps escape sequences inside the string content, so the first version
  counted `"\n"` as a docstring; two escape cases joined the pin and the escapes are now decoded.
- Red first: the analyzer is a `TreeSitterStyleAnalyzer` on `PythonCodeStructure`. The two
  `_parse_file` tests now go through `extract_all` (Q5). New: an aliased and a relative framework
  import, and a JavaScript tree with errors still counts. Each new expected value was also checked
  against the old `ast` analyzer.
- Parity: the old and the new analyzer give the same six results on the repo's 1,776 Python files.

**Mutants.** TECH-079 FR-17: `fstring-is-docstring`, `escapes-not-decoded`, `keyword-only-counts`,
`relative-is-absolute`, `broken-file-counted`, `depth-first-framework`, each objected by the pin.
`stale_mutants.py`: 0.

**Red/blue (2 cycles).** Cycle 1: (MEDIUM, fixed) escape sequences, above; (MEDIUM, checked) a
comment before the first statement is skipped, as `ast` ignores comments; (LOW, checked) a
non-UTF-8 byte in a name decodes with `errors="replace"`, as `read_text` did. The complexity gate scored `_has_docstring`
17; it is now `_leading_string` and `_plain_text`. Cycle 2: none above
threshold.

**Docs.** `language_support_guide.md` step 10 names the base and `vote_result`; step 9 no longer
names the removed `rename._RESOLVERS`. `legacy_feature_map.md` §3.5 says tree-sitter.
