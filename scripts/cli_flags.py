# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every `sw` command with its arguments and flags — the CLI contract (`D-FLOW-04` FR-4).

Read from the real Typer app. `tests/unit/interfaces/cli/test_cli_flag_contract.py` compares it with
`tests/fixtures/cli_flags.json`, so a removed, renamed or added flag is a visible, reviewed change.

Usage:
    python scripts/cli_flags.py           # print the differences from the contract
    python scripts/cli_flags.py --write   # rewrite the contract after an intended change
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

CONTRACT = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "cli_flags.json"


def _walk(command: Any, path: str, out: dict[str, list[str]]) -> None:
    params = []
    for param in command.params:
        if param.param_type_name == "argument":
            params.append(f"<{param.name}>")
        else:
            params.extend([*param.opts, *param.secondary_opts])
    out[path] = sorted(params)
    for name, sub in sorted(getattr(command, "commands", {}).items()):
        _walk(sub, f"{path} {name}", out)


def current_flags() -> dict[str, list[str]]:
    """`{"sw <command>": [arguments and flags]}` for every command, read from the app."""
    import typer

    from specweaver.interfaces.cli.main import app

    found: dict[str, list[str]] = {}
    _walk(typer.main.get_command(app), "sw", found)
    return found


def differences(recorded: dict[str, list[str]], current: dict[str, list[str]]) -> list[str]:
    """`"<command>: + <flag>"` for what is new, `- <flag>` for what is gone, per command."""
    lines = []
    for command in sorted(set(recorded) | set(current)):
        before, after = set(recorded.get(command, [])), set(current.get(command, []))
        lines += [f"{command}: + {flag}" for flag in sorted(after - before)]
        lines += [f"{command}: - {flag}" for flag in sorted(before - after)]
        if command not in current:
            lines.append(f"{command}: command removed")
        elif command not in recorded:
            lines.append(f"{command}: command added")
    return lines


def main(argv: list[str]) -> int:
    current = current_flags()
    if "--write" in argv:
        CONTRACT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Wrote {CONTRACT} ({len(current)} commands)")
        return 0
    recorded = json.loads(CONTRACT.read_text(encoding="utf-8"))
    changes = differences(recorded, current)
    for line in changes:
        print(line)
    return 1 if changes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
