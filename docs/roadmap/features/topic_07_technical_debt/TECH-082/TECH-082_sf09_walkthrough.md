# Walkthrough: TECH-082 SF-09 — The rule in every language

## CB-1: imports in every language (FR-18, FR-16 mapping)

**What changed**
- New `workspace/ast/parsers/javascript/codestructure.py`: `JavaScriptCodeStructure`, the TypeScript
  parser on the JavaScript grammar with the queries that grammar has. `extract_imports` lists ES
  imports, `export ... from`, `require("x")` and `import("x")` with a literal name. `#name` members are
  private; `export` makes the rest public. It offers no rename, remove or move: no resolver renames
  JavaScript. Registered in `get_default_parsers()` for `.js`, `.jsx`, `.mjs`, `.cjs`.
- New `workspace/ast/refactor/imports.py`: `targets_for(files, language)` and
  `import_target(files, path, written)` name the project file or folder an import reaches, or None.
  A package file (`__init__.py`, `mod.rs`, `lib.rs`, `index.*`) and a Go import name a folder.
  Each language's answer uses the resolver that renames its files (`rename.resolver_for`);
  TypeScript and JavaScript are one family, so a `.ts` file importing a real `.js` file maps. A Java
  package found in both `src/main` and `src/test` maps to the importer's side.
  The plan put an `import_target` method on each resolver; one table of per-language functions in
  `imports.py` does the same job and leaves the resolvers' interface alone, except two private
  helpers made public (`RustResolver.module_file`, `CResolver.include`).
- Found in dev, fixed: Java's `extract_imports` returned `import app.core.*;` as three names
  (`app.core`, `.`, `*`); it is now one, `app.core.*`.
- Found in dev, fixed: `CResolver.included` looked up a nested include beside the first file, not
  beside the header that includes it.
- `pyproject.toml`: the `N802` exemption for `SCM_*` query properties (TECH-035) now covers the whole
  parsers folder, and the 44 call-site `noqa: N802` are gone (the user, 2026-11-05). Suppression
  baseline 185 → 144. Duplication baseline re-frozen: the removed `noqa` text re-keyed three old
  clone pairs (94 → 93 clones).
- Test edits (FR-18): JavaScript rows in the shared parser tables (`test_visibility_vocabulary.py`,
  `test_visibility_mapping.py`, `test_symbol_docs.py`, `test_symbol_signatures.py`,
  `test_every_parser_answers_the_contract.py`); `test_archetype_languages.py` no longer expects
  JavaScript to lack a parser.
- Docs: `6_ast_surgical_editing.md` (JavaScript is parsed), `language_support_guide.md` (a new
  language adds one `_PICK` entry).

**Tests**
- `test_javascript_imports.py` (13), red first (no module): the import forms, JSX, a syntax error,
  `require(name)` not listed, the factory, `add_symbol`, the default ignores.
- `test_import_target.py` (47), red first (no `imports` module): each language, packages, static and
  wildcard imports, nested Go modules, Rust aliases, main and test packages, libraries, missing
  files, paths out of the project.
- `test_java_wildcard_imports.py` (2), red first (three names).
- `test_parsed_imports_reach_files.py` (9, integration): each language's real parser output, mapped.
  The two halves are only used together; a unit test of either writes the other's half itself.
- `test_plan_rename_c_family.py::test_a_nested_include_is_found_beside_the_header_that_includes_it`,
  red first.

**Mutants**: TECH-082 FR-18 `js-require-dropped`, FR-16 `package-file-not-folder`,
`java-wildcard-split`, all OBJECTED. A mutant removing a guard against paths out of the project
survived: the guard could never fire (only project files are candidates), so it was removed. Two
stale records re-run before refresh (`D-SENS-06 rust-glob-trusted`, `TECH-078 parsers-own-endings`):
OBJECTED. 0 stale.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `JavaScriptCodeStructure.extract_imports` | ✅ | ✅ `test_parsed_imports_reach_files.py` | CB-2 |
| JavaScript symbols, visibility, supertypes | ✅ shared parser tables | ✅ contract test | — |
| `import_target`, `targets_for`, `_nearest` | ✅ | ✅ | CB-2 |
| `CResolver.included` | ✅ | — | — |

**Architecture**: `imports.py` uses `parsers` and `rename` inside its own module; `tach check` passes;
`refactor` exposes `imports`, and tach's interfaces list `imports.import_target` and
`imports.targets_for`.

**Red/Blue (7.5)**, 2 cycles
- R1 (MEDIUM, accepted) Registering a JavaScript parser shows JavaScript to every user of
  `get_default_parsers()` (structure reads, skeletons, indexing). FR-18 wants this; every shared
  parser test now runs on JavaScript too.
- R2 (MEDIUM, fixed) A Java package in both `src/main` and `src/test` was unmapped; it now maps to the
  nearer folder, and a tie stays unmapped (counted, never silent).
- R3 (MEDIUM, fixed) Nested C includes resolved beside the wrong file (above).
- R4 (LOW) An import of the Go module root names the project root, which no rule can name; it is
  None (counted as not mapped).
- R5 (LOW) `app.core.Missing` maps to the `app.core` folder: the rule is per folder, so the verdict
  is the same as for a class that exists.
- R6 (LOW) `targets_for` reads all of a language's files; CB-2 measures it on a real tree.
- Cycle 2: challenged R2 (can "nearest" pick a wrong folder?): only folders whose files declare that
  package are candidates, so the choice is between real homes of the package. No new finding above
  LOW.
