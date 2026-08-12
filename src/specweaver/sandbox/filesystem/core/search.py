# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Filesystem search operations — ripgrep/fd accelerated with Python fallbacks.

Provides grep and find_files operations used by the FileSystemTool.
Uses ripgrep (rg) and fd when available, falling back to Python stdlib.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.sandbox.execution.executor import SubprocessExecutor

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOOL_TIMEOUT_SECONDS = 10
GREP_FALLBACK_FILE_LIMIT = 1000
READ_FILE_LINE_CAP = 200


# ---------------------------------------------------------------------------
# grep
# ---------------------------------------------------------------------------


def grep_content(
    search_dir: Path,
    pattern: str,
    *,
    context_lines: int = 3,
    case_sensitive: bool = False,
    max_results: int = 20,
    exclude_dirs: set[str] | None = None,
    executor: SubprocessExecutor | None = None,
) -> list[dict[str, Any]]:
    """Search for a pattern in file contents.

    Uses ripgrep (rg) when available, falls back to Python re module.

    Args:
        search_dir: Resolved directory to search.
        pattern: Search pattern (string or regex).
        context_lines: Lines of context before/after each match.
        case_sensitive: Whether to perform case-sensitive search.
        max_results: Maximum number of matches to return.
        executor: Optional SubprocessExecutor for the ripgrep path (DI for
            testability); a default one (cwd=search_dir) is created if omitted.

    Returns:
        List of match dicts with file, line_number, content, context.
        May include a trailing metadata dict with truncated/warning keys.
    """
    results: list[dict[str, Any]]
    truncated: bool
    warning: str

    rg_path = shutil.which("rg")
    if rg_path:
        results, truncated, warning = _grep_ripgrep(
            rg_path,
            search_dir,
            pattern,
            context_lines,
            case_sensitive,
            max_results,
            exclude_dirs,
            executor,
        )
    else:
        logger.info(
            "ripgrep (rg) not found — using Python fallback. "
            "Install ripgrep for better performance: https://github.com/BurntSushi/ripgrep",
        )
        results, truncated, warning = _grep_python(
            search_dir,
            pattern,
            context_lines,
            case_sensitive,
            max_results,
            exclude_dirs,
        )

    if truncated or warning:
        meta: dict[str, Any] = {}
        if truncated:
            meta["truncated"] = True
        if warning:
            meta["warning"] = warning
        results.append(meta)
    return results


def _grep_ripgrep(
    rg_path: str,
    search_dir: Path,
    pattern: str,
    context_lines: int,
    case_sensitive: bool,
    max_results: int,
    exclude_dirs: set[str] | None = None,
    executor: SubprocessExecutor | None = None,
) -> tuple[list[dict[str, Any]], bool, str]:
    """Run grep using ripgrep."""
    cmd = [
        rg_path,
        "--json",
        f"--max-count={max_results}",
        f"-C{context_lines}",
    ]
    if not case_sensitive:
        cmd.append("-i")

    if (search_dir / ".specweaverignore").is_file():
        cmd.append(f"--ignore-file={search_dir / '.specweaverignore'}")

    cmd.extend([pattern, str(search_dir)])

    active_executor = executor or SubprocessExecutor(cwd=search_dir)
    result = active_executor.execute(cmd, timeout_seconds=TOOL_TIMEOUT_SECONDS)
    if result.timed_out:
        return [], True, f"Search timed out after {TOOL_TIMEOUT_SECONDS}s"

    from specweaver.commons import json

    matches: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        try:
            data = json.loads(line)
            if data.get("type") == "match":
                match_data = data["data"]
                file_path = match_data["path"]["text"]
                try:
                    rel_path = str(Path(file_path).relative_to(search_dir))
                except ValueError:
                    rel_path = file_path
                matches.append(
                    {
                        "file": rel_path,
                        "line_number": match_data["line_number"],
                        "content": match_data["lines"]["text"].rstrip("\n"),
                    }
                )
                if len(matches) >= max_results:
                    break
        except (json.JSONDecodeError, KeyError):
            continue

    return matches, len(matches) >= max_results, ""


def _grep_python(
    search_dir: Path,
    pattern: str,
    context_lines: int,
    case_sensitive: bool,
    max_results: int,
    exclude_dirs: set[str] | None = None,
) -> tuple[list[dict[str, Any]], bool, str]:
    """Fallback grep using Python re module."""
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        return [], False, f"Invalid regex pattern: {exc}"

    matches: list[dict[str, Any]] = []
    files_scanned = 0
    truncated = False
    warning = ""

    for file_path in iter_text_files(search_dir, exclude_dirs=exclude_dirs):
        if files_scanned >= GREP_FALLBACK_FILE_LIMIT:
            truncated = True
            warning = f"Python fallback: scanned {GREP_FALLBACK_FILE_LIMIT} files limit reached"
            break

        files_scanned += 1
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for i, line in enumerate(lines):
            if compiled.search(line):
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                try:
                    rel_path = str(file_path.relative_to(search_dir))
                except ValueError:
                    rel_path = str(file_path)
                matches.append(
                    {
                        "file": rel_path,
                        "line_number": i + 1,
                        "content": line,
                        "context_before": lines[start:i],
                        "context_after": lines[i + 1 : end],
                    }
                )
                if len(matches) >= max_results:
                    return matches, True, warning

    return matches, truncated, warning


# ---------------------------------------------------------------------------
# find_files
# ---------------------------------------------------------------------------


def _candidates_in(
    root_path: Path, dirs: list[str], files: list[str], file_type: str
) -> list[Path]:
    """The entries in one walked directory that the requested `file_type` admits."""
    items: list[Path] = []
    if file_type in ("directory", "any"):
        items.extend(root_path / d for d in dirs)
    if file_type in ("file", "any"):
        items.extend(root_path / f for f in files)
    return items


def _relative_to(item: Path, search_dir: Path) -> str:
    """The path as reported to the caller — relative when it can be, absolute when it cannot."""
    try:
        return str(item.relative_to(search_dir))
    except ValueError:
        return str(item)


def _glob_entry(item: Path, rel_path_str: str) -> dict[str, Any]:
    """One match, with its size when it is a readable file.

    A size of 0 on `OSError` is deliberate and pre-existing: a match the caller cannot stat is
    still a match, and a broken symlink should not abort the whole search.
    """
    entry: dict[str, Any] = {
        "path": rel_path_str,
        "type": "directory" if item.is_dir() else "file",
    }
    if item.is_file():
        try:
            entry["size_bytes"] = item.stat().st_size
        except OSError:
            entry["size_bytes"] = 0
    return entry


def _matches_glob(item: Path, rel_path_str: str, pattern: str) -> bool:
    """Match on the relative path OR the bare name, so `*.py` and `a/b/*.py` both work."""
    import fnmatch

    return fnmatch.fnmatch(rel_path_str, pattern) or fnmatch.fnmatch(item.name, pattern)


def _walk_candidates(
    search_dir: Path, file_type: str, exclude_set: set[str]
) -> Iterator[tuple[Path, str]]:
    """Every admissible entry under `search_dir`, with the path string the caller will see.

    A generator rather than a nested loop inside the search: the truncation break then applies to
    one loop instead of two, which is what the `break`-then-`if truncated: break` dance existed to
    work around.
    """
    import os

    for root_str, dirs, files in os.walk(search_dir):
        if exclude_set:
            dirs[:] = [d for d in dirs if d not in exclude_set and not d.startswith(".")]
        for item in _candidates_in(Path(root_str), dirs, files, file_type):
            yield item, _relative_to(item, search_dir)


def find_by_glob(
    search_dir: Path,
    pattern: str,
    *,
    file_type: str = "any",
    max_results: int = 30,
    exclude_dirs: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Find files matching a glob pattern.

    Args:
        search_dir: Resolved directory to search.
        pattern: Glob pattern to match (e.g., '*.py', 'context.yaml').
        file_type: Filter by type: 'file', 'directory', or 'any'.
        max_results: Maximum number of results.

    Returns:
        List of file dicts with path, type, size_bytes.
    """
    results: list[dict[str, Any]] = []
    truncated = False

    try:
        for item, rel_path_str in _walk_candidates(search_dir, file_type, exclude_dirs or set()):
            if not _matches_glob(item, rel_path_str, pattern):
                continue
            results.append(_glob_entry(item, rel_path_str))
            if len(results) >= max_results:
                truncated = True
                break
    except OSError as exc:
        return [{"error": str(exc)}]

    if truncated:
        results.append({"truncated": True, "warning": f"Results limited to {max_results}"})
    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def iter_text_files(directory: Path, exclude_dirs: set[str] | None = None) -> list[Path]:
    """Iterate over text files in a directory, skipping binary and hidden files."""
    text_extensions = {
        ".py",
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".cfg",
        ".ini",
        ".rst",
        ".html",
        ".css",
        ".js",
        ".ts",
        ".sh",
        ".bat",
        ".ps1",
        ".xml",
        ".csv",
    }
    import os

    exclude_set = exclude_dirs or set()
    files: list[Path] = []
    try:
        for root_str, dirs, file_names in os.walk(directory):
            # Prune directories
            dirs[:] = [d for d in dirs if d not in exclude_set and not d.startswith(".")]

            root_path = Path(root_str)
            for f in file_names:
                if f.startswith("."):
                    continue
                item = root_path / f
                if item.suffix.lower() in text_extensions:
                    files.append(item)
    except OSError:
        pass
    return sorted(files)
