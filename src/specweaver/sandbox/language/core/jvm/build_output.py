# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading a JVM build's console output.

Maven writes its own log and the program's output on the same stream, each line of its own prefixed
with a level in brackets. Two things are pulled back out of it: the compiler's diagnostics, which
carry the file and line a caller needs, and the program's own words, which are the lines Maven did
not write.

The diagnostics come in three forms: javac's under Maven, the Kotlin plugin's under Maven, and the
Kotlin compiler's under Gradle (`e:`). Kotlin names the file as a `file://` URI; it is given back as
a path, as javac's is.

The level markers are ANSI-coloured on a terminal, so the prefix is matched after the escapes are
stripped rather than before.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

_ANSI = re.compile(r"\x1b\[[0-9;]*m")

#: The forms that name a location: javac under Maven (`[ERROR] /path/App.java:[3,34] …`), and
#: Kotlin under Maven or Gradle (`[ERROR] file:///path/A.kt:3:11 …`, `e: file:///path/A.kt:3:11 …`).
_DIAGNOSTICS = (
    re.compile(r"^\[ERROR\]\s+(?P<file>\S+?):\[(?P<line>\d+),(?P<column>\d+)\]\s+(?P<message>.+)$"),
    re.compile(
        r"^(?:\[ERROR\]|e:)\s+file://(?P<file>\S+?):(?P<line>\d+):(?P<column>\d+)\s+(?P<message>.+)$"
    ),
)

#: Maven's own lines, and the JVM's.
_TOOL_LINE = re.compile(r"^(\[(?:INFO|WARNING|ERROR|DEBUG)\]|WARNING:|OpenJDK|Picked up )")

#: Maven announces the exec plugin immediately before handing control to the program, so this
#: is where the program's output starts. Filtering by prefix alone is not enough: javac's
#: warnings are echoed unprefixed, and are indistinguishable from a program's own lines.
_EXEC_BANNER = re.compile(r"^\[INFO\]\s+---\s+exec:[^ ]*:java\b")


@dataclass(frozen=True)
class BuildDiagnostic:
    """One compiler error, located."""

    file: str
    line: int
    column: int
    message: str


def _diagnostic(line: str) -> re.Match[str] | None:
    return next((m for pattern in _DIAGNOSTICS if (m := pattern.match(line))), None)


def compile_errors(output: str) -> list[BuildDiagnostic]:
    """Every compiler diagnostic that names a source location.

    Maven's own `Failed to execute goal …` lines are excluded deliberately: they say a goal failed,
    which the exit code already said, and they name no file anyone can go and fix.
    """
    found: list[BuildDiagnostic] = []
    seen: set[tuple[str, int, int]] = set()
    for raw in output.splitlines():
        match = _diagnostic(_ANSI.sub("", raw).strip())
        if match is None:
            continue
        key = (unquote(match["file"]), int(match["line"]), int(match["column"]))
        if key in seen:
            # Maven prints each diagnostic twice — once as it compiles, once in the failure summary.
            continue
        seen.add(key)
        found.append(
            BuildDiagnostic(
                file=key[0],
                line=int(match["line"]),
                column=int(match["column"]),
                message=match["message"].strip(),
            )
        )
    return found


def program_output(stdout: str) -> str:
    """What the program printed, with Maven's log and the JVM's warnings removed.

    Returning the whole stream buried the one line a program printed under forty of build chatter,
    and a program that printed nothing came back looking like it had produced a build log.
    """
    lines = [_ANSI.sub("", raw) for raw in stdout.splitlines()]
    for index, line in enumerate(lines):
        if _EXEC_BANNER.match(line.strip()):
            lines = lines[index + 1 :]
            break
    kept = [line for line in lines if line.strip() and not _TOOL_LINE.match(line.strip())]
    return "\n".join(kept).strip()
