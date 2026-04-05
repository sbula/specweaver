# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tach Synchronization adapter — maps TopologyGraph to tach.toml."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import tomlkit

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.graph.topology import TopologyGraph

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TachSyncResult:
    """Summary of tach synchronization."""

    path: Path
    modules_synced: int
    interfaces_synced: int


def _build_modules_and_interfaces(graph: TopologyGraph) -> tuple[tomlkit.items.AoT, tomlkit.items.AoT, int, int]:
    modules_array = tomlkit.aot()
    interfaces_array = tomlkit.aot()

    modules_count = 0
    interfaces_count = 0

    # Sort to enforce determinism
    for _, node in sorted(graph.nodes.items()):
        mod_table = tomlkit.table()
        mod_table["path"] = node.name

        dep_array = tomlkit.array()
        for dep in sorted(node.consumes):
            dep_array.append(dep)

        mod_table["depends_on"] = dep_array
        modules_array.append(mod_table)
        modules_count += 1

        if node.exposes:
            iface_table = tomlkit.table()

            from_array = tomlkit.array()
            from_array.append(node.name)
            iface_table["from"] = from_array

            expose_array = tomlkit.array()
            for exp in sorted(node.exposes):
                expose_array.append(exp)
            iface_table["expose"] = expose_array

            interfaces_array.append(iface_table)
            interfaces_count += 1

    return modules_array, interfaces_array, modules_count, interfaces_count

def sync_tach_toml(graph: TopologyGraph, target_path: Path) -> TachSyncResult:
    """Synchronize a TopologyGraph into a tach.toml file natively.

    Preserves root TOML properties if the file already exists, but reconstructs
    internal [[modules]] and [[interfaces]] mappings from scratch.

    Args:
        graph: The TopologyGraph mapping the source configurations.
        target_path: Root directory of the target project to drop the tach.toml.

    Returns:
        TachSyncResult summarizing the updated arrays.
    """
    tach_file = target_path / "tach.toml"

    doc = tomlkit.parse(tach_file.read_text("utf-8")) if tach_file.exists() else tomlkit.document()

    # Root Configuration
    if "exclude" not in doc:
        # Default excludes for standard python workspaces
        exclude_array = tomlkit.array()
        doc["exclude"] = exclude_array

    if "source_roots" not in doc:
        source_array = tomlkit.array()
        source_array.append(".")
        doc["source_roots"] = source_array

    doc["exact"] = True

    # Purge existing module/interface bounds since graph is the source of truth
    if "modules" in doc:
        del doc["modules"]
    if "interfaces" in doc:
        del doc["interfaces"]

    modules_array, interfaces_array, modules_count, interfaces_count = _build_modules_and_interfaces(graph)

    if modules_count > 0:
        doc["modules"] = modules_array
    if interfaces_count > 0:
        doc["interfaces"] = interfaces_array

    tach_file.write_text(tomlkit.dumps(doc), encoding="utf-8")

    logger.info(
        "sync_tach_toml: Synced %d modules and %d interfaces to %s",
        modules_count,
        interfaces_count,
        tach_file,
    )

    return TachSyncResult(
        path=tach_file,
        modules_synced=modules_count,
        interfaces_synced=interfaces_count,
    )
