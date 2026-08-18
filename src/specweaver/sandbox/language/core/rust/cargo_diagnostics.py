# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading cargo's own JSON diagnostics.

Cargo emits one JSON object per line under `--message-format=json` — the same stream for
`clippy` and for `build` — so its findings need no conversion. Piping them through an external SARIF converter added a binary that has to be installed
separately — and when it is not, the pipe produces nothing and an empty report reads as a clean
project. Parsing the stream directly removes both the dependency and that silence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

#: cargo interleaves artifact and progress records in the same stream; only diagnostics matter.
_DIAGNOSTIC = "compiler-message"
_REPORTABLE_LEVELS = ("warning", "error")


@dataclass(frozen=True)
class CargoDiagnostic:
    """One diagnostic, with what a reader needs to find it."""

    level: str

    code: str
    message: str
    file: str
    line: int


def parse_cargo_diagnostics(stdout: str) -> list[CargoDiagnostic]:
    """Every reportable diagnostic in a cargo JSON stream.

    A line that does not parse is skipped rather than failing the run: cargo writes progress on the
    same stream, and a malformed line is not a lint verdict.
    """
    findings: list[CargoDiagnostic] = []
    for line in stdout.splitlines():
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(record, dict) or record.get("reason") != _DIAGNOSTIC:
            continue

        message = record.get("message") or {}
        if message.get("level") not in _REPORTABLE_LEVELS:
            continue

        spans = message.get("spans") or []
        first = spans[0] if spans else {}
        findings.append(
            CargoDiagnostic(
                level=message.get("level", ""),
                code=(message.get("code") or {}).get("code", "") or "",
                message=message.get("message", ""),
                file=first.get("file_name", ""),
                line=first.get("line_start", 0),
            )
        )
    return findings
