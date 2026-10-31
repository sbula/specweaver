# Walkthrough: TECH-093 — Three code checks read every language as Python

Plan: [TECH-093_implementation_plan.md](TECH-093_implementation_plan.md).

## CB-1 — C01, C06 and C08 judge Python only (FR-1, FR-2, FR-3, FR-4)

### What changed

- New `assurance/validation/rules/code/_python_only.py`:
  - `python_only(rule_id, spec_path)` returns the SKIP reason (`kotlin: C01 checks Python only`,
    or `language unknown: …`), or `None` for Python. The language comes from
    `commons.languages.language_of` (AD-1).
  - `python_tree(rule_id, spec_text, spec_path)` returns the parsed file, or the reason a rule that
    walks it skips. C06 and C08 use it; it also removed their copied parse block.
- `c01_syntax_valid.py` calls `python_only` before `ast.parse`; a Python syntax error still FAILs.
- User guide `1_installation_and_setup.md`: `sw check` and the API show the three as SKIP.
- README counts: 12,080 tests (9,608 unit, 2,022 integration), 12,017 by default, 52 corpora with
  1,258 mutants. Duplication baseline re-frozen: the C06/C08 rule-class clone shrank from 12 to
  8 lines (the shared rule shape), and two clones `TECH-087` removed were dropped from it.

### Red first

- `test_python_only.py`: 24 cases red (every non-Python and unknown case); the 3 Python cases green
  from the start, as NFR-1 and NFR-2 require.
- `test_code_checks_skip_other_languages.py` (FR-3): red with `C01 … FAIL … Syntax error at line 1`.
- `test_api_check_other_languages.py` (FR-4): red with C01 `fail`.
- 21 old cases that called the rules with no path went red (FR-2) and now pass `Path("module.py")`.

### Proof

- `TECH-093_mutants.json`, 5 of 5 killed: `language-check-removed`, `c01-skips-the-check`,
  `c06-skips-the-check`, `c08-skips-the-check`, `unknown-language-parsed`.
- `check_fr_coverage.py TECH-093`: FR-1..FR-4 planned and cited.
- Live: `sw check --level code src/main/kotlin/shop/Cart.kt` in a scratch home printed
  `C01 Syntax Valid SKIP kotlin: C01 checks Python only` (and the same for C06, C08).

### Red/Blue (Phase 7.5), 2 cycles

- R1 (LOW) A Python script with no ending (`manage`) now skips as "language unknown". Accepted:
  the user's Q1 `[agreed 2026-10-31]`.
- R2 (LOW) `.pyw` is not in `language_of`'s table. Accepted (design risk table); the table is the
  one place to add it.
- R3 (LOW) The summary line still counts no SKIP. Deferred to the next TECH ticket started
  `[agreed 2026-10-31]`.
- R4 (LOW) `python_tree` returns `ast.Module | str`; `mypy` in `cb` checks both branches. No change.
- Cycle 2: challenged R1 (could a shebang decide the language?). No: that would be a second
  language table, against AD-1. No new finding.
