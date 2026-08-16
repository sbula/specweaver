# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Detect a test run that rewrote a gate's ratchet baseline.

`scripts/baselines/` holds one version-controlled file per gate — the uncited-FR count, the
duplication clone count, the delivered-claims ratchet, the mutation ledger. They are the standard
the repo is measured against, and **nothing compares a baseline against what it used to be**. A test
that writes one therefore relaxes or corrupts a gate inside a diff that looks like ordinary test
work.

Used by `tests/conftest.py::_baselines_are_read_only`, which snapshots before and after every test.
The whole directory hashes in about 0.12 ms, so two snapshots per test cost roughly two seconds
across the full suite, spread over the xdist workers.

Deliberately not a fixture and not a gate script: the logic lives here so it can be tested directly
(`tests/unit/test_baseline_write_guard.py`), leaving the fixture thin enough to read in one glance.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The ratchet set. Named here so the fixture and its tests cannot drift to different directories.
BASELINES = REPO_ROOT / "scripts" / "baselines"


def snapshot(directory: Path) -> dict[str, str]:
    """Every file under `directory`, keyed by its relative path, valued by `<sha256>@<mtime_ns>`.

    **Both halves, and the second one was added on evidence.** Content alone answers "did a gate's
    standard move", which is the damage; it does not answer "did a test write here", which is the
    act. `record_run` rewrites the mutation ledger byte-identically whenever there is nothing to
    report, so a caller that had been overwriting it on every suite run stayed invisible to a
    content-only guard — and would have surfaced only on the day a finding existed, which is the one
    day the file's contents matter. Found by hand in `test_mutation_nightly.py`; a guard that needs
    somebody to notice a stray `M` in `git status` is the thing this replaces.

    `mtime_ns` changes on write and not on read, so it flags the act without flagging inspection.

    Raises `FileNotFoundError` when the directory is absent rather than returning an empty mapping.
    An empty snapshot compares equal to the next empty snapshot, so a missing directory would
    silently disarm the guard — the `TECH-032` failure mode, where a checker that cannot find its
    subject reports success.

    Recursive, though the directory is flat today: a guard that assumes flatness stops seeing the
    first file somebody moves into a subdirectory for tidiness.
    """
    if not directory.is_dir():
        raise FileNotFoundError(f"baseline directory not found: {directory}")

    return {
        path.relative_to(directory).as_posix(): (
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}@{path.stat().st_mtime_ns}"
        )
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def rewrites(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """One line per baseline added, deleted or written to — every one, not just the first.

    A report that names one of three rewritten files sends its reader back for two more runs.

    "changed" and "rewritten with identical content" are separate messages because they are separate
    problems: the first moved a gate's standard, the second is a latent writer that will move it as
    soon as it has something to say.
    """
    reported = []
    for name, stamp in before.items():
        if name not in after:
            reported.append(f"{name}: deleted")
        elif after[name] != stamp:
            same_content = after[name].split("@")[0] == stamp.split("@")[0]
            reported.append(
                f"{name}: rewritten with identical content" if same_content else f"{name}: changed"
            )
    reported += [f"{name}: added" for name in after if name not in before]
    return sorted(reported)
