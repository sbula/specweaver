# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""PreToolUse guard: finished roadmap stories are IMMUTABLE.

Blocks Edit calls whose old_string touches a line carrying a finished marker
("✅", or a completed story header "### 🟢") inside the roadmap REGISTRY files
(master_story_roadmap.md, capability_matrix.md, topics/**), and blocks full-file
Writes (overwrites) of those registry files. Everything else — including working
docs under docs/roadmap/features/** (task.md, design trackers, walkthroughs) —
is untouched.

Rule of record: changes to delivered behavior are minted as NEW stories
(C-XXX / TECH-XXX); traceability flows new -> old, never old -> new.

Escape hatches for an explicitly user-approved correction:
    - env var SW_ALLOW_FINISHED_EDIT=1 (session-wide, set before launching Claude Code), or
    - single-use flag file `.claude/hooks/.allow-finished-edit` (consumed+deleted on first
      allowed operation) — create it only on the user's explicit say-so.

Contract: Claude Code PreToolUse hook — stdin JSON {tool_name, tool_input};
exit 0 = allow, exit 2 + stderr = block (message is shown to the model).
"""

from __future__ import annotations

import json
import os
import sys

REGISTRY_PREFIXES = ("master_story_roadmap.md", "capability_matrix.md", "topics/")
FINISHED_MARKERS = ("✅", "### \U0001f7e2")  # ✅ anywhere, or a 🟢 story header


def _registry_relpath(file_path: str) -> str | None:
    """Return the path relative to docs/roadmap/ if inside the registry scope, else None."""
    normalized = file_path.replace("\\", "/")
    marker = "docs/roadmap/"
    idx = normalized.rfind(marker)
    if idx < 0:
        return None
    rel = normalized[idx + len(marker) :]
    return rel if rel.startswith(REGISTRY_PREFIXES) else None


def _block(message: str) -> int:
    # ASCII-safe stderr: Windows consoles may be cp1252; never crash the guard itself.
    sys.stderr.write(message.encode("ascii", "backslashreplace").decode("ascii") + "\n")
    return 2


def main() -> int:
    if os.environ.get("SW_ALLOW_FINISHED_EDIT") == "1":
        return 0
    # Single-use flag file: consumed (deleted) on first use so approval never lingers.
    flag = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".allow-finished-edit")
    if os.path.exists(flag):
        try:
            os.remove(flag)
        except OSError:
            pass
        return 0
    try:
        # Read bytes and decode UTF-8 explicitly — Claude Code sends UTF-8 JSON, but
        # sys.stdin on Windows may default to cp1252 and mangle the finished markers.
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except Exception:
        return 0  # never break tooling on malformed input
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    rel = _registry_relpath(file_path)
    if rel is None:
        return 0

    if tool == "Edit":
        old = tool_input.get("old_string") or ""
        if any(m in old for m in FINISHED_MARKERS):
            return _block(
                f"BLOCKED by guard_finished_stories: this Edit to docs/roadmap/{rel} modifies "
                "text containing a finished-story marker (checkmark / completed-story header). "
                "Finished stories are IMMUTABLE - no edits, not even annotations. Mint a NEW "
                "story (C-XXX capability or TECH-XXX) and put all cross-references there "
                "instead. If the user has explicitly approved a correction to a finished "
                "entry, retry with SW_ALLOW_FINISHED_EDIT=1."
            )
        return 0

    if tool == "Write" and os.path.exists(file_path):
        return _block(
            f"BLOCKED by guard_finished_stories: full-file Write would overwrite the roadmap "
            f"registry file docs/roadmap/{rel}, which contains finished-story entries. Use "
            "targeted Edit calls (non-finished lines only). For a user-approved exception, "
            "retry with SW_ALLOW_FINISHED_EDIT=1."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
