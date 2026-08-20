#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Whether last night's findings have been read.

This gate blocks on findings **nobody has looked at**, and releases the moment each carries a
disposition. It never demands proof that a fix worked: that would mean an on-demand corpus run,
which is the inline model this design rejects, and the next scheduled run re-measures anyway. An
unfixed finding simply comes back — and `runs` is what makes that safe, because a `will-fix`
re-confirmed for a fortnight is visible rather than quietly renewed.

## What does not block, and why

`INDETERMINATE` says the tree was already red; `STALE` says the code moved. Neither is evidence
that a requirement is unprotected, and blocking on them would train people to confirm noise. A gate
whose findings are mostly noise is a gate nobody reads, which is the failure this whole ticket
keeps circling.

## Deliberately not a `quality.py` check

`NFR-6`. This is a standalone decision about whether feature work continues, not a commit gate. The
design's own FR-11 binding row said otherwise and was corrected — a binding that disagreed with its
own NFR, which survived the design's Phase 6.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

#: The hour the nightly session is scheduled for. The gate measures freshness against the
#: schedule rather than against a tolerance, because a tolerance is a window in which a dead
#: scheduler looks alive: a 48-hour allowance let a run that hung at 03:00 and never wrote a
#: report be answered with the previous morning's verdict, and it would have kept answering that
#: way every morning after.
NIGHTLY_HOUR = 3

#: Verdicts that require a human to have looked — everything except a clean pass.
#:
#: This used to exclude `INDETERMINATE` and `STALE`, so two of the three ways to learn nothing
#: passed the gate silently. Under the vocabulary that replaced them, learning nothing is a
#: finding: `UNMEASURED` means the campaign, the tests or the environment is broken, and every one
#: of those is fixed by a human, not by waiting.
BLOCKING_VERDICTS = ("UNPROTECTED", "UNMEASURED")

#: Dispositions that release the gate **without the finding being resolved**, and so are the ones
#: the census counts. `real-gap` means you fixed it; `stale-refreshed` means you re-read the claim
#: and re-pinned it. Neither is a bypass.
OVERRIDE_DISPOSITIONS = ("will-fix", "equivalent")
#: `fixed-campaign` and `fixed-environment` answer an `UNMEASURED` finding, where `equivalent`
#: is meaningless — the campaign or the machine was wrong, not the code under test.
DISPOSITIONS = (
    "real-gap",
    "equivalent",
    "will-fix",
    "stale-refreshed",
    "fixed-campaign",
    "fixed-environment",
)


@dataclass(frozen=True)
class GateResult:
    """Continue, or read the findings first."""

    blocked: bool
    reason: str = ""
    unconfirmed: list[str] = field(default_factory=list)


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_ledger(path: Path) -> dict[str, Any]:
    """The record of what has been looked at. Missing is empty, not an error — the first run has no
    ledger and must still be able to gate."""
    data = _read_json(path, {"findings": {}, "override_count": 0})
    data.setdefault("findings", {})
    data.setdefault("override_count", 0)
    return data


def findings_in(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Every mutant in a session record.

    The record stores a flat list; campaign grouping is derived from a mutant's id when a reader
    wants it. Nothing here needs the grouping, so nothing here reconstructs it.
    """
    return list(record.get("mutants", []))


def last_expected_run(now: float) -> float:
    """The most recent moment the nightly session should have produced a report.

    Today's scheduled hour once it has passed, else yesterday's. Comparing against this rather
    than against an age in hours is what makes a silent scheduler visible: the answer changes the
    moment a run is due, so a report that was current an hour ago becomes stale on schedule.
    """
    parts = time.localtime(now)
    todays = time.mktime((parts.tm_year, parts.tm_mon, parts.tm_mday, NIGHTLY_HOUR, 0, 0, 0, 0, -1))
    return todays if todays <= now else todays - 86400


def gate_verdict(report_path: Path, ledger_path: Path) -> GateResult:
    """Three rules, in order.

    Staleness first: a verdict computed from a report nobody produced is worse than no verdict, and
    checking the contents of a file that may be a week old would answer the wrong question.
    """
    expected = last_expected_run(time.time())
    if not report_path.is_file():
        return GateResult(True, "no report — the session has not run")
    mtime = report_path.stat().st_mtime
    if mtime < expected:
        age_hours = (time.time() - mtime) / 3600
        return GateResult(
            True,
            f"the {time.strftime('%Y-%m-%d %H:%M', time.localtime(expected))} session did not "
            f"leave a report — the newest is {age_hours:.0f}h old. A run that hangs, crashes or "
            f"never starts writes nothing, so an old report is the symptom, not the all-clear",
        )

    report = _read_json(report_path, {})
    # A red baseline invalidates every verdict in the report, which the summary already states in
    # as many words. Checked before the findings, because there is no point asking whether findings
    # were read when none of them mean anything. A report with no baseline recorded was run with
    # `--no-baseline` and never claimed to know.
    baseline = (report.get("summary") or {}).get("baseline")
    if baseline is not None and not baseline.get("green"):
        return GateResult(
            True,
            f"the baseline was not green ({baseline.get('failed', '?')} failing), so every verdict "
            f"in this report was judged against a tree whose suite never passed",
        )
    # `TECH-056`: a **disposition**, not mere presence. `record_run` runs at the end of the same
    # session that discovers a finding and writes it as `{"runs": 1}` with nothing decided, so
    # keying on presence let every run mark its own findings read — and this gate then announced
    # "every finding carries a disposition" about entries that carried none. It could not block.
    known = {
        derived_id
        for derived_id, entry in load_ledger(ledger_path)["findings"].items()
        if latest_disposition(entry)
    }
    unconfirmed = [
        f["id"]
        for f in findings_in(report)
        if f.get("verdict") in BLOCKING_VERDICTS and f["id"] not in known
    ]
    if unconfirmed:
        return GateResult(True, "findings nobody has looked at", sorted(unconfirmed))
    return GateResult(False, "every finding carries a disposition")


#: How long a closed finding is kept. Long enough to answer "does this class of defect come
#: back", bounded so the file cannot grow for ever. A reappearance reopens the entry and resets
#: the clock, so a defect that returns every few months is never pruned.
RETENTION_SECONDS = 365 * 86400.0


def current_state(entry: dict[str, Any]) -> str:
    """`open`, `closed`, or `unknown` — read from the last history entry that set a state.

    Never a field beside the history. A stored current-state is a second copy of one fact, and two
    copies are two things that can disagree.
    """
    for event in reversed(entry.get("history", [])):
        if event.get("state") in {"open", "closed"}:
            return str(event["state"])
    return "unknown"


def _last_open(entry: dict[str, Any]) -> dict[str, Any]:
    for event in reversed(entry.get("history", [])):
        if event.get("state") == "open":
            return event
    return {}


def _closed_at(entry: dict[str, Any]) -> float | None:
    """When this finding closed, or `None` if it is open.

    The last *closure*, not the last history entry. A disposition recorded after a closure sits
    later in the history, and reading the clock off the tail would restart the retention year from
    a note — so a finding could be kept indefinitely by commenting on it.
    """
    for event in reversed(entry.get("history", [])):
        if event.get("state") == "closed":
            return float(event.get("at", 0.0))
        if event.get("state") == "open":
            return None
    return None


def _closure_reason(mutant_id: str, judged: dict[str, str], declared: set[str]) -> str:
    """Why a finding stopped appearing — derived, never claimed.

    "I fixed it" is exactly the assertion this tool exists to distrust, and a finding that closes
    because somebody deleted its campaign must not read the same as one that closes because the
    test was written.
    """
    if judged.get(mutant_id) == "PROTECTED":
        return "fixed"
    if mutant_id not in declared:
        return "withdrawn"
    return "unreachable"


def fold_session(
    ledger: dict[str, Any],
    *,
    judged: dict[str, str],
    reasons: dict[str, str],
    declared: set[str],
    now: float,
) -> dict[str, Any]:
    """One session folded into the ledger: open what is new, close what is gone, prune what is old.

    Pure, so the rules can be tested without a filesystem. `judged` is what this session concluded
    per mutant, `declared` is what the corpus asked for — the difference between them is what
    distinguishes a withdrawn mutant from one that never ran.
    """
    findings = {mid: v for mid, v in judged.items() if v in BLOCKING_VERDICTS}
    out: dict[str, Any] = {}

    for mutant_id, entry in ledger.get("findings", {}).items():
        entry = {**entry, "history": list(entry.get("history", []))}
        if mutant_id in findings:
            continue  # handled below, where the arriving state is known
        if current_state(entry) == "open":
            entry["history"].append(
                {
                    "at": now,
                    "state": "closed",
                    "reason": _closure_reason(mutant_id, judged, declared),
                }
            )
        closed_at = _closed_at(entry)
        if closed_at is not None and now - closed_at > RETENTION_SECONDS:
            continue
        out[mutant_id] = entry

    for mutant_id, verdict in findings.items():
        entry = {**ledger.get("findings", {}).get(mutant_id, {})}
        entry["history"] = list(entry.get("history", []))
        entry.setdefault("first_seen", now)
        entry["last_seen"] = now
        entry["occurrences"] = int(entry.get("occurrences", 0)) + 1

        latest = _last_open(entry) if current_state(entry) == "open" else {}
        unchanged = latest.get("verdict") == verdict and latest.get("reason") == reasons.get(
            mutant_id
        )
        if not unchanged:
            entry["history"].append(
                {
                    "at": now,
                    "state": "open",
                    "verdict": verdict,
                    "reason": reasons.get(mutant_id),
                }
            )
        out[mutant_id] = entry

    return {**ledger, "schema": ledger.get("schema", 1), "findings": out}


def record_run(
    report_path: Path,
    ledger_path: Path,
    *,
    declared: set[str] | None = None,
) -> dict[str, Any]:
    """Fold a session record into the ledger.

    `declared` is every mutant the corpus asked for. Without it a mutant that never ran cannot be
    told from one somebody deleted, and those close for opposite reasons — the second is how a
    ledger could be cleared by removing campaigns and read as a year of diligent fixing.
    """
    record = _read_json(report_path, {})
    mutants = findings_in(record)
    judged = {str(m["id"]): str(m.get("verdict", "")) for m in mutants if m.get("id")}
    reasons = {str(m["id"]): m.get("reason") for m in mutants if m.get("id")}

    ledger = fold_session(
        load_ledger(ledger_path),
        judged=judged,
        reasons=reasons,
        declared=set(declared) if declared is not None else set(judged),
        now=time.time(),
    )
    write_ledger(ledger_path, ledger)
    return ledger


def confirm(ledger_path: Path, derived_id: str, *, disposition: str, why: str) -> dict[str, Any]:
    """Record that a human looked at a finding and what they decided.

    One finding at a time, and `why` is mandatory. A confirmation with no reason is a click-through,
    which is precisely what the census exists to stop — the ratchet counts entries, and an entry
    nobody had to justify costs nothing to add.

    The recurrence count is preserved. Deciding what to do about a finding must not reset how long
    it has been here; that number is the only pressure on a `will-fix` that never gets fixed.
    """
    if disposition not in DISPOSITIONS:
        raise ValueError(f"unknown disposition {disposition!r}; expected one of {DISPOSITIONS}")
    if not why.strip():
        raise ValueError("why is required — a confirmation without a reason is a click-through")

    ledger = load_ledger(ledger_path)
    entry = dict(ledger["findings"].get(derived_id, {}))
    entry["history"] = [
        *entry.get("history", []),
        {
            "at": time.time(),
            "state": "disposed",
            "disposition": disposition,
            "why": why.strip(),
        },
    ]
    ledger["findings"][derived_id] = entry
    write_ledger(ledger_path, ledger)
    return ledger


def latest_disposition(entry: dict[str, Any]) -> str | None:
    """The most recent decision a human recorded, or `None`.

    Derived from the history for the same reason the state is: keeping it beside the history would
    make the two able to disagree, and it is the history that carries when it was taken.
    """
    for event in reversed(entry.get("history", [])):
        if event.get("state") == "disposed":
            return str(event.get("disposition"))
    return None


def write_ledger(ledger_path: Path, ledger: dict[str, Any]) -> None:
    """Persist the ledger, recomputing what the ratchet counts.

    `override_count` is derived on write rather than maintained: it is a roll-up, and a roll-up
    kept by hand is one that can disagree with what it summarises.
    """
    ledger = {
        **ledger,
        "override_count": sum(
            1
            for entry in ledger.get("findings", {}).values()
            if latest_disposition(entry) in OVERRIDE_DISPOSITIONS
        ),
    }
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def ratchet_ok(*, current: int, baseline: int) -> bool:
    """Whether the override census has grown.

    Falling is the point: debt may be repaid, never taken on silently. Equal passes — a steady count
    is not progress, but it is not a new bypass either, and failing on it would make the ratchet
    unpassable rather than directional.
    """
    return current <= baseline
