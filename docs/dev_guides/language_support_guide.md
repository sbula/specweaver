# Developer Guide: Adding Language Support to SpecWeaver

Welcome to SpecWeaver's polyglot architecture guide! If you are a senior engineer looking to add or update language support (e.g., adding Go or Ruby, or updating the Java runner), this document explains how SpecWeaver interfaces with external languages, compilers, and linters. 

SpecWeaver relies on a highly decoupled "QARunner" architecture to execute language-specific commands securely, predictably, and autonomously on behalf of LLM agents.

---

## 1. Architectural Foundation & Decisions

In earlier iterations of SpecWeaver, we used a single "God Class" (`PythonQARunner`, `JavaRunner`, etc.) to execute everything from compiling to linting to parsing errors using volatile Regex. This brittle approach scaled poorly. 

We redesigned the language support system into distinct, parallel components, physically separated by folder paths to enforce isolation underneath the unified `language` umbrella:

- **`parsers.py` (Commons)** ─ *Pure Logic:* Responsible strictly for extracting structural errors from output logs. **Key Decision:** We heavily favor structured outputs (e.g., JSON, SARIF) over Regex parsing. If a language native tool supports `--format=json`, use it.
- **`runner.py` (Commons)** ─ *Execution Component:* Raw OS-level execution (`subprocess`) wrapped behind strict timeout boundaries, ensuring robust termination of hanging processes.
- **`QARunnerAtom` (Atoms)** ─ *Engine Sandbox:* The internal SpecWeaver engine wrapper. It is permitted unrestricted execution rights for internal verifications. It calls `runner.py` directly.
- **`QARunnerTool` & `interfaces.py` (Tools)** ─ *Agent DMZ:* The layer exposed to the LLM. It dictates Role-Based Access Control (RBAC) and also calls `runner.py` directly. For example, a `Reviewer` agent cannot execute compilers, only linters.

> **Why `QARunner` instead of `TestRunner`?**
> In legacy architecture versions, components were named `TestRunnerTool` which caused collision issues with Pytest's standard test discovery algorithm. While we have since migrated the physical layer into `commons/language/`, the internal `QARunner` naming conventions remain deliberately scoped.

---

## 2. The Selection Mechanism

When an LLM agent executes a command (e.g., `run_linter(target="src/main.rs")`), SpecWeaver must dynamically route to the correct underlying language runner. 

The `QARunnerTool` and `QARunnerAtom` handle dynamic dispatch by sniffing the execution context and requested targets file extensions (e.g., `.rs`, `.py`, `.java` or build artifacts like `pom.xml`, `Cargo.toml`). 

If you add a new language, you must simply register the structural trigger inside the factory mapping found natively within the `QARunnerTool` and `QARunnerAtom` selection layers. 

---

## 3. Creating a New Language Submodule

To add a language, say **Go**, you will create a highly isolated submodule inside `loom/commons`:

**Location**: `src/specweaver/loom/commons/language/go/`

### A. Submodule Files

1. **`__init__.py`**
   - Keeps the namespace clean. Expose only the `GoQARunner`.
2. **`parsers.py`**
   - The pure-logic extractor. Implement functions like `extract_go_test_results(stdout: str) -> TestRunResult`. Ensure you only import from `language.interface`.
3. **`runner.py`**
   - Implements the `GoQARunner` subclass inheriting from a base `QARunnerInterface`.
   - Native bindings to `go build`, `go test`, etc.
4. **`ast_parser.py`**
   - Implements native Tree-Sitter schema endpoints (`extract_skeleton`, `extract_symbol`, `replace_symbol`, `replace_symbol_body`, `delete_symbol`, `add_symbol`, `extract_framework_markers`) to power the unified `CodeStructureTool` and `CodeStructureAtom` APIs.
5. **`scenario_converter.py`**
   - Implements `ScenarioConverterInterface` to translate JSON/YAML abstract scenarios into `_test.go` parameterized execution blocks.
6. **`stack_trace_filter.py`**
   - Implements `StackTraceFilterInterface` to strip unhelpful system stack errors, isolating the domain payload emitted from Go native test failures.
7. **Framework Evaluator Schemas**
   - Provide declarative YAML maps for popular frameworks in the target language (e.g., Gin/Fiber for Go) to unroll runtime markers into `CodeStructureAtom.read_unrolled_symbol`.

### B. The Interface Contract

Your `runner.py` must fully implement or securely stub the `QARunnerInterface`:
- `run_compiler()`
- `run_tests()`
- `run_linter()`
- `run_complexity()`
- `run_debugger()`
- `run_architecture_check(target: str) -> ArchitectureRunResult` (Added in Feature 3.20a: Maps native boundary violations into SpecWeaver)
- **`enforce_boundaries()`** (New in Feature 3.20b: You MUST provide an adapter that translates `context.yaml` boundaries into the language's native Mixed-Criticality FFI enforcement tool, e.g., `ArchUnit` for Java or `eslint` for TS).

*If Go does not support a dedicated complexity checker out-of-the-box, map `run_complexity` to a static no-op violation array or an accepted open-source equivalent (like `gocyclo`).*

---

## 4. Testing Requirements (The Boundaries)

We rigorously separate test boundaries. Do not mix Mock constraints into Live files.

### Unit Tests (Mocked Boundaries)
**Location:** `tests/unit/loom/commons/language/go/`
- Mock `subprocess.run` entirely.
- Validate the logic inside `parsers.py` by passing it raw string output fixtures gathered from real Go executions.
- *Goal:* Verify parser extraction limits.

### Integration Tests (True OS Integrity)
**Location:** 
1. `tests/integration/loom/atoms/qa_runner/go/test_atom.py`
2. `tests/integration/loom/tools/qa_runner/go/test_tool.py`
3. `tests/integration/loom/test_polyglot_ast_edge_cases.py` (Must append your target language Tree-Sitter boundaries!)

- **Absolute Rule:** Do not mock `subprocess`.
- The integration tests must actively execute the real language constraints against dummy project fixtures stored in the `fixtures/` directory.
- *Goal:* Ensure the Tool's RBAC interfaces and the Atom's uninhibited limits actually hook accurately into the OS terminal.

---

## 5. Checklist for Submitting Support

- [ ] Created submodule at `commons/language/<lang>/` with `runner.py`, `parsers.py`, `ast_parser.py`, `scenario_converter.py`, and `stack_trace_filter.py`.
- [ ] No Regex usage where JSON/SARIF is natively supported.
- [ ] Language dispatcher mapped appropriately inside `QARunnerAtom` and `QARunnerTool`.
- [ ] Tree-sitter binaries registered inside `CodeStructureAtom`.
- [ ] Added default YAML schema for macro/annotation unrolling in `workflows/evaluators/frameworks/<lang>/`.
- [ ] Unit tests constructed with static parsing fixtures.
- [ ] Live integration tests built against a dummy project fixture folder.

By following this architecture, SpecWeaver safely remains polyglot while enforcing rigid agent boundaries. Happy coding!
