# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every hook in `.claude/settings.json` runs, the way Claude Code starts it.

Until 2026-11-11 every hook called a bare `python`, which the Claude Code process PATH does not
have: each hook failed with "python: not found", which does not block, so the finished-stories
guard, the session brief and the ruff fix were off and nothing said so (the user, 2026-11-11).

Claude Code runs a hook command through `sh -c`, with `CLAUDE_PROJECT_DIR` set and the JSON event
on stdin. This test does the same, with a PATH that has neither `python` nor `ruff`.

| Bucket | Case |
|---|---|
| Happy | the guard allows an edit outside the registry; the brief prints; ruff fixes a `.py` file |
| Boundary | the guard blocks an edit of a ✅ line with exit 2 — it is on, not only runnable |
| Degradation | a hook naming an interpreter that is not there is reported, not passed |
| Hostile | no hook command calls a bare `python` or `ruff` |
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SETTINGS = REPO / ".claude" / "settings.json"
#: The Claude Code process PATH has no `python` (only `/usr/bin/python3`) and no `ruff`.
_BARE_PATH = "/usr/bin:/bin"


def _commands(event: str) -> list[str]:
    hooks = json.loads(SETTINGS.read_text(encoding="utf-8")).get("hooks", {})
    return [h["command"] for group in hooks.get(event, []) for h in group["hooks"]]


def _run(command: str, event: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", "-c", command],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        timeout=60,
        env={"PATH": _BARE_PATH, "CLAUDE_PROJECT_DIR": str(REPO)},
        check=False,
    )


def _ran(result: subprocess.CompletedProcess[str]) -> bool:
    return result.returncode != 127 and "not found" not in result.stderr


def test_every_event_has_a_hook() -> None:
    assert _commands("PreToolUse") and _commands("PostToolUse") and _commands("SessionStart")


def test_the_guard_allows_an_edit_outside_the_registry() -> None:
    event = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(REPO / "README.md"), "old_string": "a", "new_string": "b"},
    }
    for command in _commands("PreToolUse"):
        result = _run(command, event)
        assert result.returncode == 0, f"{command}\nexit {result.returncode}: {result.stderr}"


def test_the_guard_blocks_an_edit_of_a_finished_line() -> None:
    matrix = REPO / "docs" / "roadmap" / "capability_matrix.md"
    event = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(matrix),
            "old_string": "`✅ B-SENS-02`: Knowledge Graph Builder",
            "new_string": "`✅ B-SENS-02`: Knowledge Graph Builder.",
        },
    }
    for command in _commands("PreToolUse"):
        result = _run(command, event)
        assert result.returncode == 2, f"{command}\nexit {result.returncode}: {result.stderr}"
        assert "BLOCKED by guard_finished_stories" in result.stderr


def test_the_session_brief_prints() -> None:
    for command in _commands("SessionStart"):
        result = _run(command, {})
        assert _ran(result) and result.returncode == 0, f"{command}\n{result.stderr}"
        assert "read before your first change" in result.stdout


def test_the_ruff_hook_fixes_a_python_file(tmp_path: Path) -> None:
    """The hook ends in `|| exit 0`, so its exit code cannot say whether ruff ran; the file can."""
    source = tmp_path / "probe.py"
    for command in _commands("PostToolUse"):
        source.write_text("import os\n\nVALUE = 1\n", encoding="utf-8")
        result = _run(command, {"tool_input": {"file_path": str(source)}})
        assert _ran(result), f"{command}\n{result.stderr}"
        assert "import os" not in source.read_text(encoding="utf-8"), (
            f"ruff did not run: the unused import is still there\n{command}\n{result.stderr}"
        )


def test_a_missing_interpreter_is_reported() -> None:
    result = _run('"$CLAUDE_PROJECT_DIR"/.venv/bin/no-such-python -c pass', {})
    assert not _ran(result)


@pytest.mark.parametrize("event", ["PreToolUse", "PostToolUse", "SessionStart"])
def test_no_hook_calls_a_bare_interpreter(event: str) -> None:
    for command in _commands(event):
        first = command.split()[0]
        assert first not in ("python", "python3", "ruff"), f"bare {first!r} in: {command}"
