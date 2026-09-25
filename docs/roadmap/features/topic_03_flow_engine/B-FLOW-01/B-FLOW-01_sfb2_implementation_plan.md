# B-FLOW-01 SF-B2 — Polyglot Scenario Pipeline

**Status**: DRAFT (implemented — code present, see As built) · **FRs**: FR-4 (mechanical
conversion), NFR-1, NFR-2; implicit polyglot requirement · **Depends on**: SF-B (COMMITTED
`d79da22`) · **Required by**: SF-C (must be committed before SF-C dev begins) · **Feature ID**: 3.28
· Design: [B-FLOW-01_design.md](B-FLOW-01_design.md)

## Goal

SF-B shipped the scenario converter and contract generator for Python only. SF-B2 makes them
polyglot — Java, Kotlin, TypeScript, Rust, Python — using the language plugin pattern of
`commons/language/` (per `language_support_guide.md`).

Python-hardcoded in SF-B (`d79da22`):
1. `ScenarioConverter` (`workflows/scenarios/scenario_converter.py`) — generates `import pytest`,
   `@pytest.mark.parametrize`, `def test_...`.
2. `GenerateContractHandler._render_protocol()` (`flow/_generation.py:530-562`) — generates a Python
   `Protocol` class.
3. `ConvertScenarioHandler` (`flow/_scenario.py`) — calls `ScenarioConverter.convert()` directly.
   Not dispatched.
4. SF-C also needs a `StackTraceFilterInterface` per language to strip scenario file path frames
   from stack traces before writing to `context.feedback["generate_code"]`.

Scope:
1. **`language_name` property** on `QARunnerInterface` — abstract property returning canonical
   language string. Implemented in all 5 runners.
2. **`ScenarioConverterInterface` ABC** — `convert(scenario_set) -> tuple[str, str]` returning
   `(file_content, file_extension)`.
3. **Language-specific `scenario_converter.py`** in each of the 5 language subfolders.
4. **`ScenarioConverterFactory`** — `create(cwd: Path) -> ScenarioConverterInterface`.
5. **`ConvertScenarioHandler` update** — uses `ScenarioConverterFactory` instead of calling
   `ScenarioConverter` directly.
6. **`GenerateContractHandler` update** — detect language, pass to LLM prompt, write correct file
   extension and directory.
7. **`StackTraceFilterInterface` ABC** — `filter(stack_trace: str) -> str` stripping scenario file
   frames by language.
8. **Language-specific `stack_trace_filter.py`** in each of the 5 language subfolders.
9. **`StackTraceFilterFactory`** — `create(cwd: Path) -> StackTraceFilterInterface`.
10. **`detect_scenario_extension(cwd: Path) -> str`** helper — used by SF-C's `ValidateTestsHandler`
    template substitution.

## Where it plugs in

- **Language detection.** `commons/qa_runner/factory.py` already sniffs manifests. Extract that
  into a shared pure helper in `commons/language/`; the factory's `resolve_runner()` is unchanged.
  Converters and filters call `detect_language()` without constructing a runner.

```python
# commons/language/_detect.py
def detect_language(cwd: Path) -> str:
    """Return canonical language name for a project directory."""
    if (cwd / "package.json").exists():
        return "typescript"
    if (cwd / "Cargo.toml").exists():
        return "rust"
    if (cwd / "build.gradle").exists() or (cwd / "build.gradle.kts").exists():
        return "kotlin"
    if (cwd / "pom.xml").exists():
        return "java"
    return "python"
```

- **`language_name` on `QARunnerInterface`.** An abstract `language_name: str` property; all 5
  runners implement it. No
  runner defines `language_name` today, so nothing conflicts. It becomes the single source of truth
  for language identity when a runner instance exists.

```python
# In QARunnerInterface:
@property
@abstractmethod
def language_name(self) -> str:
    """Canonical language identifier: 'python', 'java', 'kotlin', 'typescript', 'rust'."""
```

- **Test-file conventions per language.** Each convention lives only in that language's
  `ScenarioConverterInterface` implementation, via `output_path()`. `ConvertScenarioHandler` calls
  `converter.output_path(stem, project_root)` and writes there — zero language-specific branching in
  the handler.

| Language | Test framework | Annotation pattern | Output directory | File name |
|----------|---------------|--------------------|-----------------|-----------|
| Python | pytest | `@pytest.mark.parametrize` | `scenarios/generated/` | `test_{stem}_scenarios.py` |
| Java | JUnit 5 | `@ParameterizedTest` + `@MethodSource` | `src/test/java/scenarios/generated/` | `{Stem}ScenariosTest.java` |
| Kotlin | JUnit 5 | `@ParameterizedTest` + `@MethodSource` | `src/test/kotlin/scenarios/generated/` | `{Stem}ScenariosTest.kt` |
| TypeScript | Jest | `test.each([...])` | `scenarios/generated/` | `{stem}.scenarios.test.ts` |
| Rust | `#[cfg(test)]` mod | `#[test]` per scenario | `tests/` | `{stem}_scenarios.rs` |

  - Java/Kotlin use `src/test/java/` / `src/test/kotlin/`: Maven and Gradle only compile files under
    the declared test source roots; a `.java` or `.kt` file in `scenarios/generated/` would be
    silently ignored. The package declaration (`package scenarios.generated;`) keeps the scenario
    namespace visible.
  - Python/TypeScript use `scenarios/generated/`: pytest discovers tests in any directory; Jest's
    default `testMatch: ["**/*.test.ts"]` covers it while `rootDir` is the project root (the
    default).
  - Rust uses `tests/`: the compiler treats files there as independent integration test crates — no
    configuration. Unit tests could live in `src/` under `#[cfg(test)]`, but scenario tests are
    integration tests.

- **Contract format per language.** Current Python output, then Java:
```python
@runtime_checkable
class PaymentProtocol(Protocol):
    def charge(self, amount: float) -> Receipt: ...
```

Java contract output:
```java
// Auto-generated API contract from spec Contract section.
public interface PaymentContract {
    Receipt charge(double amount);
}
```

  `GenerateContractHandler` must: 1. detect language; 2. pass `target_language: <language>` to the
  LLM prompt for `generate+contract` steps; 3. write to `contracts/{stem}_contract.{ext}` where
  `ext` = `py/java/kt/ts/rs`; 4. wire the contract path into `context.api_contract_paths`
  (unchanged).

  > [!NOTE]
  > `GenerateContractHandler` is mechanical (non-LLM) for Python — it parses `## Contract` code
  > blocks into a Protocol class. For other languages the spec's contract section may use other code
  > block tags (` ```java`). Specs are language-neutral, so the handler detects the project
  > language, looks for code blocks tagged with it, and falls back to Python-style parsing if none
  > are found.

- **Stack-trace markers.** Each language's scenario frame marker follows from its `output_path()`
  convention; if the path changes, the filter pattern must change with it.

| Language | Frame format | Scenario frame marker | Why that marker |
|----------|-------------|----------------------|----------------|
| Python | `File "path/to/file.py", line N, in func` | `scenarios/generated/` in path | Direct path in CPython traceback |
| Java | `at scenarios.generated.PaymentScenariosTest.testX(PaymentScenariosTest.java:N)` | `scenarios.generated.` (package prefix) | JVM uses package-qualified class names; matches `src/test/java/scenarios/generated/` |
| Kotlin | `at scenarios.generated.PaymentScenariosTest.testX(PaymentScenariosTest.kt:N)` | `scenarios.generated.` (package prefix) | Same JVM stack format as Java |
| TypeScript | `at Object.<anonymous> (scenarios/generated/payment.scenarios.test.ts:N:M)` | `scenarios/generated/` in path | V8 uses file paths in stack frames |
| Rust | `payment_scenarios::test_charge_happy` | `_scenarios::` in frame | Rust integration test crate name is the file stem |

- **Existing tests.** `tests/unit/workflows/scenarios/test_scenario_converter.py` tests
  `ScenarioConverter.convert()` directly. `ScenarioConverter` becomes `PythonScenarioConverter`;
  only the import changes.

## Changes

### 1. Language detection helper · [_detect.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/_detect.py)

~25 lines. `detect_language(cwd: Path) -> str`, plus `detect_scenario_extension(cwd: Path) -> str`:
```python
_EXTENSIONS = {
    "python": "py",
    "java": "java",
    "kotlin": "kt",
    "typescript": "ts",
    "rust": "rs",
}

def detect_scenario_extension(cwd: Path) -> str:
    """Return the file extension for generated scenario test files."""
    return _EXTENSIONS.get(detect_language(cwd), "py")
```

### 2. `language_name` on `QARunnerInterface` and all runners

[interface.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/qa_runner/interface.py):
```python
@property
@abstractmethod
def language_name(self) -> str:
    """Canonical language identifier."""
```

Each runner (5 files, one `@property` returning the constant, ~3 lines each):

- `commons/language/python/runner.py` → `PythonQARunner.language_name = "python"`
- `commons/language/java/runner.py` → `JavaRunner.language_name = "java"`
- `commons/language/kotlin/runner.py` → `KotlinRunner.language_name = "kotlin"`
- `commons/language/typescript/runner.py` → `TypeScriptRunner.language_name = "typescript"`
- `commons/language/rust/runner.py` → `RustRunner.language_name = "rust"`

### 3. `ScenarioConverterInterface` ABC · [interfaces.py (language)](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/interfaces.py)

After `CodeStructureInterface` (~50 lines):

```python
class ScenarioConverterInterface(ABC):
    """Language-specific converter from ScenarioSet to test file content.

    Mechanical (non-LLM). Produces language-native parametrized test files
    with # @trace(FR-X) tags for C09 compatibility.

    Each implementation fully owns the output path convention for its language.
    The handler calls output_path() and writes to the returned location —
    no language branching is needed in the handler.
    """

    @abstractmethod
    def convert(self, scenario_set: ScenarioSet) -> str:
        """Convert a ScenarioSet to test file content (as a string).

        Args:
            scenario_set: The scenarios to convert.

        Returns:
            The complete test file content string.
        """

    @abstractmethod
    def output_path(self, stem: str, project_root: Path) -> Path:
        """Return the full absolute output path for the generated test file.

        Encodes the language's build-tool-enforced test convention:
        - Python: project_root / scenarios / generated / test_{stem}_scenarios.py
        - Java:   project_root / src/test/java/scenarios/generated/{Stem}ScenariosTest.java
        - Kotlin: project_root / src/test/kotlin/scenarios/generated/{Stem}ScenariosTest.kt
        - TypeScript: project_root / scenarios/generated/{stem}.scenarios.test.ts
        - Rust:   project_root / tests/{stem}_scenarios.rs

        Args:
            stem: Component name (e.g., 'payment').
            project_root: Absolute path to the project root directory.

        Returns:
            Absolute Path to write the generated test file.
        """
```

> [!IMPORTANT]
> `output_path()` replaces `test_file_name()`. It returns an absolute `Path`, not a filename string,
> and is the single place each language's test directory convention is enforced.

### 4. Language-specific scenario converters

Each implements **both** `convert()` (content) and `output_path()` (location).

[scenario_converter.py
(Python)](file:///c:/development/pitbula/specweaver/src/specweaver/workflows/scenarios/scenario_converter.py)
— rename `ScenarioConverter` → `PythonScenarioConverter`, implement `ScenarioConverterInterface`:
- `convert()` returns the pytest file content string (unchanged logic)
- `output_path(stem, project_root)` returns `project_root / "scenarios" / "generated" /
  f"test_{stem}_scenarios.py"`
- keep `ScenarioConverter = PythonScenarioConverter` alias for backward compatibility.
- `scenarios/generated/` keeps generated files out of `tests/` (hand-written tests).

[scenario_converter.py
(Java)](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/java/scenario_converter.py)
— ~130 lines, `JavaScenarioConverter(ScenarioConverterInterface)`. `output_path(stem, project_root)`
returns `project_root / "src" / "test" / "java" / "scenarios" / "generated" /
f"{class_name}ScenariosTest.java"`.
Package declaration `package scenarios.generated;` matches the directory. Output (JUnit 5,
package-declared, parametrized):
```java
// Auto-generated scenario tests from spec scenarios.
package scenarios.generated;

// @trace(FR-1)
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;
import java.util.stream.Stream;
import org.junit.jupiter.params.provider.Arguments;

public class PaymentScenariosTest {

    // @trace(FR-2)
    @ParameterizedTest
    @MethodSource("chargeScenarios")
    void testChargeScenarios(Object inputs, Object expected) {
        // Arrange, Act, Assert — TODO: implement
    }

    static Stream<Arguments> chargeScenarios() {
        return Stream.of(
            Arguments.of("happy_path_inputs", "expected_receipt"),
            Arguments.of("error_path_inputs", "expected_exception")
        );
    }
}
```

[scenario_converter.py
(Kotlin)](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/kotlin/scenario_converter.py)
— ~110 lines, `KotlinScenarioConverter(ScenarioConverterInterface)`. `output_path(stem,
project_root)`
returns `project_root / "src" / "test" / "kotlin" / "scenarios" / "generated" /
f"{class_name}ScenariosTest.kt"`.
Gradle's `sourceSets.test.kotlin.srcDirs` defaults to `src/test/kotlin/`; files outside are not on
the test classpath. Output (JUnit 5 Kotlin, package-declared):
```kotlin
// Auto-generated scenario tests from spec scenarios.
package scenarios.generated

// @trace(FR-1)
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.MethodSource
import java.util.stream.Stream
import org.junit.jupiter.params.provider.Arguments

class PaymentScenariosTest {

    // @trace(FR-2)
    @ParameterizedTest
    @MethodSource("chargeScenarios")
    fun testChargeScenarios(inputs: Any, expected: Any) {
        // TODO: implement
    }

    companion object {
        @JvmStatic
        fun chargeScenarios(): Stream<Arguments> = Stream.of(
            Arguments.of("happy_path_inputs", "expected_receipt")
        )
    }
}
```

[scenario_converter.py
(TypeScript)](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/typescript/scenario_converter.py)
— ~110 lines, `TypeScriptScenarioConverter(ScenarioConverterInterface)`. `output_path(stem,
project_root)`
returns `project_root / "scenarios" / "generated" / f"{stem}.scenarios.test.ts"`. Jest's default
`testMatch: ["**/*.test.ts", "**/*.spec.ts"]` covers any directory under `rootDir`; no Jest config
changes. Output (Jest):
```typescript
// Auto-generated scenario tests from spec scenarios.
// @trace(FR-1)

describe('payment scenarios', () => {
  // @trace(FR-2)
  test.each([
    { inputs: 'happy_path_inputs', expected: 'expected_receipt' },
    { inputs: 'error_path_inputs', expected: 'expected_error' },
  ])('charge: $#', ({ inputs, expected }) => {
    // arrange / act / assert — TODO: implement
    expect(true).toBe(true);
  });
});
```

[scenario_converter.py
(Rust)](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/rust/scenario_converter.py)
— ~100 lines, `RustScenarioConverter(ScenarioConverterInterface)`. `output_path(stem, project_root)`
returns `project_root / "tests" / f"{stem}_scenarios.rs"`. Rust has no native parametrized tests,
so one `#[test]` function per scenario. Output (Rust integration tests):
```rust
// Auto-generated scenario tests from spec scenarios.
// @trace(FR-1)

#[cfg(test)]
mod payment_scenarios {
    // @trace(FR-2)
    #[test]
    fn test_charge_happy() {
        // Arrange: happy_path_inputs
        // Act
        // Assert: expected_receipt
        todo!()
    }

    #[test]
    fn test_charge_error() {
        // Arrange: error_path_inputs
        // Act
        // Assert: expected_exception
        todo!()
    }
}
```

### 5. `ScenarioConverterFactory` · [scenario_converter_factory.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/scenario_converter_factory.py)

~60 lines:

```python
from pathlib import Path
from specweaver.core.loom.commons.language._detect import detect_language, detect_scenario_extension
from specweaver.core.loom.commons.language.interfaces import ScenarioConverterInterface


def create_scenario_converter(cwd: Path) -> ScenarioConverterInterface:
    """Create the appropriate ScenarioConverter for the detected language."""
    language = detect_language(cwd)
    if language == "java":
        from specweaver.core.loom.commons.language.java.scenario_converter import JavaScenarioConverter
        return JavaScenarioConverter()
    if language == "kotlin":
        from specweaver.core.loom.commons.language.kotlin.scenario_converter import KotlinScenarioConverter
        return KotlinScenarioConverter()
    if language == "typescript":
        from specweaver.core.loom.commons.language.typescript.scenario_converter import TypeScriptScenarioConverter
        return TypeScriptScenarioConverter()
    if language == "rust":
        from specweaver.core.loom.commons.language.rust.scenario_converter import RustScenarioConverter
        return RustScenarioConverter()
    # Default: Python
    from specweaver.workflows.scenarios.scenario_converter import PythonScenarioConverter
    return PythonScenarioConverter()
```

Also re-exports `detect_scenario_extension` from `_detect.py`, so SF-C's `ValidateTestsHandler` has
one import point.

### 6. `StackTraceFilterInterface` ABC + language implementations

[interfaces.py
(language)](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/interfaces.py)
— ~35 lines:

```python
class StackTraceFilterInterface(ABC):
    """Strips scenario test file frames from stack traces.

    Used by the Arbiter to produce coding agent feedback that contains
    zero scenario vocabulary — only the coding agent's own source frames.
    """

    @abstractmethod
    def filter(self, stack_trace: str) -> str:
        """Remove scenario file frames; preserve source code frames.

        Args:
            stack_trace: Raw stack trace text from a test failure.

        Returns:
            Filtered stack trace with scenario frames removed.
        """

    @abstractmethod
    def is_scenario_frame(self, line: str) -> bool:
        """Return True if this line is a scenario test file frame."""
```

`stack_trace_filter.py` in each language subfolder (~35 lines each):

**Python** (`commons/language/python/stack_trace_filter.py`):
```python
class PythonStackTraceFilter(StackTraceFilterInterface):
    def is_scenario_frame(self, line: str) -> bool:
        return "scenarios/generated/" in line or "scenarios\\generated\\" in line

    def filter(self, stack_trace: str) -> str:
        return "\n".join(
            line for line in stack_trace.split("\n")
            if not self.is_scenario_frame(line)
        )
```

**Java** (`commons/language/java/stack_trace_filter.py`):
```python
class JavaStackTraceFilter(StackTraceFilterInterface):
    def is_scenario_frame(self, line: str) -> bool:
        return "scenarios.generated." in line

    def filter(self, stack_trace: str) -> str:
        return "\n".join(
            line for line in stack_trace.split("\n")
            if not self.is_scenario_frame(line)
        )
```

**Kotlin** (`commons/language/kotlin/stack_trace_filter.py`) — same as Java,
`"scenarios.generated."`.

**TypeScript** (`commons/language/typescript/stack_trace_filter.py`) — path-based like Python,
`"scenarios/generated/"`.

**Rust** (`commons/language/rust/stack_trace_filter.py`):
```python
class RustStackTraceFilter(StackTraceFilterInterface):
    def is_scenario_frame(self, line: str) -> bool:
        return "scenario_tests::" in line or "_scenarios::" in line

    def filter(self, stack_trace: str) -> str:
        return "\n".join(
            line for line in stack_trace.split("\n")
            if not self.is_scenario_frame(line)
        )
```

[stack_trace_filter_factory.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/commons/language/stack_trace_filter_factory.py)
— ~50 lines, same dispatch as `scenario_converter_factory.py`.

### 7. `ConvertScenarioHandler` · [_scenario.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_scenario.py)

Factory dispatch replaces the direct `ScenarioConverter` call. **Zero language awareness** —
`output_path()` encodes every convention and creates the right directory. ~10 lines changed; no
`if language == "rust"` or other branching:

```python
# Before (Python-only):
from specweaver.workflows.scenarios.scenario_converter import ScenarioConverter
pytest_content = ScenarioConverter.convert(scenario_set)
output_path = output_dir / f"test_{stem}_scenarios.py"

# After (polyglot — handler is fully language-agnostic):
from specweaver.core.loom.commons.language.scenario_converter_factory import create_scenario_converter
converter = create_scenario_converter(context.project_path)
file_content = converter.convert(scenario_set)
output_path = converter.output_path(stem, context.project_path)

output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(file_content, encoding="utf-8")
```

Also stores the resolved path for SF-C:
```python
context.feedback["scenario_test_path"] = str(output_path)
```

### 8. `GenerateContractHandler` · [_generation.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/_generation.py)

Language detection before rendering in `GenerateContractHandler.execute()`:

```python
from specweaver.core.loom.commons.language._detect import detect_language
language = detect_language(context.project_path)

# Language-specific output path and rendering
if language == "java":
    output_path = contracts_dir / f"{class_name}Contract.java"
    contract_content = self._render_java_interface(class_name, signatures, docstrings)
elif language == "kotlin":
    output_path = contracts_dir / f"{class_name}Contract.kt"
    contract_content = self._render_kotlin_interface(class_name, signatures, docstrings)
elif language == "typescript":
    output_path = contracts_dir / f"{stem}.contract.ts"
    contract_content = self._render_typescript_interface(class_name, signatures, docstrings)
elif language == "rust":
    output_path = contracts_dir / f"{stem}_contract.rs"
    contract_content = self._render_rust_trait(class_name, signatures, docstrings)
else:
    output_path = contracts_dir / f"{stem}_contract.py"
    contract_content = self._render_protocol(class_name, signatures, docstrings)
```

New static methods `_render_java_interface()`, `_render_kotlin_interface()`,
`_render_typescript_interface()`, `_render_rust_trait()` (~40 lines each, `_render_protocol()`
pattern). `_extract_signatures()` matches code blocks tagged with the project language first:
```python
# Look for code blocks matching the project language first
code_blocks = re.findall(rf"```{language}\s*\n(.*?)```", contract_text, re.DOTALL)
if not code_blocks:
    # Fallback to language-agnostic extraction
    code_blocks = re.findall(r"```\w*\s*\n(.*?)```", contract_text, re.DOTALL)
```

> [!CAUTION]
> `_generation.py` is already 564 lines, over the 450-line soft limit; ~170 more would regress it.
> All new `_render_*` methods MUST go into `flow/_contract_renderers.py` (~160 lines), imported
> from `_generation.py`.

### Files

| File | Change |
|---|---|
| `src/specweaver/core/loom/commons/language/_detect.py` | new, ~25 lines |
| `src/specweaver/core/loom/commons/language/scenario_converter_factory.py` | new, ~60 lines |
| `src/specweaver/core/loom/commons/language/stack_trace_filter_factory.py` | new, ~50 lines |
| `src/specweaver/core/flow/_contract_renderers.py` | new, ~160 lines |
| `src/specweaver/core/loom/commons/language/python/scenario_converter.py` | new, ~80 lines |
| `src/specweaver/core/loom/commons/language/java/scenario_converter.py` | new, ~120 lines |
| `src/specweaver/core/loom/commons/language/kotlin/scenario_converter.py` | new, ~100 lines |
| `src/specweaver/core/loom/commons/language/typescript/scenario_converter.py` | new, ~110 lines |
| `src/specweaver/core/loom/commons/language/rust/scenario_converter.py` | new, ~100 lines |
| `src/specweaver/core/loom/commons/language/python/stack_trace_filter.py` | new, ~35 lines |
| `src/specweaver/core/loom/commons/language/java/stack_trace_filter.py` | new, ~35 lines |
| `src/specweaver/core/loom/commons/language/kotlin/stack_trace_filter.py` | new, ~35 lines |
| `src/specweaver/core/loom/commons/language/typescript/stack_trace_filter.py` | new, ~35 lines |
| `src/specweaver/core/loom/commons/language/rust/stack_trace_filter.py` | new, ~35 lines |
| `tests/unit/core/loom/commons/language/test_detect.py` | new, ~40 lines |
| `tests/unit/core/loom/commons/language/test_scenario_converters.py` | new, ~160 lines |
| `tests/unit/core/loom/commons/language/test_stack_trace_filters.py` | new, ~120 lines |
| `tests/unit/core/loom/commons/language/test_factories.py` | new, ~50 lines |
| `tests/unit/core/loom/commons/language/test_contract_renderers.py` | new, ~60 lines |
| `src/specweaver/core/loom/commons/language/interfaces.py` | +75 lines — 2 new ABCs |
| `src/specweaver/core/loom/commons/qa_runner/interface.py` | +5 lines — abstract property |
| `src/specweaver/core/loom/commons/language/python/runner.py` | +3 lines |
| `src/specweaver/core/loom/commons/language/java/runner.py` | +3 lines |
| `src/specweaver/core/loom/commons/language/kotlin/runner.py` | +3 lines |
| `src/specweaver/core/loom/commons/language/typescript/runner.py` | +3 lines |
| `src/specweaver/core/loom/commons/language/rust/runner.py` | +3 lines |
| `src/specweaver/core/flow/_scenario.py` | +15 lines |
| `src/specweaver/core/flow/_generation.py` | +20 lines — dispatch only; renderers in new file |
| `src/specweaver/workflows/scenarios/scenario_converter.py` | +5 lines — rename + alias |
| `tests/unit/workflows/scenarios/test_scenario_converter.py` | +3 lines — import update |
| `tests/unit/core/flow/test_scenario_handlers.py` | +10 lines — mock factory |

Commit: `feat(3.28-polyglot): add polyglot scenario converters, contract renderers, and stack trace
filters for Java, Kotlin, TypeScript, Rust, Python`

## Tests

`tests/unit/workflows/scenarios/test_scenario_converter.py` — `ScenarioConverter` →
`PythonScenarioConverter`; test logic unchanged.

`tests/unit/core/loom/commons/language/test_detect.py`
- `test_detect_python_by_default`
- `test_detect_java_by_pom_xml`
- `test_detect_kotlin_by_build_gradle`
- `test_detect_typescript_by_package_json`
- `test_detect_rust_by_cargo_toml`
- `test_detect_scenario_extension_all_languages`

`tests/unit/core/loom/commons/language/test_scenario_converters.py` — one class per converter,
testing **both** content and output path:
- `TestPythonScenarioConverter`:
  - `test_convert_returns_pytest_content`
  - `test_trace_tags_present`
  - `test_output_path_is_in_scenarios_generated` — asserts
    `scenarios/generated/test_{stem}_scenarios.py`
  - `test_output_path_parent_created`
- `TestJavaScenarioConverter`:
  - `test_convert_returns_junit5_content`
  - `test_package_declaration_present` — `package scenarios.generated;`
  - `test_parametrized_test_annotation_present`
  - `test_output_path_is_in_src_test_java` — asserts
    `src/test/java/scenarios/generated/{Stem}ScenariosTest.java`
- `TestKotlinScenarioConverter`:
  - `test_convert_returns_kotlin_content`
  - `test_package_declaration_present` — `package scenarios.generated`
  - `test_companion_object_present`
  - `test_output_path_is_in_src_test_kotlin` — asserts
    `src/test/kotlin/scenarios/generated/{Stem}ScenariosTest.kt`
- `TestTypeScriptScenarioConverter`:
  - `test_convert_returns_jest_content`
  - `test_test_each_present`
  - `test_output_path_is_in_scenarios_generated` — asserts
    `scenarios/generated/{stem}.scenarios.test.ts`
- `TestRustScenarioConverter`:
  - `test_convert_returns_rust_content`
  - `test_cfg_test_present`
  - `test_output_path_is_in_tests_dir` — asserts `tests/{stem}_scenarios.rs` (NOT
    `scenarios/generated/`)

`tests/unit/core/loom/commons/language/test_stack_trace_filters.py` — one class per filter, each
with a realistic multi-frame stack trace:
- `TestPythonStackTraceFilter`:
  - `test_strips_scenarios_generated_frame` — frame with `scenarios/generated/` is removed
  - `test_preserves_src_frame` — frame with `src/` is kept
  - `test_empty_trace_returns_empty`
- `TestJavaStackTraceFilter`:
  - `test_strips_scenarios_generated_package_frame` — `at
    scenarios.generated.PaymentScenariosTest...` removed
  - `test_preserves_user_package_frame` — `at com.example.Payment...` kept
- `TestKotlinStackTraceFilter`: same as Java (identical JVM frame format)
- `TestTypeScriptStackTraceFilter`: same as Python (path-based V8 frames)
- `TestRustStackTraceFilter`:
  - `test_strips_scenarios_module_frame` — `payment_scenarios::test_charge_happy` removed
  - `test_preserves_src_crate_frame` — `crate::payment::charge` kept

`tests/unit/core/loom/commons/language/test_factories.py`
- `test_scenario_converter_factory_python` — mock `package.json` absent → `PythonScenarioConverter`
- `test_scenario_converter_factory_java` — mock `pom.xml` present → `JavaScenarioConverter`
- `test_scenario_converter_factory_kotlin` — mock `build.gradle` present → `KotlinScenarioConverter`
- `test_scenario_converter_factory_typescript` — mock `package.json` present →
  `TypeScriptScenarioConverter`
- `test_scenario_converter_factory_rust` — mock `Cargo.toml` present → `RustScenarioConverter`
- `test_stack_trace_filter_factory_all_languages`

`tests/unit/core/flow/test_scenario_handlers.py` — mock `create_scenario_converter` and verify:
- Factory is called with `context.project_path`
- `converter.convert(scenario_set)` is called
- `converter.output_path(stem, context.project_path)` is called
- The returned path's parent is `mkdir`'d
- `context.feedback["scenario_test_path"]` is set to the string path

`tests/unit/core/loom/commons/language/test_contract_renderers.py`
- `test_render_java_interface`
- `test_render_kotlin_interface`
- `test_render_typescript_interface`
- `test_render_rust_trait`
- `test_render_protocol_python` (existing, moved)

`tests/unit/core/flow/test_scenario_pipeline_integration.py` — pass a language-aware mock runner /
project path fixture.

`tests/unit/core/loom/commons/qa_runner/` (each runner test file) — `test_language_name_property`
asserts the right string.

```
pytest tests/unit/core/loom/commons/language/ -v
pytest tests/unit/workflows/scenarios/test_scenario_converter.py -v
pytest tests/unit/core/flow/test_scenario_handlers.py -v
python -m tach check
ruff check src/ tests/
mypy src/ tests/
pytest tests/ -v --tb=short   # full regression
```

Key assertions:
- All 5 runners expose `language_name` string property
- All 5 scenario converters return `str` from `convert()` and `Path` from `output_path()`
- Java output path is under `src/test/java/scenarios/generated/`
- Kotlin output path is under `src/test/kotlin/scenarios/generated/`
- Python and TypeScript output paths are under `scenarios/generated/`
- Rust output path is under `tests/`
- Java and Kotlin generated files contain `package scenarios.generated;` / `package
  scenarios.generated`
- All 5 stack trace filters strip scenario frames and preserve source frames
- `ConvertScenarioHandler` has ZERO language branching — calls `output_path()` only
- `context.feedback["scenario_test_path"]` is set by `ConvertScenarioHandler`
- `GenerateContractHandler` writes correct file extension and content per language

## As built

**Since moved** (noted 2026-09-25): `loom/commons/language/` is now `sandbox/language/core/`
(`_detect.py`, `scenario_converter_factory.py` with `create_scenario_converter`, per-language
`python/`, `java/`, … subfolders, including `PythonScenarioConverter`); `QARunnerInterface` is in
`sandbox/qa_runner/core/interface.py`; `ScenarioConverterInterface` and
`StackTraceFilterInterface` are in `workspace/ast/parsers/interfaces.py`; the renderers are public
functions (`render_java_interface`, …) in `core/flow/handlers/contract_renderers.py`.
