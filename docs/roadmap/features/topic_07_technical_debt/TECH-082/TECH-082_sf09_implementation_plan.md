# Implementation Plan: Domain Logic Lives in the Flow Engine [SF-09: The rule in every language]
- **Feature ID**: TECH-082
- **Sub-Feature**: SF-09 — The rule in every language
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-09
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf09_implementation_plan.md
- **Status**: APPROVED

## Scope

One shared check judges a code file's imports in all 9 languages by FR-15's effective rules; a
JavaScript parser lists imports; an undeclared widening fails C05 and names the fix; stricter tools a
project configured run as extras. FRs: **FR-16, FR-17, FR-18, FR-19, FR-20**. NFRs: NFR-1 (these FRs
change behaviour by design), NFR-2, NFR-4, **NFR-5** (one fixture tree in 9 languages). Depends on
SF-08 (resolver, committed) and SF-01 (hydrator in `assurance/validation/orchestration`, committed).
Paths owned: P-9, P-10, P-11.

Today (measured 2026-11-05):

- C05 (`rules/code/c05_import_direction.py`) reads `qa_architecture_result`, which
  `_hydrate_architecture` (`orchestration/validation_hydrator.py:291`) fills from the QA atom's
  `run_architecture` intent → the project language's runner `run_architecture_check`.
- Python: `forbids_checker.check_file_forbids` (nearest `context.yaml` only, skips `TYPE_CHECKING`)
  plus `tach check`. Java: writes a generated `SpecweaverArchUnitTest.java` and runs Maven. TypeScript:
  writes an ESLint config with `no-restricted-imports`. All three read only the nearest manifest's
  `forbids`. Kotlin and Rust return a `note` ("not implemented") → C05 SKIP.
- Go, C, C++, JavaScript have no runner: `runner_factory._runner_class` falls back to
  `PythonQARunner`, so their C05 is tach's verdict on the whole project.
- The resolver exists: `assurance/graph/boundary_rule.allows(nodes, root, folder, target) -> bool`
  and `breaches(nodes, root)`.
- `extract_imports` per parser (run 2026-11-05): Python `['..up', '.sib', 'app.core', 'app.t', 'os']`
  (lists `TYPE_CHECKING` imports); Java/Kotlin dotted names; TS specifiers (`'./core/a'`, `'react'`,
  no `require`); Rust `'crate::core::service'`, `'super::x'` (no `mod x;`); Go `'example.com/app/core'`;
  C/C++ the whole directive `'#include "core/a.h"'`. No JavaScript parser in `factory.py`.
- The per-language import → project file logic already exists in `workspace/ast/refactor`
  (built on all project files, pure): `PythonResolver.resolve_module(module, from_file)`
  (`python.py:71`, roots `""` and `src/`), `JvmResolver.resolve_text(path, written)` (`jvm.py:151`,
  by parsed package), `TypeScriptResolver.resolve_module(spec, from_file)` (`typescript.py:105`,
  `.ts`/`.tsx` only), `GoResolver.import_dir(import_path)` (`go.py:97`, module from each `go.mod`),
  `CResolver._include(path, written)` (`c_family.py:132`, private), Rust `module_of` / `resolve_path`
  / `_start` (`rust.py:113-171`, no one-call method).
- `sw scan` (`workspace/project/tach_sync.py`) writes each manifest as a tach module with
  `depends_on` = its `consumes`. A declared widening is a `consumes` entry, so it is written already;
  nothing tests it.

## Findings reviewed by the user (Phase 4)

The user chose A for Q1..Q8 `[agreed 2026-11-05]`; Q7 and Q8 came up during CB-2. Each decision is
also written into the design's FR-16, FR-17, FR-20, AD-10 and NFR-1 rows.

| # | Question | Decision `[agreed 2026-11-05]` |
|---|---|---|
| Q1 | Where manifest paths start | The project root, as `context_yaml_spec.md:116` says. Our own guard keeps `src` |
| Q2 | Python imports under `if TYPE_CHECKING:` | They count, as in tach; Python adds no rule of its own |
| Q3 | Where the extras run | Shared check + extras table in `sandbox/language/core`, behind the atom's `run_architecture`; runners lose `run_architecture_check`; AD-10 amended |
| Q4 | A file no `context.yaml` covers | C05 SKIP, "no context.yaml covers this file; no boundary rule was examined" |
| Q5 | A Python project with no `tach.toml` | tach is not configured: no extra, no failure. Retires `D-VAL-05` FR-5's "run `sw scan`" failure |
| Q6 | A configured extra that cannot run (missing, timeout, crash) | C05 WARN naming the tool; the shared verdict stands; `--strict` fails |
| Q7 | A fresh project's tests import `src` | `sw init` writes `tests/context.yaml` with `consumes: [src]` |
| Q8 | A `forbids` entry that names a library (`*.orm`, the scaffold's `specweaver/sandbox/*`) | It still judges an import that reaches no project folder, by the import's written name; `consumes` never applies to a library; FR-17 amended |

### F-1 (HIGH) The mapping reuses the refactor resolvers

Each language's import → project file logic already lives in `workspace/ast/refactor` (Scope). The
shared check asks the language's resolver which project file an import names, takes that file's
folder relative to the project root, and asks `allows`. `external` and `unknown` count as "not
mapped" (FR-17). New: a public `import_target(path, written) -> str | None` on each resolver,
returning a project file path relative to the project root, or None:

- Python: `resolve_module(written, path)`; a `("module", p)` or `("def", p, _)` gives `p`.
- Java/Kotlin: `resolve_text(path, written)`; a static import (`app.util.X.y`) that misses retries
  one segment shorter.
- TypeScript/JavaScript: `resolve_module(written, path)`, which also tries `.js`, `.jsx`, `.mjs`,
  `.cjs` and `/index.js` (FR-18). A bare specifier (`react`) is None.
- Rust: `crate::`, `super::`, `self::` paths through `resolve_path`/`_start`; the longest prefix that
  names a module file wins (`crate::core::service::Thing` → `src/core/service.rs`). Their bodies were
  not read in planning: if they do not compose, walk the prefixes over `_module_file(crate, segments)`.
- Go: `import_dir(written)` gives a folder; return it as is (the check takes a folder or a file).
- C/C++: unwrap `#include "x"` to `x`, then `_include(path, x)` (made public as `include`); an
  angle include (`<stdio.h>`) is None.

A new `workspace/ast/refactor/imports.py` holds one function, `import_target(files, path, written)`,
which picks the resolver by `commons.languages.language_of(path)`; it has its own table where
`typescript` and `javascript` both map to a `ScriptResolver(TypeScriptResolver)` whose `SUFFIXES` are
the TypeScript and JavaScript ones together, so a `.ts` file importing a real `.js` file maps (R-3).
The rename table `_RESOLVERS` stays as it is, so rename behaviour does not change (NFR-1).

### F-2 (HIGH) Placement and edges

- `[NEW] sandbox/language/core/boundary_check.py`: `check_boundaries(project_root, target) ->
  BoundaryVerdict` — reads, parses, maps, judges. No executor: it runs no process.
- `[NEW] sandbox/language/core/boundary_extras.py`: the FR-20 table and `run_extras(project_root,
  language, executor) -> list[ExtraRun]`.
- `[MODIFY] sandbox/qa_runner/core/atom.py`: `_intent_run_architecture` calls both. `QARunnerAtom`
  gains `executor: SubprocessExecutor | None = None` (keyword; `qa_atom` passes the one it built, so
  container mode runs the extras in the container, as tach does today).
- `sandbox` is one tach module; it gains `specweaver.assurance.graph` (`sandbox/context.yaml`
  `consumes` and `tach.toml` together). It is a sibling under `specweaver`, so no `widens`. No cycle:
  `assurance.graph` → `graph`, `workspace.analyzers`, `workspace.context` → `workspace.ast.*`; none
  reaches `sandbox`.
- `workspace/ast/refactor/context.yaml` `exposes` and tach's interfaces gain `imports` and
  `imports.import_target`.

### F-3 (MEDIUM) Cost

A resolver is built from every file with its language's suffixes. `check_boundaries` reads only
those files, skips folders `.specweaverignore` and the parser's `get_default_directory_ignores()`
list, and builds one resolver per call. Measured in dev on SpecWeaver's own tree (about 450 Python
files); a check slower than 2 s is reported before CB-2 commits.

Measured 2026-11-05 on SpecWeaver's own `src/specweaver` (451 Python files): one file 0.24 s, all
451 files in one call 1.35 s, because the tree and the resolver are read once per call. Ignored
folders (`node_modules/`, `.git/`) are not entered; before that fix one file took 0.67 s.

### F-4 (MEDIUM) Proof tiers

| FR | Claim | Tier | File |
|---|---|---|---|
| FR-18 | the JavaScript parser lists ESM imports, `require(...)`, dynamic `import(...)`, JSX files | unit | `tests/unit/workspace/ast/parsers/javascript/test_javascript_imports.py` |
| FR-16 | each resolver's `import_target` maps project imports and returns None for others | unit | `tests/unit/workspace/ast/refactor/test_import_target.py` |
| FR-16, FR-17, NFR-5 | one fixture tree in 9 languages: same violations, same unmapped count | integration | `tests/integration/sandbox/language/test_boundary_rule_every_language.py` |
| FR-19, Q4 | the verdict's messages; no manifest → note | unit | `tests/unit/sandbox/language/core/test_boundary_check.py` |
| FR-16..FR-19 (P-9) | C05 through the real atom and hydrator | integration | `tests/integration/assurance/validation/test_c05_shared_check.py` |
| FR-16, FR-19 (P-9) | `sw check` on a Go file with an undeclared widening fails and names `widens` | e2e | `tests/e2e/capabilities/assurance/test_boundary_rule_any_language_e2e.py` |
| FR-20, Q5, Q6 (P-11) | configured runs; not configured skips; missing → "not run", WARN | unit + integration | `test_boundary_extras.py` (unit), `test_boundary_extras_run.py` (integration) |
| FR-20 (P-10) | `sw scan` writes a declared widening into `tach.toml` | integration | `tests/integration/workspace/project/test_scan_writes_widenings.py` |

### F-5 (MEDIUM) What is removed and which tests move

Removed: `python/forbids_checker.py`; `run_architecture_check` on the interface and the 5 runners
(Java's generated `SpecweaverArchUnitTest.java`, TypeScript's ESLint config, the Kotlin and Rust
notes, Python's `forbids` merge); `PythonQARunner._run_tach_check` moves into the extras table.

The 14 test files that touch them: each is read in dev; a test of a removed behaviour moves to the
shared check or the extras (NFR-1 exception in the design), a test that only built a fake runner
drops the method. Three retired behaviours of closed stories, each re-cited where the behaviour
now lives so their FR ledgers stay whole:

- `C-VAL-03` FR-5 (native linter merged with `forbids`) → `test_boundary_linter_merge.py` runs the
  shared check plus the tach extra on one real project and keeps its `Proves:` line.
- `TECH-087` FR-5 (C05 never passes where no check exists) → `test_c05_not_built.py` now asserts
  Kotlin and Rust are judged; the no-manifest SKIP (Q4) keeps FR-5's claim, and the file keeps its
  `Proves:` line.
- `D-VAL-05` FR-5 (fail an import `context.yaml` forbids or tach refuses) keeps its first half; its
  "run `sw scan`" half is retired (Q5).

### F-6 (MEDIUM) The C05 result

`exports` keep `violation_count`, `violations`, `note`, and gain `unmapped: int` and
`extras: [{tool, ran, reason, violation_count}]`. C05, in order:

1. no `exports` / no `violation_count` → FAIL "could not run" (today's line, unchanged);
2. `violation_count > 0` → FAIL, one finding per violation (FR-19 text below), then the extras' findings;
3. `note` and no violation → SKIP with the note (Q4);
4. an extra with `ran: false` → WARN "<tool> is configured but did not run: <reason>" (Q6);
5. else PASS "All imports follow the boundary rule; N imports not mapped to a project folder" (FR-17).

FR-19 message: `<file>: import '<written>' reaches '<target>', which the rule of '<folder>' does not
allow; declare it in <folder>/context.yaml under widens: with a reason`. `<folder>` is the nearest
folder with a manifest (`_Tree.owner_of`); the resolver gains a public `owner(nodes, root, folder)`
so the message and `allows` agree.

## Decisions (no user choice needed)

### D-1 Mutants (NFR-4)

- Re-point: `D-VAL-05 no-scan-hint` is retired with Q5 (its claim is gone; the record is deleted
  with a note in the walkthrough). `TECH-087 ts-arch-timeout-says-jest` moves to the extras table
  (a timed-out extra names its tool). `TECH-087 c05-ignores-note` stays (Q4 uses the note).
- New TECH-082 campaigns, each killed before its claim is called proven:
  `forbids-not-inherited` (FR-16: drop the ancestor `forbids`), `widening-allowed-silently` (FR-19),
  `unmapped-judged` (FR-17: an unmapped import judged as a breach), `type-checking-skipped` (Q2),
  `no-manifest-passes` (Q4), `missing-extra-clean` (Q6), `js-require-dropped` (FR-18).
- `stale_mutants.py` reports 0 stale before each commit.

### D-2 Documents

- `docs/dev_guides/language_support_guide.md:63-77`: a new language adds an `import_target`, not a
  `run_architecture_check`; the "not built" note is gone.
- `docs/dev_guides/adding_validation_rules.md:78`: the new `exports` keys.
- `docs/dev_guides/special_patterns_and_adaptations.md:73-85`: C05 reads the shared check.
- `docs/user_guides/1_installation_and_setup.md:179`: `tach.toml` is optional; C05 judges without it.
- `docs/architecture/03_system_topology/context_yaml_spec.md`: `TYPE_CHECKING` imports count; the
  check runs in all 9 languages; the extras table.
- `.agents/STATE.md`: Kotlin, Rust, Go, C, C++, JavaScript boundary checks exist now.

## Path List rows this SF owns

| # | Path | Proven by |
|---|---|---|
| P-9 | `sw check <code file>` in any language → C05 → shared check → parser imports → effective rules | the e2e (Go), the 9-language integration, `test_c05_shared_check.py` |
| P-10 | `sw scan` → `tach.toml` with the declared widenings | `test_scan_writes_widenings.py` |
| P-11 | a configured stricter tool → C05 runs it as an extra | `test_boundary_extras_run.py` |

## Commit Boundaries

### CB-1 (interior): imports in every language — FR-18, FR-16 (mapping)

1. Red: `test_javascript_imports.py` (fails: no JavaScript parser; `.js` is not in
   `get_default_parsers()`).
2. Green: `[NEW] workspace/ast/parsers/javascript/codestructure.py`, a `JavaScriptCodeStructure` on
   the JavaScript grammar (`tree_sitter_javascript.language`), reusing the TypeScript parser where
   its queries hold for JavaScript; `extract_imports` also lists `require("x")` and `import("x")`
   with a string argument. `[MODIFY] factory.py`: `"javascript"` in `by_language`.
3. Red: `test_import_target.py`, one class per resolver, the bucket matrix below (fails: no
   `import_target`, no `imports.py`).
4. Green: `import_target` on the 6 resolvers, `JavaScriptResolver`, `refactor/imports.py`;
   `CResolver._include` → `include`.
5. Mutant: `js-require-dropped`. Gate: `tests.py cb TECH-082 --kind refactor`, pre-commit, commit.

| Bucket | Cases |
|---|---|
| Happy | each language's project import maps to the right file |
| Boundary | Python relative `..up`; Java static import; Rust `super::`; TS `index.ts`; Go nested module |
| Degradation | an import of a file that does not exist → None (unmapped), never an error |
| Hostile | `../../etc/passwd`, an absolute include, `crate::..` → None |

### CB-2 (interior): one shared check — FR-16, FR-17, FR-19, NFR-5, Q1, Q2, Q4

1. Red first, before any wiring:
   - the e2e: `sw init` a Go project with `go.mod`, `domain/context.yaml` forbidding `infra`, a
     `domain/cli/context.yaml` that consumes `infra` without `widens`, `domain/cli/main.go` importing
     the infra package; `sw check domain/cli/main.go --level code` with a project pipeline holding
     only C05. Red today: Go falls back to the Python runner, so C05 reports tach's "No tach.toml"
     failure, not the widening; the assertion on `widens` and the file name fails.
   - `test_boundary_rule_every_language.py`: one tree (`domain` forbids `infra`; `domain/cli`
     consumes `infra` and declares `widens`; `domain/core` imports `infra` without it; one third-party
     import each), written in all 9 languages. Each must give 1 violation (`domain/core` → `infra`)
     and 1 unmapped import. Red: there is no shared check.
     Each language's tree sits under its own base (`.` for Python, TypeScript, JavaScript, Go, C, C++;
     `src/main/java`, `src/main/kotlin`; Rust `src` with `Cargo.toml`), and its manifests name paths
     from the project root with that base (Q1). Only the base and the import syntax differ.
   - `test_boundary_check.py` and `test_c05_shared_check.py`, the matrix below.
2. Green: `boundary_check.py`; `boundary_rule.owner`; the atom wiring; the C05 order of F-6.
3. Remove: F-5's list; move or drop the 14 test files' cases.
4. Mutants: `forbids-not-inherited`, `widening-allowed-silently`, `unmapped-judged`,
   `type-checking-skipped`, `no-manifest-passes`; re-point or retire the three of D-1 whose code goes.
5. Measure F-3. Gate, pre-commit, commit.

`check_boundaries(project_root, target)`, in order:

1. language from the target's suffix (`language_of`); none → note "not a code file";
2. `load_nodes(project_root)`; the target's folder has no owner → note (Q4);
3. read the language's files (F-3), build the resolver through `imports.import_target`;
4. for each import of the target (the parser's `extract_imports` on its text): no target → count
   unmapped; else drop the target's language suffix (`src/core.py` → `src/core`, so a one-file module
   matches an entry naming it, R-2) and `allows(nodes, project_root, folder, target)` false → a
   violation with FR-19's message; build the node tree once per call, not once per import;
5. return violations, unmapped count, note.

| Bucket | Cases |
|---|---|
| Happy | allowed imports pass; the unmapped count is right |
| Boundary | an inherited `forbids` (grandparent) catches; a declared `widens` lets it pass; a sibling import passes; a `TYPE_CHECKING` import counts (Q2) |
| Degradation | no manifest → note (Q4); a file that does not parse → FAIL "could not run", never PASS; an unreadable file in the tree is skipped |
| Hostile | a target outside the project root → refused by the atom's existing path check; a manifest with a `..` entry is a `bad-entry` and judges nothing open |

### CB-3 (closes SF-09, HITL): the extras — FR-20, Q5, Q6

During CB-2 the tach extra moved into CB-2: the runners' tach code was removed there, so the extras
table had to exist in the same commit. CB-3 adds dependency-cruiser and go-arch-lint.

1. Red: `test_boundary_extras.py` (unit, executor doubled), `test_boundary_extras_run.py`
   (integration: real tach on a real project; a missing go-arch-lint and dependency-cruiser through a
   PATH without them → "not run" → C05 WARN), `test_scan_writes_widenings.py` (real `sw scan` on a
   project with a `widens`; the edge is in `tach.toml`, and `tach check` passes on that tree).
2. Green: `boundary_extras.py`. The table:

   | Tool | Languages | Configured when | Command |
   |---|---|---|---|
   | tach | python | `tach.toml` | `python -m tach check --output json` (today's) |
   | dependency-cruiser | typescript, javascript | `.dependency-cruiser.*` | `npx depcruise --output-type json --config <file> <target>` |
   | go-arch-lint | go | `.go-arch-lint.yml` | `go-arch-lint check --json` |

   A tool not configured is not listed. Configured and not on PATH, timed out, or with unreadable
   output → `ran: false` with the reason. Each tool's violations add to `violations`, tagged with
   the tool's name.
3. Mutants: `missing-extra-clean`; `ts-arch-timeout-says-jest` re-pointed. Docs (D-2). `readme_counts.py`.
4. Full gate, pre-commit; stage and stop for the user.

## Research Notes

- `QARunnerAtom.__init__(self, cwd: Path, runner: QARunnerInterface, *, scenarios_mounted: bool =
  False)` (`atom.py:59`); `_intent_run_architecture` (`atom.py:423`) builds `exports` from
  `violation_count`, `violations`, `note`.
- `failed_architecture(reason) -> ArchitectureRunResult` (`toolchain.py:187`).
- `Resolver.__init__(self, files: Mapping[str, str], parser: CodeStructureInterface)` (`_base.py:47`);
  `resolver_for(path)` and `_BY_LANGUAGE` (`rename.py:48-72`).
- `allows(nodes, root, folder, target) -> bool`; `_Tree.owner_of(folder)` (`boundary_rule.py`).
- `load_nodes(project_root) -> (nodes, warnings)` (`topology.py:90`).
- `sync_tach_toml(graph, target_path)` writes `depends_on` from `consumes` (`tach_sync.py:41-48`).
- `tree_sitter_javascript.language()` loads (checked 2026-11-05); the grammar includes JSX.
- `runner_factory._runner_class` falls back to `PythonQARunner` for any language without a runner
  (`runner_factory.py:62-81`).
- dependency-cruiser and go-arch-lint flags are checked against each tool's own docs in dev (CB-3);
  neither is installed here, so their happy path is proven with a doubled executor and the real
  "not installed" path.

## Consistency (Phase 5)

- **FRs**: FR-16 (CB-1 mapping, CB-2 check), FR-17 (CB-2), FR-18 (CB-1), FR-19 (CB-2), FR-20 (CB-3).
  NFR-1 (design exception row), NFR-2 (F-2 edges), NFR-4 (D-1), NFR-5 (CB-2 fixture). AD-9 (the one
  resolver), AD-10 amended (Q3), AD-11 (the extras table lists only CLI tools with a config file),
  AD-12 (entries keep the `consumes` path form). Risk rows: R10 of the design (Python users whose
  `tach.toml` allowed an undeclared widening now fail C05) is intended; the message names `widens`.
- **Open questions**: none. All decisions are resolved and written inline, Q1..Q8 `[agreed 2026-11-05]`.
- **Architecture**: one new edge, `sandbox → assurance.graph`; no cycle (F-2). The shared check reads
  files, so it sits in `sandbox` (adapters), not in pure `assurance/graph`, which keeps the rule.
- **Principles**: one rule (AD-9) and one mapping per language (the refactor resolvers, DRY); the
  check runs no process (KISS); the processes (extras) go through the executor (CLAUDE.md rule 4).
- **Hand-off**: a fresh agent needs this plan, the design rows FR-15..FR-20, and `boundary_rule.py`.
  The one unread code is Rust's `resolve_path`/`_start` (F-1 says what to do if it does not fit).

## Red/Blue (Phase 5), 2 cycles

- R-1 (HIGH, accepted) A manifest with no `consumes` allows nothing outside its own folder. This is
  the committed resolver (SF-08, FR-15) and what `sw scan` already writes for tach (`depends_on = []`).
  Java and TypeScript users whose manifests list only `forbids` will now see failures; each message
  names the import and the fix. The user guide says so (D-2).
- R-2 (MEDIUM, fixed) A Python one-file module `src/core.py` would not match the entry `src/core`.
  The check drops the language suffix before asking `allows`.
- R-3 (MEDIUM, fixed) The TypeScript resolver keeps only `.ts`/`.tsx` files, so a TypeScript import of
  a `.js` file would be unmapped. One resolver now covers both families for the check.
- R-4 (MEDIUM, fixed) `allows` built the node tree once per import; the check builds it once per call.
- R-5 (LOW) Rust resolver bodies not read in planning; F-1 names the fallback.
- R-6 (LOW) A `.h` file is read as C even in a C++ project; includes have one syntax, so the mapping
  is the same.
- Cycle 2: challenged R-2 for Java, C, Rust and Go (`Db.java` → `infra/Db`, `db.h` → `infra/db`,
  `mod.rs` → `infra/mod`, Go gives folders): each still lies inside its folder's entry. Challenged
  R-1 (does `sw scan` write a `consumes`-less module as open?): no, `depends_on = []`. No new finding
  above LOW.
