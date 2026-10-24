# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`validate_code` on a Rust crate and a Kotlin-on-Maven project: C02 finds the file's own tests
and C03 runs them with the real build tool.

Proves: TECH-078 FR-3

The seam is validation → the language's test convention → the QA runner. Rust runs in the default
suite and skips without cargo; Kotlin on Maven downloads its packages, so it is in the `toolchain`
tier (nightly, `scripts/toolchain.py`).

| Bucket | Case |
|---|---|
| Happy | a passing test file: C02 and C03 pass |
| Boundary | the code file's name differs from the spec's: the code file's tests are judged |
| Degradation | a failing test fails C03; no test file fails C02, naming the file it expects |
| Hostile | a test of the same name in a `tests/` subfolder is not a Rust test target |
"""

from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateCodeHandler

pytestmark = pytest.mark.integration

SAMPLES = Path(__file__).resolve().parents[3] / "fixtures" / "toolchain"


def _write(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    (root / "feature_spec.md").write_text("# Feature\n", encoding="utf-8")
    return root


async def _rules(root: Path, code: str) -> dict[str, tuple[str, str]]:
    step = PipelineStep(
        name="validate_code",
        action=StepAction.VALIDATE,
        target=StepTarget.CODE,
        params={"target": code},
    )
    context = RunContext(project_path=root, spec_path=root / "feature_spec.md")
    result = await ValidateCodeHandler().execute(step, context)
    return {r["rule_id"]: (r["status"], r["message"]) for r in result.output.get("results", [])}


_CARGO = '[package]\nname = "probe"\nversion = "0.1.0"\nedition = "2021"\n'
_ORDERS = "pub fn total(a: u32, b: u32) -> u32 { a + b }\n"
_RUST_TEST = "#[test]\nfn adds() {{ assert_eq!(probe::orders::total(1, 2), {want}); }}\n"


@pytest.mark.skipif(shutil.which("cargo") is None, reason="cargo not installed")
class TestRust:
    def _crate(self, root: Path, test: dict[str, str]) -> Path:
        files = {"Cargo.toml": _CARGO, "src/lib.rs": "pub mod orders;\n", "src/orders.rs": _ORDERS}
        return _write(root, files | test)

    async def test_a_passing_test_passes_c02_and_c03(self, tmp_path: Path) -> None:
        root = self._crate(tmp_path, {"tests/orders.rs": _RUST_TEST.format(want=3)})

        rules = await _rules(root, "src/orders.rs")

        assert rules["C02"][0] == "pass", rules
        assert rules["C03"][0] == "pass", rules

    async def test_a_failing_test_fails_c03(self, tmp_path: Path) -> None:
        root = self._crate(tmp_path, {"tests/orders.rs": _RUST_TEST.format(want=4)})

        rules = await _rules(root, "src/orders.rs")

        assert rules["C03"][0] == "fail", rules

    async def test_a_test_in_a_subfolder_is_not_a_target(self, tmp_path: Path) -> None:
        root = self._crate(tmp_path, {"tests/common/orders.rs": _RUST_TEST.format(want=3)})

        rules = await _rules(root, "src/orders.rs")

        assert rules["C02"] == ("fail", "No test file 'orders.rs' found"), rules


_KOTLIN_CODE = "package shop\n\nfun total(a: Int, b: Int): Int = a + b\n"
_KOTLIN_TEST = """
    package shop

    import kotlin.test.Test
    import kotlin.test.assertEquals

    class OrdersTest {{
        @Test fun adds() {{ assertEquals({want}, total(1, 2)) }}
    }}
"""


@pytest.mark.toolchain
@pytest.mark.skipif(
    shutil.which("mvn") is None or shutil.which("java") is None, reason="maven and a JDK required"
)
class TestKotlinMaven:
    def _project(self, root: Path, test: dict[str, str]) -> Path:
        shutil.copytree(SAMPLES / "kotlin", root)
        return _write(root, {"src/main/kotlin/shop/Orders.kt": _KOTLIN_CODE} | test)

    async def test_a_passing_test_passes_c02_and_c03(self, tmp_path: Path) -> None:
        root = self._project(
            tmp_path / "kt", {"src/test/kotlin/shop/OrdersTest.kt": _KOTLIN_TEST.format(want=3)}
        )

        rules = await _rules(root, "src/main/kotlin/shop/Orders.kt")

        assert rules["C02"][0] == "pass", rules
        assert rules["C03"][0] == "pass", rules

    async def test_no_test_file_fails_c02_naming_it(self, tmp_path: Path) -> None:
        root = self._project(tmp_path / "kt", {})

        rules = await _rules(root, "src/main/kotlin/shop/Orders.kt")

        assert rules["C02"] == ("fail", "No test file 'OrdersTest.kt' found"), rules
