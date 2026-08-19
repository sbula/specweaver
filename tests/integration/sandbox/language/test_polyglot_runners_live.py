# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The Rust, Java and Kotlin runners against their real toolchains.

**Nothing had ever run them unmocked.** no test in the repository gated on
`shutil.which("cargo" | "java" | "kotlinc" | "mvn")`, so all five language runners were proven only
against mocked executors — and the four fixtures under `tests/fixtures/` that look like projects hold
no source files at all. They are language-detection stubs, so no test could have run them even if one
had tried.

That is how `RustQARunner` shipped issuing `cargo test --format=json -q`, which real cargo rejects
with *"unexpected argument '--format' found"*, piped into a `cargo2junit` that is installed nowhere.
A mocked executor returns whatever the test author imagined; only the real tool can say no.

Each test writes a project, runs the production runner against the real binary, and asserts the
counts. Skips cite the toolchain and nothing else — the one thing `check_conventions` R8 permits.

Proves: TECH-031 FR-11, TECH-031 FR-12, TECH-031 FR-13
"""

from __future__ import annotations

import shutil
import textwrap
from typing import TYPE_CHECKING

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return root


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
class TestRustRunnerAgainstRealCargo:
    """`cargo test` on a crate with no dependencies: no network, no prepare step."""

    _CARGO_TOML = '[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n'

    def _runner(self, root: Path):
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        return RustRunner(cwd=root, executor=SubprocessExecutor(cwd=root))

    def test_a_passing_crate_is_counted(self, tmp_path: Path) -> None:
        root = _write(
            tmp_path / "pass",
            {
                "Cargo.toml": self._CARGO_TOML,
                "src/lib.rs": """
                    pub fn v() -> i32 { 42 }

                    #[cfg(test)]
                    mod t {
                        #[test]
                        fn works() { assert_eq!(super::v(), 42); }
                    }
                """,
            },
        )

        result = self._runner(root).run_tests(target=".", timeout=600)

        assert result.passed == 1, result
        assert result.failed == 0 and result.errors == 0, result

    def test_a_failing_test_is_reported_with_its_panic(self, tmp_path: Path) -> None:
        """The half a mock cannot reach: the panic text comes from rustc, not from us."""
        root = _write(
            tmp_path / "fail",
            {
                "Cargo.toml": self._CARGO_TOML,
                "src/lib.rs": """
                    pub fn v() -> i32 { 41 }

                    #[cfg(test)]
                    mod t {
                        #[test]
                        fn broken() { assert_eq!(super::v(), 42); }
                    }
                """,
            },
        )

        result = self._runner(root).run_tests(target=".", timeout=600)

        assert result.failed == 1, result
        assert result.failures, "a failing crate produced no failure detail"
        assert "left" in result.failures[0].message.lower(), result.failures[0].message

    def test_a_crate_that_does_not_compile_is_not_a_clean_run(self, tmp_path: Path) -> None:
        """Hostile: a compile error prints to stderr and no summary to stdout.

        Counting that as `0 passed, 0 failed` is the vacuous success the QA gate exists to prevent,
        and it is the case the old JSON parser would have hit on every single run.
        """
        root = _write(
            tmp_path / "broken",
            {
                "Cargo.toml": self._CARGO_TOML,
                "src/lib.rs": "pub fn v() -> i32 { this is not rust }",
            },
        )

        result = self._runner(root).run_tests(target=".", timeout=600)

        assert result.failed >= 1 or result.errors >= 1, (
            f"a crate that does not compile reported as a clean run: {result}"
        )


@pytest.mark.skipif(
    shutil.which("mvn") is None or shutil.which("javac") is None,
    reason="maven and a JDK required",
)
class TestJavaRunnerAgainstRealMaven:
    """`mvn test` through the production runner, with no wrapper in the project.

    The runner falls back from `mvnw` to the system `mvn` when no wrapper is present, which is what
    makes this reachable at all — and that fallback had never been exercised.
    """

    _POM = """
        <project xmlns="http://maven.apache.org/POM/4.0.0">
          <modelVersion>4.0.0</modelVersion>
          <groupId>probe</groupId><artifactId>probe</artifactId><version>1.0</version>
          <properties>
            <maven.compiler.source>17</maven.compiler.source>
            <maven.compiler.target>17</maven.compiler.target>
            <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
          </properties>
          <dependencies><dependency>
            <groupId>junit</groupId><artifactId>junit</artifactId>
            <version>4.13.2</version><scope>test</scope>
          </dependency></dependencies>
        </project>
    """

    def _runner(self, root: Path):
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        return JavaRunner(cwd=root, executor=SubprocessExecutor(cwd=root))

    def test_a_passing_suite_is_counted(self, tmp_path: Path) -> None:
        root = _write(
            tmp_path / "javapass",
            {
                "pom.xml": self._POM,
                "src/test/java/ProbeTest.java": """
                    import org.junit.Test;
                    import static org.junit.Assert.assertEquals;

                    public class ProbeTest {
                        @Test public void works() { assertEquals(42, 42); }
                    }
                """,
            },
        )

        result = self._runner(root).run_tests(target=".", timeout=900)

        assert result.passed == 1, result
        assert result.failed == 0, result

    def test_a_failing_suite_is_counted(self, tmp_path: Path) -> None:
        root = _write(
            tmp_path / "javafail",
            {
                "pom.xml": self._POM,
                "src/test/java/ProbeTest.java": """
                    import org.junit.Test;
                    import static org.junit.Assert.assertEquals;

                    public class ProbeTest {
                        @Test public void broken() { assertEquals(42, 41); }
                    }
                """,
            },
        )

        result = self._runner(root).run_tests(target=".", timeout=900)

        assert result.failed == 1, result
        assert result.passed == 0, result
        # The half that used to be missing entirely: the runner returned `failures=[]` while the
        # surefire report beside it held the assertion and the stack. A caller given only `failed=1`
        # has to re-run the suite by hand to learn anything, which is what the sandbox avoids.
        assert result.failures, "a failing suite carried no detail to act on"
        assert result.failures[0].nodeid == "ProbeTest.broken", result.failures[0].nodeid
        assert "expected:<42> but was:<41>" in result.failures[0].message, result.failures[
            0
        ].message
        assert "ProbeTest.broken" in result.failures[0].stacktrace, result.failures[0].stacktrace

    def test_a_build_that_does_not_compile_is_not_an_empty_suite(self, tmp_path: Path) -> None:
        """The vacuous shape, reproduced against real Maven before it was fixed.

        The build exits non-zero and prints freely, so `did_not_run` — which keys on empty stdout —
        lets it through, and a `surefire-reports` directory that was never written harvests as
        `0 passed, 0 failed`. Indistinguishable, to a caller, from a project with no tests.
        """
        root = _write(
            tmp_path / "javabroken",
            {
                "pom.xml": self._POM,
                "src/test/java/ProbeTest.java": "public class ProbeTest { this is not java }",
            },
        )

        result = self._runner(root).run_tests(target=".", timeout=900)

        assert result.failed >= 1 or result.errors >= 1, (
            f"a build that does not compile reported as a clean run: {result}"
        )


@pytest.mark.skipif(
    shutil.which("mvn") is None or shutil.which("kotlinc") is None,
    reason="maven and kotlinc required",
)
class TestKotlinRunnerAgainstRealMaven:
    """Kotlin through Maven rather than Gradle.

    `KotlinRunner` drives whichever build tool the project declares. Maven is chosen here because the
    system Gradle is 4.4.1, far older than the Kotlin plugin needs, and a Gradle wrapper would fetch
    its own distribution on first run — network the sandbox's execute phase does not have.
    """

    _POM = """
        <project xmlns="http://maven.apache.org/POM/4.0.0">
          <modelVersion>4.0.0</modelVersion>
          <groupId>probe</groupId><artifactId>kprobe</artifactId><version>1.0</version>
          <properties><kotlin.version>2.4.10</kotlin.version></properties>
          <dependencies>
            <dependency><groupId>org.jetbrains.kotlin</groupId>
              <artifactId>kotlin-stdlib</artifactId><version>${kotlin.version}</version></dependency>
            <dependency><groupId>org.jetbrains.kotlin</groupId>
              <artifactId>kotlin-test-junit</artifactId><version>${kotlin.version}</version>
              <scope>test</scope></dependency>
          </dependencies>
          <build>
            <sourceDirectory>src/main/kotlin</sourceDirectory>
            <testSourceDirectory>src/test/kotlin</testSourceDirectory>
            <plugins><plugin>
              <groupId>org.jetbrains.kotlin</groupId><artifactId>kotlin-maven-plugin</artifactId>
              <version>${kotlin.version}</version>
              <executions>
                <execution><id>compile</id><phase>compile</phase>
                  <goals><goal>compile</goal></goals></execution>
                <execution><id>test-compile</id><phase>test-compile</phase>
                  <goals><goal>test-compile</goal></goals></execution>
              </executions>
            </plugin></plugins>
          </build>
        </project>
    """

    def test_a_passing_suite_is_counted(self, tmp_path: Path) -> None:
        from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

        root = _write(
            tmp_path / "kotlinpass",
            {
                "pom.xml": self._POM,
                "src/main/kotlin/Probe.kt": "fun v(): Int = 42\n",
                "src/test/kotlin/ProbeTest.kt": """
                    import kotlin.test.Test
                    import kotlin.test.assertEquals

                    class ProbeTest {
                        @Test fun works() { assertEquals(42, v()) }
                    }
                """,
            },
        )
        runner = KotlinRunner(cwd=root, executor=SubprocessExecutor(cwd=root))

        result = runner.run_tests(target=".", timeout=900)

        assert result.passed == 1, result
        assert result.failed == 0, result

    def test_a_build_that_does_not_compile_is_not_an_empty_suite(self, tmp_path: Path) -> None:
        """This is the exact run that exposed the defect: `BUILD FAILURE`, exit 1, and a
        `TestRunResult(passed=0, failed=0, errors=0, total=0)` handed to the caller."""
        from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

        root = _write(
            tmp_path / "kotlinbroken",
            {
                "pom.xml": self._POM,
                "src/main/kotlin/Probe.kt": "fun v(): Int = 42\n",
                "src/test/kotlin/ProbeTest.kt": "class ProbeTest { this is not kotlin }",
            },
        )
        runner = KotlinRunner(cwd=root, executor=SubprocessExecutor(cwd=root))

        result = runner.run_tests(target=".", timeout=900)

        assert result.failed >= 1 or result.errors >= 1, (
            f"a Kotlin build that does not compile reported as a clean run: {result}"
        )

    def test_a_failing_suite_carries_its_detail(self, tmp_path: Path) -> None:
        """Kotlin had the same empty-`failures` hole as Java, from the same shared harvester."""
        from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

        root = _write(
            tmp_path / "kotlinfail",
            {
                "pom.xml": self._POM,
                "src/main/kotlin/Probe.kt": "fun v(): Int = 41\n",
                "src/test/kotlin/ProbeTest.kt": """
                    import kotlin.test.Test
                    import kotlin.test.assertEquals

                    class ProbeTest {
                        @Test fun broken() { assertEquals(42, v()) }
                    }
                """,
            },
        )
        runner = KotlinRunner(cwd=root, executor=SubprocessExecutor(cwd=root))

        result = runner.run_tests(target=".", timeout=900)

        assert result.failed == 1, result
        assert result.failures, "a failing Kotlin suite carried no detail to act on"
        assert result.failures[0].nodeid == "ProbeTest.broken", result.failures[0].nodeid
        assert "42" in result.failures[0].message, result.failures[0].message


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
class TestRustIntentsBeyondTests:
    """Lint, complexity, compile and debug against real cargo.

    Only `run_tests` had ever been exercised unmocked, and the three defects below were all hiding
    behind mocks that returned whatever their author imagined.

    Proves: TECH-031 FR-19
    """

    _CARGO_TOML = '[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n'

    def _runner(self, root: Path):
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        return RustRunner(cwd=root, executor=SubprocessExecutor(cwd=root))

    def test_clippy_findings_reach_the_caller(self, tmp_path: Path) -> None:
        """These were piped through `clippy-sarif`, which is installed nowhere — so the pipe
        produced nothing and the guard around it reported a clean project."""
        root = _write(
            tmp_path / "lint",
            {
                "Cargo.toml": self._CARGO_TOML,
                "src/lib.rs": """
                    pub fn messy(x: i32) -> i32 {
                        let y = x;
                        return y;
                    }
                """,
            },
        )

        result = self._runner(root).run_linter(".")

        assert result.error_count >= 1, (
            f"clippy flags this code and nothing reached the caller: {result}"
        )
        finding = result.errors[0]
        assert finding.code.startswith("clippy::"), finding
        assert finding.file.endswith("lib.rs") and finding.line > 0, finding

    def test_a_clean_crate_lints_clean(self, tmp_path: Path) -> None:
        """The control. Without it, a linter that invented findings would pass the test above."""
        root = _write(
            tmp_path / "clean",
            {"Cargo.toml": self._CARGO_TOML, "src/lib.rs": "pub fn v() -> i32 { 42 }\n"},
        )

        assert self._runner(root).run_linter(".").error_count == 0

    def test_a_good_crate_compiles_without_error(self, tmp_path: Path) -> None:
        """`cargo build` writes progress to stderr, so its stdout is empty — which the old check
        read as an absent toolchain and reported as a compile failure for every healthy crate."""
        root = _write(
            tmp_path / "good",
            {
                "Cargo.toml": self._CARGO_TOML,
                "src/lib.rs": "pub fn v() -> i32 { 42 }\n",
                "src/main.rs": 'fn main() { println!("ok"); }\n',
            },
        )

        result = self._runner(root).run_compiler(".")

        assert result.error_count == 0, result

    def test_a_broken_crate_reports_the_compiler_error(self, tmp_path: Path) -> None:
        root = _write(
            tmp_path / "broken",
            {
                "Cargo.toml": self._CARGO_TOML,
                "src/lib.rs": "pub fn v() -> i32 { this is not rust }",
            },
        )

        result = self._runner(root).run_compiler(".")

        assert result.error_count >= 1, result
        assert result.errors[0].message, "a compile failure with no message to act on"

    def test_the_debugger_runs_the_program(self, tmp_path: Path) -> None:
        root = _write(
            tmp_path / "dbg",
            {
                "Cargo.toml": self._CARGO_TOML,
                "src/main.rs": 'fn main() { println!("hello from main"); }\n',
            },
        )

        result = self._runner(root).run_debugger(".", "main")

        assert result.exit_code == 0, result
        assert any("hello from main" in e.output for e in result.events), result.events


@pytest.mark.skipif(
    shutil.which("mvn") is None or shutil.which("javac") is None,
    reason="maven and a JDK required",
)
class TestJavaIntentsBeyondTests:
    """Java's compiler and debugger against real Maven.

    Both returned something true and useless: the compiler reported that a build failed, which the
    exit code already said, with an empty message; and the debugger returned Maven's whole log as
    the program's output, burying the one line the program printed.

    Proves: TECH-031 FR-20
    """

    _POM = """
        <project xmlns="http://maven.apache.org/POM/4.0.0">
          <modelVersion>4.0.0</modelVersion>
          <groupId>probe</groupId><artifactId>probe</artifactId><version>1.0</version>
          <properties>
            <maven.compiler.source>17</maven.compiler.source>
            <maven.compiler.target>17</maven.compiler.target>
            <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
          </properties>
        </project>
    """

    def _runner(self, root: Path):
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        return JavaRunner(cwd=root, executor=SubprocessExecutor(cwd=root))

    def test_a_compile_error_carries_its_location_and_message(self, tmp_path: Path) -> None:
        root = _write(
            tmp_path / "jbad",
            {
                "pom.xml": self._POM,
                "src/main/java/App.java": """
                    public class App {
                        public int broken() { return "not an int"; }
                    }
                """,
            },
        )

        result = self._runner(root).run_compiler(
            ".",
        )

        assert result.error_count >= 1, result
        error = result.errors[0]
        assert error.file.endswith("App.java"), error
        assert error.line > 0, error
        assert "cannot be converted to int" in error.message, error

    def test_a_good_build_reports_no_errors(self, tmp_path: Path) -> None:
        """The control: a compiler that invents diagnostics would pass the test above."""
        root = _write(
            tmp_path / "jgood",
            {
                "pom.xml": self._POM,
                "src/main/java/App.java": "public class App { public int f(){ return 1; } }\n",
            },
        )

        assert self._runner(root).run_compiler(".").error_count == 0

    def test_the_debugger_returns_the_programs_output_not_the_build_log(
        self, tmp_path: Path
    ) -> None:
        root = _write(
            tmp_path / "jdbg",
            {
                "pom.xml": self._POM,
                "src/main/java/App.java": """
                    public class App {
                        public static void main(String[] a) {
                            System.out.println("hello from java");
                        }
                    }
                """,
            },
        )

        result = self._runner(root).run_debugger(".", "App")

        assert result.exit_code == 0, result
        printed = [e.output for e in result.events]
        assert printed == ["hello from java"], printed
