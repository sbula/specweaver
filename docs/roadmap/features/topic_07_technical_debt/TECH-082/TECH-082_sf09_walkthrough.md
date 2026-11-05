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

## CB-2: one boundary check behind C05 (FR-16, FR-17, FR-19, FR-20 tach, NFR-5, Q1–Q8)

**What changed**
- New `sandbox/language/core/boundary_check.py`. `check_architecture(root, target, executor)` judges
  a file, or every code file under a folder, by the effective rule of its folder (SF-08's
  `BoundaryRule`), from the imports its parser lists and the project file each reaches (CB-1's
  `imports.py`). An import that reaches no project file is counted; only an inherited `forbids`
  entry that names it by its written name judges it (Q8). The fix in each message says
  `consumes`, or `consumes` and `widens` where `consumes` alone cannot allow it.
- New `sandbox/language/core/boundary_extras.py`: the extras table. Only tach for now
  (`tach.toml`); CB-3 adds dependency-cruiser and go-arch-lint. A configured tool that did not run
  is `ran: false` with the reason.
- `BoundaryRule.forbids_library(folder, written)` (Q8) and `_Tree.lineage`.
- The QA atom gets the check injected (`architecture=`), because `sandbox/qa_runner` may not import
  `sandbox/language` (TECH-087 FR-12). `qa_atom` passes `check_architecture` with the executor. The
  atom exports `note`, `unmapped` and `extras` too.
- C05: a configured extra that did not run is WARN; a clean pass says how many imports were not
  mapped; a note is SKIP.
- Removed: `run_architecture_check` from the runner interface and the 5 runners,
  `python/forbids_checker.py`, Java's generated ArchUnit program, TypeScript's ESLint rule,
  `toolchain.failed_architecture`, Python's own tach call.
- `sw init` writes `tests/context.yaml` with `consumes: [src]` (Q7).
- `sandbox` consumes `specweaver/assurance/graph` (manifest and tach). `language-atom`'s purpose
  names the boundary check.
- Docs: `language_support_guide.md`, `adding_validation_rules.md` (the exports),
  `special_patterns_and_adaptations.md` §5, `1_installation_and_setup.md` (C05 needs no
  `tach.toml`), `context_yaml_spec.md` (a library meets only `forbids`).
- Plan change: the tach extra moved from CB-3 into CB-2, because the runners' tach code was removed
  here.

**Decisions taken with the user in this boundary**
- Q7 (A, 2026-11-05): `sw init` writes `tests/context.yaml` with `consumes: [src]`. Found because a
  fresh project's test imports `src`.
- Q8 (A, 2026-11-05): `forbids` still judges a library import by its written name. Found because
  the scaffold forbids `specweaver/sandbox/*` and the spec's example forbids `*.orm`; FR-17 read
  literally made both do nothing. FR-17 amended in the design.

**Tests** (full suite 12,375 passed, 9 skipped; unit 9,922, integration 2,036, e2e 426 collected)
- New: `test_boundary_check.py` (17), `test_boundary_extras.py` (13),
  `test_boundary_rule_every_language.py` (NFR-5, the same verdict in 9 languages),
  `test_c05_judges_by_the_boundary_rule.py` (5, the real atom and hydrator),
  `test_boundary_rule_any_language_e2e.py` (Go, a widening, a fresh project's tests importing
  `src`), `test_boundary_rule.py::test_a_library_is_forbidden_by_its_written_name`.
- Rewritten: `test_architecture_check_honesty.py`, `test_qa_runner_atom.py` (the architecture class),
  `test_runner_architecture.py` (C-VAL-03 FR-5, the merge), `test_boundary_linter_merge.py` (real
  tach), `test_c05_not_built.py` (Kotlin and Rust are judged now), `test_c05_architecture_integration.py`,
  `test_tach_sync_e2e.py`, `test_code_rules_on_a_fresh_project_e2e.py`.
- Deleted with their code: 12 tach tests in `test_python_runner.py`, 2 Java architecture tests, the
  TypeScript ESLint timeout tests, the lost-results case for the import report.

**Mutants**: new TECH-082 FR-16 `no-manifest-passes`, FR-17 `unmapped-not-counted`,
`library-forbids-ignored`, FR-19 `widening-fix-says-consumes`, FR-20 `missing-extra-clean`,
`missing-tool-ran`: all OBJECTED. `missing-extra-clean` was SILENT at first: no test proved C05's
WARN; `test_a_configured_tool_that_did_not_run_is_warn_never_pass` was added. Retired:
`D-VAL-05 FR-5` (Q5: no `tach.toml`, no failure) and `TECH-087 ts-arch-timeout-says-jest` (the
ESLint check is gone). Five stale records re-run (all OBJECTED) and refreshed; 0 stale. No mutant
for Q2 (`TYPE_CHECKING` imports count): the parsers have no code that skips them, so there is no
line to neutralise; `test_an_import_for_type_checking_counts` holds it.

**Gates**: `quality.py cb` 17/17, `quality.py doc` 14/14, `tach check`, `mypy` (450 files), ruff.
Duplication re-frozen at 93: removing Kotlin's import lines re-keyed an old Java/Kotlin import
clone. Suppression baseline 144 → 140. F-3: one file 0.24 s, 451 files 1.35 s.

**Combined analysis (Phases 1–2)**

Architecture: no violation. Placement is Q3's (`sandbox/language/core`, an adapter that reads files
and runs tools). No cycle: `sandbox` → `assurance/graph` (pure logic), which forbids
`specweaver/sandbox/*`. One fix: the `language-atom` purpose did not name the check.

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `check_architecture`, `_Judge.code_files`, `_walk` | ✅ | ✅ `test_c05_judges_by_the_boundary_rule.py` | ✅ |
| `_Judge.judge`, `_fix`, `_violation`, `_library_violation` | ✅ | ✅ 9 languages | ✅ |
| `BoundaryRule.forbids_library`, `lineage` | ✅ | ✅ | ✅ fresh project `imports` |
| `run_extras`, `_run`, `_tach_violations` | ✅ | ✅ real tach | — |
| `QARunnerAtom._intent_run_architecture` | ✅ | ✅ | ✅ |
| `ImportDirectionRule._clean` | ✅ | ✅ (added) | ✅ |
| `scaffold` tests manifest | ✅ | — | ✅ |

Gaps found and closed: C05 WARN for a configured tool that did not run (integration, added); a
folder target skips `.specweaverignore` and `node_modules/` (unit, added); tach output `[1]`
crashed instead of "not run" (fixed, unit case added). Sequence: hydrator → atom → check → C05 is
driven by `test_c05_judges_by_the_boundary_rule.py`. Agreement: tach and the shared rule both judge
Python; `test_boundary_linter_merge.py` runs both on one tree.

**Red/Blue (7.5)**, 2 cycles
- R1 (MEDIUM, fixed) The walk entered `node_modules/` and filtered afterwards; a JavaScript project
  can hold 100,000 files there. Ignored folders are now pruned; `test_an_ignored_folder_is_never_entered`
  kills the mutant that stops pruning.
- R2 (MEDIUM, fixed) A forbidden name that reaches no file was called "a library", also when it is a
  missing project folder. The message now says it reaches no project file and names the entry.
- R3 (MEDIUM, fixed) tach output that is a list of non-objects crashed the check.
- R4 (LOW, accepted) The host check looks for `tach` on the PATH, and the run is `python -m tach`. Both
  come from the same install in every setup we support; a mismatch reads as "did not run", never
  clean.
- R5 (LOW, accepted) A syntax error still lists the imports tree-sitter can read; the verdict covers
  those. A file that cannot be decoded fails the atom ("Cannot read"), never PASS.
- R6 (LOW, accepted) A folder `os.walk` cannot read is skipped; imports into it count as not mapped.
- Path traversal: `run_architecture` is in the atom's path guard (`test_qa_runner_atom.py`, `../outside.py`).
- Cycle 2: challenged R1 (does pruning follow symlinks or loop?): `os.walk` does not follow links. No
  new finding above LOW.

## CB-3: the other boundary tools (FR-20), closes SF-09

**What changed**
- `boundary_extras.py` gains two rows. dependency-cruiser runs for TypeScript and JavaScript when
  the project root holds a `.dependency-cruiser.*` file:
  `npx --no-install depcruise --output-type json --config <that file> .`. go-arch-lint runs for Go
  when it holds `.go-arch-lint.yml`: `go-arch-lint check --json --project-path .`. A command names
  the config file it found with `{config}`; a folder named like a config is not one.
- Readers, checked against each tool's documentation and JSON schema (2026-11-05):
  dependency-cruiser's `summary.violations` with `error` or `warn` severity (a rule without a
  severity is `warn`, the tool's default) are violations, `info` and `ignore` are not;
  go-arch-lint's `ArchWarningsDeps` entries are violations, the result may come inside `Payload`,
  and output without `ArchHasWarnings` is unreadable, never clean.
- Docs: `1_installation_and_setup.md` (the three tools, never installed by SpecWeaver),
  `language_support_guide.md` (the table holds three tools). README counts updated.

**Tests** (unit 9,935, integration 2,038, e2e 427 collected; README 12,463)
- `test_boundary_extras.py` (25): each tool's command, each reader, wrong shapes, not installed,
  a rule with no severity, a folder named like a config. Red first: 10 failed before the rows existed.
- `test_boundary_extras_run.py` (integration, 2): a TypeScript and a Go project with the tool
  configured and a PATH that holds no tool: the real atom, hydrator and C05 give WARN naming the tool.
- `test_scan_writes_widenings_e2e.py` (e2e): real `sw init`, `sw scan` and tach. `src` forbids
  `src.infra`; `src.api` widens to it. The edge is in `tach.toml` and `tach check` passes. It passed
  on its first run, because a `widens` key must also be in `consumes`; the mutant
  `scan-drops-widened-edge` proves it can fail.

**Mutants**: TECH-082 FR-20 `depcruise-info-counts`, `depcruise-config-not-passed`,
`go-arch-lint-shape-trusted`, `extra-timeout-says-jest` (the re-pointed TECH-087 mutant: it was SILENT
until the timeout case asserted "tach timed out after 120 s"), `scan-drops-widened-edge`: all
OBJECTED. Two more were OBJECTED by hand but are not in the corpus: removing go-arch-lint's language
and TypeScript from dependency-cruiser's languages. Both lines sit in the module-level table, and the
corpus pins mutants only inside a function or class. `missing-tool-ran` re-run (OBJECTED) and
refreshed; 0 stale.

**Gates**: `quality.py cb` 17/17, `quality.py sf` 18/18, `quality.py doc` 14/14, `tests.py cb` and
`sf` for TECH-082, `tach check`, `mypy` (450 files). Full suite: 12,390 passed, 1 failed:
`test_cqrs_e2e.py::test_story_9_sigint_survival`. It sends SIGINT after a fixed `sleep 0.5`; it passed
3 times alone and twice in the e2e and sandbox tiers under `-n auto`. Recorded as a timing flake
seen once; nothing in this boundary touches it. `commit_gated.py` runs the suite again at the commit.

**Combined analysis (Phases 1–2)**

Architecture: no new import, `tach check` passes; the rows live in the table CB-2 made for them.

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `_config_of`, `{config}` in `_run` | ✅ | ✅ | — |
| `_depcruise_violations` | ✅ | — (tool not installed here) | — |
| `_go_arch_lint_violations` | ✅ | — (tool not installed here) | — |
| missing tool → C05 WARN | ✅ | ✅ `test_boundary_extras_run.py` | — |
| `sync_tach_toml` with a widening | — | — | ✅ `test_scan_writes_widenings_e2e.py` |

Gaps found and closed: a dependency-cruiser rule without a severity, and a folder named like a
config (unit, added; both mutants OBJECTED). The readers' happy path uses doubled output, as the plan
said: neither tool is installed here.

**Red/Blue (7.5)**, 2 cycles
- R1 (MEDIUM, accepted) go-arch-lint's deep-scan warnings (`ArchWarningsDeepScan`, its opt-in
  dependency-injection check) are not read: the JSON names of their nested fields are not documented.
  The dependency warnings, the main check, are read.
- R2 (MEDIUM, accepted) dependency-cruiser cruises `.`; how far it follows is its own config's
  choice. The 120 s timeout makes a slow run "did not run", never clean.
- R3 (LOW, accepted) Only the project root is searched for a config file, as for `tach.toml`.
- R4 (LOW, accepted) `npx --no-install` is the older spelling of `--no` in npm 7+; both npm lines
  accept it and neither installs anything.
- R5 (LOW, accepted) go-arch-lint's files that match no component (`ArchWarningsNotMatched`) are not
  violations, as an unmapped import is not one in the shared check.
- R6 (LOW, invalid) A config name cannot inject a flag: it always starts with `.dependency-cruiser.`
  or is `.go-arch-lint.yml`, it follows `--config`, and no shell runs.
- Cycle 2: challenged R1 (can a project rely on deep scan alone?): deep scan adds to the dependency
  check, it does not replace it. No new finding above LOW.
