# Implementation Plan: AST Semantic Chunking [SF-02: A symbol yields its signature and its description]

- **Feature ID**: B-SENS-03
- **Sub-Feature**: SF-02 — A symbol yields its signature and its description
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_design.md
- **Design Section**: §Sub-Feature Breakdown → Group A → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf02_implementation_plan.md
- **Status**: DRAFT
- **FRs**: FR-5 (the description), FR-6 (the signature) · **Depends on**: none

## Research Notes

Measured 2026-08-26 against all ten shipped parsers. Nothing here is recalled.

### A doc comment is a previous sibling, at one of two depths

| Depth | Languages | Shape |
|---|---|---|
| 0 — `name_node.parent.prev_sibling` | Java, Kotlin, TypeScript, Rust, Go | `method_declaration <- prev: block_comment` |
| 1 — one level further up | C, C++ | `function_declarator` is the parent; the comment precedes `function_definition` |
| **none** | **Python** | the docstring is **inside** the body: `function_definition > block > expression_statement > string` |

So the walk is short and bounded, and the only per-language variance is a **depth** and Python's
entirely different mechanism.

### Three measurements that shaped the decisions

1. **Stacked comments are separate siblings.** `/// Line one.` and `/// Line two.` arrive as two
   `line_comment` nodes, as do consecutive Go `//` lines. Collecting only the nearest would return
   the last line of a doc block and drop the rest.
2. **A blank line does not break `prev_sibling`.** A Go comment **three lines above** a function is
   still its previous sibling. Adjacency has to be checked on line numbers, not on tree position —
   `comment.end_point[0]` versus `declaration.start_point[0]`.
3. **`SCM_COMMENT_QUERY` is not the tool for this.** It returns *every* comment in the file with no
   relation to any declaration. `extract_traceability_tags` uses it exactly that way, and that is
   the right use for it. This feature needs attachment, which the query cannot express.

### The comment query, per parser

| | query |
|---|---|
| java · kotlin · rust | `(line_comment) @comment` + `(block_comment) @comment` |
| c · cpp · go · python · typescript | `(comment) @comment` |
| markdown | `(html_block) @comment` — not a doc-comment concept |
| **sql** | **empty** |

### `FR-6` is almost free

`extract_symbol` minus `extract_symbol_body` yields the signature for **9 of 10** parsers, verified
by running both on every language: the body string is a suffix of the symbol string in every case
except SQL, where `extract_symbol_body` raises `CodeStructureError` because the declarative tier has
no target block. SQL's whole declaration **is** its signature.

Existing signatures, quoted from `interfaces.py`:

```python
def extract_symbol(self, code: str, symbol_name: str) -> str
def extract_symbol_body(self, code: str, symbol_name: str) -> str
def extract_skeleton(self, code: str) -> str        # whole file, not per symbol
```

`extract_skeleton` already elides bodies and keeps doc comments — it is the whole-file form of what
`FR-6` needs per symbol, and confirms the output shape is one this codebase already produces.

### No marker stripping exists anywhere

`_trace_tags` regex-searches raw comment text and never strips. `FR-5`'s stripping is new code.

## Audit resolutions

| # | Question | Resolution |
|---|---|---|
| Q38 | What counts as attached? | **No blank line** between the comment and the declaration `[agreed 2026-08-26]`. Not an invented number — godoc, rustdoc and javadoc all require adjacency. Under the alternative a file-header licence block becomes the description of the first declaration in every file |
| Q39 | Which comments count? | **Any adjacent comment**, whatever its marker `[agreed 2026-08-26]`. Filtering to `///` and `/** */` gives **Go nothing**, and Go is one of the eight |
| Q40 | Strip the markers? | **Yes** `[agreed 2026-08-26]`. The consumer is an embedding model, and `/**`, `///` and `#` appear in every doc in a language, so they carry no signal and make same-language chunks look alike |
| — | SQL and markdown | Return `""`. Neither has a doc-comment concept: SQL's query is empty and markdown's captures `html_block`. Recorded as a limit, not solved |
| — | Python's docstring | It **is** the description. `FR-5`'s purpose says descriptions must reach the index *"in every language, not only Python"*, so Python is the baseline rather than an open question |
| — | Where the code lives | A `_docs.py` beside `_visibility.py`: the shared walk and the stripping. Per-language variance is a **class attribute** (the depth) plus one module function for Python — the shape SF-01 CB-2 settled on, which keeps `check_class_health` quiet by construction rather than by re-freezing |

## Commit boundaries

### CB-1 — `extract_symbol_doc`

**Goal**: `FR-5`. A symbol's description, marker-free, or `""`.

| Task | File |
|---|---|
| 1 | `_docs.py` — collect consecutive preceding comment siblings, reject on a line gap, strip markers. **A "comment sibling" is a node whose type contains `comment`**, which is why markdown falls out correctly for free: its comment node is `html_block`, so the walk finds nothing and returns `""` without a special case |
| 2 | `extract_symbol_doc(code, symbol_name) -> str` on the mixin, delegating to **one hook** `_doc_of(name_node) -> str`. The default hook is the sibling walk, at `_DOC_DEPTH` (class attribute, `0`) |
| 3 | `_DOC_DEPTH = 1` on C and C++ — a different **depth**, same mechanism. **Python overrides the hook itself**, not the depth: its docstring is inside the body and no walk finds it. `_doc_of = staticmethod(_docstring_of)`, the binding shape SF-01 CB-2 settled on |
| 4 | Abstract method on `CodeStructureInterface`, and the `CompleteParser` stub in `test_parsers_interfaces.py` implements it — SF-01 CB-2 hit this exact stub |

**Tier**: unit. Behaviour of one module, no seam.

**Red first**: the accessor does not exist, so every case fails on attribute lookup before any
docstring is written.

**Test matrix**: happy path — one doc per language, all ten · boundary — stacked comment lines,
a symbol with no doc, an empty file · degradation — unparseable source, SQL and markdown returning
`""` · hostile — a comment separated by a blank line (**must not attach**), a name not in the file,
an empty name.

> **Expected mutants**, both required:
> - the gap check always passes → the distant-comment test must object
> - the stripping is skipped → the marker-free assertions must object
>
> **Done when** both are killed. The first is the one that matters: without it the feature quietly
> attaches licence headers to code, and every assertion about a *present* doc still passes.

### CB-2 — `extract_symbol_signature`

**Goal**: `FR-6`. Doc plus signature, body elided.

| Task | File |
|---|---|
| 1 | `extract_symbol_signature(code, symbol_name) -> str` on the mixin: doc from CB-1, then `extract_symbol` with the body **span** removed. Cut by AST byte offsets rather than by string subtraction — the body is a suffix in all nine cases today, so both work, but only one keeps working when a body's text repeats elsewhere in the declaration |
| 2 | SQL: no body to remove, so the declaration is returned whole |
| 3 | Abstract method + stub, as CB-1 |

**Tier**: unit.

**Red first**: the accessor does not exist.

**It must compose CB-1 for real.** The dev skill's rule — *is this only ever used in sequence with
something else?* — applies directly: `FR-6` is `FR-5` plus an elision. A test that hand-builds the
doc string proves the elision and mocks the half that is harder to get right. The assertions here
assert the **pair**.

**Python needs no special case here, and that was checked rather than assumed.** Its
`extract_symbol_body` **includes** the docstring, so removing the body strips it too and `FR-6`
re-adds it from `FR-5` — one copy, not two. Measured: `symbol - body` leaves
`def add(self, a: int) -> int:` exactly.

> **Expected mutant**: the body elision is skipped → the signature returns the whole implementation.
> **Done when** killed by a test asserting a body token is **absent** *and* a paired assertion that
> the signature text is **present**. Absence alone passes for free when the function returns `""`,
> and presence alone passes for free when nothing was elided. Neither half is a test on its own.

## Risks

| Risk | Mitigation |
|---|---|
| The gap check attaches a licence header | The hostile case is written in CB-1 and carries a required mutant, so a green run cannot hide it |
| Marker stripping mangles a doc's content | Strip **leading** markers only, per line — `///`, `//!`, `//`, `/**`, `#`, a continuation `*`, and the trailing `*/`. A block comment's interior lines start ` * ` and would otherwise read as bullet points. Assert on a doc whose **text** contains `*` and `/`, so a greedy strip is caught |
| `extract_symbol_body` raising for SQL leaks out of `FR-6` | SQL's case is written before the implementation, and `FR-6` must never raise — it is called per symbol during a scan |
| A new abstract method breaks a stub | Happened in SF-01 CB-2. `test_parsers_interfaces.py` is on the task list for both boundaries rather than discovered by a red suite |

## Not in this sub-feature

- Chunking. `extract_symbol_signature` is what SF-06's **skeleton layer** is built from; nothing
  consumes it here, which is the same shape SF-01 shipped under `[agreed 2026-08-26]`
- SQL and markdown descriptions — no concept exists to read
- Rust's lost trait names and SQL's torn ones — **SF-03**
