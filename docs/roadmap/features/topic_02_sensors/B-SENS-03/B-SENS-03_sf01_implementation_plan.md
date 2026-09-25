# B-SENS-03 SF-01 — Visibility is a value, not a guess

**Status**: APPROVED 2026-08-26 · **FRs owned**: FR-1, FR-2, FR-3, FR-4 · **NFRs**: NFR-5 (backward
compatibility) · **Depends on**: none · Design: [B-SENS-03_design.md](B-SENS-03_design.md)
§Sub-features → SF-01

## Goal

Replace the boolean hidden-check with a normalised access level on all ten parsers, and make
`list_symbols(visibility=[...])` return exactly what was asked for.

## Where it plugs in

Read or run 2026-08-26.

| Fact | Where |
|---|---|
| Two shapes to merge: `_is_symbol_hidden(parent) -> bool` overridden in Java, Kotlin, Rust, TypeScript (`{java,kotlin,rust,typescript}/codestructure.py`); `_is_symbol_valid(...)` overridden with an inline `"public" in visibility` test in C, C++, Go, Python (`{c,cpp,go,python}/codestructure.py`). **Neither** — markdown, SQL inherit the shared default | per-language `codestructure.py` |
| The shared filter `_is_symbol_valid(sym_name, name_node, visibility, decorator_filter, framework_markers) -> bool`; its whole visibility test is below. **Anything not the literal `"public"` falls through to `return True`** — the fail-open | `_reading.py:98` |
| `TECH-035` created the shared filter; `tests/unit/workspace/ast/parsers/test_symbol_filtering.py` carries `test_the_filter_is_not_redeclared_on_the_language`, asserted over **four** parsers | — |
| The hook already exists: `_get_symbol_visibility(self, name_node) -> str`, handles `class`-defaults-private vs `struct`-defaults-public via `_preceding_access_specifier`. **Adopted by that exact name**, so C++ needs no hook change | `cpp/codestructure.py:133` |
| TypeScript: `_is_symbol_hidden` walks ancestors for an `export_statement` and returns `False` if found, so a `private` member of an exported class reads as visible — two independent axes collapsed into one | `typescript/codestructure.py:77` |
| Python: the filter below puts `__secret` — name-mangled so outsiders cannot reach it — **in the public set** | `python/codestructure.py:73` |
| C: `return visibility is None` — empty for every filter | `c/codestructure.py:90` |
| Capability declaration: `supported_parameters() -> list[str]` — `["visibility"]` on C++, Rust, Go; `[]` on C, SQL, markdown; inherited default (all) elsewhere. A parser that does not declare `visibility` is the design's `unknown` case — reused, not a second list (`PRINCIPLES.md` §5, one fact one place) | `interfaces.py:172` |

```python
if visibility and "public" in visibility and name_node and self._is_symbol_hidden(name_node.parent):
    return False
```

```python
if visibility and "public" in visibility and sym_name.split(".")[-1].startswith("_") \
        and not sym_name.split(".")[-1].startswith("__"):
    return False
```

```
all    : B, B.__init__, B.__repr__, B._helper, B.__secret, B.pub
public : B, B.__init__, B.__repr__,            B.__secret, B.pub
```

Measured before the change:

| Language | `list_symbols(code)` | `visibility=["public"]` | `["protected"]` / `["private"]` |
|---|---|---|---|
| Java | `B, B.a, B.b, B.c, B.d` | `B, B.a` ✅ | **the whole file** ❌ |
| Kotlin | all | public only ✅ | not run — same shared path ❌ |
| Rust | all | `pub` only ✅ | same ❌ |
| TypeScript | `B, B.a, B.b, B.c` | **all four** ❌ | all four ❌ |
| Go | `B, B.Pub, B.priv` | `B, B.Pub` ✅ | falls through ❌ |
| Python | see above | see above | falls through ❌ |
| C | — | **empty** | empty |
| C++, SQL, markdown | — | unfiltered / no support | — |

Consumers of the surface:

| Caller | File | Passes |
|---|---|---|
| `extract_public_symbols` | `analyzers/factory.py:191` (defined `:185`) → `workspace/context/inferrer.py:108` → the **`exposes:` list written into generated `context.yaml` files** | `visibility=["public"]` — a user-visible artefact, which is why the change went to the user |
| `CodeStructureAtom._handle_list` | `sandbox/code_structure/core/atom.py:136-139` | whatever an **agent** put in `context["visibility"]` |
| `graph_adapter` | `workspace/ast/adapters/graph_adapter.py:88` | no visibility — unaffected |

`sandbox/code_structure/interfaces/tool.py:118` `list_symbols(path, visibility, decorator_filter)`
calls `_check_grant(path, ...)` — **the path, not the visibility**. The dev guide claimed the tool
*"bounds-checks the request against the Role `FolderGrant` and target `visibility`"*
(`code_structure_and_ast_editing.md:120`); corrected in CB-3.

No new dependency. Every node access needed (`.type`, `.text`, `.parent`, `.children`) is already
used by the per-language code.

## Changes

### CB-1 — The net, before anything moves (`NFR-5`)

| Task | File |
|---|---|
| 1 | Parameterised characterization over **all ten** parsers: exact `list_symbols(code)` and `list_symbols(code, visibility=["public"])` per language fixture — `tests/unit/workspace/ast/parsers/test_visibility_vocabulary.py`. **Each fixture contains the shape whose delta is predicted**: a Python `__dunder__` and a `__mangled`, a Java `interface`, a Rust `pub trait`, a TypeScript exported class with a `private` member, a lowercase Go identifier |
| 2 | Integration: `extract_public_symbols` → `inferrer` produces the prior `exposes` list — the seam `NFR-5` claims (crosses `analyzers` → `context`) |

Green on first run by design — a *must-not-change* claim is proved by capture-then-compare. Its
ability to fail is proved by probe:

> `python scripts/_mutate.py --file src/specweaver/workspace/ast/parsers/_reading.py --old 'and "public" in visibility' --new 'and False'`
>
> The anchor is the fail-open expression itself, and it appears once. A shorter one such as `    if (` matches in several places and would neutralise something else.

**Done when** the characterization test is in the objectors list.

### CB-2 — Visibility becomes a value (`FR-1`, `FR-3`, `FR-4`)

Nothing consumes the hook yet, so CB-1's net stays green throughout.

| Task | File |
|---|---|
| 1 | `VISIBILITY` frozen tuple + `Visibility` Literal alias | `parsers/interfaces.py` |
| 2 | `_get_symbol_visibility(name_node) -> Visibility` on the base, returning `unknown` | `_reading.py` |
| 3 | Per-language mappings, one file each (table below) | `*/codestructure.py` |
| 4 | C++: assert its existing returns are inside the vocabulary; no logic change | `cpp/codestructure.py` |

| Language | → `public` | → `protected` | → `internal` | → `private` | → `unknown` |
|---|---|---|---|---|---|
| Java | `public`; **any interface member** | `protected` | no modifier **inside a class** (package-private) | `private` | — |
| Kotlin | no modifier | `protected` | `internal` | `private` | — |
| TypeScript | exported **and** no accessibility modifier | `protected` | **not exported**, no modifier | `private` | — |
| Rust | `pub`; **any trait member** | — | `pub(crate)`, `pub(super)` | no modifier **outside a trait** | — |
| Go | capitalised | — | **lowercase** | — | — |
| Python | plain, **or** `__dunder__` | — | `_leading` | `__leading` only | — |
| C++ | existing `_get_symbol_visibility` — positional labels, `class` defaults private, `struct` public | " | — | " | — |
| C, SQL, markdown | — | — | — | — | everything |

Rules:

- **A member with no modifier takes its container's rule** `[agreed 2026-08-26]`. In a class: the
  language default — package-private in Java, private in Rust. In an interface or trait: implicitly
  public, inheriting the container's own level — a member of a non-`pub` Rust trait is not public
  just because it has no modifier. Before: Java `interface I { void x(); }` returned `['I']` under
  `["public"]`, and `pub trait T` lost both its methods.
- **TypeScript: two axes, the more restrictive wins.** A `private` member of an exported class is
  `private`; a plain member of a non-exported class is `internal`.
- **Go has no `private`.** Lowercase is package-visible; `private` would hide code from
  package-mates entitled to it.
- **Python**: `__dunder__` is interface, `__leading` is name-mangled.

**Red first**: the tests name a hook absent on nine of ten parsers. Expected mutant:
`go/codestructure.py`, `short_name[0].isupper()` → `True`; done when the Go mapping test objects.

### CB-3 — The filter consumes the value (`FR-2`)

| Task | File |
|---|---|
| 1 | `_is_symbol_valid` filters on `_get_symbol_visibility(name_node) in visibility`, `unknown` matching a request containing `public`. **`name_node is None` is guarded before the hook** — C++'s implementation dereferences `name_node.parent`. `None` = cannot judge = `unknown` = kept; `test_a_public_filter_with_no_name_node_cannot_judge_and_keeps_it` pins it | `_reading.py` |
| 2 | Delete `_is_symbol_hidden` from Java, Kotlin, Rust, TypeScript **and** the base | |
| 3 | Delete the `_is_symbol_valid` overrides from C, C++ (`cpp/codestructure.py:181`), Go, Python. Their non-visibility behaviour moves to the decorator hook: C still raises on `decorator_filter`, Go still rejects it | |
| 4 | Extend `test_the_filter_is_not_redeclared_on_the_language` from **four** parsers to **ten** | |
| 5 | Update CB-1's characterization for the **four agreed deltas**, each with its decision in the docstring: Python's `__secret` leaves the public set · C stops returning empty · Java interface members join · Rust trait members join `[agreed 2026-08-26]` | |
| 6 | Correct `code_structure_and_ast_editing.md:120` — the tool checks the **path**, not the visibility | |
| 7 | Add the `NFR-5` C exception and the `[proof: integration]` marker to the design | |

**Red first**: `["private"]` returns only private symbols; `["public","protected"]` returns both.

**Done when** both mutant directions die (always-admit → CB-1 net + the `["private"]` test;
always-reject → the `["public"]` characterization), and the characterization diff holds **only the
enumerated deltas**.

## Tests

| Tier | File | Covers |
|---|---|---|
| Unit | `test_visibility_vocabulary.py` | ten-parser characterization (CB-1), deltas (CB-3) |
| Unit | `test_visibility_mapping.py` | per-language mapping (CB-2) |
| Unit | `test_visibility_filter.py`, `test_symbol_filtering.py` | the one filter, ten parsers |
| Integration | `tests/integration/workspace/context/test_exposes_seam.py` | `NFR-5` seam into `exposes:` |

## Decisions (audit)

| # | Question | Resolution |
|---|---|---|
| Q33 | Is `__init__` public? | **Leading *and* trailing** underscores → `public`; leading-only → `private` `[agreed 2026-08-26]`. Fixes the `__secret` leak as a side effect |
| Q34 | Fix C or freeze it? | **Fix** `[agreed 2026-08-26]`. C reports `unknown`; `NFR-5` gains a named exception. Returning nothing is not a truthful answer |
| Q36 | Interface and trait members read as hidden | **Fix** `[agreed 2026-08-26]`. Freezing would pin a wrong answer as correct |
| Q37 | Rust loses trait method names | **SF-03**, widened to *a parser does not lose names* `[agreed 2026-08-26]` — a listing defect, not a visibility one |
| Q35 | How far does the refactor reach? | **All ten parsers share one filter** `[agreed 2026-08-26]`; each supplies `_get_symbol_visibility`. `TECH-035` finished |
| Q2 | Hook name | Reuse C++'s `_get_symbol_visibility` |
| Q3 | Vocabulary representation | Frozen tuple + `Literal` alias in `interfaces.py`, so mypy strict rejects a typo |
| Q6 | `name_node is None` | `unknown`, therefore kept — same rule as SQL and markdown (`AD-5`) |
| Q7 | A level a language cannot produce | Empty list, never raise. `supported_parameters()` declares the capability |
| Q12 | The `unknown` signal | `supported_parameters()`, reused |
| Q13 | Import chains | The alias lives in `interfaces.py`, which every parser imports. No new edge |

`NFR-5`'s proof tier is **integration**, not unit: the claim crosses into `workspace/context`
(`ADR-003`). Corrected in the design in CB-3.

| Risk | Mitigation |
|---|---|
| An eleventh behaviour change hides in the CB-3 diff | CB-1's net covers ten parsers and is read as a diff |
| `unknown` matching `public` floods a filtered result | Intended (`AD-5`), asserted directly |
| The agent-facing tool's behaviour changes | For the better: `private` returns private symbols, not the whole file |
| C++'s hook returns a value outside the vocabulary | CB-2 task 4 asserts it |

Not here: doc/signature accessors (SF-02); SQL names and Rust trait names (SF-03 — until then SQL
reports `public` and `orders`, both `unknown`, and Rust has no name for a required trait method);
`chunking.py` (SF-04+); the 617 constants and TypeScript interfaces (parked with the graph
classifier `[agreed 2026-08-26]`).

## As built (2026-08-26)

| Where | What |
|---|---|
| `parsers/interfaces.py` | `VISIBILITY = ("public", "protected", "internal", "private", "unknown")` + `Visibility` Literal; `extract_symbol_visibility(code, symbol_name) -> Visibility` on every parser |
| `parsers/_visibility.py` | the mapping rules as **module-level functions** (a visibility rule is a pure function of one AST node); each parser binds `_get_symbol_visibility = staticmethod(_visibility_of)`, the shape `grammar = staticmethod(...)` already used. Keeps LCOM4 clean — all 22 classes within limits. A shared keyword scan holds TypeScript's mapping under complexity 15 |
| `_reading.py` | **one** `_is_symbol_valid` for all ten parsers. `_matches_decorator` hook carries C's raise and Go's `False` (Go's is a claim about the language, not an empty marker table) |
| `DeclarativeParser._is_symbol_valid` | removed — it returned `True` unconditionally (*"no body whose shape could be wrong"*), a body-shape answer that also disabled visibility and decorator filtering for SQL and markdown. Nine copies became one |
| Rust dedup | moved **before** the filter: `pub struct Circle` and `impl Circle` both yield a name node, only the first carries visibility; first occurrence wins, the rule `extract_symbol_visibility` and `_declared_names` use |
| `code_structure_and_ast_editing.md` | the tool checks the **path** only; visibility is a **relevance filter for information hiding, not a security boundary** |

Walkthroughs: [cb1](B-SENS-03_sf01_cb1_walkthrough.md) · [cb2](B-SENS-03_sf01_cb2_walkthrough.md) ·
[cb3](B-SENS-03_sf01_cb3_walkthrough.md).
