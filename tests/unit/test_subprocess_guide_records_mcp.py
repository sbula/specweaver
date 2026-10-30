# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The subprocess guide records MCP's raw `Popen`: why, and the env filter it still applies.

Proves: TECH-087 FR-18

`MCPExecutor` is the one `src` module that may start a process without `SubprocessExecutor`. A
developer reading the guide should find the exception, the reason and the safeguard in one place.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_GUIDE = _ROOT / "docs" / "dev_guides" / "subprocess_execution.md"


def _text() -> str:
    assert _GUIDE.is_file(), _GUIDE
    return " ".join(_GUIDE.read_text(encoding="utf-8").split())


def test_the_guide_names_the_exception_its_reason_and_its_env_filter() -> None:
    text = _text()
    for needle in ("`MCPExecutor`", "`subprocess.Popen`", "JSON-RPC pipe", "`build_child_env`"):
        assert needle in text, needle


def test_the_guide_names_the_only_noqa_left_in_src() -> None:
    hits = [
        p.relative_to(_ROOT).as_posix()
        for p in (_ROOT / "src").rglob("*.py")
        if "noqa: TID251" in p.read_text(encoding="utf-8")
    ]

    assert hits == ["src/specweaver/sandbox/mcp/core/executor.py"]
