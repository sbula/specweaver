#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The `mutation.py` sub-commands that do not run a corpus.

`--confirm`, `--gate`, `--install-timer` and `--summary` share nothing with the session runner
except an argument parser. They read files, print prose and return an exit code; the runner builds
worktrees and judges mutants. Splitting them is the same seam `_mutation_timer.py` was split on,
arriving from the other direction — and `mutation.py` reached its 600-line ceiling exactly, so the
next honest addition had to be an extraction rather than another comment cut.

Public names on purpose. `mutation.py` calls them; nothing else should.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _sibling(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parent / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_gate = _sibling("_mutation_gate")
_report = _sibling("_session_record")
_reach = _sibling("_run_reach")
_store = _sibling("_record_store")
_timer = _sibling("_mutation_timer")

install_timer = _timer.install_timer
UNIT_NAME = _timer.UNIT_NAME


def cmd_confirm(args: Any, ap: Any) -> int:
    """Record one decision. `--as` and `--why` are both required, and that is the point."""
    if not args.disposition or not args.why:
        ap.error("--confirm needs --as <disposition> and --why <reason>")
    try:
        _gate.confirm(Path(args.ledger), args.confirm, disposition=args.disposition, why=args.why)
    except ValueError as exc:
        print(f"could not confirm: {exc}", file=sys.stderr)
        return 2
    print(f"{args.confirm}: {args.disposition} — {args.why}")
    return 0


def cmd_gate(args: Any) -> int:
    """Blocked or clear, and when blocked, exactly what to do about it."""
    # `.tmp/` is invisible to every gate in this repo — the handover reached 23 MB there before
    # anyone noticed — so the backlog is said out loud here as well as by the run.
    backlog = _store.warning_for(Path(args.out))
    if backlog:
        print(f"WARNING: {backlog}")
    result = _gate.gate_store(
        Path(args.out), Path(args.ledger), current_tree_sha=_reach.current_tree_sha()
    )
    if not result.blocked:
        print(f"CLEAR: {result.reason}")
        return 0
    print(f"BLOCKED: {result.reason}")
    for finding in result.unconfirmed:
        print(f"  unconfirmed: {finding}")
    if result.unconfirmed:
        # Only when there is something to confirm. A block on staleness or a red baseline is not
        # fixed by recording a disposition, and offering that sends the reader nowhere.
        print("\nconfirm with: mutation.py --confirm '<id>' --as <disposition> --why '<why>'")
    return 1


def cmd_install() -> int:
    for path in install_timer():
        print(f"wrote {path}")
    print(f"enable with: systemctl --user enable --now {UNIT_NAME}.timer")
    return 0


def cmd_summary(store: Path) -> int:
    """Re-render the record that answers for the corpus. Reads nothing else and runs nothing."""
    report = _gate.latest_covering_record(store)
    if report is None:
        print(f"no record in {store} answers for the corpus — run it first", file=sys.stderr)
        return 1
    print(_report.render_summary(json.loads(report.read_text(encoding="utf-8"))))
    return 0


def announce_sweep(store: Path) -> None:
    """Prune the store and say what happened. Printing is this layer's job, not the runner's.

    Two lines in `main` took it past its cognitive-complexity ceiling, which is the gate saying the
    same thing: deciding what to run and narrating it are different concerns.
    """
    swept, backlog = _store.sweep(store)
    if swept:
        print(f"swept {len(swept)} superseded record(s) from {store}")
    if backlog:
        print(f"WARNING: {backlog}")
