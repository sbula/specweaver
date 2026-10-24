# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real Kotlin (Maven and Gradle) and Vitest run exactly what a target names, at every size.

Proves: TECH-078 FR-7

The `toolchain` tier: these builds download their packages, so they run nightly
(`scripts/toolchain.py`), not in the default suite. Each project holds two test files in a folder
and its subfolder; each file has one passing and one failing test, the passing one's name a prefix
of the failing one's.

| Bucket | Case |
|---|---|
| Happy | one test runs one; one file runs its two; the project runs all four |
| Boundary | a folder runs its subfolder's tests too |
| Degradation | a missing tool or registry skips, saying which; a target naming no test fails, naming it |
| Hostile | a name that is a prefix or a suffix of another test's runs only its own |
"""

from __future__ import annotations

import functools
import shutil
import socket
import subprocess
import textwrap
from pathlib import Path

import pytest

from specweaver.sandbox.execution.executor import SubprocessExecutor

pytestmark = [pytest.mark.integration, pytest.mark.toolchain]

SAMPLES = Path(__file__).resolve().parents[3] / "fixtures" / "toolchain"


@functools.cache
def _reachable(host: str) -> bool:
    try:
        socket.create_connection((host, 443), timeout=3).close()
    except OSError:  # expected: the machine has no route to the registry
        return False
    return True


def _require(tools: tuple[str, ...], registry: str) -> None:
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        pytest.skip(f"toolchain not installed: {', '.join(missing)}")
    if not _reachable(registry):
        pytest.skip(f"package registry unreachable: {registry}")


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


_KOTLIN = """
    package {package}

    import kotlin.test.Test
    import kotlin.test.assertTrue

    class {name} {{
        @Test fun {a}() {{ assertTrue(true) }}
        @Test fun {a}{b}() {{ assertTrue(false) }}
    }}
"""
_KOTLIN_TESTS = {
    "src/test/kotlin/shop/OrdersTest.kt": _KOTLIN.format(
        package="shop", name="OrdersTest", a="place", b="Refund"
    ),
    "src/test/kotlin/shop/deep/StockTest.kt": _KOTLIN.format(
        package="shop.deep", name="StockTest", a="count", b="Low"
    ),
}
_KOTLIN_SIZES = [
    ("src/test/kotlin/shop/OrdersTest.kt::place", (1, 0)),
    ("src/test/kotlin/shop/OrdersTest.kt", (1, 1)),
    ("src/test/kotlin/shop", (2, 2)),
    (".", (2, 2)),
]
_GRADLE = """
    plugins { kotlin("jvm") version "2.0.21" }
    repositories { mavenCentral() }
    dependencies { testImplementation(kotlin("test-junit")) }
"""


def _kotlin(root: Path, target: str):
    from specweaver.sandbox.language.core.kotlin.runner import KotlinRunner

    return KotlinRunner(cwd=root, executor=SubprocessExecutor(cwd=root)).run_tests(
        target=target, timeout=1800
    )


class TestKotlinMaven:
    @pytest.fixture(scope="class")
    def root(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        _require(("mvn", "java"), "repo.maven.apache.org")
        root = tmp_path_factory.mktemp("sizes") / "kt"
        shutil.copytree(SAMPLES / "kotlin", root)
        return _write(root, _KOTLIN_TESTS)

    @pytest.mark.parametrize(("target", "counts"), _KOTLIN_SIZES)
    def test_each_size_runs_exactly_its_tests(
        self, root: Path, target: str, counts: tuple[int, int]
    ) -> None:
        assert _counts(_kotlin(root, target)) == counts

    def test_a_target_naming_no_test_fails_naming_it(self, root: Path) -> None:
        target = "src/test/kotlin/shop/OrdersTest.kt::gone"

        assert _names_the_target(_kotlin(root, target), target)


class TestKotlinGradle:
    @pytest.fixture(scope="class")
    def root(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        _require(("gradle", "java"), "plugins.gradle.org")
        files = {"build.gradle.kts": _GRADLE, "settings.gradle.kts": 'rootProject.name = "kt"\n'}
        return _write(tmp_path_factory.mktemp("sizes") / "gradle", {**files, **_KOTLIN_TESTS})

    @pytest.mark.parametrize(("target", "counts"), _KOTLIN_SIZES)
    def test_each_size_runs_exactly_its_tests(
        self, root: Path, target: str, counts: tuple[int, int]
    ) -> None:
        assert _counts(_kotlin(root, target)) == counts

    def test_a_target_naming_no_test_fails_naming_it(self, root: Path) -> None:
        target = "src/test/kotlin/shop/OrdersTest.kt::gone"

        assert _names_the_target(_kotlin(root, target), target)


_VITEST = """
    import {{ describe, expect, it }} from "vitest";

    describe("{group}", () => {{
      it("{a}", () => {{ expect(true).toBe(true); }});
      it("{a} {b}", () => {{ expect(true).toBe(false); }});
      it("re{a}", () => {{ expect(true).toBe(false); }});
    }});
"""


class TestVitest:
    @pytest.fixture(scope="class")
    def root(self, tmp_path_factory: pytest.TempPathFactory) -> Path:
        _require(("npm", "node"), "registry.npmjs.org")
        root = tmp_path_factory.mktemp("sizes") / "ts"
        shutil.copytree(SAMPLES / "typescript", root)
        _write(
            root,
            {
                "tests/shop/orders.test.ts": _VITEST.format(group="orders", a="place", b="refund"),
                "tests/shop/deep/stock.test.ts": _VITEST.format(group="stock", a="count", b="low"),
            },
        )
        installed = subprocess.run(
            ["npm", "install", "--no-audit", "--no-fund"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=1800,
        )
        assert installed.returncode == 0, installed.stdout[-2000:] + installed.stderr[-2000:]
        return root

    def _run(self, root: Path, target: str):
        from specweaver.sandbox.language.core.typescript.runner import TypeScriptRunner

        return TypeScriptRunner(cwd=root, executor=SubprocessExecutor(cwd=root)).run_tests(
            target=target, timeout=600
        )

    @pytest.mark.parametrize(
        ("target", "counts"),
        [
            ("tests/shop/orders.test.ts::place", (1, 0)),
            ("tests/shop/orders.test.ts", (1, 2)),
            ("tests/shop", (2, 4)),
            ("tests/shop/deep", (1, 2)),
            (".", (2, 4)),
        ],
    )
    def test_each_size_runs_exactly_its_tests(
        self, root: Path, target: str, counts: tuple[int, int]
    ) -> None:
        assert _counts(self._run(root, target)) == counts

    def test_a_target_naming_no_test_fails_naming_it(self, root: Path) -> None:
        target = "tests/shop/orders.test.ts::gone"

        assert _names_the_target(self._run(root, target), target)
