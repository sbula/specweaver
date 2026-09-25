# B-SENS-03 SF-02 — A symbol yields its signature and its description

**Status**: DRAFT · **FRs owned**: FR-5 (the description), FR-6 (the signature) · **Depends on**:
none · Design: [B-SENS-03_design.md](B-SENS-03_design.md) §Sub-features → SF-02

## Goal

Two additive parser accessors: `extract_symbol_doc` (`FR-5`) and `extract_symbol_signature`
(`FR-6`). `extract_symbol` stays unchanged (`AD-2`). They feed SF-06's skeleton layer.

## Where it plugs in

Measured 2026-08-26 against all ten parsers.

| Fact | Where |
|---|---|
| A doc comment is a previous sibling. Java, Kotlin, TypeScript, Rust, Go: `name_node.parent.prev_sibling` (`method_declaration <- prev: block_comment`). C, C++: one level up — `function_declarator` is the parent; the comment precedes `function_definition`. **Python**: the docstring is **inside** the body — `function_definition > block > expression_statement > string` | tree shape |
| **Stacked comments are separate siblings**: `/// Line one.` and `/// Line two.` arrive as two `line_comment` nodes, as do consecutive Go `//` lines. Taking only the nearest drops all but the last line | tree shape |
| **A blank line does not break `prev_sibling`**: a Go comment **three lines above** a function is still its previous sibling. Adjacency is checked on line numbers — `comment.end_point[0]` vs `declaration.start_point[0]` | tree shape |
| `SCM_COMMENT_QUERY` returns *every* comment with no relation to a declaration — right for `extract_traceability_tags`, wrong for attachment | every parser |
| Comment queries: java · kotlin · rust `(line_comment) @comment` + `(block_comment) @comment`; c · cpp · go · python · typescript `(comment) @comment`; markdown `(html_block) @comment` (not a doc-comment concept); **sql** empty | per parser |
| `extract_symbol` minus `extract_symbol_body` yields the signature for **9 of 10** parsers — the body is a suffix of the symbol in every case except SQL, where `extract_symbol_body` raises `CodeStructureError` (the declarative tier has no target block). SQL's whole declaration **is** its signature | `interfaces.py` |
| `extract_skeleton` already elides bodies and keeps doc comments — the whole-file form of `FR-6` | `interfaces.py` |
| No marker stripping exists: `_trace_tags` regex-searches raw comment text | — |

```python
def extract_symbol(self, code: str, symbol_name: str) -> str
def extract_symbol_body(self, code: str, symbol_name: str) -> str
def extract_skeleton(self, code: str) -> str        # whole file, not per symbol
```

## Changes

### CB-1 — `extract_symbol_doc` (`FR-5`)

| Task | File |
|---|---|
| 1 | `_docs.py` beside `_visibility.py`: collect consecutive preceding comment siblings, reject on a line gap, strip markers. **A "comment sibling" is a node whose type contains `comment`** — so markdown (`html_block`) returns `""` with no special case |
| 2 | `extract_symbol_doc(code, symbol_name) -> str` on the mixin, delegating to one hook `_doc_of(name_node) -> str`; default is the sibling walk |
| 3 | **Python overrides the hook**, not the walk: `_doc_of = staticmethod(_docstring_of)`, the SF-01 CB-2 binding shape |
| 4 | Abstract method on `CodeStructureInterface`; the `CompleteParser` stub in `test_parsers_interfaces.py` implements it |

Matrix: happy — one doc per language, all ten · boundary — stacked lines, no doc, empty file ·
degradation — unparseable source, SQL and markdown return `""` · hostile — comment separated by a
blank line (**must not attach**), a name not in the file, an empty name.

Required mutants: the gap check always passes (without it licence headers attach to code and every
*present*-doc assertion still passes); the stripping is skipped.

### CB-2 — `extract_symbol_signature` (`FR-6`)

| Task | File |
|---|---|
| 1 | `extract_symbol_signature(code, symbol_name) -> str`: doc from CB-1, then `extract_symbol` with the body **span** removed by AST byte offsets, not string subtraction — only offsets keep working when a body's text repeats elsewhere in the declaration |
| 2 | SQL: no body, so the declaration is returned whole |
| 3 | Abstract method + stub, as CB-1 |

**It composes CB-1 for real**: `FR-6` is `FR-5` plus an elision, so tests assert the pair rather
than hand-build the doc. Python needs no special case: its `extract_symbol_body` **includes** the
docstring, so `symbol - body` leaves `def add(self, a: int) -> int:` exactly and `FR-6` re-adds the
doc once.

Required mutant: body elision skipped — killed by a body token **absent** *and* the signature
**present** (each alone passes for free).

## Tests

| Tier | File | Covers |
|---|---|---|
| Unit | `tests/unit/workspace/ast/parsers/test_symbol_docs.py` | `FR-5` |
| Unit | `tests/unit/workspace/ast/parsers/test_symbol_signatures.py` | `FR-6` |

Unit only: behaviour of one module, no seam. Red first: the accessors do not exist.

## Decisions (audit)

| # | Question | Resolution |
|---|---|---|
| Q38 | What counts as attached? | **No blank line** between comment and declaration `[agreed 2026-08-26]`. godoc, rustdoc and javadoc all require adjacency. Otherwise a file-header licence becomes the first declaration's description in every file |
| Q39 | Which comments count? | **Any adjacent comment**, whatever its marker `[agreed 2026-08-26]`. Filtering to `///` and `/** */` gives **Go nothing**, and Go is one of the eight |
| Q40 | Strip the markers? | **Yes** `[agreed 2026-08-26]`. The consumer is an embedding model; `/**`, `///` and `#` appear in every doc in a language and make same-language chunks look alike |
| — | SQL and markdown | Return `""` — no doc-comment concept. A limit, not solved |
| — | Python's docstring | It **is** the description, and the baseline |
| — | Where the code lives | `_docs.py` beside `_visibility.py`, per-language variance as a hook binding — keeps `check_class_health` quiet by construction |

| Risk | Mitigation |
|---|---|
| The gap check attaches a licence header | Hostile case + required mutant |
| Marker stripping mangles content | Strip **leading** markers only, per line — `///`, `//!`, `//`, `/**`, `#`, a continuation `*`, and the trailing `*/`. Assert on a doc whose **text** contains `*` and `/` |
| `extract_symbol_body` raising for SQL leaks out of `FR-6` | `FR-6` never raises — called per symbol during a scan |
| A new abstract method breaks a stub | `test_parsers_interfaces.py` on the task list for both boundaries |

Not here: chunking (SF-06 builds the skeleton layer; nothing consumes these yet, the shape SF-01
shipped under `[agreed 2026-08-26]`); SQL and markdown descriptions; Rust and SQL names (SF-03).

## As built (2026-08-26)

| Where | What |
|---|---|
| `parsers/_docs.py` | **Anchor rule: climb to the outermost ancestor starting on the same row, then read its previous sibling.** A wrapper always opens on the same row as what it wraps, so the climb finds it everywhere and stops before the file. Replaces the planned per-language `_DOC_DEPTH` in all ten languages — a fixed depth cannot say that C needs one extra level for a function and none for a struct |
| | Rust's `line_comment` owns its trailing newline, so adjacency normalises to the comment's last *content* row — one strict rule, no "gap of 0 or 1" that would also admit a trailing inline comment. The same newline is stripped when joining stacked `///` lines; newlines *inside* a block comment are kept |
| `extract_symbol_doc` | marker-free, or `""`. Never raises |
| `extract_symbol_signature` | description, then declaration without body. **No `{ ... }` placeholder**, unlike `extract_skeleton` — `FR-12` labels the chunk a skeleton, so a placeholder would be the same three characters in every skeleton chunk. Description stripped per Q40 |

Wrappers the row rule handles:

| | inner node | the wrapper the comment precedes |
|---|---|---|
| TypeScript | `class_declaration` | `export_statement` |
| Go | `type_spec` | `type_declaration` |
| C, C++ | `struct_specifier` | *(none — already outermost)* |

Open: a doc comment carrying a `@trace(...)` tag reaches the description as text — harmless for an
embedding, recorded rather than filtered.

Walkthroughs: [cb1](B-SENS-03_sf02_cb1_walkthrough.md) · [cb2](B-SENS-03_sf02_cb2_walkthrough.md).
