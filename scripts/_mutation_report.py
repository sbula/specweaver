#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one artefact of a mutation session that outlives it.

The sandbox is a detached worktree, removed when the run ends. So a report that points into it is
unreadable by the time anyone acts on it — and "anyone" includes the gate, which reads this file
hours later on a machine that has since rebooted.

## Sanitisation is a document-level pass, not a per-field one

Applied once over the whole structure at build time rather than at each call site. A field added
later cannot then be forgotten, which is the failure mode a per-field approach guarantees eventually.

Paths are rewritten to **repo-relative** rather than blanked: the sandbox mirrors the repository, so
`/tmp/sw-x-1/src/specweaver/x.py` is genuinely `src/specweaver/x.py`, and a placeholder would throw
away the only half of the string worth reading.

## Exit codes report the run, not the decision

`0` nothing failed · `1` something failed · `2` could not run. **Zero campaigns is `2`, not `0`** —
a session that found no corpus is a session that measured nothing, and reporting that as success is
indistinguishable from one where every requirement was protected. Whether work continues is the
gate's call, not this file's.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

#: A sandbox path. `_mutate` and `mutation` both build sandboxes under the system temp directory
#: with a `sw-` prefix, and the segment after it is the mirror of the repo tree.
_SANDBOX_PATH = re.compile(r"/(?:private/)?tmp/sw-[A-Za-z0-9_-]+/")


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
        "derived_id": result.derived_id,
        "verdict": result.verdict,
        "reason": result.reason,
        "drift": result.drift,
        "confirmed": getattr(result, "confirmed", False),
        "killers": list(getattr(result, "killers", [])),
        "leaked": list(getattr(result, "leaked", [])),
        "detail": getattr(result, "detail", ""),
    }


def _age(generated_at: str, now: str | None) -> str:
    """How old this evidence is, in words a reader will notice.

    `--gate` reported CLEAR for two days against a report from before the change it was judging. The
    file's mtime knew; the document did not, and the document is what gets read. So the age travels
    with the verdict.
    """
    if not generated_at:
        return "age unknown — this report predates `generated_at`"
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
    """The report as prose, derived from the same document the JSON holds.

    A pure function of `document`, deliberately: the JSON stays the single source of truth and this is
    a view of it, so the two cannot drift. Written because the machine-readable format was hand-parsed
    three times in one session and produced a confident wrong answer each time — `dict.get` returns a
    default rather than raising, so a mistyped key reads as a zero. A reader with a parse in hand can
    check it against this.

    Only failures are listed individually. Twenty-six passing lines would bury the two that matter,
    which is how "no tests were collected for this scope" sat unread for two days.
    """
    summary = document.get("summary", {})
    campaigns = document.get("campaigns", [])
    counts = summary.get("counts", {})
    baseline = summary.get("baseline") or {}

    lines = [
        "MUTATION REPORT",
        f"  verdict      {summary.get('verdict', '?')}",
        f"  generated    {summary.get('generated_at', '(none)')}  ({_age(summary.get('generated_at', ''), now)})",
        f"  commit       {summary.get('head', '?')}"
        + (
            "  **TREE WAS DIRTY — this verdict describes no commit**"
            if summary.get("dirty")
            else ""
        ),
    ]

    if baseline:
        green = baseline.get("green")
        state = "green" if green else f"NOT GREEN ({baseline.get('failed', '?')} failed)"
        lines.append(f"  baseline     {state}")
        if not green:
            lines.append(
                "               every verdict below is meaningless while the baseline is red"
            )

    lines += [
        f"  mutants      {summary.get('declared', 0)} declared, {summary.get('returned', 0)} returned"
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
            f" {campaign.get('mutants_declared', 0)} declared"
        )

    failures = [
        result
        for campaign in campaigns
        for result in campaign.get("results", [])
        if result.get("verdict") != "PASS"
    ]
    if failures:
        lines += ["", f"  {len(failures)} mutant(s) not passing:"]
        for result in failures:
            reason = result.get("reason") or "(no reason recorded)"
            lines.append(f"    {result.get('derived_id', '?')}")
            lines.append(f"      {result.get('verdict', '?')}: {reason}")

    return "\n".join(lines)


def build_report(
    *,
    campaigns: list[dict[str, Any]],
    head: str,
    dirty: bool,
    baseline: Any = None,
    not_run: int = 0,
) -> dict[str, Any]:
    """The document, summary first.

    Summary first is not cosmetic: a reader that stops after one block must still learn the verdict,
    and a machine that streams the file gets the decision before the detail.
    """
    declared = sum(c["mutants_declared"] for c in campaigns)
    returned = sum(c["verdicts_returned"] for c in campaigns)
    verdicts = [c["verdict"] for c in campaigns]

    document = {
        "summary": {
            # First field for the same reason the summary is first: a reader who stops early must
            # still learn how old the evidence is. Its absence is why `--gate` read CLEAR for two days.
            "generated_at": datetime.now(UTC).isoformat(),
            "head": head,
            "dirty": dirty,
            "verdict": "FAILED" if "FAILED" in verdicts else ("PASSED" if verdicts else "NOT_RUN"),
            "baseline": {
                "green": getattr(baseline, "green", None),
                "failed": len(getattr(baseline, "failures", []) or []),
            },
            "counts": _counts(campaigns),
            "declared": declared,
            "returned": returned,
            "not_run": not_run,
        },
        "campaigns": [
            {
                "feature": c["feature"],
                "requirement": c["requirement"],
                "verdict": c["verdict"],
                "mutants_declared": c["mutants_declared"],
                "verdicts_returned": c["verdicts_returned"],
                "results": [_as_dict(r) for r in c["results"]],
            }
            for c in campaigns
        ],
    }
    return sanitise_document(document)


def exit_code_for(campaign_verdicts: list[str]) -> int:
    """`0` nothing failed · `1` something failed · `2` could not run."""
    if not campaign_verdicts:
        return 2
    return 1 if "FAILED" in campaign_verdicts else 0
