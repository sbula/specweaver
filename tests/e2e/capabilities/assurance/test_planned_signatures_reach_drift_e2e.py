# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A plan the planner produced is a plan the drift engine can judge code against.

Proves: INT-US-10 P-5

`B-VAL-01` compares a file's AST against `expected_signatures` carried by a `PlanArtifact`. Every test
of it — and every test of the planner — uses a plan written by hand for the occasion. So the two sides
have never been shown to agree: the planner emits a `PlanArtifact`, the drift engine consumes one, and
nothing checks that what the first produces is what the second can read.

That is a schema contract between two capabilities with no test across it. If the planner renamed a
field, or nested `expected_signatures` differently, both suites stay green and drift detection quietly
finds nothing on real plans.

The LLM is faked, and deliberately so: what is under test is the planner's **parsing and validation**
of a model reply into a `PlanArtifact`, then that artifact's use by the detector. A live model would
add nondeterminism without adding coverage of the seam.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.assurance.validation.drift_detector import detect_drift
from specweaver.infrastructure.llm.prompt.builder import PromptBuilder
from specweaver.workflows.planning.planner import Planner

if TYPE_CHECKING:
    from pathlib import Path

_SPEC = "# Ledger\n\n## 1. Purpose\n\nPost amounts.\n"

#: What the model is asked to return. `expected_signatures` maps a file path to the methods the plan
#: says that file will contain — the field the drift engine reads.
_PLAN_REPLY: dict[str, Any] = {
    "spec_path": "specs/ledger.md",
    "spec_name": "Ledger",
    "spec_hash": "overwritten-by-the-planner",
    "timestamp": "2026-01-01T00:00:00Z",
    "file_layout": [{"path": "src/ledger.py", "action": "create", "purpose": "Posting math"}],
    "architecture": {
        "module_layout": "flat",
        "dependency_direction": "downward",
        "archetype": "pure-logic",
    },
    "reasoning": "One module, one entry point.",
    "confidence": 90,
    "tasks": [
        {
            "sequence_number": 1,
            "name": "Implement posting",
            "description": "Add the posting entry point",
            "files": ["src/ledger.py"],
            "dependencies": [],
            "expected_signatures": {
                "src/ledger.py": [
                    {"name": "post", "parameters": ["amount", "currency"], "return_type": "int"}
                ]
            },
        }
    ],
}


class _Reply:
    def __init__(self, text: str) -> None:
        self.text = text
        self.usage = None


class _FakeLLM:
    """Returns one canned reply. The planner still parses and validates it for real."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def generate(self, messages: Any, config: Any = None) -> _Reply:
        return _Reply(json.dumps(self._payload))


async def _plan() -> Any:
    """A `PlanArtifact` the real planner produced — never one written by this test."""
    return await Planner(_FakeLLM(_PLAN_REPLY)).generate_plan(
        spec_content=_SPEC,
        spec_path="specs/ledger.md",
        spec_name="Ledger",
        base_prompt=PromptBuilder(),
    )


@pytest.mark.asyncio
async def test_a_generated_plan_carries_signatures_the_detector_can_read(tmp_path: Path) -> None:
    """Planner → PlanArtifact → drift engine, with a real mismatch caught at the far end."""
    plan = await _plan()

    # The seam itself: the planner's own output has the field, in the shape the detector expects.
    signatures = plan.tasks[0].expected_signatures
    assert "src/ledger.py" in signatures, (
        f"the planner produced a plan the drift engine cannot key into: {signatures}"
    )

    # Code that drifts from what the plan said: `post` lost a parameter and grew a sibling.
    source = tmp_path / "ledger.py"
    source.write_text("def post(amount):\n    return amount\n\n\ndef audit():\n    pass\n", "utf-8")

    import tree_sitter
    import tree_sitter_python

    parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))
    tree = parser.parse(source.read_text(encoding="utf-8").encode("utf-8"))

    report = detect_drift(file_ast=tree, plan=plan, file_path="src/ledger.py")

    assert report.is_drifted, (
        "the detector read a planner-generated plan and found no drift in code that plainly "
        f"contradicts it: {report.findings}"
    )
    described = " ".join(f.description for f in report.findings)
    assert "post" in described, f"the drifted method was not named: {described}"


@pytest.mark.asyncio
async def test_code_matching_the_generated_plan_is_clean(tmp_path: Path) -> None:
    """The control. Without it, 'drift was found' could mean the detector flags everything.

    Same plan, same detector, code that matches what the planner asked for.
    """
    plan = await _plan()

    source = tmp_path / "ledger.py"
    source.write_text("def post(amount, currency):\n    return amount\n", encoding="utf-8")

    import tree_sitter
    import tree_sitter_python

    parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))
    tree = parser.parse(source.read_text(encoding="utf-8").encode("utf-8"))

    report = detect_drift(file_ast=tree, plan=plan, file_path="src/ledger.py")

    assert not report.is_drifted, (
        f"code implementing exactly what the plan specified was reported as drift: {report.findings}"
    )
