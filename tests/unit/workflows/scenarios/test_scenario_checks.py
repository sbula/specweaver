# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The generator refuses a scenario set that does not match the spec and the contract.

Proves: B-FLOW-01 FR-3

| Bucket | Case |
|---|---|
| Happy | a set naming spec ids and contract methods is kept on the first answer |
| Boundary | a lettered id counts; a constructor that takes `**kwargs` takes any key |
| Degradation | a refused answer goes back to the model with the reason; three refusals fail |
| Hostile | no scenario; an unknown id; an unknown method; an uncalled method; constructor values on a function; an unknown constructor key |
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from specweaver.workflows.scenarios.scenario_generator import ScenarioGenerator

_METHODS = ["Greeter.greet", "farewell"]
_CONSTRUCTORS: dict[str, list[str] | None] = {"Greeter": ["greeting"]}


def _scenario(method: str, req: str = "FR-91", **extra: Any) -> dict[str, Any]:
    return {
        "name": f"{method}_{req}",
        "description": "d",
        "function_under_test": method,
        "req_id": req,
        "inputs": {"name": "Ann"},
        **extra,
    }


def _answer(*scenarios: dict[str, Any]) -> str:
    return json.dumps({"spec_path": "s", "contract_path": "c", "scenarios": list(scenarios)})


_GOOD = _answer(
    _scenario("Greeter.greet", constructor_inputs={"greeting": "Hi"}),
    _scenario("farewell", "FR-92"),
)


async def _generate(*answers: str, constructors: Any = _CONSTRUCTORS, req_ids: Any = None) -> Any:
    llm = AsyncMock()
    llm.generate.side_effect = list(answers)
    generator = ScenarioGenerator(llm, max_retries=3)
    result = await generator.generate_scenarios(
        "spec",
        "contract",
        req_ids or ["FR-91", "FR-92"],
        methods=_METHODS,
        constructors=constructors,
    )
    return result, [call.args[0] for call in llm.generate.call_args_list]


@pytest.mark.asyncio
async def test_a_matching_set_is_kept_first_time() -> None:
    result, prompts = await _generate(_GOOD)

    assert [s.function_under_test for s in result.scenarios] == _METHODS
    assert len(prompts) == 1
    assert "Greeter.greet" in prompts[0] and "farewell" in prompts[0]


@pytest.mark.asyncio
async def test_a_lettered_id_and_open_constructor_are_accepted() -> None:
    answer = _answer(
        _scenario("Greeter.greet", "FR-95a", constructor_inputs={"anything": 1}),
        _scenario("farewell", "FR-95a"),
    )

    result, _ = await _generate(answer, constructors={"Greeter": None}, req_ids=["FR-95a"])

    assert len(result.scenarios) == 2


_UNKNOWN_ID = _answer(_scenario("Greeter.greet", "FR-99"), _scenario("farewell"))
_REFUSED = [
    (_answer(), "no scenario"),
    (_UNKNOWN_ID, "FR-99"),
    (
        _answer(_scenario("Greeter.greet"), _scenario("farewell"), _scenario("delete_all")),
        "delete_all",
    ),
    (_answer(_scenario("Greeter.greet")), "farewell"),
    (
        _answer(_scenario("Greeter.greet"), _scenario("farewell", constructor_inputs={"x": 1})),
        "farewell",
    ),
    (
        _answer(
            _scenario("Greeter.greet", constructor_inputs={"tone": "loud"}), _scenario("farewell")
        ),
        "tone",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("answer", "reason"),
    _REFUSED,
    ids=[
        "no-scenario",
        "unknown-id",
        "unknown-method",
        "uncalled-method",
        "ctor-on-function",
        "unknown-ctor-key",
    ],
)
async def test_a_mismatched_set_is_refused(answer: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        await _generate(answer, answer, answer)


@pytest.mark.asyncio
async def test_a_refusal_goes_back_to_the_model() -> None:
    result, prompts = await _generate(_UNKNOWN_ID, _GOOD)

    assert {s.req_id for s in result.scenarios} == {"FR-91", "FR-92"}
    assert len(prompts) == 2
    assert "FR-99" in prompts[1] and "FR-99" not in prompts[0]
