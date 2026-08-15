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
    tally = {"pass": 0, "fail": 0, "indeterminate": 0, "stale": 0, "broken": 0}
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
