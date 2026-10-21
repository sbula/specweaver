# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real Maven and cargo run only the test file they are given.

Proves: D-INTL-08 FR-5

Each project holds a passing and a failing test file; asking for the passing one passes. Skipped
where the tool is missing, like `test_polyglot_runners_live.py`.

| Bucket | Case |
|---|---|
| Happy | the passing file's tests pass alone |
| Boundary | the whole project still fails |
| Degradation | a file that names no test class fails rather than passing empty |
| Hostile | not applicable — the target comes from the task's own files |
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
_JAVA = """
    import org.junit.Test;
    import static org.junit.Assert.assertEquals;

    public class {name} {{
        @Test public void it() {{ assertEquals(42, {value}); }}
    }}
"""


@pytest.mark.skipif(
    shutil.which("mvn") is None or shutil.which("javac") is None, reason="maven and a JDK required"
)
class TestMaven:
    def _project(self, tmp_path: Path) -> Path:
        return _write(
            tmp_path / "two",
            {
                "pom.xml": _POM,
                "src/test/java/PassTest.java": _JAVA.format(name="PassTest", value=42),
                "src/test/java/FailTest.java": _JAVA.format(name="FailTest", value=41),
            },
        )

    def _run(self, root: Path, target: str):
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        return JavaRunner(cwd=root, executor=SubprocessExecutor(cwd=root)).run_tests(
            target=target, timeout=900
        )

    def test_the_passing_file_passes_alone(self, tmp_path: Path) -> None:
        result = self._run(self._project(tmp_path), "src/test/java/PassTest.java")

        assert (result.passed, result.failed) == (1, 0), result

    def test_the_whole_project_still_fails(self, tmp_path: Path) -> None:
        result = self._run(self._project(tmp_path), ".")

        assert result.failed == 1, result

    def test_a_missing_class_is_not_an_empty_pass(self, tmp_path: Path) -> None:
        result = self._run(self._project(tmp_path), "src/test/java/GoneTest.java")

        assert result.failed + result.errors >= 1, result


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
class TestCargo:
    def _project(self, tmp_path: Path) -> Path:
        return _write(
            tmp_path / "crate",
            {
                "Cargo.toml": '[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n',
                "src/lib.rs": "pub fn answer() -> u8 { 42 }\n",
                "tests/pass.rs": "#[test]\nfn it() { assert_eq!(probe::answer(), 42); }\n",
                "tests/fail.rs": "#[test]\nfn it() { assert_eq!(probe::answer(), 41); }\n",
            },
        )

    def _run(self, root: Path, target: str):
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        return RustRunner(cwd=root, executor=SubprocessExecutor(cwd=root)).run_tests(
            target=target, timeout=600
        )

    def test_the_passing_file_passes_alone(self, tmp_path: Path) -> None:
        result = self._run(self._project(tmp_path), "tests/pass.rs")

        assert (result.passed, result.failed) == (1, 0), result

    def test_the_whole_crate_still_fails(self, tmp_path: Path) -> None:
        result = self._run(self._project(tmp_path), ".")

        assert result.failed >= 1, result
