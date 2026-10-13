# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The test folders to run for what changed since the last green test run.

The hash cache (`.specweaver/topology.cache.json`) is saved after a run whose tests passed. A
module's hash covers every file below it, nested modules included, so comparing whole hashes would
mark the root changed for any change. The cache keeps each file's hash, so the change is found per
file: a changed test file runs its own folder; a changed code file runs the tests of its closest
module and of every module that uses it.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from specweaver.assurance.graph.changes import changed_files

if TYPE_CHECKING:
    from specweaver.assurance.graph.topology import TopologyGraph

_TESTS = "tests"


def folders_to_test(
    project_root: Path, code_root: Path, graph: TopologyGraph, kind: str
) -> list[str]:
    """The folders to run, none inside another; empty when the whole tier must run as given.

    `project_root` holds the cache; `code_root` holds the code to compare, the run's worktree when
    it has one.
    """
    files = changed_files(project_root, code_root, list(_boundaries(code_root, graph)))
    if not files:
        return []
    boundaries = _boundaries(code_root, graph)
    tier = PurePosixPath(_TESTS, kind)
    folders: set[str] = set()
    code_files = []
    for path in files:
        posix = PurePosixPath(path)
        if posix.parts[0] != _TESTS:
            code_files.append(path)
        elif tier in posix.parents:
            folders.add(str(Path(posix.parent)))
    seeds = {boundaries[_closest(f, boundaries)] for f in code_files}
    seeds |= {name for name, node in graph.nodes.items() if set(node.consumes) - graph.nodes.keys()}
    for name in seeds.union(*(graph.impact_of(seed) for seed in seeds)):
        node = graph.nodes.get(name)
        if node and node.yaml_path:
            folders.add(_test_dir_for(node.yaml_path.parent, code_root / "src", code_root, kind))
    return _outermost(folders)


def _test_dir_for(module_dir: Path, src_dir: Path, project_path: Path, kind: str) -> str:
    """The test directory mirroring one source module, e.g. `specweaver/core/flow` ->
    `tests/unit/core/flow`.

    Falls back to the tier root (`tests/<kind>`) when the module sits directly under `src/`, when
    the mirrored directory does not exist yet, or when the module is not under `src/` at all —
    three distinct reasons that all mean "run the whole tier rather than nothing".
    """
    tier_root = str(Path(_TESTS) / kind)
    try:
        parts = module_dir.relative_to(src_dir).parts
    except ValueError:
        return tier_root
    if len(parts) <= 1:
        return tier_root
    mirrored = Path(_TESTS) / kind / Path(*parts[1:])
    return str(mirrored) if (project_path / mirrored).exists() else tier_root


def _boundaries(code_root: Path, graph: TopologyGraph) -> dict[str, str]:
    """Each module's folder, from the root, to its name."""
    return {
        node.yaml_path.parent.relative_to(code_root).as_posix(): name
        for name, node in graph.nodes.items()
        if node.yaml_path
    }


def _closest(path: str, boundaries: dict[str, str]) -> str:
    """The deepest boundary that holds `path`."""
    holders = [key for key in boundaries if key == "." or path.startswith(f"{key}/")]
    return max(holders, key=lambda key: 0 if key == "." else key.count("/") + 1)


def _outermost(folders: set[str]) -> list[str]:
    """The folders that no other folder in the set holds."""
    paths = {PurePosixPath(Path(f).as_posix()) for f in folders}
    return sorted(str(Path(p)) for p in paths if not any(o in p.parents for o in paths))
