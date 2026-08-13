# Design: Split the AST Parser Hierarchy by Language Paradigm

- **Feature ID**: TECH-034
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-12 — see §Delivery.
- **Origin**: Found 2026-08-12 while reducing `TECH-023`'s complexity debt across
  `workspace/ast/parsers/`. Refactoring nine parsers in two batches made the duplication
  structural rather than anecdotal, and the measurements below were taken during that work.

## Problem Statement

`BaseTreeSitterParser` is one abstract base for **ten** wildly different languages, from C++ to
SQL. Every parser must answer the whole contract, so a language without the concept answers with a
stub.

**Measured 2026-08-12** — ten parsers, 2,587 lines:

| Method | Implementations | Total lines | Range each |
|---|---|---|---|
| `add_symbol` | 10 | 254 | 6–35 |
| `_is_symbol_valid` | 10 | 182 | 9–22 |
| `_format_body_injection` | 10 | 146 | 4–21 |
| `extract_imports` | 10 | 141 | 2–22 |
| `extract_framework_markers` | 10 | 129 | 2–25 |
| `_find_symbol_node` | 10 | 126 | 7–23 |
| `_find_target_block` | 10 | 103 | 2–25 |
| `_get_symbol_scope` | 9 | 102 | 2–17 |

The `2–` end of those ranges is the finding. A two-line implementation is a **stub written to
satisfy the ABC**, not a design:

| Parser | Methods | Stubs | Real |
|---|---|---|---|
| `sql` | 18 | **11 (61%)** | 7 |
| `markdown` | 23 | **11 (48%)** | 12 |
| `go` | 23 | 9 | 14 |
| `c` / `rust` / `cpp` | 19–28 | 7–8 | 11–20 |
| `java` / `kotlin` / `python` / `typescript` | 21–27 | 6 | 15–21 |

`check_class_health` reaches the same conclusion independently: every parser is flagged incohesive
(`LCOM4` 4–5), with components that separate almost exactly along the lines below.

## The paradigm split is visible in the code, not just in theory

Which parsers override the *concept-bearing* methods:

| | c | cpp | go | java | kotlin | md | py | rust | sql | ts |
|---|---|---|---|---|---|---|---|---|---|---|
| `_extract_bases` | – | **–** | – | ✅ | ✅ | – | ✅ | – | – | ✅ |
| `_extract_decorators` | – | – | – | ✅ | ✅ | – | ✅ | ✅ | – | ✅ |
| `extract_framework_markers` | ✅ | ✅ | stub | ✅ | ✅ | stub | ✅ | ✅ | stub | ✅ |
| `_is_symbol_valid` | ✅ | ✅ | ✅ | ✅ | ✅ | stub | ✅ | ✅ | stub | ✅ |

Three tiers fall out:

- **Class-based** — `java`, `kotlin`, `python`, `typescript` (and `cpp`, see the gap below). The
  only parsers overriding *both* bases and decorators, and the ones with the fewest stubs.
- **Function-based** — `c`, `go`, `rust`. No inheritance to extract. **`rust` is the useful
  awkward case**: attributes give it decorators without bases, which is why the axis is "does it
  have inheritance", not "is it OO".
- **Declarative** — `markdown`, `sql`. Roughly half their surface is stubs. They are answering a
  contract written for programming languages.

## Candidate Approaches (not yet designed) — proposed shape

```
CodeStructureInterface
└── BaseTreeSitterParser        query/walk/edit mechanics — genuinely shared by all
    ├── ClassBasedParser        bases + decorators/annotations
    ├── FunctionBasedParser     free functions, no inheritance
    └── DeclarativeParser       named declarations, no executable bodies
```

`TECH-023`'s work already moved `_split_scope`, `_named_nodes`, `_named_matches`,
`_children_of_type` and `_text_of` onto the base — **this ticket inherits a half-finished state**,
which is part of why it is worth doing deliberately rather than leaving to drift.

## The C++ inheritance gap — must be fixed

**`CppCodeStructure` extracts no inheritance at all.** Zero references to `_extract_bases` or
`base_class_clause` in the whole parser, while its four class-based siblings all extract it. C++
plainly has inheritance, so this is a **capability gap, not a design decision** — `class D : public B`
currently reports no bases.

The user's decision (2026-08-12) is that this **must be fixed**, not merely recorded. It is called
out separately because it is the one **behaviour change** in an otherwise structural ticket, and it
is the clearest argument for the split: an intermediate layer would have made a class-based parser
that cannot report a base class structurally obvious rather than invisible.

## Future languages are the real test of the split

The tiers must be judged against what is *coming*, not only what exists — a split that only fits
today's ten is a description, not a design. Named as design input, **not to be implemented here**:

| Candidate | Tier it argues for | What it stresses |
|---|---|---|
| `xml` | Declarative | Deep nesting, attributes, no symbols with bodies — like `markdown`, unlike `sql` |
| `proto` | Declarative | **Breaks a naive split**: messages/services look like type declarations *and* it has real `import` statements, which no other declarative language here has |
| `http` | Declarative | Requests, not declarations at all — may not fit any current tier |
| `lisp` | Function-based | Homoiconic: `defun`/`defmacro` are list forms, and there is no `block` node to inject a body into |
| `typescript` | Class-based | Already present; interfaces and type aliases sit awkwardly beside classes |

Two of these are load-bearing for the design:

- **`proto` has imports.** Every current declarative parser stubs `extract_imports`. If
  `DeclarativeParser` stubs it at the tier level, `proto` immediately has to override it back —
  which means the tier is wrong, or the tier must not stub it.
- **`lisp` has no block node.** `_find_target_block` and `_format_body_injection` assume a brace or
  indent-delimited body. A tier that assumes those is a tier `lisp` cannot join.

**The discriminator to design against is not "OO vs procedural"** but four independent questions,
which the table above shows do not co-vary cleanly:

1. Does it have **inheritance**? (bases)
2. Does it have **annotations**? (`rust` says yes without inheritance)
3. Does it have **executable bodies** to inject into? (`lisp` complicates this)
4. Does it have **imports**? (`proto` says yes without any of the above)

A design that answers all four with one axis will be wrong for `rust` today and `proto` tomorrow.

## Non-Goals (proposed, pending design)

- **Not** a change to any parser's *extraction behaviour*, with the single, explicit exception of
  the C++ inheritance gap above.
- **Not** implementing `xml` / `proto` / `http` / `lisp`. They are design input only.
- **Not** `TECH-023`'s remaining complexity reduction, which continues independently outside
  `parsers/`. The seven violations still inside `parsers/` (`base.py`'s three, `cpp`'s visibility
  walk, and the three external-tool report parsers) should be re-measured *after* this lands rather
  than fixed twice.

## Verification the design must specify

- Every existing parser test passes untouched — 636 in `tests/unit/workspace` and
  `tests/integration/workspace` — except those asserting the C++ gap's current (wrong) behaviour.
- A **new** test that C++ reports base classes, which is the one behaviour this ticket changes.
- A guard that a parser cannot silently answer a tier's method with a stub, so the pathology this
  ticket removes cannot regrow. `check_class_health`'s `LCOM4` on these classes is the obvious
  before/after measurement.

## Delivery, 2026-08-12

### The design question, settled before building

`proto` and `lisp` do **not** break the three-tier shape, on one condition: **a tier supplies
defaults, never prohibitions.**

- `proto` is declarative *with real imports*. `DeclarativeParser.extract_imports` returns `[]` as a
  **default**, so `proto` overrides it — ordinary subclassing, not a broken tier. A tier that
  *forbade* imports would have been wrong the day `proto` arrived.
- `lisp` has bodies but no brace-delimited block. `_find_target_block` therefore stays
  per-language rather than being implemented in a tier, so a tier never assumes braces.

Both are written into `tiers.py` where the next person meets them.

### What shipped, in three steps

**1. One declared grammar per parser.** All ten carried identical `__init__` plus two pass-through
properties to hold one value. Now `grammar = staticmethod(tree_sitter_x.language)` and the base
builds everything. A static method rather than a class attribute because a bare callable in a class
body is a *method* to the type checker and would be handed `self`; a callable rather than a module
reference because TypeScript needs `language_typescript`.

**2. Three tiers.** `ClassBasedParser` (Java, Kotlin, Python, TypeScript, C++),
`FunctionBasedParser` (C, Go, Rust), `DeclarativeParser` (Markdown, SQL). SQL and Markdown shed
four hand-written stubs each.

**3. The C++ gap, fixed** — the ticket's one intended behaviour change.

### The tier caught the C++ gap by construction

The moment `CppCodeStructure` was reparented onto `ClassBasedParser`, **it stopped being
instantiable**: `TypeError: Can't instantiate abstract class CppCodeStructure without an
implementation for abstract methods '_extract_bases', '_extract_decorators'`.

That is the ticket's central argument, demonstrated rather than asserted. The gap had been
invisible for as long as one base class served every language, because that base never asked.

The gap was also **wider than recorded**: `extract_framework_markers` returned `{}`
unconditionally, so C++ reported no bases *and* no attributes. Both are implemented now, with
`_ACCESS_SPECIFIERS` documented because a naive walk over `base_class_clause` collects `public` /
`private` / `protected` as base names — the obvious way to get C++ inheritance wrong, pinned by its
own test.

### Cohesion, measured before and after

`check_class_health`'s `LCOM4` is the independent evidence the ticket asked for:

| | before | after |
|---|---|---|
| Language parsers flagged | 10 | **7** |
| Worst parser | TypeScript, 6 | **2** |
| Every remaining parser | 3–6 | **2** (the minimum failing value) |
| C++, Python, C | flagged | **off the list** |
| `BaseTreeSitterParser` | 6 | **8** |

**The base got worse, and that is the honest trade.** The parsers shed their shared mechanics into
it, so the concentration moved rather than vanishing. Splitting the base itself — its query, walk,
edit and format concerns are four different jobs — is the natural next step and belongs to
`TECH-035`, which already owns the class-health debt.

### Test changes

Only two, both required rather than incidental:

- `test_polyglot_ast_cpp` asserted `markers == {}` — it was **codifying the gap**. Now it asserts
  the key *exists* with an empty `extends`, which is the difference between "no bases" and "not
  supported". The ticket anticipated exactly this exception.
- `check_conventions`' parser family required inheriting `BaseTreeSitterParser` **literally**. The
  invariant still holds transitively through the tiers, so the rule learned `also_accepts` rather
  than the hierarchy being forced flat to satisfy a checker.

6479 tests pass, `mypy` and `tach` clean. `class_health` remains red at 20 classes — pre-existing,
tracked as `TECH-035`, and **down from 23** partly because of this work.

## Next Step

Done. `xml` / `proto` / `http` / `lisp` remain design input only; the tiers are shaped for them but
none is implemented.
