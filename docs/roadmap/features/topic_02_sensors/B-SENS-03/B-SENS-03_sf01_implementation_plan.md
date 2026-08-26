# Implementation Plan: AST Semantic Chunking [SF-01: Visibility is a value, not a guess]

- **Feature ID**: B-SENS-03
- **Sub-Feature**: SF-01 — Visibility is a value, not a guess
- **Design Document**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_design.md
- **Design Section**: §Sub-Feature Breakdown → Group A → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/B-SENS-03/B-SENS-03_sf01_implementation_plan.md
- **Status**: DRAFT
- **FRs**: FR-1, FR-2, FR-3, FR-4 · **NFRs**: NFR-5 (backward compatibility)

## Research Notes

Every fact below was read or run on 2026-08-26. Signatures are quoted, not paraphrased.

### The two shapes that must become one

| Shape | Who has it | File |
|---|---|---|
| `_is_symbol_hidden(parent) -> bool` overridden | Java, Kotlin, Rust, TypeScript | `{java,kotlin,rust,typescript}/codestructure.py` |
| `_is_symbol_valid(...)` overridden with an inline `"public" in visibility` test | C, C++, Go, Python | `{c,cpp,go,python}/codestructure.py` |
| **Neither — inherits the shared default** | markdown, SQL | — |

The shared filter is `_is_symbol_valid(sym_name, name_node, visibility, decorator_filter,
framework_markers) -> bool` at `_reading.py:98`. Its whole visibility test is:

```python
if visibility and "public" in visibility and name_node and self._is_symbol_hidden(name_node.parent):
    return False
```

**Anything that is not the literal string `"public"` falls through to `return True`.** That is the
fail-open. `TECH-035` created this shared filter and its test file
`tests/unit/workspace/ast/parsers/test_symbol_filtering.py` carries
`test_the_filter_is_not_redeclared_on_the_language`, a structural invariant currently asserted over
**four** parsers.

### The hook already exists, in C++

`cpp/codestructure.py:133` — `_get_symbol_visibility(self, name_node) -> str`, returning a string
and already handling `class`-defaults-private versus `struct`-defaults-public via
`_preceding_access_specifier`. **This plan adopts that exact name**, so C++ needs no change to the
hook itself, only a check that its outputs are inside the five-value vocabulary.

### Measured behaviour, per language

| Language | `list_symbols(code)` | `visibility=["public"]` | `["protected"]` / `["private"]` |
|---|---|---|---|
| Java | `B, B.a, B.b, B.c, B.d` | `B, B.a` ✅ | **the whole file** ❌ |
| Kotlin | all | public only ✅ | not run — same shared path ❌ |
| Rust | all | `pub` only ✅ | same ❌ |
| TypeScript | `B, B.a, B.b, B.c` | **all four** ❌ | all four ❌ |
| Go | `B, B.Pub, B.priv` | `B, B.Pub` ✅ | falls through ❌ |
| Python | see below | see below | falls through ❌ |
| C | — | **empty** — `return visibility is None` (`c/codestructure.py:90`) | empty |
| C++, SQL, markdown | — | unfiltered / no support | — |

**TypeScript's cause** (`typescript/codestructure.py:77`): `_is_symbol_hidden` walks ancestors for
an `export_statement` and returns `False` if it finds one. A `private` member of an exported class
is therefore reported as visible. Export and member accessibility are two independent axes and the
code collapses them into one.

**Python's cause and the critical consequence** (`python/codestructure.py:73`):

```python
if visibility and "public" in visibility and sym_name.split(".")[-1].startswith("_") \
        and not sym_name.split(".")[-1].startswith("__"):
    return False
```

Ran it:

```
all    : B, B.__init__, B.__repr__, B._helper, B.__secret, B.pub
public : B, B.__init__, B.__repr__,            B.__secret, B.pub
```

`__secret` — name-mangled specifically so outsiders cannot reach it — **is in the public set
today**. And this set is not local: `analyzers/factory.py:185 extract_public_symbols` →
`workspace/context/inferrer.py:108` → the **`exposes:` list written into generated `context.yaml`
files**. Changing it changes a user-visible artefact, which is why it went to the user.

### Consumers of the surface

| Caller | File | Passes |
|---|---|---|
| `extract_public_symbols` | `analyzers/factory.py:191` | `visibility=["public"]` — crosses into `workspace/context` |
| `CodeStructureAtom._handle_list` | `sandbox/code_structure/core/atom.py:136-139` | whatever an **agent** put in `context["visibility"]` |
| `graph_adapter` | `workspace/ast/adapters/graph_adapter.py:88` | no visibility — unaffected |

`sandbox/code_structure/interfaces/tool.py:118` `list_symbols(path, visibility, decorator_filter)`
calls `_check_grant(path, ...)` — **the path, not the visibility.** The dev guide's claim that the
tool *"bounds-checks the request against the Role `FolderGrant` and target `visibility`"*
(`code_structure_and_ast_editing.md:120`) is false and is corrected in CB-3.

### Capability declaration already exists

`supported_parameters() -> list[str]` — `["visibility"]` on C++, Rust, Go; `[]` on C, SQL,
markdown; inherited default (all parameters) elsewhere (`interfaces.py:172`). A parser that does
not declare `visibility` is exactly the design's `unknown` case, so this plan **reuses that
declaration rather than inventing a second list** — §5 of `PRINCIPLES.md`, one fact one place.

### External

No new dependency. tree-sitter is unchanged; every node access this plan needs (`.type`, `.text`,
`.parent`, `.children`) is already used by the existing per-language code.

## Audit resolutions

| # | Question | Resolution |
|---|---|---|
| Q33 | Is `__init__` public? | **Leading *and* trailing** underscores → `public`; leading-only → `private` `[agreed 2026-08-26]`. Fixes the `__secret` leak as a side effect |
| Q34 | Fix C or freeze it? | **Fix** `[agreed 2026-08-26]`. C reports `unknown`; `NFR-5` gains a named exception for it. Returning nothing is not a truthful answer |
| Q36 | Interface and trait members read as hidden | **Fix** `[agreed 2026-08-26]`. Freezing would pin a wrong answer as correct, which is worse than the bug because it looks decided |
| Q37 | Rust loses trait method names | Not this sub-feature — **SF-03**, widened to *a parser does not lose names* `[agreed 2026-08-26]`. It is a symbol-listing defect, not a visibility one |
| Q35 | How far does the refactor reach? | **All ten parsers share one filter** `[agreed 2026-08-26]`; each supplies `_get_symbol_visibility`. `TECH-035` finished rather than half-done |
| Q2 | Hook name | Reuse C++'s `_get_symbol_visibility`. C++ then needs no hook change |
| Q3 | Vocabulary representation | A frozen tuple plus a `Literal` alias in `interfaces.py`, so mypy strict rejects a typo |
| Q6 | `name_node is None` | `unknown`, therefore kept — the same rule as SQL and markdown (`AD-5`) |
| Q7 | A level a language cannot produce | Return an empty list, never raise. `supported_parameters()` already declares the capability |
| Q12 | The `unknown` signal | `supported_parameters()`, reused |
| Q13 | Import chains | The alias lives in `interfaces.py`, which every parser already imports. No new edge |

**One design correction this plan forces.** `NFR-5`'s proof marker reads `[proof: unit]`. The
compatibility claim crosses into `workspace/context` via `extract_public_symbols`, so its real tier
is **integration** (`ADR-003`). Corrected in the design as part of CB-3.

## Commit boundaries

### CB-1 — The net, before anything moves

**Goal**: capture what all ten parsers return today, so any unintended change is loud.

| Task | File |
|---|---|
| 1 | A parameterised characterization test over **all ten** parsers: for a fixture per language, assert the exact `list_symbols(code)` and `list_symbols(code, visibility=["public"])` sets — `tests/unit/workspace/ast/parsers/test_visibility_vocabulary.py`. **Each fixture must contain the shape whose delta this plan predicts**, or the net cannot show the change: a Python `__dunder__` and a `__mangled`, a Java `interface`, a Rust `pub trait`, a TypeScript exported class with a `private` member, a lowercase Go identifier |
| 2 | An integration test that `extract_public_symbols` → `inferrer` produces today's `exposes` list — the seam `NFR-5` really claims |

**Tier**: unit for task 1; **integration** for task 2 — it crosses `analyzers` → `context`.

**This test is green on its first run, and that is its job.** It is a regression net for a
*must-not-change* requirement, not a proof of new behaviour. A "did not change" claim can only be
proved by capturing before and comparing after. Its ability to fail is proved by probe, not by red:

> `python scripts/_mutate.py --file src/specweaver/workspace/ast/parsers/_reading.py --old 'and "public" in visibility' --new 'and False'`
>
> The anchor is the fail-open expression itself, and it appears once. A shorter one such as `    if (` matches in several places and would neutralise something else.
>
> **Done when**: the characterization test is in the objectors list. If it is not, the net has holes
> and CB-1 is not finished.

### CB-2 — Visibility becomes a value

**Goal**: `FR-1`, `FR-3`, `FR-4`. The hook exists and answers correctly; **nothing consumes it yet**,
so CB-1's net must stay green throughout.

| Task | File |
|---|---|
| 1 | `VISIBILITY` frozen tuple + `Visibility` Literal alias — `parsers/interfaces.py` |
| 2 | `_get_symbol_visibility(name_node) -> Visibility` on the base, returning `unknown` — `_reading.py` |
| 3 | Per-language mappings, one file each — see the table below |
| 4 | C++: assert its existing returns are inside the vocabulary; no logic change |

The mapping, which is the whole substance of this boundary:

| Language | → `public` | → `protected` | → `internal` | → `private` | → `unknown` |
|---|---|---|---|---|---|
| Java | `public`; **any interface member** | `protected` | no modifier **inside a class** (package-private) | `private` | — |
| Kotlin | no modifier | `protected` | `internal` | `private` | — |
| TypeScript | exported **and** no accessibility modifier | `protected` | **not exported**, no modifier | `private` | — |
| Rust | `pub`; **any trait member** | — | `pub(crate)`, `pub(super)` | no modifier **outside a trait** | — |
| Go | capitalised | — | **lowercase** | — | — |
| Python | plain, **or** `__dunder__` | — | `_leading` | `__leading` only | — |
| C++ | existing `_get_symbol_visibility` | " | — | " | — |
| C, SQL, markdown | — | — | — | — | everything |

**A member with no modifier takes its container's rule** `[agreed 2026-08-26]`. Inside a class
that is the language default — package-private in Java, private in Rust. Inside an interface or
trait it is implicitly public, and inherits the container's own level: a member of a non-`pub`
Rust trait is not public just because the member has no modifier. Measured before the change: Java
`interface I { void x(); }` returns `['I']` under `["public"]`, and `pub trait T` loses both its
methods.

**TypeScript has two axes and the more restrictive one wins.** A `private` member of an exported
class is `private`, not `public`; a plain member of a non-exported class is `internal`. Collapsing
them is the bug.

**Two rows are the reason this boundary exists.** Go has **no** `private` — a lowercase identifier
is package-visible, and mapping it to `private` would hide code from the package-mates entitled to
it. Python's `__dunder__` is interface, `__leading` is name-mangled: one column apart, and the
current code puts both on the wrong side.

**Tier**: unit. Each mapping is one parser's behaviour on fixture text.

**Red first**: the tests name a hook that does not exist on nine of the ten parsers, so they fail on
import/attribute lookup before a single mapping is written.

> **Expected mutant**: `go/codestructure.py`, `short_name[0].isupper()` → `True`.
> **Done when**: the Go mapping test objects. A mutant nothing kills means the mapping is asserted
> nowhere.

### CB-3 — The filter consumes the value, and eight overrides die

**Goal**: `FR-2`. This is where behaviour changes and where the two agreed deltas land.

| Task | File |
|---|---|
| 1 | `_is_symbol_valid` filters on `_get_symbol_visibility(name_node) in visibility`, with `unknown` matching a request containing `public` — `_reading.py`. **`name_node is None` is guarded before the hook is called**: C++'s implementation dereferences `name_node.parent` and would raise. `None` means *cannot judge*, which is `unknown`, which is kept — the existing `test_a_public_filter_with_no_name_node_cannot_judge_and_keeps_it` already pins that and must stay green |
| 2 | Delete `_is_symbol_hidden` from Java, Kotlin, Rust, TypeScript **and** the base |
| 3 | Delete the `_is_symbol_valid` overrides from **all four** that have them — C, C++, Go, Python (`cpp/codestructure.py:181` was missed on the first pass and found by the review). Their non-visibility behaviour moves to the decorator hook, not to a second filter: C still raises on `decorator_filter`, Go still rejects it |
| 4 | Extend `test_the_filter_is_not_redeclared_on_the_language` from **four** parsers to **ten** |
| 5 | Update CB-1's characterization for the **four agreed deltas**, each with its decision in the docstring: Python's `__secret` leaves the public set · C stops returning empty · Java interface members join it · Rust trait members join it `[agreed 2026-08-26]` |
| 6 | Correct `code_structure_and_ast_editing.md:120` — the tool checks the **path**, not the visibility |
| 7 | Add the `NFR-5` C exception and the `[proof: integration]` marker to the design |

**Tier**: unit for the filter; the CB-1 integration test re-runs and is the seam proof.

**Red first**: assert `["private"]` returns only private symbols and `["public","protected"]` returns
both. Both fail today — the first returns the entire file.

> **Expected mutants**, both directions:
> - the filter always admits → CB-1's net **and** the new `["private"]` test object
> - the filter always rejects → the `["public"]` characterization objects
>
> **Done when**: both are killed, and the diff to the characterization file contains **only the
> deltas this plan enumerates**, each with its decision in the docstring. Anything else is an
> unintended regression, and the net exists to say so. The count is deliberately not written as a
> number here — the Phase 5 review already found one more than the first draft claimed.

## Risks

| Risk | Mitigation |
|---|---|
| An eleventh behaviour change hides in the CB-3 diff | CB-1's net covers all ten parsers and is read as a diff, not as a pass/fail |
| `unknown` matching `public` lets an unfiltered language flood a filtered result | Intended (`AD-5`), asserted directly, and recorded as a limit rather than discovered later |
| The agent-facing tool's behaviour changes | It does — for the better. An agent asking for `private` gets private symbols instead of the whole file. Strictly less exposure than today |
| C++'s existing hook returns a value outside the vocabulary | CB-2 task 4 asserts it. Cheap, and it is the only parser whose hook is not written here |

## Not in this sub-feature

- The doc-comment and signature accessors — **SF-02**
- SQL qualified names **and Rust trait method names** — **SF-03**. Until it lands, SQL reports
  `public` and `orders` separately (both `unknown`, which is correct for what SQL can say) and Rust
  reports no name at all for a required trait method. SF-01 maps the visibility of whatever names it
  is given; it does not recover missing ones
- Anything in `chunking.py` — SF-04 onward
- Naming the 617 top-level constants, and TypeScript interfaces becoming symbols — parked with the
  graph classifier by decision `[agreed 2026-08-26]`
