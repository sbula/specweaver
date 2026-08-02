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
_WORD_TOKEN = re.compile(r"[A-Za-z_]\w*")


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


def _signature_from_text(text: str) -> str:
    """The dotted-path-stripped, whitespace-free, punctuation-free reduction shared by
    `_hunk_signature` (fresh diff text) and the single-token-rename closure check (substituted
    text) — see `_hunk_signature` for why the three strips run in this exact order."""
    without_paths = _DOTTED_PATH_TOKEN.sub("", text)
    without_whitespace = _WHITESPACE_RUN.sub("", without_paths)
    return _WRAPPING_PUNCTUATION.sub("", without_whitespace)


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
    return _signature_from_text(_joined_with_word_boundaries(lines))


def _normalized_group_text(group: list[str]) -> str:
    """A logical group's lines collapsed to one whitespace-normalized string — unlike
    `_hunk_signature`, paths and punctuation are NOT stripped here, because the single-token-rename
    inference below needs to see and diff literal tokens (e.g. `nodes` vs `graph_nodes`), not a
    signature that has already erased word content."""
    return _WHITESPACE_RUN.sub(" ", _joined_with_word_boundaries(group)).strip()


def _surviving_candidates(
    removed_idx: int,
    removed_token_lists: list[list[str]],
    added_token_lists: list[list[str]],
    used_added_indices: set[int],
    rename_map: dict[str, str],
) -> list[tuple[int, tuple[str, str]]]:
    """Every added index still usable that differs from `removed_idx`'s tokens in EXACTLY one
    position, excluding candidates whose implied pair conflicts with `rename_map`'s current state
    — see `_infer_token_rename_map` for why this filtering is fixpoint-driven, not one-shot."""
    removed_tokens = removed_token_lists[removed_idx]
    out: list[tuple[int, tuple[str, str]]] = []
    for added_idx, added_tokens in enumerate(added_token_lists):
        if added_idx in used_added_indices or len(removed_tokens) != len(added_tokens):
            continue
        diffs = [(r, a) for r, a in zip(removed_tokens, added_tokens, strict=True) if r != a]
        if len(diffs) != 1:
            continue
        old_token, new_token = diffs[0]
        if old_token in rename_map and rename_map[old_token] != new_token:
            continue  # conflicts with an already-established mapping — not a real candidate
        out.append((added_idx, (old_token, new_token)))
    return out


def _infer_token_rename_map(
    removed_texts: list[str], added_texts: list[str]
) -> dict[str, str] | None:
    """Pair every removed leftover text with a DISTINCT added leftover text that differs from it
    in EXACTLY one identifier-shaped token, and collect those (old_token, new_token) pairs into a
    rename map — refusing (returning `None`) the moment any removed text ends up with zero or
    more than one candidate that survives filtering against pairs already established, or a
    candidate that conflicts with one already collected.

    This intentionally allows MULTIPLE simultaneous renames in the same file (e.g. `nodes` ->
    `graph_nodes` on most lines and `edges` -> `graph_edges` on one line, both parts of the same
    table-prefix rename) — an earlier single-global-pair design rejected that real, non-hypothetical
    shape as "ambiguous" even though every individual line was unambiguously explained.

    Resolution runs as a FIXPOINT, not a single left-to-right pass, because with multiple
    simultaneous renames a removed line can have a genuinely ambiguous candidate set on its own
    (two same-length, one-token-different added lines, each implying a DIFFERENT substitution) that
    only resolves once ANOTHER, less coincidentally-shaped line has already pinned down one of
    those substitutions. The real case this fixes: `cursor.execute("SELECT COUNT(*) FROM
    nodes;")` is the same token length as, and differs in exactly one position from, BOTH its true
    counterpart (`...FROM graph_nodes;`) AND an unrelated line from a DIFFERENT simultaneous rename
    (`...FROM graph_edges;`) — resolvable only after `edges -> graph_edges` is independently
    established elsewhere and used to filter out the spurious cross-candidate. Each fixpoint round
    locks in only the removed lines whose SURVIVING candidate set (after filtering out anything
    that conflicts with already-established pairs) reduces to exactly one distinct pair; repeat
    until no more progress. A removed line still unresolved when the fixpoint settles — or one that
    has zero candidates the moment its only matches get consumed by other lines — is genuinely
    unexplained or ambiguous, and this returns `None`. That is the load-bearing guard against
    laundering a real behaviour change as a fake rename: a bug-hiding edit essentially never
    reduces to "every changed line pairs uniquely with some added line via one consistent,
    fixpoint-derivable global mapping" — and if it somehow did, `_is_safe_file_diff`'s closure
    check after this still re-verifies the full multiset, not just this per-line discovery.

    `_WORD_TOKEN` matches identifier-shaped tokens only (`[A-Za-z_]\\w*`) — NOT bare numeric
    literals. The regression this specifically fixes: `assert result == 5` -> `assert result ==
    3` alongside an unrelated genuine rename elsewhere in the same leftover set. With digits
    treated as tokens, `('5', '3')` was inferred as a rename candidate and the closure check then
    rewrote the weakened assertion into matching the new expected value, laundering exactly the bug
    this gate exists to catch. Excluding digit-only tokens from candidacy makes a value change
    invisible to this inference entirely.
    """
    removed_token_lists = [_WORD_TOKEN.findall(text) for text in removed_texts]
    added_token_lists = [_WORD_TOKEN.findall(text) for text in added_texts]

    rename_map: dict[str, str] = {}
    used_added_indices: set[int] = set()
    resolved_removed_indices: set[int] = set()

    made_progress = True
    while made_progress:
        made_progress = False
        for removed_idx in range(len(removed_texts)):
            if removed_idx in resolved_removed_indices:
                continue
            candidates = _surviving_candidates(
                removed_idx,
                removed_token_lists,
                added_token_lists,
                used_added_indices,
                rename_map,
            )
            if not candidates:
                return None  # no viable match remains — unexplained, not a rename
            distinct_pairs = {pair for _idx, pair in candidates}
            if len(distinct_pairs) != 1:
                continue  # still ambiguous this round — may resolve after others lock in
            added_idx, (old_token, new_token) = candidates[0]
            rename_map[old_token] = new_token
            used_added_indices.add(added_idx)
            resolved_removed_indices.add(removed_idx)
            made_progress = True

    if len(resolved_removed_indices) != len(removed_texts):
        return None  # fixpoint settled with genuine, unresolvable ambiguity left over

    return rename_map or None


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
    signature means something existing was lost with nothing provably equivalent replacing it —
    UNLESS the entire remaining gap closes under one or more consistent literal-token renames (see
    `_infer_token_rename_map`): identifiers renamed consistently across every touched line, which
    cannot be a dotted-path relocation (the pattern above already covers that) but is just as
    provably safe when the closure is exact and total.
    """
    removed_sigs: Counter[str] = Counter()
    added_sigs: Counter[str] = Counter()
    removed_raw_by_sig: dict[str, list[str]] = {}
    added_raw_by_sig: dict[str, list[str]] = {}

    for removed, added in hunks:
        for group in _logical_line_groups(removed):
            sig = _hunk_signature(group)
            if sig:
                removed_sigs[sig] += 1
                removed_raw_by_sig.setdefault(sig, []).append(_normalized_group_text(group))
        for group in _logical_line_groups(added):
            sig = _hunk_signature(group)
            if sig:
                added_sigs[sig] += 1
                added_raw_by_sig.setdefault(sig, []).append(_normalized_group_text(group))

    residual_removed = removed_sigs - added_sigs
    if not residual_removed:
        return True

    residual_added = added_sigs - removed_sigs
    removed_leftover_texts = [
        text for sig, count in residual_removed.items() for text in removed_raw_by_sig[sig][:count]
    ]
    added_leftover_texts = [
        text for sig, count in residual_added.items() for text in added_raw_by_sig[sig][:count]
    ]

    rename_map = _infer_token_rename_map(removed_leftover_texts, added_leftover_texts)
    if rename_map is None:
        return False

    pattern = re.compile(r"\b(" + "|".join(re.escape(old) for old in rename_map) + r")\b")
    substituted_sigs: Counter[str] = Counter()
    for text in removed_leftover_texts:
        substituted_text = pattern.sub(lambda m: rename_map[m.group(0)], text)
        substituted_sigs[_signature_from_text(substituted_text)] += 1

    return not (substituted_sigs - residual_added)


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
