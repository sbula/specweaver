# Walkthrough: `B-SENS-03` SF-01 CB-2 — visibility becomes a value

- **Story**: `B-SENS-03` SF-01, commit boundary 2 of 3 · **DAL-B** · 2026-08-26
- **Proves**: `FR-1` (the vocabulary), `FR-3` (TypeScript's two axes), `FR-4` (Go has no private)

## What shipped

`extract_symbol_visibility(code, symbol_name) -> Visibility` on every parser, answering with one of
five words. Behind it, a per-language `_visibility_of(name_node)` — and **nothing consumes it yet**.
`list_symbols` is untouched by design, which is why CB-1's net stayed green throughout.

`VISIBILITY = ("public", "protected", "internal", "private", "unknown")`, plus a `Literal` alias so
mypy rejects a typo the tuple alone would only catch at runtime.

## The mapping, and the two rows that carry the reasoning

| | → public | → protected | → internal | → private |
|---|---|---|---|---|
| Java | `public`; **any interface member** | `protected` | no modifier **in a class** | `private` |
| Kotlin | no modifier | `protected` | `internal` | `private` |
| TypeScript | exported, no accessibility modifier | `protected` | **not exported** | `private` |
| Rust | `pub`; **any trait member** | — | `pub(crate)`, `pub(super)` | no modifier outside a trait |
| Go | capitalised | — | **lowercase** | — |
| Python | plain, **or `__dunder__`** | — | `_leading` | `__leading` only |
| C++ | positional labels, `class` defaults private, `struct` public | " | — | " |
| C · SQL · markdown | — | — | — | — (all `unknown`) |

**Go has no `private`.** Lowercase is package-visible, so it is `internal`. Calling it private
would hide code from the package-mates entitled to use it.

**A member with no modifier takes its container's rule.** Inside a class that is the language
default; inside an interface or trait it is implicitly public. Java and Rust both read "no
modifier" as hidden, which is right for a class and wrong for an interface — that single confusion
is why every Java interface method and every Rust trait method was missing from the public set.

## Red, and what it proved

The tests failed on **collection** first (`VISIBILITY` did not exist), then on **125 errors**
(the parsers could not instantiate against a new abstract method), then on **46 value assertions**
once the base hook returned `unknown` for everything. The third state is the one worth having: it
shows each assertion discriminates rather than merely running.

Every mapping was then green on the first implementation attempt, container rules included.

## Six mutants, six kills

| # | Neutralised | Objections |
|---|---|---|
| M1 | Go's capitalisation test | 2 |
| M2 | Java's interface rule | 2 |
| M3 | Rust's `pub(crate)` detection | **1** |
| M4 | Python's dunder-versus-mangled distinction | **1** |
| M5 | TypeScript's member accessibility | 2 |
| M6 | the shared keyword scan | 11 |

**M3 and M4 have a single point of protection each.** Carried here rather than shrugged at: one
skipped or renamed test away from none, and both are behaviours the user decided explicitly.

## The gate found four things, and one of them was me gaming it

**1. I nearly accepted a ratchet regression.** `check_class_health` reported *"2 classes improved —
re-freeze with `--update-baseline`"*, so I re-froze. The diff told a different story: Java 2→3,
Kotlin 3→4, TypeScript 3→4, and a new Rust entry. The summary showed the improvement; the
**regressions were only visible in the baseline diff**. Reverted, and the scoped run said plainly
`BLOCKED: 4 class(es) failed`.

LCOM4 was right and the fix was not cosmetic: `_get_symbol_visibility` and its helpers formed their
own connected component in four classes, because **a visibility rule is a pure function of one AST
node and needs no object at all**. They are now module-level functions in `_visibility.py` and each
parser binds one with `_get_symbol_visibility = staticmethod(_visibility_of)` — the same shape
`grammar = staticmethod(...)` already used. All 22 classes are now within limits, none incohesive.

**Reading the summary is not reading the diff**, and a ratchet that reports an improvement can be
hiding a regression in the same run.

**2. Complexity.** TypeScript's mapping hit 17 against a ceiling of 15. The shared keyword scan
fixed it and the duplication in the same move.

**3. Comment provenance.** A docstring named `TECH-035`. Code documents the present.

**4. Duplication — re-frozen deliberately, and this is the judgement call.** Five clones across
sibling parser modules: four are import headers, one is per-parser capability declarations
(`supported_intents`), and one was pre-existing code re-keyed by the edit, which the tool warns
about itself. None is extractable without harming clarity — ten sibling modules importing the same
infrastructure is the shape, not a defect. **Unlike the class-health case, nothing here represents
a design problem**, which is the whole difference between a deliberate re-freeze and gaming one.

## Results

| Check | Result |
|---|---|
| Full suite | **8,652 passed, 11 skipped** in 84 s |
| `quality.py cb` | **15 of 15** |
| `mypy` | clean across 23 parser files |
| New tests | 137 |

## Not done here

- `list_symbols` still fails open. That is CB-3, and CB-1's net is what will read the diff
- The four agreed deltas have not landed — nothing consumes the hook yet
