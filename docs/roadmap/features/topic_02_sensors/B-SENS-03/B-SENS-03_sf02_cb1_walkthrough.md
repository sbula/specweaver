# Walkthrough: `B-SENS-03` SF-02 CB-1 — a symbol yields its description

- **Story**: `B-SENS-03` SF-02, commit boundary 1 of 2 · **DAL-B** · 2026-08-26
- **Proves**: `FR-5`

## What shipped

`extract_symbol_doc(code, symbol_name) -> str` on every parser: the description written above a
declaration, marker-free, or `""`. Never raises — it is called once per symbol during a
whole-repository scan.

`extract_symbol` had been dropping doc comments in every language but Python, which passed only by
accident: a docstring lives *inside* the body, so extracting the body took it along.

## Attachment is a position **and** a line gap

`prev_sibling` alone is not enough. Measured: a Go comment **three blank lines above** a function is
still its previous sibling. Without a gap check, every file's licence header becomes the description
of its first declaration — and **every test about a present description still passes**.

That case carries a required mutant for exactly that reason.

## The design the tests forced

The plan said a per-language **depth**: 0 for most, 1 for C and C++. That passed every method-level
test. Then the Phase 2 gap analysis asked for **type**-level cases, and four of eight failed:

| | inner node | the wrapper the comment actually precedes |
|---|---|---|
| TypeScript | `class_declaration` | `export_statement` |
| Go | `type_spec` | `type_declaration` |
| C, C++ | `struct_specifier` | *(none — already outermost)* |

A fixed depth cannot express that: **C needs one extra level for a function and none for a struct.**

The rule that does: **climb to the outermost ancestor starting on the same row, then read its
previous sibling.** A wrapper always opens on the same row as what it wraps, so the climb finds it
everywhere and stops before reaching the file. `_DOC_DEPTH` was deleted — the row rule replaces it
in all ten languages.

That design came from the gap analysis, not from the plan.

## Two grammar differences, normalised rather than papered over

1. **Rust's `line_comment` owns its trailing newline**, so `end_point` already sits on the next row
   while Go's and Java's do not. The fix normalises to the comment's last *content* row, keeping
   adjacency a single strict statement. Allowing "a gap of 0 or 1" would have hidden the difference
   behind a looser rule that also admits a trailing inline comment.
2. **The same newline** would have inserted a blank line when joining stacked `///` lines. Stripped
   at collection; newlines *inside* a block comment are kept.

## Two of my own tests were fake, and the mutant said so both times

1. The licence-header case was written in **Python** — which reads a docstring and never walks
   siblings, so it passed whatever the gap check did.
2. Rewritten in Go, the header sat **before `package m`** — so `func`'s previous sibling was the
   package clause, not a comment, and the walk stopped before reaching the gap check at all.

Both were green. Both proved nothing. The mutant survived both times, which is the only signal
that said so. Python's real protection is now stated as what it is — a separate test, named for
the docstring mechanism rather than for the gap rule.

## Mutants — six, all killed

| # | Neutralised | Objections |
|---|---|---|
| M1 | the line-gap check | 3 |
| M2 | marker stripping | 13 |
| M3 | only the nearest comment is taken | 2 |
| M4 | Python's docstring reader | **1** |
| M6 | the wrapper climb stops | 4 |
| M7 | the climb never stops, and reaches the file | 21 |

**M4 has a single point of protection.** Carried here rather than shrugged at.

## Results

| Check | Result |
|---|---|
| Full suite | **8,795 passed, 11 skipped** |
| `quality.py cb` | 15 of 15 · `doc` 13/13 · `mypy` clean · `tach` ✅ |
| New tests | 72 |

**And the lesson from CB-3 was applied, and paid.** `quality.py cb` printed only *"1 clone removed"*.
Running `check_duplication.py` directly showed a `NEW duplication` section the gate's summary had
cut. Verified by `git diff` that TypeScript is **untouched** by this boundary and Python gained two
lines, neither inside the clone region — pre-existing SF-01 shape re-keyed by one added import.
Re-frozen on that evidence.

## Not done here

- `extract_symbol_signature` — CB-2, which composes this
- A doc comment carrying a `@trace(...)` tag reaches the description as text. Harmless for an
  embedding, and recorded rather than filtered
