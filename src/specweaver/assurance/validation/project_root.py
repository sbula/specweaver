# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The folders above a file that a rule may search, never above the run's project root, and the
test file of a code file found there."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.commons.languages import language_of, name_tests_for, root_of_tests

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def walk_up(start: Path, stop: Path | None) -> Iterator[Path]:
    """`start`, then each parent, ending at `stop` (the filesystem root when `stop` is None).

    A `start` outside `stop` yields only its own folders up to where it would pass `stop`'s level,
    so nothing above the project is ever searched.
    """
    boundary = stop.resolve() if stop is not None else None
    current = start
    while True:
        yield current
        parent = current.parent
        if parent == current:
            return
        if boundary is not None and not parent.resolve().is_relative_to(boundary):
            return
        current = parent


def find_tests(code_path: Path, stop: Path | None) -> Path | str:
    """The test file of `code_path` by its language's convention, or why there is none.

    From the file's folder up to `stop`, the first `<folder>/<tests root>` holding the test file's
    name wins; any depth below it, except Rust, whose tests are only the files directly in `tests/`.
    """
    language = language_of(code_path)
    root = root_of_tests(language) if language else None
    name = name_tests_for(code_path.name, language) if language else None
    if root is None or name is None:
        return f"no test convention for {language or code_path.suffix or code_path.name}"
    for folder in walk_up(code_path.parent, stop):
        tests_dir = folder / root
        if not tests_dir.is_dir():
            continue
        if language == "rust":
            if (tests_dir / name).is_file():
                return tests_dir / name
            continue
        found = sorted(tests_dir.rglob(name))
        if found:
            return found[0]
    return f"No test file '{name}' found"
