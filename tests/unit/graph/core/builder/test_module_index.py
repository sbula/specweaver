# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Imports resolve through an index built once per build, with the same answers as before.

Proves: TECH-070 FR-1

The old resolution compared every import with every collected file: on Kafka, 96,027 imports by
6,623 files, 96% of a 503 s build (profiled 2026-11-11). The index is built once and each import is
a lookup. The answers must not change (the user, 2026-11-11), so the old scan is kept here as the
reference and the index is checked against it.

| Bucket | Case |
|---|---|
| Happy | 3,000 generated imports over 6 generated file sets give the reference's answer |
| Boundary | a package `__init__`, a dot in a directory, a file with no suffix, case and backslashes |
| Degradation | an empty file set resolves nothing; a module naming nothing resolves nothing |
| Hostile | the index reads the file set once, however many imports follow; a build makes one index |
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.graph.core.builder import mapper as mapper_module
from specweaver.graph.core.builder.mapper import ModuleIndex, _module_segments, resolve_module
from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine

if TYPE_CHECKING:
    from pathlib import Path


def _reference(module: str, known_files: frozenset[str]) -> str | None:
    """The resolution before the index: every import against every file."""

    def matches(candidate: str, stem: str) -> bool:
        for tail in (stem, f"{stem}/__init__"):
            without_suffix = candidate.rsplit(".", 1)[0]
            if without_suffix == tail or without_suffix.endswith(f"/{tail}"):
                return True
        return False

    segments = _module_segments(module)
    if not segments:
        return None
    lowered = {path.replace("\\", "/").lower(): path for path in known_files}
    for start in range(len(segments)):
        stem = "/".join(segments[start:]).lower()
        found = {original for lower, original in lowered.items() if matches(lower, stem)}
        if len(found) == 1:
            return found.pop()
        if found:
            return None
    return None


_PARTS = ["src", "main", "alpha", "Beta", "gamma", "pkg", "a.b", "util", "__init__", "kafka"]
_ENDINGS = [".py", ".rs", ".java", ".kt", "", ".d.ts"]


def _file_set(rng: random.Random) -> frozenset[str]:
    files = set()
    for _ in range(rng.randint(5, 60)):
        path = "/".join(rng.choice(_PARTS) for _ in range(rng.randint(1, 4)))
        path += rng.choice(_ENDINGS)
        files.add(path.replace("/", "\\") if rng.random() < 0.1 else path)
    return frozenset(files)


def _module(rng: random.Random) -> str:
    separator = rng.choice([".", "::", "/"])
    parts = [rng.choice(_PARTS).replace(".", "") for _ in range(rng.randint(1, 4))]
    name = separator.join(parts)
    return name.upper() if rng.random() < 0.1 else name


@pytest.mark.parametrize("seed", range(6))
def test_the_index_answers_like_the_reference(seed: int) -> None:
    rng = random.Random(seed)
    files = _file_set(rng)
    index = ModuleIndex(files)

    wrong = [
        (module, got, want)
        for module in (_module(rng) for _ in range(500))
        if (got := index.resolve(module)) != (want := _reference(module, files))
    ]

    assert wrong == [], f"{len(wrong)} imports resolve differently, first: {wrong[:3]}"


@pytest.mark.parametrize(
    ("module", "files", "expected"),
    [
        ("pkg", {"src/pkg/__init__.py"}, "src/pkg/__init__.py"),
        ("b.c", {"src/a.b/c.py", "lib/c.py"}, None),
        ("Makefile", {"src/Makefile"}, "src/Makefile"),
        ("alpha.beta", {"src\\Alpha\\Beta.rs"}, "src\\Alpha\\Beta.rs"),
        ("beta", {"src/alpha/notbeta.py"}, None),
        ("x.thing", {"a/thing.py", "b/thing.py", "thing.py"}, None),
    ],
)
def test_the_edges_of_the_rule_are_kept(module: str, files: set[str], expected: str | None) -> None:
    assert resolve_module(module, frozenset(files)) == expected
    assert ModuleIndex(frozenset(files)).resolve(module) == expected


@pytest.mark.parametrize("module", ["alpha", "", "::"])
def test_nothing_to_resolve_against_or_nothing_named(module: str) -> None:
    assert ModuleIndex(frozenset()).resolve(module) is None


class _CountingSet(frozenset[str]):
    reads = 0

    def __iter__(self) -> Any:
        type(self).reads += 1
        return super().__iter__()


def test_the_file_set_is_read_once_however_many_imports_follow() -> None:
    _CountingSet.reads = 0
    index = ModuleIndex(_CountingSet({f"src/m{i}.py" for i in range(200)}))

    for i in range(1000):
        index.resolve(f"m{i % 300}")

    assert _CountingSet.reads == 1


def test_a_build_makes_one_index(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for i in range(30):
        (tmp_path / f"m{i}.py").write_text("", encoding="utf-8")
    builder = GraphBuilder(engine=InMemoryGraphEngine(), parser=None)
    built: list[int] = []
    real_init = ModuleIndex.__init__

    def counting_init(self: ModuleIndex, files: frozenset[str]) -> None:
        built.append(len(files))
        real_init(self, files)

    monkeypatch.setattr(mapper_module.ModuleIndex, "__init__", counting_init)

    def parser(path: str) -> dict[str, Any]:
        return {"type": "module", "imports": [f"m{n}" for n in range(30)], "children": []}

    builder.parser = parser
    builder.ingest_target(tmp_path)

    assert built == [30], f"one index of 30 files per build, got {built}"
