#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a mutation session may answer for, and over which tree.

Two facts a record must carry, and neither can be recovered from the record's contents afterwards.

## Reach

`--corpus <one file>` writes a record shaped **exactly** like the nightly's — same block, same
mutant list, same everything. Read at the path the gate watches, a 51-mutant by-hand run answered
for a 187-mutant nightly on 2026-08-27, and nothing in the document said otherwise.

So the run states its own reach. Coverage is *which corpora it was pointed at*, never how many
mutants came back: a rule counting mutants blocks every day somebody adds one, and `TECH-056`
`NFR-1` is explicit that a gate blocking on ordinary work gets switched off within a week.

## Tree

`_build_sandbox` makes the sandbox HEAD **plus** `git diff HEAD` **plus** every untracked file, so
a run measures the tree you actually have. That is a feature — and it means a dirty verdict names
no commit, so nobody can re-derive it later.

The fingerprint is what makes it usable anyway: uncommitted work stays admissible for exactly as
long as it is still there. Both halves are hashed, because the sandbox carries both, and a helper
existing only in the working tree once made every importing file fail to collect.

**One function, two callers.** The producer stamps it and the gate re-takes it. Two places
computing one fact is how a record and its reader came to disagree about where the baseline lived.
"""

from __future__ import annotations

import importlib.util
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


_mutate = _sibling("_mutate")
_record = _sibling("_session_record")


def scope_of(*, full_sweep: bool, paths: list[Path]) -> dict[str, Any]:
    """The run's own statement of what it covered."""
    if full_sweep:
        return {"kind": "full"}
    return {"kind": "scoped", "corpora": sorted(p.name for p in paths)}


def tree_sha() -> str:
    """Fingerprint the tree a session measures: the tracked diff plus every untracked file."""
    untracked = {
        name: (REPO_ROOT / name).read_text(encoding="utf-8", errors="replace")
        for name in _mutate._run(
            ["git", "ls-files", "--others", "--exclude-standard"], REPO_ROOT
        ).split()
        if (REPO_ROOT / name).is_file()
    }
    return str(
        _record.working_tree_sha(_mutate._run(["git", "diff", "HEAD"], REPO_ROOT), untracked)
    )


def current_tree_sha() -> str | None:
    """The tree as it is now, or `None` if it cannot be read.

    `None` is not "unchanged". The gate treats an unreadable tree as a reason to block, because a
    fingerprint it could not take is a comparison it cannot make — and a missing measurement
    counting as a pass is the failure this whole gate keeps circling.
    """
    try:
        return tree_sha()
    except Exception:
        return None
