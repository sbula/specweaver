# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The Rust, Java and Kotlin runners against their real toolchains.

**Nothing had ever run them unmocked.** Measured 2026-08-18: no test in the repository gated on
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
