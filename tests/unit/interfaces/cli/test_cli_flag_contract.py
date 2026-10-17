# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every `sw` command keeps its arguments and flags; a change to one is deliberate and visible.

Proves: D-FLOW-04 FR-4

The commands are read from the real Typer app. The contract is `tests/fixtures/cli_flags.json`;
after an intended change, rewrite it with `python scripts/cli_flags.py --write` and review the diff.

| Bucket | Case |
|---|---|
| Happy | every command's flags match the recorded contract |
| Boundary | a short alias (`-p`) counts as part of its flag |
| Degradation | not applicable — the app is built in-process, with nothing to fail |
| Hostile | a removed, renamed or unrecorded flag, and a removed command, are each named |
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
CONTRACT = REPO_ROOT / "tests" / "fixtures" / "cli_flags.json"


def _flags() -> object:
    path = REPO_ROOT / "scripts" / "cli_flags.py"
    spec = importlib.util.spec_from_file_location("cli_flags", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cli_flags"] = module
    spec.loader.exec_module(module)
    return module


def test_every_command_keeps_its_flags() -> None:
    recorded = json.loads(CONTRACT.read_text(encoding="utf-8"))

    current = _flags().current_flags()

    removed = sorted(set(recorded) - set(current))
    added = sorted(set(current) - set(recorded))
    changed = sorted(c for c in set(recorded) & set(current) if recorded[c] != current[c])
    assert (removed, added, changed) == ([], [], []), (
        "CLI contract changed — if intended, run `python scripts/cli_flags.py --write`"
    )


def test_the_contract_names_the_flags_users_rely_on() -> None:
    recorded = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert "--project" in recorded["sw implement"]
    assert "--model" in recorded["sw run"]
    assert "--console" in recorded["sw config set-log-level"]


def test_a_removed_flag_is_named(tmp_path: Path) -> None:
    module = _flags()
    current = module.current_flags()
    edited = {**current, "sw implement": [f for f in current["sw implement"] if f != "--project"]}

    assert module.differences(edited, current) == ["sw implement: + --project"]
