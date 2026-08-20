# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a mutant taught us, and the words for saying it.

Split from `mutation.py` when the vocabulary landed: the session runner is about sandboxes,
subprocesses and scheduling, and none of that is needed to decide what a run means.

The verdicts name the conclusion about our own code rather than the mutant's fate. `KILLED` and
`SURVIVED` invert against test semantics — the good line reads as the bad one — and that inversion
confused the people designing this vocabulary twice in one sitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class MutantRun(Protocol):
    """What deciding a verdict needs from a run, and nothing more.

    A structural type rather than an import: the runner owns the concrete `MutantRun`, and this
    module owning a copy of it would give the same idea two definitions.
    """

    derived_id: str
    outcome: str
    killers: list[str]
    detail: str
    drift: str


PROTECTED = "PROTECTED"
UNPROTECTED = "UNPROTECTED"
UNMEASURED = "UNMEASURED"

#: Which `BROKEN` this was. A campaign someone wrote wrong and a test that hangs are both
#: `UNMEASURED`, and they are fixed in different places.
_BROKEN_REASONS = (
    ("timed out", "timed-out"),
    ("anchor appears", "bad-anchor"),
    ("not in the sandbox", "file-missing"),
)


def _broken_reason(detail: str) -> str:
    for needle, code in _BROKEN_REASONS:
        if needle in detail:
            return code
    return "run-failed"


def is_finding(verdict: str) -> bool:
    """Whether a human has to answer for this. Everything except a clean pass."""
    return verdict != PROTECTED


@dataclass(frozen=True)
class Verdict:
    """What a mutant's run means for the requirement it was aimed at.

    `verdict` names what we learned about our own code, not what happened to the mutant.
    `reason` is a code a script can branch on; `explanation` is the sentence a human reads.
    """

    derived_id: str
    verdict: str
    reason: str | None = None
    explanation: str = ""
    drift: str = "OK"


def _files_of(node_ids: list[str]) -> set[str]:
    """The files a list of node ids belongs to. Node ids are `path::test`."""
    return {node.split("::", 1)[0] for node in node_ids}


def scope_killers(records: list[dict[str, Any]], *, scope: list[str]) -> list[dict[str, Any]]:
    """Mark each killer with whether the campaign named its file.

    Marked, never filtered: a bystander that objected is evidence about the scope, and dropping
    it leaves a reader unable to see why the verdict went the way it did.
    """
    scoped = set(scope)
    return [
        {
            "nodeid": record["nodeid"],
            "in_scope": str(record["nodeid"]).split("::", 1)[0] in scoped,
            "message": record.get("message"),
        }
        for record in records
    ]


def verdict_of(
    run: MutantRun,
    *,
    scope: list[str],
    baseline_failures: list[str] | None = None,
    confirmed: bool = False,
) -> Verdict:
    """Seven ordered rules, first match wins. The order is the design, not an implementation detail.

    The distinction this whole sub-feature exists for: `KILL` means *tests failed*; `PASS` means
    *this requirement is protected*. A bystander test dying satisfies the first and not the second,
    and treating them as one is how a campaign certifies a requirement nothing covers.

    `drift` rides through rather than deciding anything. "The code moved" and "the requirement is
    unprotected" need different responses, and a result that can only say one of them makes the
    other invisible.
    """
    scoped = set(scope)

    def out(verdict: str, reason: str | None = None, explanation: str = "") -> Verdict:
        return Verdict(run.derived_id, verdict, reason, explanation, run.drift)

    # 1. A baseline failure inside this scope makes everything else unreadable.
    if _files_of(list(baseline_failures or [])) & scoped:
        return out(
            UNMEASURED,
            "scope-already-red",
            "a test in this scope was already failing before the mutant",
        )
    # 2. Nothing collected is not a gap in the code — it is a scope that names no tests.
    if run.outcome == "NOTHING_RAN":
        return out(UNMEASURED, "nothing-collected", "no tests were collected for this scope")
    # 3. The anchor no longer applies: the code moved, so nothing was measured against it.
    #    Falling through to rule 5 reported this as `UNPROTECTED` — a claim about the code under
    #    test — and sent readers to write a test for a requirement that may already be covered.
    if run.outcome == "STALE":
        return out(UNMEASURED, "symbol-drifted", run.detail[:200] or "the anchor no longer applies")
    # 4. Pytest itself broke; there is nothing here to judge.
    if run.outcome == "BROKEN":
        return out(UNMEASURED, _broken_reason(run.detail), run.detail[:200])
    # 5. Nothing objected. This is the one that means our code is unguarded.
    if run.outcome == "NO_KILL":
        return out(UNPROTECTED, "no-killer", "no test noticed the behaviour disappearing")
    # 6. Something objected, but nothing the campaign named.
    if not (_files_of(run.killers) & scoped):
        return out(
            UNPROTECTED,
            "out-of-scope-killer",
            "killed only by tests outside this campaign's scope",
        )
    # 7/8. An in-scope kill counts only once it reproduces without the mutant.
    if not confirmed:
        return out(UNMEASURED, "killer-already-failing", "the killer fails without the mutant too")
    return out(PROTECTED, None, "an in-scope test objected, and passes without the mutant")


def campaign_verdict(verdicts: list[Verdict], *, declared: int) -> str:
    """`FR-8` — accounting first, then the worst verdict present.

    Accounting comes first because a campaign that lost a result cannot be scored on the results it
    kept: the missing one is exactly where a crash or a silent skip would hide.
    """
    if len(verdicts) != declared or not verdicts:
        return "FAILED"
    # `PARTIAL` is gone with the old vocabulary. It used to mean "nothing failed, but something
    # was inconclusive" — and inconclusive is now `UNMEASURED`, which is a finding. There is no
    # third state left for it to name.
    if any(is_finding(v.verdict) for v in verdicts):
        return "FAILED"
    return "PASSED"
