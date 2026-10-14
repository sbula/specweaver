# Implementation Plan: Structured Code Editing for Agents [SF-02: Rename in seven more languages]
- **Feature ID**: D-SENS-06
- **Sub-Feature**: SF-02 — Rename in Java, Kotlin, TypeScript, Rust, Go, C, C++; override family; enums and interfaces
- **Design Document**: docs/roadmap/features/topic_02_sensors/D-SENS-06/D-SENS-06_design.md
- **Design Section**: §Sub-features → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/D-SENS-06/D-SENS-06_sf02_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-14

**FRs owned**: FR-7, FR-8, FR-9 · **Depends on**: SF-01 (committed `fedc2299`)

## Goal

`rename_symbol` works in all 8 code languages, renames a method's whole override family, and
TypeScript enums and interfaces and Rust enums are symbols. The SF-01 rules hold everywhere:
proven uses change, one unsure use refuses, mentions are reported.

## Shape

SF-01 built one resolver (`workspace/ast/refactor/python.py`) over one parser finder
(`parsers/python/_references.py`). SF-02 repeats that shape per language and pulls out what is
shared:

| Piece | Where |
|---|---|
| class hierarchy, outside bases, override family | `workspace/ast/refactor/_family.py` (new, from `python.py`) |
| one finder per language: `find_references`, `file_bindings` | `workspace/ast/parsers/<lang>/_references.py` |
| one resolver per language | `workspace/ast/refactor/<lang>.py` |
| suffix → resolver; Java and Kotlin searched together, and C and C++ (`extern "C"`) | `workspace/ast/refactor/rename.py` |
| all code suffixes read | `sandbox/code_structure/core/changes.py` `CODE_SUFFIXES` |
| `"rename"` in each parser's `supported_intents` | each `<lang>/codestructure.py`, as its CB lands |

`Reference` keeps its kinds. Two fields are added: `qualifier` (the text before `::` or `.` in a
qualified name) and `in_macro` (the name sits in a macro body or macro call: always unsure).

### Proven uses, per language

Every language: the definition, an import that resolves to it, a bare name that resolves to it,
a call on the class or module, the override family. Everything else in code is unsure.

| Language | Also proven | Unsure on top of the common rule |
|---|---|---|
| Java, Kotlin | a bare call `m()` inside the class or a subclass (implicit `this`); `this.m()`, `super.m()` in the family; a class seen without import from the same package; constructors and `new C()` with a class rename; Kotlin `import p.C as D` changes only `C` | `import p.*`; an extension function's call; reflection strings. A Java public top-level class named like its file refuses: rename the file with `move_module` `[agreed 2026-10-14]` |
| TypeScript | `import { X } from "./a"`, `import * as ns` then `ns.X`, `export { X } from` (re-export); relative paths to `.ts`, `.tsx`, `index.ts` | `export * from`; a non-relative path when `tsconfig.json` has `paths` or `baseUrl`; an object-literal key equal to the name; the name as a word in a `.js`, `.jsx`, `.mjs` or `.cjs` file, which no parser reads |
| Rust | `use crate::a::B`, `use super::`, `self::`, use trees and `as`; `mod a;` to `a.rs` / `a/mod.rs`; `self.m()` and `Self::m()` in `impl S`; `S::m()` | `use a::*`; any name inside a macro; a path through another crate of the workspace |
| Go | a bare name from any file of the same package folder; `pkg.F()` through an import resolved by `go.mod`; `r.M()` where `r` is the method's own receiver of type `S` | a dot import; a method name that any interface of the project declares; a method named `String`, `Error`, `Read`, `Write`, `Close`, `ServeHTTP`, `Len`, `Less`, `Swap`, `MarshalJSON` or `UnmarshalJSON` refuses `[agreed 2026-10-14]` |
| C | a declaration (prototype) in any file; a bare use in the defining file, or in a file that declares it or includes, through quoted includes, a header that declares it; `static` limits it to its file | a use inside `#define`; a use with no declaration in reach |
| C++ | C's rule, plus `ns::f`, `using ns::f`; `this->m()`, bare `m()` in a member function of the class or a subclass; `C::m()`; an out-of-line definition `void C::m() {}`; `.h` files parsed as C++ | `using namespace ns`; a dependent name in a template (`T::m`); an overload |

### Override family (FR-7)

`_family.py` builds, from each file's class bases (extends **and** implements), the hierarchy
component of the class. Renaming method `C.m`:

1. Refuse when a class in the component has a base outside the project, except the root types
   that add no methods (`object`, `ABC`, `Protocol`, `Generic`; Java `Object`; Kotlin `Any`).
2. Rename `m` in **every** class and interface of the component that defines or declares it, and
   every proven call on any of them.
3. SF-01's "override family is not supported yet" refusal goes away.

### Enums and interfaces (FR-9)

`SCM_SYMBOL_QUERY` gains `(enum_declaration name: …)` and `(interface_declaration name: …)` in
TypeScript and `(enum_item name: …)` in Rust. `list_symbols`, `read_symbol`, `replace_symbol`,
`delete_symbol` and `rename_symbol` then take them like any other symbol.

## Commit boundaries

Each language boundary writes, red first: the finder's unit test, the resolver's unit test (the
SF-01 test shapes, per language), and one more case in
`tests/integration/sandbox/test_code_structure_changes_for_an_implementer.py`, parametrized by
language (a two-file project renamed through `ToolDispatcher`). Its mutants go into
`D-SENS-06_mutants.json`.

| CB | Does | Proves |
|---|---|---|
| CB-1 | FR-9 symbols; `_family.py`; the Python override family | FR-7 (Python), FR-9 |
| CB-2 | Java and Kotlin | FR-7, FR-8 (JVM) |
| CB-3 | TypeScript | FR-7, FR-8 |
| CB-4 | Rust | FR-7 (traits), FR-8 |
| CB-5 | Go | FR-8 |
| CB-6 | C and C++ | FR-7 (C++), FR-8 |

SQL and Markdown keep refusing: `plan_rename` has no resolver for them (FR-8).

## Mutants (one per row at least, per language)

| id pattern | Line neutralised | Must kill |
|---|---|---|
| `<lang>-unsure-is-proven` | the resolver's unsure verdict | resolver unit |
| `<lang>-import-ignored` | an import that resolves is treated as unrelated | resolver unit |
| `<lang>-shadow-ignored` | a local binding is treated as free | finder unit |
| `family-half-renamed` | step 2 renames only the target class | CB-1 unit |
| `outside-base-ignored` | step 1 skipped | CB-1 unit |
| `enum-not-listed` | the new `SCM_SYMBOL_QUERY` line removed | CB-1 unit |
| `<lang>-not-offered` | `"rename"` dropped from `supported_intents` | integration |

## Research Notes

- Parser suffixes (`factory.get_default_parsers`, run 2026-10-14): C `.c .h`, C++ `.cpp .hpp .cc
  .cxx`, Java `.java`, TypeScript `.ts .tsx`, Rust `.rs`, Kotlin `.kt .kts`, Go `.go`. `.h` goes
  to the C parser today.
- Probe of `list_symbols` (design §Research): TypeScript has no `enum` or `interface`, Rust no
  `enum`; Kotlin lists `enum class` already; C lists `enum` and `struct`.
- Bases: `extract_supertypes(code)` keeps extends and implements apart for Java, TypeScript, Go
  (embedding), C++, Rust (`impl T for S`); `_family.py` uses both.
- `rename.py` `_checked` and `_text_mentions` are language-free already; `_text_mentions` must
  skip every code suffix, not just Python's.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | A Java public class named like its file | refuse, and point to `move_module` (SF-03) `[agreed 2026-10-14]` |
| Q2 | Go methods named like standard interface methods | refuse `String`, `Error`, `Read`, `Write`, `Close`, `ServeHTTP`, `Len`, `Less`, `Swap`, `MarshalJSON`, `UnmarshalJSON` `[agreed 2026-10-14]` |

## Backlog

none
