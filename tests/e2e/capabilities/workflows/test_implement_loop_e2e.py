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
    "import importlib.util\n"
    "from pathlib import Path\n\n"
    "_src = Path(__file__).resolve().parents[1] / 'src' / 'greeter.py'\n"
    "_spec = importlib.util.spec_from_file_location('greeter', _src)\n"
    "_mod = importlib.util.module_from_spec(_spec)\n"
    "_spec.loader.exec_module(_mod)\n\n\n"
    "def test_greet_uses_the_specified_salutation() -> None:\n"
    '    assert _mod.greet("Ada") == "Hello Ada"\n'
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


def test_the_real_generator_writes_code_and_tests(project: Path) -> None:
    """[Happy] `INT-US-03` C1/C6 — the REAL `GenerateCodeHandler` runs and its output lands.

    Modest, and it is the part that holds. The three prior tests of this pipeline each doubled the
    generator; here only the LLM is doubled, so `D-INTL-01` genuinely produces both files and the
    pipeline carries them onward.

    `INT-US-03` C4 (*"in one autonomous loop"*) is **not** asserted here and stays `unproven`: the
    loop cannot be driven red, because generated tests are never collected — see
    `test_generated_tests_are_never_collected`. An earlier draft did assert the loop and killed a
    `loop_target` mutant, but only in a configuration where the run failed for an unrelated reason.
    Keeping that would have been a proof of the wrong thing.
    """
    llm = _LoopAwareLLM(collectable=True)
    with _scripted(llm), _no_router():
        result = _run_implement(project)

    assert llm.code_calls >= 1 and llm.test_calls >= 1, result.output[-600:]
    assert (project / "src" / "greeter.py").read_text(encoding="utf-8") == _BUGGY, (
        "the file on disk is not what the generator was given"
    )
    assert (project / "tests" / "test_greeter.py").is_file()


def test_generated_tests_are_never_collected(project: Path) -> None:
    """[Finding, pinned] `run_tests` collects ZERO tests from the generated file, whatever it holds.

    Established by SF-04 CB-2 across three payload shapes — a plain import, a `sys.path` insert, and
    an `importlib` load by absolute path. All three collect nothing, so the content is not the
    variable. Whatever `run_tests` points pytest at, it is not the file `generate_tests` just wrote.

    **This is the root cause behind two other symptoms**, not a separate bug:

    * it is why the loop could never be observed going red-then-GREEN — the gate cannot turn green
      on tests that never run, so `INT-US-03` C4 is provable only as *the loop iterates*;
    * it is why `tests: 0 passed, 0 failed` used to render as a tick — the false green now fixed.

    Pinned rather than fixed: repairing collection means changing what the QA step targets, which is
    a product decision with a blast radius beyond this audit. If this test starts failing, the
    collection was fixed — delete it and re-verdict `INT-US-03` C3, which stays `unproven` until
    then because `validate_code` grades `0/0` rules on a run that never went green.
    """
    llm = _LoopAwareLLM(collectable=True)
    with _scripted(llm), _no_router():
        result = _run_implement(project)

    assert "0 passed, 0 failed" in result.output, (
        f"generated tests are being collected now — see this test's docstring: {result.output[-600:]}"
    )
    assert (project / "tests" / "test_greeter.py").is_file(), "the test file was written"


def test_zero_collected_is_reported_as_a_passing_qa_step(project: Path) -> None:
    """[Finding, pinned] `run_tests` reports SUCCESS when pytest collected nothing.

    **The fix was attempted and reverted, deliberately.** `INT-US-24` FR-3 already fails loud on
    `kind="scenario"`; widening that guard to any step naming a specific `.py` target is the right
    rule and it lands correctly here — but with collection broken (see
    `test_generated_tests_are_never_collected`) it makes **every** `sw implement` run fail, taking
    9 tests with it including `INT-US-24`'s own zero-collected guards.

    Converting a false green into a universal red is not a fix. The guard cannot land until
    collection works, so the ordering is: fix what `run_tests` points pytest at, **then** widen the
    guard. Recorded here so the sequence is not rediscovered.

    This pins the current behaviour rather than endorsing it. If it starts failing, the guard landed
    — delete this test and re-verdict `INT-US-03` C3.
    """
    llm = _LoopAwareLLM(collectable=True)
    with _scripted(llm), _no_router():
        result = _run_implement(project)

    assert "0 passed, 0 failed" in result.output, result.output[-600:]
    assert "Implementation complete" in result.output, (
        "zero-collected now fails loud — that is the fix, not a regression; delete this test"
    )
