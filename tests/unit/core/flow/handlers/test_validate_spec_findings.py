# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation findings must survive the handler boundary. `INT-US-04` SF-01 CB-1.

The rules compute a `Finding` per issue — `message`, `line`, `severity`, `suggestion`
(`assurance/validation/models.py:39-45`) — and both validate handlers threw all of it away,
keeping only `rule_id`/`status`/`message` per rule. Line numbers and suggestions were computed and
discarded at `validation.py:108` and `:245`, which is why `INT-US-04` FR-1 now says *without loss*.

Two call sites built **byte-identical** payloads, so the widening lives in one shared helper. That
is also the trap this file guards: wiring only `ValidateSpecHandler` and forgetting
`ValidateCodeHandler` passes every helper test, so `ValidateCodeHandler` is driven here too.

> [!NOTE]
> **The nesting looks wrong and is not.** `inject_feedback` stores a whole step output under a key
> it calls `"findings"`, so a rule's own list reads as
> `feedback[step]["findings"]["results"][0]["findings"]`. The inner key is the domain term
> (`Finding`, and FR-1's own wording); the outer one is `inject_feedback`'s misnomer and is not this
> boundary's to rename.

Proves: INT-US-04 FR-1.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.assurance.validation.models import Finding, RuleResult, Severity, Status
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.core.flow.handlers.validation import ValidateCodeHandler, ValidateSpecHandler

if TYPE_CHECKING:
    from pathlib import Path


def _rule(rule_id: str, *findings: Finding, status: Status = Status.FAIL) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        rule_name=f"{rule_id} rule",
        status=status,
        findings=list(findings),
        message=f"{rule_id} says so",
    )


def _spec_ctx(tmp_path: Path) -> RunContext:
    spec = tmp_path / "test_spec.md"
    spec.write_text("# Test Spec\n\n## 1. Purpose\n\nDoes one thing.\n", encoding="utf-8")
    return RunContext(project_path=tmp_path, spec_path=spec)


def _step() -> PipelineStep:
    return PipelineStep(name="val", action=StepAction.VALIDATE, target=StepTarget.SPEC)


async def _spec_output(tmp_path: Path, results: list[RuleResult]) -> dict[str, Any]:
    handler = ValidateSpecHandler()
    with patch.object(handler, "_run_validation", return_value=results):
        result = await handler.execute(_step(), _spec_ctx(tmp_path))
    return result.output


class TestValidateSpecHandlerFindings:
    """`ValidateSpecHandler` — every `Finding` field reaches `StepResult.output`."""

    @pytest.mark.asyncio
    async def test_every_finding_field_survives(self, tmp_path: Path) -> None:
        """[Happy] All four fields, both findings, in order."""
        rule = _rule(
            "S01",
            Finding(message="first", line=12, severity=Severity.ERROR, suggestion="split it"),
            Finding(message="second", line=99, severity=Severity.WARNING, suggestion="or this"),
        )
        output = await _spec_output(tmp_path, [rule])

        findings = output["results"][0]["findings"]
        assert [f["message"] for f in findings] == ["first", "second"]
        assert [f["line"] for f in findings] == [12, 99]
        assert [f["severity"] for f in findings] == ["error", "warning"]
        assert [f["suggestion"] for f in findings] == ["split it", "or this"]

    @pytest.mark.asyncio
    async def test_a_rule_with_no_findings_still_carries_the_key(self, tmp_path: Path) -> None:
        """[Boundary] Absent is not the same as empty — a consumer must not need `.get`."""
        output = await _spec_output(tmp_path, [_rule("S02", status=Status.PASS)])
        assert output["results"][0]["findings"] == []

    @pytest.mark.asyncio
    async def test_optional_fields_are_present_as_none(self, tmp_path: Path) -> None:
        """[Boundary] `line` and `suggestion` are optional on the model; the keys are not."""
        output = await _spec_output(tmp_path, [_rule("S03", Finding(message="bare"))])

        finding = output["results"][0]["findings"][0]
        assert finding["line"] is None
        assert finding["suggestion"] is None
        assert finding["severity"] == "error", "the model default must survive too"

    @pytest.mark.asyncio
    async def test_the_widened_payload_persists_as_the_store_would_write_it(
        self, tmp_path: Path
    ) -> None:
        """[Degradation] `Severity` is a `StrEnum`, and this payload gets persisted verbatim.

        `StateStore.save_run` serializes with `json.dumps(..., default=str)` (`store.py:175`), and
        `hydration.py:110-115` records what happens when the two sides disagree: an output carrying
        a non-JSON type raises on the LIVE path and hydrates fine on the RESUME path, so the same
        run behaves differently depending on whether it was resumed.

        **A first draft of this test asserted `"Severity." not in blob`, which can never fail.**
        Mutation testing caught it: swapping `f.severity.value` for `f.severity` SURVIVED, because
        `Severity` is a `StrEnum` and the two are indistinguishable to `json.dumps` and to `==`. The
        mutant is equivalent, not a coverage gap — but the assertion was decoration.

        What can actually fail is the premise. If `Severity` ever becomes a plain `Enum`,
        `default=str` starts writing `"Severity.ERROR"` into every persisted payload. So the pin is
        on the `StrEnum`, and it is a real assertion.
        """
        assert issubclass(Severity, str), (
            "Severity stopped being a StrEnum — json.dumps(default=str) will now persist "
            "'Severity.ERROR' instead of 'error' in every step record"
        )

        output = await _spec_output(
            tmp_path, [_rule("S04", Finding(message="x", severity=Severity.INFO))]
        )

        blob = json.dumps(output, default=str)
        assert json.loads(blob)["results"][0]["findings"][0]["severity"] == "info"

    @pytest.mark.asyncio
    async def test_a_hostile_message_survives_unmangled(self, tmp_path: Path) -> None:
        """[Hostile] A finding's message quotes spec content, which is user input."""
        nasty = 'he said "no"\n\tand\\or {"json": true}\x00' + ("A" * 10_000)
        output = await _spec_output(tmp_path, [_rule("S05", Finding(message=nasty, line=0))])

        finding = output["results"][0]["findings"][0]
        assert finding["message"] == nasty
        assert (
            json.loads(json.dumps(output, default=str))["results"][0]["findings"][0]["message"]
            == nasty
        )
        assert finding["line"] == 0, "line 0 is falsy and must not be coerced to None"

    @pytest.mark.asyncio
    async def test_many_rules_keep_their_order_and_count(self, tmp_path: Path) -> None:
        """[Boundary] U-1 — every other test passes a SINGLE rule.

        Finding order *within* one rule is asserted above; rule order across the list was not, so a
        comprehension that dropped or reordered rules passed everything. The payload is consumed by
        `rule_id` lookup today, but it is also what CB-2 persists row-per-rule, where order and
        count stop being cosmetic.
        """
        rules = [_rule(f"S{i:02d}", Finding(message=f"finding {i}", line=i)) for i in range(1, 8)]
        output = await _spec_output(tmp_path, rules)

        assert [r["rule_id"] for r in output["results"]] == [f"S{i:02d}" for i in range(1, 8)]
        assert [r["findings"][0]["line"] for r in output["results"]] == list(range(1, 8))
        assert len(output["results"]) == 7

    @pytest.mark.asyncio
    async def test_the_sibling_counts_are_untouched_by_the_widening(self, tmp_path: Path) -> None:
        """[Boundary] U-2 — `results` gained a key; `total`/`passed`/`failed` must not have moved.

        Existing tests assert the counts **or** the findings, never both in one payload, so a
        widening that disturbed the tallies would land green. `passed` counts everything that is
        not FAIL, so WARN and SKIP belong on that side — asserting with a mixed set is the only way
        that distinction can fail.
        """
        output = await _spec_output(
            tmp_path,
            [
                _rule("S01", Finding(message="bad"), status=Status.FAIL),
                _rule("S02", Finding(message="iffy"), status=Status.WARN),
                _rule("S03", status=Status.PASS),
                _rule("S04", status=Status.SKIP),
            ],
        )

        assert output["total"] == 4
        assert output["failed"] == 1
        assert output["passed"] == 3, "WARN and SKIP are not failures"
        assert len(output["results"]) == 4
        assert [len(r["findings"]) for r in output["results"]] == [1, 1, 0, 0]


class TestValidateCodeHandlerFindings:
    """`ValidateCodeHandler` — the second call site, which a helper-only test cannot catch."""

    @pytest.mark.asyncio
    async def test_the_code_handler_carries_findings_too(self, tmp_path: Path) -> None:
        """[Happy] `validation.py:245` is a separate payload builder from `:108`.

        Wiring one and forgetting the other leaves every test above green. Its findings never reach
        a regeneration prompt — `validate_code` is report-only behind a CONTINUE gate — so they
        exist purely for the persistence FR-2 adds next.
        """
        code = tmp_path / "src" / "greeter.py"
        code.parent.mkdir(parents=True)
        code.write_text("def greet():\n    pass\n", encoding="utf-8")
        ctx = _spec_ctx(tmp_path)
        step = PipelineStep(
            name="val",
            action=StepAction.VALIDATE,
            target=StepTarget.CODE,
            params={"target": "src/greeter.py"},
        )

        handler = ValidateCodeHandler()
        rule = _rule("C01", Finding(message="too complex", line=3, suggestion="extract"))
        with (
            patch.object(handler, "_run_validation", return_value=[rule]),
            patch(
                "specweaver.core.flow.handlers.validation._resolve_merged_settings",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            result = await handler.execute(step, ctx)

        finding = result.output["results"][0]["findings"][0]
        assert finding == {
            "message": "too complex",
            "line": 3,
            "severity": "error",
            "suggestion": "extract",
        }
