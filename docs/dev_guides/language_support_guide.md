# Adding Language Support

Use when: you add a language to SpecWeaver (e.g. Go or Ruby) or change an existing runner (e.g. Java).

SpecWeaver runs compilers, tests and linters for LLM agents through the QARunner architecture: small,
separate components under the `language` umbrella instead of one class per language.

## Architecture

| Component | Layer | Job |
|---|---|---|
| Output parsers (e.g. `pytest_output.py`, `cargo_output.py`) | pure logic | Extract structural errors from tool output. Prefer structured output (JSON, SARIF) over Regex: if the tool supports `--format=json`, use it. |
| `runner.py` | execution | Runs the native tools through `SubprocessExecutor` (timeouts, termination of hanging processes). |
| `QARunnerAtom` | engine | Internal SpecWeaver wrapper; unrestricted, for internal verification. Calls the runner directly. |
| `QARunnerTool` | agent DMZ | What the LLM sees. Role-based access control (RBAC) via `ROLE_INTENTS`; also calls the runner directly. |

RBAC example: a `planner` may run tests, linters, complexity and architecture checks, not the
compiler; a `drafter` has no access.

Replaced: one "God Class" per language (`PythonQARunner`, `JavaRunner`, etc.) that compiled, linted
and Regex-parsed everything. It scaled poorly.

Why `QARunner`, not `TestRunner`: the old name `TestRunnerTool` collided with Pytest's test discovery.

## Selection

`resolve_runner(cwd, executor, language)` in `src/specweaver/sandbox/language/core/runner_factory.py`
picks the runner: the run's `language` when given, else `detect_language` from
`sandbox/language/core/detect.py` (`SUPPORTED_LANGUAGES`), which reads the manifest files:
`package.json` (TypeScript), `Cargo.toml` (Rust), `build.gradle` / `build.gradle.kts` (Kotlin),
`pom.xml` (Java), default Python. `create_scenario_converter` and `create_stack_trace_filter` use the
same detector.

`qa_atom(cwd, language, sandbox_settings, scenarios_root)` beside it builds the QA atom: it picks the
executor (host or container), resolves the runner and hands it to `QARunnerAtom`. `sandbox/qa_runner`
never imports `sandbox/language` (`TECH-087` FR-12; `test_qa_runner_imports_no_language.py` holds it).

A new language registers its manifest trigger in `detect.py` and its runner class in the factory.
Its constructor is `__init__(self, cwd, executor)` with no default for `executor`: host or container
is the caller's choice, and `qa_atom` makes it (`TECH-087` FR-9;
`test_no_host_executor_fallback.py` fails a runner that builds its own).

## Steps

Example: **Go**, at `src/specweaver/sandbox/language/core/go/`.

0. **`commons/languages.py`**: one row in `LANGUAGE_SUFFIXES` with every file ending of the language,
   and, if the language has a test convention, its folder in `_TESTS_ROOT` and its file name in
   `name_tests_for`. The prompt fences, the parser registry, rename, the archetype rules, the skeleton
   reader, the code-structure atom and `task_files_for` all read it; no other list of endings exists
   (`TECH-078`). The test convention is what C02 and C03 judge a code file by
   (`assurance/validation/project_root.find_tests`): with one, `validate_code` runs those two rules on
   the language; without one, no rule judges it.
1. **`runner.py`**: `GoQARunner`, implementing `QARunnerInterface`, bound to `go build`, `go test`,
   etc. Implement or stub every method:
   - `run_compiler()`
   - `run_tests()`: read the target with `run_targets.parse_target` and turn each size (one test,
     file, folder with subfolders, project) into the tool's filter; a run of zero tests returns
     `failed_tests(no_test_ran(target))`
   - `run_linter()`
   - `run_complexity()`
   - `run_debugger()`

   A runner has no boundary check of its own. The shared check
   (`sandbox/language/core/boundary_check.py`) judges every language by the `context.yaml` tree; a
   new language adds only its parser's `extract_imports` and its pick in
   `workspace/ast/refactor/imports.py`, which names the project file an import reaches. A stricter
   boundary tool for the language is one row in `boundary_extras.py`'s table (`TECH-082`; today
   tach, dependency-cruiser and go-arch-lint): its config file, command and output reader. Where no
   `context.yaml` covers the file, the check returns a `note` and no violations: C05 skips, naming
   the note.

   Each QA method ends in one of three ways, and never a bare zero, which every reader takes as a
   clean result (`TECH-087`):
   - **It ran:** report what the tool found. Zero findings is clean only when the tool ran and
     its report was read.
   - **It did not run:** the tool is missing, timed out, found no container engine, or wrote no
     report or one that cannot be read. Return the shared result from
     `sandbox/language/core/toolchain.py` (`failed_tests`, `failed_lint`, `failed_complexity`,
     `failed_compile`); the step fails and says why. Check `timed_out`
     before reading output, and remove an earlier run's report before the run.
   - **It is not built for this language:** say so. The method returns its `failed_*` result
     with "<Language> <check> checks are not implemented", as `run_complexity` does for TypeScript.
     An open tool (like `gocyclo`) is better than either.
2. **Output parser**: pure-logic functions like `extract_go_test_results(stdout: str) -> TestRunResult`,
   beside the runner (`typescript/tsc_output.py`, `rust/cargo_output.py`). A SARIF-emitting tool
   reuses `sarif.py` (`lint_errors_from_sarif`, `parse_sarif_complexity`); a JVM language subclasses
   `jvm/runner.py` `JvmRunner` and reads its build with `jvm/build_output.py`.
3. **`scenario_converter.py`**: implements `ScenarioConverterInterface`; turns JSON/YAML abstract
   scenarios into `_test.<ext>` parameterized blocks.
4. **`stack_trace_filter.py`**: implements `StackTraceFilterInterface`; strips system frames and keeps
   the domain payload of native test failures. JVM languages share `jvm/stack_trace_filter.py`.
5. **Tree-Sitter parser**: inherit `BaseTreeSitterParser` in
   `src/specweaver/workspace/ast/parsers/<lang>/codestructure.py` and register it in
   `get_default_parsers()`. Implement `get_binary_ignore_patterns()` and
   `get_default_directory_ignores()` (language-specific topological exclusions). Traceability needs
   `extract_test_mapped_requirements()` on the language analyzer. Find a grammar in the
   [official Tree-Sitter List of Parsers](https://github.com/tree-sitter/tree-sitter/wiki/List-of-parsers).
   `extract_imports` lists each import as one name, as written. Then say which project file or
   folder an import names: one entry in `_PICK` (`workspace/ast/refactor/imports.py`). That is the
   language's only part in the boundary check; `test_parsed_imports_reach_files.py` checks the pair.
6. **Generator text**: `workflows/languages/<lang>.md` (front-matter `name:`; sections `# Code`,
   `# Tests`, `# Code role`, `# Tests role`, `# Coder role`) and the name in `_LANGUAGES`
   (`workflows/implementation/languages.py`). This is what the model is told to write.
7. **Task files**: `task_files_for` (`workflows/implementation/task_files.py`) says where the
   task's code and test files go; every step after generation finds the file there
   (`qa_targets.step_file`). Callers pass the language from `core/flow/engine/run_profile.py` (the run's one profile).
8. **Detection and scenarios**: the manifest in `detect_language`, the name in `SUPPORTED_LANGUAGES`
   and its scenario file ending in `_SCENARIO_EXTENSIONS` (`sandbox/language/core/detect.py`).
9. **Rename and move**: a resolver in `workspace/ast/refactor/<lang>.py`, registered in
   `rename._RESOLVERS`; without it `rename_symbol` and `move_module` refuse the language.
10. **Standards**: an analyzer in `assurance/standards/languages/<lang>/`, registered in
    `assurance/standards/scanner.py`, so `sw standards` reads the project's conventions.
11. **Framework evaluator schemas**: flat YAML files (e.g. `gin.yaml` for Gin/Fiber) in
   `specweaver.workflows.evaluators.frameworks`. Bind each to the language with
   `metadata: supported_languages: ["go"]` so it cannot leak into another language. Users override
   with their own `<framework>.yaml` in `<project_dir>/.specweaver/evaluators/`.

Why static YAML for frameworks: mapping meta-annotations or macros to their expansion (e.g.
`@RestController` to `@Controller + @ResponseBody`) gives the LLM deterministic compiler vision
without the 5-10 second cost of a Language Server (LSP) or compiler plugin (like `cargo expand` or
`KSP`) in the agent feedback loop.

## Rules

- Tree-Sitter extraction is separate from the QARunner lifecycle (Feature 3.32 SF-1: Deep Semantic
  Hashing, pure-logic analysis). Do NOT add `ast_parser.py` to a runner submodule.
- No Regex where the tool emits JSON/SARIF.
- Test filenames are unique repo-wide. Name the file for language and subject
  (`test_go_atom.py`, not `test_atom.py`). Duplicate basenames (nine each of `test_atom.py` /
  `test_tool.py` until 2026-07-26) made reference searches unreliable and failure output ambiguous.

## Tests

| Kind | Location | Rules |
|---|---|---|
| Unit | `tests/unit/sandbox/language/core/language/go/` | Mock `subprocess.run` / the executor entirely. Feed parsers raw output fixtures captured from real Go runs. Goal: parser extraction limits. |
| Integration, atom | `tests/integration/sandbox/atoms/qa_runner/go/test_go_atom.py` | Do not mock `subprocess`. Run the real toolchain against dummy projects in `fixtures/`. |
| Integration, tool | `tests/integration/sandbox/tools/qa_runner/go/test_go_tool.py` | Same. Goal: the Tool's RBAC and the Atom's unrestricted path both reach the real OS terminal. |
| AST edge cases | `tests/integration/sandbox/test_polyglot_ast_edge_cases.py` | Append your language's Tree-Sitter boundaries. |

Keep mocks out of live test files.

## Checklist

- [ ] Submodule at `sandbox/language/core/<lang>/` with `runner.py`, output parser,
  `scenario_converter.py`, `stack_trace_filter.py`.
- [ ] No Regex where JSON/SARIF is supported.
- [ ] Manifest trigger in `detect.py`; runner class in `runner_factory.py`; both other factories.
- [ ] Tree-Sitter parser registered in `get_default_parsers()` (used by `CodeStructureAtom`).
- [ ] Row in `commons/languages.py`, with its test convention if it has one.
- [ ] Generator text in `workflows/languages/<lang>.md` and `_LANGUAGES`.
- [ ] `task_files_for` places its code and test files.
- [ ] `SUPPORTED_LANGUAGES` and `_SCENARIO_EXTENSIONS` in `_detect.py`.
- [ ] Rename/move resolver in `workspace/ast/refactor/`.
- [ ] Import → project path in `workspace/ast/refactor/imports.py` (`_PICK`).
- [ ] Standards analyzer in `assurance/standards/languages/`.
- [ ] Default YAML schema for macro/annotation unrolling in
  `workflows/evaluators/frameworks/<archetype>.yaml` with `"supported_languages": ["<lang>"]`.
- [ ] Unit tests with static parsing fixtures.
- [ ] Live integration tests against a dummy project fixture folder.
