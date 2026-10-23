# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real pytest, Maven and cargo run exactly what a target names, at every size.

Proves: TECH-078 FR-7

Each project holds two test files in a folder and its subfolder; each file has one passing and one
failing test, the passing one's name a prefix of the failing one's. Skipped where the tool is
missing, like `test_one_test_file_live.py`.

| Bucket | Case |
|---|---|
| Happy | one test runs one; one file runs its two; the project runs all four |
| Boundary | a folder runs its subfolder's tests too; the subfolder alone runs its own |
| Degradation | a target naming no test fails, naming the target |
| Hostile | a name that is a prefix of another test's runs only its own |
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


def _counts(result: object) -> tuple[int, int]:
    return result.passed, result.failed  # type: ignore[attr-defined]


def _names_the_target(result: object, target: str) -> bool:
    messages = " ".join(f.message for f in result.failures)  # type: ignore[attr-defined]
    return result.errors >= 1 and target in messages  # type: ignore[attr-defined]


class TestPytest:
    @pytest.fixture(scope="class")
    def root(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        pair = "def test_{a}():\n    assert True\n\n\ndef test_{a}_{b}():\n    assert False\n"
        return _write(
            tmp_path_factory.mktemp("sizes") / "py",
            {
                "tests/shop/test_orders.py": pair.format(a="place", b="refund"),
                "tests/shop/deep/test_stock.py": pair.format(a="count", b="low"),
            },
        )

    def _run(self, root: Path, target: str, kind: str = ""):
        from specweaver.sandbox.language.core.python.runner import PythonQARunner

        return PythonQARunner(cwd=root, executor=SubprocessExecutor(cwd=root)).run_tests(
            target=target, kind=kind, timeout=300
        )

    @pytest.mark.parametrize(
        ("target", "counts"),
        [
            ("tests/shop/test_orders.py::test_place", (1, 0)),
            ("tests/shop/test_orders.py", (1, 1)),
            ("tests/shop", (2, 2)),
            ("tests/shop/deep", (1, 1)),
            (".", (2, 2)),
        ],
    )
    def test_each_size_runs_exactly_its_tests(
        self, root: Path, target: str, counts: tuple[int, int]
    ) -> None:
        assert _counts(self._run(root, target)) == counts

    def test_a_named_test_runs_under_a_marker_it_does_not_carry(self, root: Path) -> None:
        result = self._run(root, "tests/shop/test_orders.py::test_place", kind="unit")

        assert _counts(result) == (1, 0), result

    def test_a_target_naming_no_test_fails_naming_it(self, root: Path) -> None:
        result = self._run(root, "tests/shop/test_orders.py::test_gone")

        assert _names_the_target(result, "tests/shop/test_orders.py::test_gone"), result

    def test_the_qa_step_fails_a_folder_with_no_tests(self, root: Path) -> None:
        from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

        (root / "tests" / "empty").mkdir(exist_ok=True)
        result = QARunnerAtom(cwd=root, language="python").run(
            {"intent": "run_tests", "target": "tests/empty", "kind": ""}
        )

        assert result.status.value == "FAILED", result
        assert "tests/empty" in str(result.exports["failures"])


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
    package {package};

    import org.junit.Test;
    import static org.junit.Assert.assertTrue;

    public class {name} {{
        @Test public void {a}() {{ assertTrue(true); }}
        @Test public void {a}{b}() {{ assertTrue(false); }}
    }}
"""


@pytest.mark.skipif(
    shutil.which("mvn") is None or shutil.which("javac") is None, reason="maven and a JDK required"
)
class TestMaven:
    @pytest.fixture(scope="class")
    def root(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        return _write(
            tmp_path_factory.mktemp("sizes") / "jvm",
            {
                "pom.xml": _POM,
                "src/test/java/shop/OrdersTest.java": _JAVA.format(
                    package="shop", name="OrdersTest", a="place", b="Refund"
                ),
                "src/test/java/shop/deep/StockTest.java": _JAVA.format(
                    package="shop.deep", name="StockTest", a="count", b="Low"
                ),
            },
        )

    def _run(self, root: Path, target: str):
        from specweaver.sandbox.language.core.java.runner import JavaRunner

        return JavaRunner(cwd=root, executor=SubprocessExecutor(cwd=root)).run_tests(
            target=target, timeout=900
        )

    @pytest.mark.parametrize(
        ("target", "counts"),
        [
            ("src/test/java/shop/OrdersTest.java::place", (1, 0)),
            ("src/test/java/shop/OrdersTest.java", (1, 1)),
            ("src/test/java/shop", (2, 2)),
            ("src/test/java/shop/deep/", (1, 1)),
            (".", (2, 2)),
        ],
    )
    def test_each_size_runs_exactly_its_tests(
        self, root: Path, target: str, counts: tuple[int, int]
    ) -> None:
        assert _counts(self._run(root, target)) == counts

    def test_a_target_naming_no_test_fails_naming_it(self, root: Path) -> None:
        target = "src/test/java/shop/OrdersTest.java::gone"

        assert _names_the_target(self._run(root, target), target)


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
class TestCargo:
    @pytest.fixture(scope="class")
    def root(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        pair = "#[test]\nfn {a}() {{ assert!(true); }}\n\n#[test]\nfn {a}_{b}() {{ assert!(false); }}\n"
        return _write(
            tmp_path_factory.mktemp("sizes") / "crate",
            {
                "Cargo.toml": '[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n',
                "src/lib.rs": "pub mod shop;\n",
                "src/shop/mod.rs": "pub mod stock;\n",
                "src/shop/stock.rs": "#[cfg(test)]\nmod tests {\n"
                + pair.format(a="count", b="low")
                + "}\n",
                "tests/orders.rs": pair.format(a="place", b="refund"),
            },
        )

    def _run(self, root: Path, target: str):
        from specweaver.sandbox.language.core.rust.runner import RustRunner

        return RustRunner(cwd=root, executor=SubprocessExecutor(cwd=root)).run_tests(
            target=target, timeout=600
        )

    @pytest.mark.parametrize(
        ("target", "counts"),
        [
            ("tests/orders.rs::place", (1, 0)),
            ("src/shop/stock.rs::count", (1, 0)),
            ("tests/orders.rs", (1, 1)),
            ("src/shop/stock.rs", (1, 1)),
            ("tests/", (1, 1)),
            ("src/shop", (1, 1)),
            ("src/", (1, 1)),
            (".", (2, 2)),
        ],
    )
    def test_each_size_runs_exactly_its_tests(
        self, root: Path, target: str, counts: tuple[int, int]
    ) -> None:
        assert _counts(self._run(root, target)) == counts

    def test_a_target_naming_no_test_fails_naming_it(self, root: Path) -> None:
        target = "tests/orders.rs::gone"

        assert _names_the_target(self._run(root, target), target)
