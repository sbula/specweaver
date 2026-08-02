# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Diff-safety classification for `scripts/tests.py`'s `--kind refactor` gate.

Split out of `tests.py` (2026-08-02) purely to keep that file under the file-size RED
threshold — no behaviour change, this is a straight extraction. See `refactor_violations`
below for the actual rule.
"""

from __future__ import annotations

import re
import subprocess
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_DOTTED_PATH_TOKEN = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+")
_WHITESPACE_RUN = re.compile(r"\s+")
_WRAPPING_PUNCTUATION = re.compile(r"[()\[\]{},]")


def _joined_with_word_boundaries(lines: list[str]) -> str:
    """Join a hunk's lines with real spaces preserved between them.

    Dotted-path stripping runs on THIS, before any whitespace is removed. Joining with an empty
    separator and stripping whitespace first would glue adjacent words across the join point
    together (`"from specweaver.x"` -> `"fromspecweaver.x"`), making the dotted-path regex
    misidentify `from` as part of the path and over-strip. Word boundaries have to survive long
    enough for the regex to see them.
    """
    return " ".join(lines)


def _parse_hunks(diff_text: str) -> list[tuple[list[str], list[str]]]:
    """`git diff -U0` text -> one (removed_lines, added_lines) pair per `@@ ... @@` hunk."""
    hunks: list[tuple[list[str], list[str]]] = []
    removed: list[str] = []
    added: list[str] = []

    def flush() -> None:
        if removed or added:
            hunks.append((removed[:], added[:]))
        removed.clear()
        added.clear()

    for line in diff_text.splitlines():
        if line.startswith("@@"):
            flush()
        elif line.startswith("+++") or line.startswith("---"):
            continue  # file-identity header, not a removed/added content line
        elif line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    flush()
    return hunks


def _hunk_signature(lines: list[str]) -> str:
    """One logical group of lines, reduced to a dotted-path-stripped, whitespace-free signature.

    Order matters here: dotted-path tokens are stripped FIRST, while spaces still separate words
    (see `_joined_with_word_boundaries`), THEN all whitespace is removed, THEN wrapping
    punctuation. Doing whitespace-removal before path-stripping was the actual bug this ordering
    fixes — see that function's docstring.

    Wrapping punctuation (`()[]{},`) is dropped last. Brackets are already load-bearing for
    GROUPING (bracket depth decides where one logical statement ends — see
    `_logical_line_groups`); once grouping is decided, their literal presence is pure line-wrap
    syntax, not content:
    - `ruff format`'s Black-style convention adds a trailing comma when it reflows a call onto
      multiple lines (`f(x)` -> `f(\\n    x,\\n)`) that the single-line form never had.
    - Python REQUIRES wrapping parens for a multi-line `from x import (...)` that a single-line
      `from x import a, b` never needs — the parens exist only because of the line wrap.
    Neither changes what the statement does, so neither may register as a content change.
    """
    without_paths = _DOTTED_PATH_TOKEN.sub("", _joined_with_word_boundaries(lines))
    without_whitespace = _WHITESPACE_RUN.sub("", without_paths)
    return _WRAPPING_PUNCTUATION.sub("", without_whitespace)


def _logical_line_groups(lines: list[str]) -> list[list[str]]:
    """Split a hunk-side's physical lines into logical statement groups, by bracket depth.

    The unit that must match across a diff is a LOGICAL statement, not a physical line and not a
    whole hunk-side — both are wrong in different, real cases:
    - Too coarse (whole hunk-side as one unit): a hunk can bundle two INDEPENDENT statements that
      happen to fall in the same `git diff -U0` hunk (e.g. an import-sorter relocates one import
      and, in the same hunk, also reflows an unrelated adjacent line) — joining them into one blob
      makes neither independently matchable against a relocation elsewhere in the file.
    - Too fine (every physical line its own unit): a formatter reflowing ONE statement across
      several physical lines (`monkeypatch.setattr(\\n    "...",\\n)`) would then look like N
      unrelated small changes instead of one substitution.

    Bracket depth distinguishes them without a real parser: a line that leaves `(`/`[`/`{` open
    is a continuation, so it merges with the following lines until depth returns to zero. A line
    that opens and closes balanced (the common one-statement-per-line case) is its own group.
    """
    groups: list[list[str]] = []
    current: list[str] = []
    depth = 0
    for line in lines:
        current.append(line)
        depth += sum(line.count(c) for c in "([{")
        depth -= sum(line.count(c) for c in ")]}")
        if depth <= 0:
            groups.append(current)
            current = []
            depth = 0
    if current:
        groups.append(current)
    return groups


def _is_safe_hunk(removed: list[str], added: list[str]) -> bool:
    """True if THIS hunk, considered alone (no cross-hunk matching), is provably safe.

    Thin wrapper around `_is_safe_file_diff` treating the hunk as a one-hunk file — see there for
    the actual rule (logical-group matching). Kept as its own name because "is this one hunk
    self-contained" is a meaningful, separately-tested question even though the implementation is
    shared.
    """
    return _is_safe_file_diff([(removed, added)])


def _is_safe_file_diff(hunks: list[tuple[list[str], list[str]]]) -> bool:
    """Whether a file's WHOLE diff (every hunk together) is provably incapable of hiding a
    weakened assertion.

    A formatter or import-sorter can split what is semantically ONE line-move into two separate
    hunks: an addition at the line's new position and a deletion at its old one (e.g. `ruff`
    resorting imports after a path substitution changes where a line sorts alphabetically), and
    can bundle multiple independent relocations into the SAME hunk alongside each other. Judging
    whole hunk-sides in isolation misses both: a deletion elsewhere in the file that covers it, or
    a bundled sibling statement that needs to match separately. Instead, every hunk's removed and
    added sides are first split into logical groups (`_logical_line_groups` — bracket-depth aware,
    so a formatter's multi-line reflow of ONE statement still counts as one unit), and EVERY
    group across the WHOLE file contributes one signature to its respective multiset. The file is
    safe iff every removed signature has an available matching added signature somewhere in the
    file — duplicates must each be matched individually (a multiset difference, not a set
    difference), so two identical deletions need two identical additions, not one covering both.
    Unmatched added signatures (pure new coverage, anywhere) never block; any unmatched removed
    signature means something existing was lost with nothing provably equivalent replacing it.
    """
    removed_sigs: Counter[str] = Counter()
    added_sigs: Counter[str] = Counter()
    for removed, added in hunks:
        for group in _logical_line_groups(removed):
            sig = _hunk_signature(group)
            if sig:
                removed_sigs[sig] += 1
        for group in _logical_line_groups(added):
            sig = _hunk_signature(group)
            if sig:
                added_sigs[sig] += 1
    return not (removed_sigs - added_sigs)


def _is_import_path_only_change(path: Path, repo_root: Path) -> bool:
    """Whether `path`'s current diff (working tree, else staged) is provably safe as a whole
    file, per `_is_safe_file_diff`.

    No diff found (untracked new file with nothing to compare, or git failure) proves nothing —
    conservative default is "not safe", the same outcome the old any-diff check gave it.
    """
    for extra in ([], ["--cached"]):
        proc = subprocess.run(
            ["git", "diff", "-U0", *extra, "--", path.as_posix()],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return _is_safe_file_diff(_parse_hunks(proc.stdout))
    return False


def refactor_violations(changed: list[Path], repo_root: Path = REPO_ROOT) -> list[Path]:
    """Test files a pure refactor modified in a way that ISN'T provably safe.

    A raw "any diff to a test file" check cannot tell a `git mv`-triggered import-path update, or
    a test file extended with new coverage, from a weakened assertion hiding a bug behind a green
    run. Each candidate's actual diff is checked as a whole file via `_is_safe_file_diff`: a pure
    addition (new test cases, nothing existing touched), a path-only substitution, or a line moved
    by a formatter/import-sorter (split across an addition hunk and a deletion hunk elsewhere in
    the same file) do not block. Any modification or deletion of an existing line with no matching
    counterpart anywhere in the file — or a diff that can't be examined at all — still does.
    """
    candidates = [p for p in changed if p.as_posix().startswith("tests/") and p.suffix == ".py"]
    return [p for p in candidates if not _is_import_path_only_change(p, repo_root)]
