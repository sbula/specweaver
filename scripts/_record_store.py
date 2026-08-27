#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the session store keeps, and what a later run has made redundant.

Retention is tied to **state, not age** `[agreed 2026-08-27]`. A record is deleted only when a
later `PASSED` record supersedes it; a record of a failure is kept until the failure is fixed and a
clean run of covering scope proves it, however old that takes.

That inverts the usual rule on purpose. Age says nothing about whether anybody acted on what a
record found, so a fourteen-day sweep deletes the evidence of a fault nobody has looked at yet —
which is precisely the evidence worth keeping. `.tmp/` is gitignored, so no diff and no gate would
ever have shown what went missing.

## No cap, and a warning instead

An unfixed repo grows the store for ever. That is the honest consequence and it is accepted: a cap
deletes the record of an unfixed fault, which is the one thing this rule exists to prevent. So the
run warns past `WARN_ABOVE` unsuperseded records rather than tidying any of them away, and
`overgrown` has no path that names a file.

The other half of the bargain is that the warning must be seen. `.tmp/` is invisible to every gate
in this repo — the handover grew to 23 MB there before anyone noticed — so it is printed by the
run **and** by `--gate`.

## Pure rules, one I/O edge

Every rule is a function of `(name, verdict, scope)` triples, so it can be tested by writing three
tuples. Reading and deleting live at the bottom of this file, deliberately thin: the rules must not
be re-derived from a directory listing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def _sibling(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_record = _sibling("_session_record")

#: Unsuperseded records above which the run says so. Not a cap — nothing is deleted at any count
#: `[agreed 2026-08-27]`. Twenty is roughly three weeks of nightlies that nobody has drained, which
#: is long enough to be a backlog and short enough to still be actionable.
WARN_ABOVE = 20

#: The only verdict that retires an earlier record. A newer failure is more evidence, not less.
_SUPERSEDING = "PASSED"

#: Verdicts a record may carry, for reference: `PASSED`, `FAILED`, `NOT_RUN`. The last two are kept
#: identically — a session that judged nothing is an error, and `STATE.md` already says a run that
#: leaves no record is an alarm rather than a pass. A run that leaves an empty one is the same
#: alarm with a file attached.

Entry = tuple[str, str, dict[str, Any]]


def covers(outer: dict[str, Any], inner: dict[str, Any]) -> bool:
    """Whether a run of reach `outer` looked at everything a run of reach `inner` did.

    A scope that does not say what it covered covers nothing. Reading silence as "everything" is
    the mistake the gate refuses one level up, and it is worse here: there it blocks a morning,
    here it deletes evidence.
    """
    if outer.get("kind") == "full":
        return True
    if outer.get("kind") != "scoped" or inner.get("kind") != "scoped":
        return False
    outer_corpora = outer.get("corpora")
    inner_corpora = inner.get("corpora")
    if outer_corpora is None or inner_corpora is None:
        return False
    return set(inner_corpora) <= set(outer_corpora)


def superseded(entries: list[Entry]) -> list[str]:
    """The records a later clean run of covering scope has made redundant, oldest first.

    Sorted by name rather than trusting the caller's order: names lead with the timestamp, so
    sorting them **is** chronology, and a function trusting list order would delete the newest
    record the day somebody globbed without sorting.
    """
    ordered = sorted(entries)
    return [
        name
        for index, (name, _verdict, scope) in enumerate(ordered)
        if any(
            later_verdict == _SUPERSEDING and covers(later_scope, scope)
            for _later_name, later_verdict, later_scope in ordered[index + 1 :]
        )
    ]


def overgrown(entries: list[Entry]) -> str | None:
    """Prose when the backlog of unsuperseded records has grown past `WARN_ABOVE`, else `None`.

    Counts what is **left after** superseding, not what is on disk: a healthy store passes twenty
    records the moment somebody runs the corpus twenty-one times, which is a Tuesday.
    """
    remaining = len(entries) - len(superseded(entries))
    if remaining <= WARN_ABOVE:
        return None
    return (
        f"{remaining} session records in the store are not superseded by any later clean run. "
        f"Each one holds a failure or a session that judged nothing, and none is deleted at any "
        f"count — a cap would throw away the record of an unfixed fault. Drain them by fixing what "
        f"they found and running the whole corpus."
    )


# --- the single I/O edge -----------------------------------------------------------------------
#
# Everything above is pure and testable by writing three tuples. This part reads and deletes, and
# it is deliberately thin: the rules must not be re-derived from a directory listing.


def entries_in(store: Path) -> list[Entry]:
    """Every record in the store as `(name, verdict, scope)`.

    An unreadable record is skipped rather than raised on, for the same reason selection skips it:
    a run killed mid-write leaves one, and taking the store down over the newest byte would make
    every good record unreachable.
    """
    if not store.is_dir():
        return []
    found: list[Entry] = []
    for path in sorted(store.glob("*.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        session = document.get(_record.SESSION_BLOCK) or {}
        found.append((path.name, _record.session_verdict_of(document), session.get("scope") or {}))
    return found


def sweep(store: Path) -> tuple[list[str], str | None]:
    """Delete what a later clean run has superseded; report what is left un-drained.

    Called at the **start** of a session, not the end. A run that crashes never reaches its own
    end, and the records worth sweeping are exactly the ones a crashing run keeps producing — so
    pruning on the way out would stop happening precisely when it is needed.
    """
    entries = entries_in(store)
    removed: list[str] = []
    for name in superseded(entries):
        (store / name).unlink(missing_ok=True)
        # The rendered summary is a view of the record, so it goes when the record goes. Leaving it
        # would make `ls` show a session whose evidence no longer exists.
        (store / name).with_suffix(".md").unlink(missing_ok=True)
        removed.append(name)
    return removed, overgrown([e for e in entries if e[0] not in set(removed)])


def warning_for(store: Path) -> str | None:
    """The backlog warning, without deleting anything. What `--gate` prints."""
    return overgrown(entries_in(store))
