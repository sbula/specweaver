# Implementation Plan: Polyglot Implementation Loop [SF-03: Generation speaks the language]
- **Feature ID**: D-INTL-08
- **Sub-Feature**: SF-03 — Generation speaks the language
- **Design Document**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_sf03_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-21

**FRs owned**: FR-4, FR-6 (the `lint_fix` prompt), FR-7, FR-9 (doubled model and runner) ·
**NFRs**: NFR-1, NFR-3, NFR-4 · **Depends on**: SF-01 (committed 3c2cf22c). US-03 P-5 (doubled half).

## Shape

| Piece | Where | Tag |
|---|---|---|
| `TaskFiles.language`: the language the files were derived for — the named one, else the detected one — so every caller reads one answer and none detects again (NFR-4) | `core/flow/engine/task_files.py` | MODIFY |
| Five content files, one per language. Each holds a `name:` front-matter line (`Java`) and five sections: `## Code`, `## Tests` (the instructions), `## Code role`, `## Tests role`, `## Coder role` (the model's role lines). `python.md` holds today's text byte for byte (NFR-1). Java tests with JUnit 5, Kotlin with `kotlin.test`, Rust with `#[test]` in `tests/`, TypeScript with the project's tool | `workflows/languages/{python,java,kotlin,typescript,rust}.md` (+ `context.yaml`, like `workflows/pipelines/`) | NEW |
| The loader: `language_guide(language, project_dir) -> LanguageGuide(name, code, tests, code_role, tests_role, coder_role)`; the project's `.specweaver/languages/<lang>.md` first (Q1); a missing section or `name:` is an error naming the file; a language outside the five is refused (it is a validated `Literal`, so it never reaches a path). SF-04 reuses this loader for `frameworks/` | `workflows/implementation/languages.py` | NEW |
| The task brief, for languages other than Python: the file to write, and what it must agree with — the JVM package and class, the class under test; the Rust crate (from `Cargo.toml` `[package] name`, `-` → `_`) and module; the TypeScript import path and the test tool named in `package.json` (`vitest`, else `jest`, else "the project's test script"). Added as context after the instructions, so the prompt start stays stable (`C-FLOW-14`) | `core/flow/engine/task_files.py` (`task_brief(files, project_root)`) | NEW |
| Generation in the language: `GenerateCodeHandler`/`GenerateTestsHandler` take the instructions from the guide; `Generator` takes the guide's role line; the tag in the language's comment syntax; the agentic coder's role line from the guide | `core/flow/handlers/generation.py`, `workflows/implementation/generator.py` | MODIFY |
| One fence stripper for any language: an opening fence with any info string (```` ```java ````, ```` ```ts ````, none) and the closing fence; fences inside the code stay | `workflows/implementation/generator.py` (`strip_fences`) | MODIFY |
| Kotlin and `kt` get `//` tags | `commons/lineage.py` | MODIFY |
| Rust: after the code step, in either mode, `src/lib.rs` declares `pub mod <module>;` once — appended, never duplicated, the file created when missing. The crate root is always `src/lib.rs`, also beside a `src/main.rs`, because tests in `tests/` reach only a library crate (Q2) | `core/flow/handlers/generation.py`; `core/flow/engine/task_files.py` (`_rust_root` → always `src/lib.rs`) | MODIFY |
| `generate contract` takes the run's language instead of detecting its own (NFR-4; it ignored `[implement] language`) | `core/flow/handlers/generation.py` (`GenerateContractHandler`) | MODIFY |
| `lint_fix` asks to fix "this <Name> file", fences and tags in the language, strips with `strip_fences` (today it drops every line that starts with ```` ``` ````, inside the code too) | `core/flow/handlers/lint_fix.py` | MODIFY |
| `validate_code`: a file whose suffix (`LANGUAGE_SUFFIXES`) is not Python, with no archetype pipeline for its language → `PASSED`, no rules run, output `note: "no code rules for <language>"`; `sw implement` prints that line instead of "0/0 rules passed". An archetype pipeline that covers the language (Spring Boot) still runs | `core/flow/handlers/validation.py`, `workflows/implementation/interfaces/cli.py` | MODIFY |

> [!NOTE]
> `PASSED`, not `SKIPPED`: the gate counts anything but `PASSED` as a failure (`engine/gates.py:131`),
> so `SKIPPED` would mark the run as failed in its step list. The note says nothing was judged.

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | language files, loader, brief, generation and the coder in the language, the fence stripper, Kotlin tags, the Rust module line, the contract step's language | FR-4, NFR-1, NFR-4 | a Java run's prompt says "You are a Python code generator" and asks for `# sw-artifact` |
| CB-2 | `lint_fix` and `validate_code` in the language; the `sw implement` journey per language | FR-6, FR-7, FR-9 (doubled), US-03 P-5 (doubled half) | the journey: a Java run's lint prompt says "Python file"; `validate_code` fails C01 and C02 |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | the loader: each shipped language; a project file first (Q1); a missing section refused, naming the file; an unknown language refused. `strip_fences`: ```` ```java ````, ```` ```ts ````, no info string, none, a fence inside the code kept. `wrap_artifact_tag` for `kotlin`/`kt`. `task_brief`: package and class (Java, Kotlin, default package), the crate from `Cargo.toml` (hyphenated name; no `[package]`), the TS import path and test tool (vitest, jest, neither). `TaskFiles.language`: named wins, else detected. `_rust_root` is `src/lib.rs` for `lib.rs`, `main.rs` and neither (SF-01's `main.rs` case changes, Q2) |
| CB-1 | integration (**seam**: handler → generator → model) | a doubled model records what it gets: per language, the instructions, the role line, the `//` tag and the brief; **Python's prompt and role line are byte-identical to today's (NFR-1)**; agentic: the coder's role line is the language's; Rust, one-shot and agentic: `src/lib.rs` gains `pub mod greet_service;` once; a second run adds nothing; beside a `main.rs` a `lib.rs` is created and `main.rs` is untouched; the contract step under `[implement] language = "java"` renders a `.java` contract in a project whose manifests say Python |
| CB-2 | unit | `lint_fix`'s prompt per language; `strip_fences` used; tag fallback in the language. `validate_code`: a `.java` file with no archetype → the note, `PASSED`, no rule run; a `.py` file → C01–C08 as today; Spring Boot archetype on `.java` → its pipeline runs |
| CB-2 | e2e (**journey**, written red at the start of CB-2) | `sw implement` in a Python, Java, Kotlin, TypeScript and Rust project. Doubled model (`doubled_llm`) answers in the language, fenced; doubled runner at `factory.resolve_runner` records lint and test targets. Asserts: the files at the derived paths, fences gone, `//` or `#` tag asked for; lint on the code file and test on the test file; "no code rules for <language>" printed (not Python); exit 0 |

## Mutants (into `D-INTL-08_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the guide's instructions replaced by Python's; the tag language fixed to `python`; the brief dropped; `strip_fences` keeps the opening fence; Kotlin removed from the `//` set; the Rust module line never written; the contract step detects again | CB-1 tests |
| CB-2 | `lint_fix`'s prompt says "Python"; the no-rules branch removed (C01 runs on Java); the note not printed | CB-2 tests |

## Research Notes

- The Python text lives in `workflows/implementation/generator.py:27-56` (`CODE_GEN_INSTRUCTIONS`,
  `TEST_GEN_INSTRUCTIONS`), read lazily by `GenerateCodeHandler._instructions` /
  `GenerateTestsHandler._instructions` (`generation.py:328-348`). Role lines: `generator.py:135`,
  `:189-190`; the coder's: `generation.py:273`. The tag: `generator.py:73` (`"python"`).
- `PromptBuilder.add_artifact_tagging(artifact_id, language)` (`prompt/adders.py:477`) builds the
  instruction from `wrap_artifact_tag`; `None` means no tag — today a `.kt` file.
- `task_files_for(project_root, spec_path, language)` (`task_files.py:51`) detects when `language`
  is None; the run root sets `IsolationPolicy.language` to the named one or None
  (`_core.language_at`). Hence `TaskFiles.language`.
- `lint_fix._llm_fix` (`lint_fix.py:229-294`): prompt, tag and fallback `tag_content(…, "python")`.
- `ValidateCodeHandler._run_validation` → `archetype_pipelines.code_pipeline(code_path, project)`:
  the archetype's pipeline when it covers the file's suffix, else `validation_code_default`
  (C01–C13, Python). `LANGUAGE_SUFFIXES` (`archetype_pipelines.py:28`) maps languages to suffixes.
- `GenerateContractHandler` (`generation.py:533-538`) runs `LanguageAtom` `detect_language`, not
  the run's language.
- Kotlin fixtures test with `kotlin.test` (`tests/fixtures/kotlin_gradle_project`).
- Rust integration tests (`tests/<x>.rs`) can only `use` a library crate; a binary-only crate's
  modules are unreachable from them (Q2).
- `doubled_llm` (`tests/scripted_llm.py`) patches `RoleResolver`; the runner double patches
  `specweaver.sandbox.qa_runner.core.factory.resolve_runner` (imported lazily by
  `qa_runner/core/atom.py:50`).

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | May a project override a language file? | yes — `.specweaver/languages/<lang>.md` first; one loader, reused by SF-04 `[agreed 2026-10-21]` |
| Q2 | Rust crate with only `src/main.rs` | create `src/lib.rs` declaring the module; `main.rs` untouched; revises SF-01's "lib.rs, or main.rs" `[agreed 2026-10-21]` |

Settled in the plan, no trigger fired: Python keeps today's prompt with no brief (NFR-1); the brief
sits after the instructions (prompt-cache stability); one generic fence stripper; `PASSED` with a
note (the gate rule above); the contract step's language fix folds in (NFR-4, this feature).

## Caveats

> [!WARNING]
> The NFR-1 pin (Python's prompt and role lines byte-identical) is a regression guard: green before
> and after by design. Its proof is the mutant that edits `python.md`, not a red run.

> [!NOTE]
> A module in a new `lib.rs` beside a `main.rs` cannot use modules declared only in `main.rs`.
> Accepted: a generated module depends on its spec, not on the binary's internals.

## Documentation

- User guide, "Languages and frameworks": generation follows the language; the prompt files and the
  `.specweaver/languages/<lang>.md` override; Rust's `src/lib.rs`; "no code rules for <language>".
- Design FR-3: Rust's `src/lib.rs`, created beside a `main.rs` `[agreed 2026-10-21]`.

## Backlog

none
