#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one artefact of a mutation session that outlives it.

The sandbox is a detached worktree, removed when the run ends. So a session record that points into it is
unreadable by the time anyone acts on it — and "anyone" includes the gate, which reads this file
hours later on a machine that has since rebooted.

## Sanitisation is a document-level pass, not a per-field one

Applied once over the whole structure at build time rather than at each call site. A field added
later cannot then be forgotten, which is the failure mode a per-field approach guarantees eventually.

Paths are rewritten to **repo-relative** rather than blanked: the sandbox mirrors the repository, so
`/tmp/sw-x-1/src/specweaver/x.py` is genuinely `src/specweaver/x.py`, and a placeholder would throw
away the only half of the string worth reading.

## Exit codes state the run, not the decision

`0` nothing failed · `1` something failed · `2` could not run. **Zero campaigns is `2`, not `0`** —
a session that found no corpus is a session that measured nothing, and reporting that as success is
indistinguishable from one where every requirement was protected. Whether work continues is the
gate's call, not this file's.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

#: The two top-level blocks of a session record, named once so both sides of the seam import the
#: name instead of spelling it. `68a089d4` renamed the first block `summary` -> `session` here and
#: in the renderer, and left `_mutation_gate`'s single reader on the old spelling: each half kept
#: its own tests and stayed green while the pair could not work, so the red-baseline rule matched
#: no document any producer had written and could never fire.
#:
#: `anti_patterns.md` names this shape — *two modules naming one thing differently across a seam* —
#: and asks for both halves of the remedy: the shared constant, and an agreement test that hands
#: one side's output to the other side's reader. The test is
#: `test_mutation_seam.py::TestTheGateReadsWhatTheProducerWrites`.
SESSION_BLOCK = "session"
MUTANTS_BLOCK = "mutants"

#: A sandbox path. `_mutate` and `mutation` both build sandboxes under the system temp directory
#: with a `sw-` prefix, and the segment after it is the mirror of the repo tree.
_SANDBOX_PATH = re.compile(r"/(?:private/)?tmp/sw-[A-Za-z0-9_-]+/")

#: How many failing test names the PROSE prints before summarising the rest. The JSON keeps all of
#: them -- the record is the record. Ten with the remainder counted is the shape the repo already
#: used for oversized findings; a truncation that does not say it truncated reads as a full list.
_BASELINE_NAMES_SHOWN = 10


def sanitise(text: str) -> str:
    """A string with sandbox prefixes rewritten away, leaving the repo-relative remainder."""
    return _SANDBOX_PATH.sub("", text)


def sanitise_document(node: Any) -> Any:
    """The same, applied to every string anywhere in a nested structure.

    Recursive rather than field-by-field on purpose: the whole point is that a field nobody
    remembered still gets cleaned.
    """
    if isinstance(node, str):
        return sanitise(node)
    if isinstance(node, dict):
        return {key: sanitise_document(value) for key, value in node.items()}
    if isinstance(node, list):
        return [sanitise_document(item) for item in node]
    return node


def _counts(campaigns: list[dict[str, Any]]) -> dict[str, int]:
    """One key per verdict, plus drift, which is orthogonal to all three."""
    tally = {"protected": 0, "unprotected": 0, "unmeasured": 0, "stale": 0}
    for campaign in campaigns:
        for result in campaign["results"]:
            data = _as_dict(result)
            key = str(data["verdict"]).lower()
            if key in tally:
                tally[key] += 1
            if data.get("drift") == "STALE":
                tally["stale"] += 1
    return tally


def _as_dict(result: Any) -> dict[str, Any]:
    """A result as plain data, carrying its evidence.

    `detail` is included deliberately, and it is the field the sanitiser exists for: a stale anchor
    or a broken run puts an absolute sandbox path in it verbatim. Dropping it would make the
    document trivially clean and useless — the reader would learn a mutant was `STALE` and nothing
    about which symbol moved.
    """
    if isinstance(result, dict):
        return result
    return {
        "id": result.derived_id,
        "verdict": result.verdict,
        "reason": result.reason,
        "explanation": getattr(result, "explanation", ""),
        "drift": result.drift,
        "confirmed": getattr(result, "confirmed", False),
        "killers": list(getattr(result, "killers", [])),
        "leaked": list(getattr(result, "leaked", [])),
        "breaks": getattr(result, "breaks", None),
        "detail": getattr(result, "detail", ""),
    }


def _age(generated_at: str, now: str | None) -> str:
    """How old this evidence is, in words a reader will notice.

    `--gate` reported CLEAR for two days against a session record from before the change it was judging. The
    file's mtime knew; the document did not, and the document is what gets read. So the age travels
    with the verdict.
    """
    if not generated_at:
        return "age unknown — this record predates `started_at`"
    if now is None:
        now = datetime.now(UTC).isoformat()
    try:
        delta = datetime.fromisoformat(now) - datetime.fromisoformat(generated_at)
    except ValueError:
        return "age unknown — unparseable timestamp"
    days, hours = delta.days, delta.seconds // 3600
    if days >= 1:
        return f"{days} day{'s' if days != 1 else ''} old — CHECK THIS IS STILL THE CODE YOU MEAN"
    if hours >= 1:
        return f"{hours} hour{'s' if hours != 1 else ''} old"
    return "fresh"


def render_summary(document: dict[str, Any], now: str | None = None) -> str:
    """The session record as prose, derived from the same document the JSON holds.

    A pure function of `document`, deliberately: the JSON stays the single source of truth and this is
    a view of it, so the two cannot drift. Written because the machine-readable format was hand-parsed
    three times in one session and produced a confident wrong answer each time — `dict.get` returns a
    default rather than raising, so a mistyped key reads as a zero. A reader with a parse in hand can
    check it against this.

    Only failures are listed individually. Twenty-six passing lines would bury the two that matter,
    which is how "no tests were collected for this scope" sat unread for two days.
    """
    summary = document.get(SESSION_BLOCK, {})
    campaigns = campaigns_of(document)
    counts = counts_of(document)
    baseline = summary.get("baseline") or {}
    mutants = mutants_of(document)
    verdict = session_verdict_of(document)

    lines = [
        "MUTATION SESSION",
        f"  verdict      {verdict}",
        f"  generated    {summary.get('started_at', '(none)')}  ({_age(summary.get('started_at', ''), now)})",
        f"  commit       {summary.get('head', '?')}"
        + (
            "  **TREE WAS DIRTY — this verdict describes no commit**"
            if summary.get("dirty")
            else ""
        ),
    ]

    if baseline.get("ran"):
        green = baseline.get("green")
        state = "green" if green else f"NOT GREEN ({baseline.get('failed', '?')} failed)"
        if not green and not (baseline.get("failures") or []):
            state += f", pytest exit {baseline.get('code', '?')}"
        lines.append(f"  baseline     {state}")
        if not green:
            lines.append(
                "               every verdict below is meaningless while the baseline is red"
            )
            failures = baseline.get("failures") or []
            lines += [f"               {name}" for name in failures[:_BASELINE_NAMES_SHOWN]]
            if len(failures) > _BASELINE_NAMES_SHOWN:
                hidden = len(failures) - _BASELINE_NAMES_SHOWN
                lines.append(f"               ... and {hidden} more")

    lines += [
        f"  mutants      {len(mutants)} judged"
        f"  (protected {counts.get('protected', 0)},"
        f" unprotected {counts.get('unprotected', 0)},"
        f" unmeasured {counts.get('unmeasured', 0)},"
        f" stale {counts.get('stale', 0)})",
        "",
    ]

    if not campaigns:
        lines.append("  no campaigns ran — this is not the same as everything passing")
        return "\n".join(lines)

    lines.append(f"  {len(campaigns)} campaign(s):")
    for campaign in campaigns:
        mark = " " if campaign.get("verdict") == "PASSED" else "!"
        lines.append(
            f"   {mark} {campaign.get('feature', '?'):<12} {campaign.get('requirement', '?'):<6}"
            f" {campaign.get('verdict', '?'):<8}"
            f" {len(campaign.get('mutants', []))} declared"
        )

    failures = [m for m in mutants if m.get("verdict") != "PROTECTED"]
    if failures:
        lines += ["", f"  {len(failures)} mutant(s) not passing:"]
        for result in failures:
            # The code is for scripts and the sentence is for the reader. Showing only the code
            # made "nothing-collected" the whole explanation of a campaign that measured nothing.
            code = result.get("reason") or "?"
            said = result.get("explanation") or "(no explanation recorded)"
            lines.append(f"    {result.get('id', '?')}")
            lines.append(f"      {result.get('verdict', '?')} [{code}]: {said}")
            if result.get("breaks"):
                lines.append(f"      breaks: {result['breaks']}")

    return "\n".join(lines)


def mutants_of(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Every mutant in a session record, whatever shape it is stored in."""
    return list(record.get(MUTANTS_BLOCK, []))


def counts_of(record: dict[str, Any]) -> dict[str, int]:
    """One key per verdict, plus drift, which is orthogonal to all three.

    Computed, never stored. A count kept beside the detail it summarises is a second copy of one
    fact, and this repo has already had a roll-up outlive the run it described.
    """
    tally = {"protected": 0, "unprotected": 0, "unmeasured": 0, "stale": 0}
    for mutant in mutants_of(record):
        key = str(mutant.get("verdict", "")).lower()
        if key in tally:
            tally[key] += 1
        if mutant.get("drift") == "STALE":
            tally["stale"] += 1
    return tally


def campaigns_of(record: dict[str, Any]) -> list[dict[str, Any]]:
    """The mutants regrouped by the campaign that declared them.

    The grouping comes from the mutant's own id — `"<FEATURE> <REQUIREMENT> <slug>"` — which is
    why the record stores a flat list. A campaign passes only when every one of its mutants is
    protected; anything else is a finding somebody has to answer.
    """
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for mutant in mutants_of(record):
        parts = str(mutant.get("id", "")).split(" ")
        key = (parts[0] if parts else "", parts[1] if len(parts) > 1 else "")
        grouped.setdefault(key, []).append(mutant)
    return [
        {
            "feature": feature,
            "requirement": requirement,
            "verdict": (
                "PASSED" if all(m.get("verdict") == "PROTECTED" for m in mutants) else "FAILED"
            ),
            "mutants": mutants,
        }
        for (feature, requirement), mutants in sorted(grouped.items())
    ]


def session_verdict_of(record: dict[str, Any]) -> str:
    """Did this session pass. The only place that answers it.

    The prose and the exit code used to work it out separately, from different inputs. Two
    derivations of one fact agree on the day they are written and not reliably after.
    """
    mutants = mutants_of(record)
    if not mutants:
        return "NOT_RUN"
    return "PASSED" if all(m.get("verdict") == "PROTECTED" for m in mutants) else "FAILED"


def _baseline_block(baseline: Any) -> dict[str, Any]:
    """Whether a baseline ran, and what it found if so.

    `{"green": null, "failed": 0}` could not tell *not attempted* from *attempted and
    inconclusive*, and put a meaningless zero beside the null. Absence is a fact about the
    session, not a null-valued property of one.
    """
    if baseline is None:
        return {"ran": False}
    failures = [str(name) for name in (getattr(baseline, "failures", None) or [])]
    return {
        "ran": True,
        "green": bool(getattr(baseline, "green", False)),
        "failed": len(failures),
        "failures": failures,
        # `killers()` returns nothing when pytest ITSELF errored, so `failed: 0` beside
        # `green: false` means either "red with no names" or "could not collect". The exit code is
        # the only thing that tells them apart, and `Baseline` has carried it all along.
        "code": int(getattr(baseline, "code", 0) or 0),
    }


def build_session_record(
    *,
    campaigns: list[dict[str, Any]],
    head: str,
    dirty: bool,
    baseline: Any = None,
) -> dict[str, Any]:
    """What one session saw. Scratch, and it stores nothing it can recompute.

    Session block first: a reader who stops after one block must still learn how old the evidence
    is, and its absence is why the gate read CLEAR for two days.

    The mutants are flat. Campaign grouping is derivable from a mutant's id, which already carries
    the feature and the requirement, so storing the nesting as well would store the same fact
    twice — and two copies of one fact are two things that can disagree.
    """
    document = {
        "schema": 1,
        SESSION_BLOCK: {
            "started_at": datetime.now(UTC).isoformat(),
            "head": head,
            "dirty": dirty,
            "baseline": _baseline_block(baseline),
        },
        MUTANTS_BLOCK: [
            _as_dict(result) for campaign in campaigns for result in campaign["results"]
        ],
    }
    return sanitise_document(document)


def exit_code_for(record: dict[str, Any]) -> int:
    """`0` nothing failed · `1` something failed · `2` could not run.

    Takes the record rather than a list of verdicts, so the code and the prose cannot disagree
    about what the session concluded.
    """
    return {"NOT_RUN": 2, "FAILED": 1}.get(session_verdict_of(record), 0)
