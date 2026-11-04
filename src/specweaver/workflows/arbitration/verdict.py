# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Who is at fault when the scenario tests fail: the verdict, the model call, and what each side
may read of it.

The coder must never learn the scenario tests exist, and the scenario side must never see code, so
each side's feedback passes a text guard here.
"""

from __future__ import annotations

import enum
import logging
import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from specweaver.commons import json
from specweaver.infrastructure.llm.models import Message, Role

if TYPE_CHECKING:
    from specweaver.workspace.ast.parsers.interfaces import StackTraceFilterInterface

logger = logging.getLogger(__name__)


class ArbitrateVerdict(enum.StrEnum):
    CODE_BUG = "code_bug"
    SCENARIO_ERROR = "scenario_error"
    SPEC_AMBIGUITY = "spec_ambiguity"
    ERROR = "error"


class ArbitrateResult(BaseModel):
    verdict: ArbitrateVerdict
    reasoning: str = ""
    spec_clause: str = ""
    coding_feedback: str = ""
    scenario_feedback: str = ""
    #: The readings of an unclear clause, for the person who must settle it.
    interpretations: list[str] = []
    raw_response: str = ""


class UnreadableVerdictError(ValueError):
    """The model's reply holds no JSON verdict."""

    def __init__(self, raw: str) -> None:
        super().__init__(f"Failed to parse LLM verdict: {raw}")
        self.raw = raw


SCENARIO_VOCABULARY: frozenset[str] = frozenset(
    {
        "scenario",
        "scenarios/",
        "test_",
        "_scenarios",
        "yaml",
        "parametrize",
        "convert",
        "ScenarioSet",
        "scenario_validation",
        "generate_scenarios",
        "scenario_agent",
        "scenario pipeline",
    }
)


def guard_coding_feedback(text: str) -> str:
    """Guard strictly against scenario term leakage into the coding agent feedback."""
    if not text:
        return text

    lower_text = text.lower()
    for banned in SCENARIO_VOCABULARY:
        if banned.lower() in lower_text:
            logger.warning(
                "ArbitrateVerdictHandler: Vocabulary leak caught! Banned term '%s' found in string: %s",
                banned,
                text,
            )
            return (
                "The implementation violates the exact behavioral requirement stipulated in the spec. "
                "The provided code does not behave according to the behavioral constraints on the given inputs. "
                "Please review the method definition logic against the specification."
            )
    return text


_FENCE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)
_CODE_LINE = re.compile(
    r"^\s*(?:def |class |return\b|import |from \S+ import |@\w)"
    r"|^\s*(?:if|elif|else|for|while|with|try|except|finally)\b.*:\s*$"
    r"|[{}]\s*$|\bself\."
)
_SOURCE_PATH = re.compile(r"/workspace|\b(?:src|tests?)/|\b\w+\.(?:py|java|kt|ts|rs)\b")


def scenario_safe(text: str, clause: str) -> str:
    """The report for the scenario side, words only: no code block, code line or source path."""
    kept = [
        line.strip()
        for line in _FENCE.sub("", text or "").splitlines()
        if line.strip() and not _CODE_LINE.search(line) and not _SOURCE_PATH.search(line)
    ]
    return " ".join(kept) or (
        f"The expected behaviour for {clause or 'the failing requirement'} was judged wrong. "
        "Derive it again from the spec."
    )


ARBITRATE_INSTRUCTIONS = """
You are a strict test arbitration agent. Scenario tests have failed for the component described
in the spec below. Your job is to determine WHO is at fault.

## Verdict types
- code_bug: The implementation code does not satisfy the spec's behavioral requirements.
- scenario_error: The scenario test setup is incorrect or tests the wrong behavior.
- spec_ambiguity: The spec clause is ambiguous and both interpretations are valid.

## Output format (JSON only — no other text)
{
  "verdict": "<code_bug|scenario_error|spec_ambiguity>",
  "reasoning": "<internal reasoning>",
  "spec_clause": "<e.g. FR-2 or missing>",
  "coding_feedback": "<spec-flavored feedback for the coding agent. MUST NOT contain the words: scenario, test, yaml, parametrize, convert, or any path. MUST read like a spec compliance behavioral review.>",
  "scenario_feedback": "<behavioral delta report for scenario agent. MUST NOT contain source code or implementation details.>",
  "interpretations": ["<for spec_ambiguity only: reading A of the clause>", "<reading B>"]
}
"""


#: A frame line: pytest's `path:line:` or a JVM `at ...` line.
_FRAME = re.compile(r"^(?:\S[^\s:]*:\d+:|\s+at\s)")


def code_trace(stacktrace: str, trace_filter: StackTraceFilterInterface) -> str:
    """The lines of a failure's trace that belong to the coder's own code, else "".

    Each line belongs to the frame above it (a header before the first frame belongs to that
    frame); a check's frames and everything they own are dropped. A trace that would still
    name the hidden check is dropped whole.
    """
    lines = stacktrace.splitlines()
    frames = [i for i, line in enumerate(lines) if _FRAME.match(line)]
    if not frames:
        return ""
    kept = []
    for i, line in enumerate(lines):
        owner = max((f for f in frames if f <= i), default=frames[0])
        if not trace_filter.is_scenario_frame(lines[owner]):
            kept.append(line)
    text = "\n".join(kept).strip()
    if not text or any(word.lower() in text.lower() for word in SCENARIO_VOCABULARY):
        return ""
    return text


def with_trace(
    feedback: str, failures: list[dict[str, Any]], trace_filter: StackTraceFilterInterface
) -> str:
    """The coder's feedback, with the frames of its own code where it failed."""
    trace = "\n\n".join(
        t for f in failures if (t := code_trace(f.get("stacktrace", ""), trace_filter))
    )
    return f"{feedback}\n\nWhere your code failed:\n{trace}" if trace else feedback


def evidence_text(failures: list[dict[str, Any]], errors: int, total: int) -> str:
    """The failures as text for the model; the aggregate count when none carries any text."""
    text = "".join(
        f"{f.get('nodeid', '')}: {f.get('message', '')}\n{f.get('stacktrace', '')}\n\n"
        for f in failures
    )
    if text.strip():
        return text
    # An errors-only run (a collection or import crash) has no per-test entries.
    return (
        f"{errors} collection/execution error(s) out of {total} scenario tests; "
        "no per-test failure details available."
    )


async def arbitrate(adapter: Any, config: Any, prompt: str) -> ArbitrateResult:
    """The model's verdict on `prompt`; adapter errors propagate."""
    response = await adapter.generate([Message(role=Role.USER, content=prompt)], config)
    # String replies are the unit-mock convention only.
    raw = response.text if hasattr(response, "text") else response
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        data = json.loads(match.group(0) if match else raw)
    except json.JSONDecodeError as exc:
        raise UnreadableVerdictError(raw) from exc
    result = ArbitrateResult(**data)
    result.raw_response = raw
    return result
