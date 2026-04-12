# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TypeScript parsing utilities for log extraction."""

import re

from specweaver.core.loom.commons.qa_runner.interface import CompileError

# Regex fallback for compiling TS errors from tsc stdout.
# Format: <file>(<line>,<col>): error TS<code>: <msg>
TSC_ERROR_REGEX = re.compile(
    r"^(?P<file>[^\(]+)\((?P<line>\d+),(?P<col>\d+)\):\s+error\s+(?P<code>TS\d+):\s+(?P<msg>.*)$"
)


def extract_tsc_errors(stdout_text: str) -> list[CompileError]:
    """Parse raw standard output from tsc into structured errors."""
    errors: list[CompileError] = []
    for raw_line in stdout_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = TSC_ERROR_REGEX.match(line)
        if match:
            errors.append(
                CompileError(
                    file=match.group("file").strip(),
                    line=int(match.group("line")),
                    column=int(match.group("col")),
                    code=match.group("code").strip(),
                    message=match.group("msg").strip(),
                    is_warning=False,
                )
            )

    return errors
