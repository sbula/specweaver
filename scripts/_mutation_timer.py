#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The nightly timer: two systemd user units, generated rather than checked in.

Split out of `mutation.py` when that file crossed the 451-line YELLOW — the same accretion the
report was split out to avoid, arriving from the other direction. Scheduling is its own concern:
nothing here knows what a mutant is.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


#: Where the units land. `~/.config/systemd/user` is outside the repository, which is why the repo
#: ships the content and an installer rather than the installed file itself.
USER_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"
UNIT_NAME = "specweaver-mutation"


def timer_units() -> dict[str, str]:
    """The `.service` and `.timer` bodies, generated rather than checked in.

    Generated because two values must be right at install time and cannot be known when the file is
    written: the absolute interpreter and the absolute repository path. systemd has no useful
    `PATH`, and a bare `python` would find whichever interpreter the login shell happened to leave
    around — the project already lost four full-suite runs to exactly that mistake, and a timer
    would never notice at all.

    `PY_COLORS=0` is set here for the same reason it is set in the sandbox: a timer inherits
    whatever environment systemd hands it, and a colour-forcing variable would silently turn every
    nightly verdict back into `SURVIVED`. That was this ticket's first defect; this is the one place
    nobody would think to look for it again.
    """
    python = sys.executable
    service = f"""[Unit]
Description=SpecWeaver nightly mutation session
Documentation=file://{REPO_ROOT}/docs/dev_guides/writing_mutation_campaigns.md

[Service]
Type=oneshot
WorkingDirectory={REPO_ROOT}
Environment=PY_COLORS=0
# A user service inherits a minimal PATH without `.venv/bin`. Python starts anyway, because
# ExecStart names the interpreter absolutely — but the suite shells out to a bare `tach`, and
# without it that is a collection error, which makes the baseline red while naming no failing test.
Environment=PATH={REPO_ROOT}/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
# A user service starts with `nofile` soft-limited to 1024, where a login shell gets 524288.
# `pytest -n auto` is one worker per core, and between them 1024 descriptors run out — as roughly
# 690 OSErrors scattered across unrelated unit tests, none of which fail alone or in any pair of
# tiers. Raising only this takes the baseline from red to green.
LimitNOFILE=65536
ExecStart={python} {REPO_ROOT}/scripts/mutation.py --corpus-dir docs/roadmap/features
"""
    timer = f"""[Unit]
Description=Run the SpecWeaver mutation corpus nightly

[Timer]
OnCalendar=*-*-* 03:00
Persistent=true
Unit={UNIT_NAME}.service

[Install]
WantedBy=timers.target
"""
    return {"service": service, "timer": timer}


def install_timer(target: Path | None = None) -> list[Path]:
    """Write the units where systemd will find them, and say what was written.

    Idempotent: the content is a pure function of the interpreter and the repository path, so
    re-running writes identical bytes. A failure to create the directory is raised rather than
    swallowed — a timer nobody notices is missing is worse than one that never installed.
    """
    directory = target or USER_UNIT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    units = timer_units()
    written = []
    for suffix, body in (("service", units["service"]), ("timer", units["timer"])):
        path = directory / f"{UNIT_NAME}.{suffix}"
        path.write_text(body, encoding="utf-8")
        written.append(path)
    return written
