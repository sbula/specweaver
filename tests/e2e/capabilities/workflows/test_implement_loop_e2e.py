# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw implement`'s autonomous loop, observed looping. `TECH-017` SF-04.

`INT-US-03` promises *"generates code + tests, runs the tests, runs C01-C08, and auto-fixes lint
**in one autonomous loop**"*. Until this file, three tests looked like they covered it and none ran
the generator:

* `test_implement_loop_worktree_isolation_e2e.py` replaces generation with a **bash script** — it
  proves isolation, not the loop;
* `test_scenario_verification_e2e.py` patches **`GenerateCodeHandler.execute`** itself;
* `test_implement_pipeline.py` reads the **declared shape** — five steps, order, a loop-back gate.

So the loop had never been observed to loop, `validate_code` had never been observed to run, and the
`D-INTL-01` → `D-VAL-01`/`D-VAL-05` pipe had never carried anything. `INT-US-03` C1/C3/C4/C6 and
`INT-US-24` C5 were all `unproven` for want of this file.

**Only the LLM is doubled** (`tests/scripted_llm.py`); the real `GenerateCodeHandler`, real `ruff`
and real `pytest` run. The double is **content-aware** rather than a positional payload queue: the
loop's call sequence is exactly what is under test, so a test that hard-codes it would encode an
assumption about the thing it is meant to measure.

Proves: INT-US-03 FR-1.

FR-1 only — *"SHALL append a `run_tests` step executing the generated tests"* is what these tests
drive. `FR-2` (the `lint_fix` step) was in the first draft of this tag and removed: `lint_fix` runs
here, but nothing below asserts on it, and citing a requirement a test merely passes through is the
loose-credit habit `TECH-017` spent three sub-features removing.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from tests.scripted_llm import settings_mock

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

SPEC = "greeter_spec.md"
SPEC_BODY = """# Greeter

## 1. Purpose
Greet a person by name.

## 2. Requirements
| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Greet | System | `greet(name)` is called | Returns `"Hello <name>"` |
"""

#: First generation is WRONG in a way only the tests can catch — it lints clean and imports fine,
#: so the failure has to come from `run_tests`, which is the loop-back trigger under test.
_BUGGY = 'def greet(name: str) -> str:\n    return f"Hi {name}"\n'
_FIXED = 'def greet(name: str) -> str:\n    return f"Hello {name}"\n'
_UNCOLLECTABLE_TESTS = (
    "from greeter import greet\n\n\n"
    "def test_greet() -> None:\n"
    '    assert greet("Ada") == "Hello Ada"\n'
)
_TESTS = (
    "import sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))\n"
    "from greeter import greet\n\n\n"
    "def test_greet_uses_the_specified_salutation() -> None:\n"
    '    assert greet("Ada") == "Hello Ada"\n'
)


class _LoopAwareLLM:
    """Returns code or tests depending on what the prompt asks for, and fixes on the second pass.

    Positional payload queues cannot express this: the number of calls the loop makes is precisely
    the quantity under test, so scripting it by index would bake in the answer.
    """

    def __init__(self, *, collectable: bool) -> None:
        self.code_calls = 0
        self.test_calls = 0
        self._collectable = collectable

    def _reply(self, messages: Any) -> str:
        text = " ".join(str(m) for m in (messages or []))
        if re.search(r"\btest", text, re.I) and "pytest" in text.lower():
            self.test_calls += 1
            return _TESTS if self._collectable else _UNCOLLECTABLE_TESTS
        self.code_calls += 1
        return _FIXED if self.code_calls > 1 else _BUGGY

    async def generate(self, messages: Any, config: Any = None, *a: Any, **kw: Any) -> LLMResponse:
        return LLMResponse(text=self._reply(messages), model="scripted-1")

    async def generate_with_tools(
        self, messages: Any, config: Any, dispatcher: Any, **kw: Any
    ) -> LLMResponse:
        return await self.generate(messages, config)


@pytest.fixture(autouse=True)
def _data_dir(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / ".specweaver-test"
    d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(d))
    return d


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    project_dir = tmp_path / "greeterproj"
    project_dir.mkdir()
    result = runner.invoke(app, ["init", "greeterproj", "--path", str(project_dir)])
    assert result.exit_code == 0, result.output
    specs = project_dir / "specs"
    specs.mkdir(exist_ok=True)
    (specs / SPEC).write_text(SPEC_BODY, encoding="utf-8")
    return project_dir


def _scripted(llm: _LoopAwareLLM) -> Iterator[None]:
    return patch.multiple(
        "specweaver.infrastructure.llm.factory",
        create_llm_adapter=MagicMock(return_value=(settings_mock(), llm, MagicMock())),
    )


def _no_router():
    return patch("specweaver.infrastructure.llm.router.ModelRouter.get_for_task", return_value=None)


def _run_implement(project: Path):
    return runner.invoke(
        app, ["implement", str(project / "specs" / SPEC), "--project", str(project)]
    )


def test_the_loop_regenerates_when_qa_does_not_pass(project: Path) -> None:
    """[Happy] `INT-US-03` C4 — the loop-back LOOPS. Real generator, real ruff, real pytest.

    **Probed, per the plan's Done-when:** removing `loop_target="generate_code"` from the
    `run_tests` gate fails this test. A green run alone would prove only that the pipeline is
    declared, which `test_implement_pipeline.py` already covers.
    """
    llm = _LoopAwareLLM(collectable=False)
    with _scripted(llm), _no_router():
        result = _run_implement(project)

    assert llm.code_calls >= 2, (
        f"generate_code ran {llm.code_calls}x — the loop-back never looped: {result.output[-600:]}"
    )
    assert (project / "src" / "greeter.py").is_file(), "the generator never wrote code"


def test_the_generated_code_reaches_the_code_rules(project: Path) -> None:
    """[Happy] `INT-US-03` C3/C6 — `validate_code` runs the C-series over generated code.

    The pipe the contract names: `D-INTL-01` writes the file, `D-VAL-05` grades it. Before this,
    `validate_code` was declared in the pipeline and had never been observed running.
    """
    llm = _LoopAwareLLM(collectable=True)
    with _scripted(llm), _no_router():
        result = _run_implement(project)

    rules = re.search(r"code validation: (\d+)/(\d+) rules", result.output)
    assert rules, f"validate_code never reported: {result.output[-600:]}"
    assert int(rules.group(2)) > 0, "the C-series ran zero rules over the generated code"
    assert (project / "src" / "greeter.py").read_text(encoding="utf-8") == _BUGGY


def test_zero_collected_is_reported_as_a_passing_qa_step(project: Path) -> None:
    """[Finding, pinned] `run_tests` reports SUCCESS when pytest collected nothing.

    Found by SF-04 CB-2 while trying to drive the loop red-then-green. With a test file pytest
    cannot collect, the step still renders `tests: 0 passed, 0 failed` as a **tick** and the run
    completes. Nothing ran, and the gate agreed.

    `INT-US-24`'s scenario pipeline has an explicit *zero-collected fails loud* guard (its E6). The
    implement loop has none, so a generated test file that fails to import reads as a clean QA pass.

    This test **pins the current behaviour** rather than asserting it is correct — changing it is a
    product decision, and pinning it means the change cannot happen silently.
    """
    llm = _LoopAwareLLM(collectable=True)
    with _scripted(llm), _no_router():
        result = _run_implement(project)

    assert "0 passed, 0 failed" in result.output, result.output[-600:]
    assert "Implementation complete" in result.output, (
        "if this now fails, zero-collected has started failing loud — a fix, not a regression; "
        "update INT-US-03's matrix entry rather than restoring this assertion"
    )
