# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The arbiter sends one report, to the side at fault; the scenario side's report holds no code.

Proves: B-FLOW-01 FR-8

The real arbiter with a scripted verdict hands its report to the real scenario step, whose
prompt is recorded.

| Bucket | Case |
|---|---|
| Happy | a scenario error: the scenario side gets the words, the coder side gets nothing |
| Boundary | a sentence that ends in `:` stays; a report that is all code becomes the standard sentence |
| Degradation | an empty report becomes the standard sentence |
| Hostile | code blocks, code lines, `self.` calls and source paths never reach the scenario prompt or the run record |
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.arbiter import ArbitrateVerdictHandler, scenario_safe
from specweaver.core.flow.handlers.reviewed_spec import record_review
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext, RunHandle
from specweaver.core.flow.handlers.scenario import GenerateScenarioHandler
from tests.fixtures.db_utils import register_test_project
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_SPEC = '''# Greet

| FR-91 | greet |

## 2. Contract

```python
def greet(name: str) -> str:
    """Hello."""
```
'''

_LEAKY = (
    "The expected greeting for FR-91 is 'Hello Bob', as the spec says:\n"
    "```python\ndef greet(name):\n    return f'Hi {name}'\n```\n"
    "The code in src/greet.py returns Hi.\n"
    "    return name.upper()\n"
    "It calls self.prefix() first.\n"
    "if not name:\n"
    "See /workspace/src/greet.py line 3."
)
_CODE = ("def ", "return", "src/", "/workspace", "self.", "if not name", "```")
_STANDARD = "The expected behaviour for FR-91 was judged wrong. Derive it again from the spec."


def _model(*answers: str) -> AsyncMock:
    llm = AsyncMock(spec=["generate"])
    llm.generate = AsyncMock(side_effect=list(answers))
    return llm


@pytest.fixture
def context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> RunContext:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "greeter"
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "greet_spec.md").write_text(_SPEC, encoding="utf-8")
    register_test_project(db, "greeter", str(root))
    context = RunContext(project_path=root, spec_path=root / "specs" / "greet_spec.md", db=db)
    record_review(context)  # the spec was reviewed before the dual run
    context.run = RunHandle(run_id="r1", step_name="arbitrate_verdict")
    context.feedback = {
        "scenario_test_failures": {
            "total": 1,
            "passed": 0,
            "failed": 1,
            "errors": 0,
            "failures": [{"nodeid": "t::x", "message": "AssertionError", "stacktrace": ""}],
        }
    }
    return context


_ANSWER = json.dumps(
    {
        "spec_path": "s",
        "contract_path": "c",
        "scenarios": [
            {
                "name": "a",
                "description": "d",
                "function_under_test": "greet",
                "req_id": "FR-91",
                "inputs": {"name": "Bob"},
                "expected_output": "Hello Bob",
            }
        ],
    }
)


async def _arbitrate(context: RunContext, report: str) -> Any:
    verdict = {
        "verdict": "scenario_error",
        "spec_clause": "FR-91",
        "coding_feedback": "",
        "scenario_feedback": report,
    }
    context.model = ModelAccess(llm_router=FixedRouter(_model(json.dumps(verdict))))
    step = PipelineStep(
        name="arbitrate_verdict", action=StepAction.ARBITRATE, target=StepTarget.VERDICT
    )
    return await ArbitrateVerdictHandler().execute(step, context)


async def _regenerate(context: RunContext) -> str:
    llm = _model(_ANSWER)
    context.model = ModelAccess(llm_router=FixedRouter(llm), config=None)
    step = PipelineStep(
        name="generate_scenarios", action=StepAction.GENERATE, target=StepTarget.SCENARIO
    )
    result = await GenerateScenarioHandler().execute(step, context)
    assert result.status == StepStatus.PASSED
    return str(llm.generate.call_args.args[0])


@pytest.mark.asyncio
async def test_the_scenario_side_gets_words_and_no_code(context: RunContext) -> None:
    result = await _arbitrate(context, _LEAKY)

    assert "generate_code" not in context.feedback
    prompt = await _regenerate(context)
    assert "The expected greeting for FR-91 is 'Hello Bob', as the spec says:" in prompt
    assert "It calls" not in prompt
    for code in _CODE:
        assert code not in (result.error_message or ""), code
    feedback = prompt.split("Prior Verdict Feedback", 1)[1].split("Respond with", 1)[0]
    for code in _CODE:
        assert code not in feedback, code


@pytest.mark.asyncio
async def test_a_report_of_code_only_becomes_the_standard_sentence(context: RunContext) -> None:
    await _arbitrate(context, "```python\nreturn 'Hi'\n```")

    assert _STANDARD in await _regenerate(context)


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        ("The greeting must be:", "The greeting must be:"),
        ("", _STANDARD),
        ("class Greeter {\n}", _STANDARD),
        ("import os\nfrom x import y", _STANDARD),
        ("for name in names:\n  while True:", _STANDARD),
        ("Read tests/test_greet.py and Greeter.java", _STANDARD),
    ],
    ids=["colon-sentence", "empty", "braces", "imports", "loops", "paths"],
)
def test_the_filter_keeps_words_only(text: str, kept: str) -> None:
    assert scenario_safe(text, "FR-91") == kept
