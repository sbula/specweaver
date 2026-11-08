# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Real `context.yaml` files, read by `load_nodes`, judged by the boundary rule.

Proves: TECH-082 FR-15
Proves: TECH-088 FR-6

The resolver is only ever fed what the loader read, so this checks the pair: a `widens` the loader
drops, or a folder it records wrongly, would turn a declared widening into a breach here.

| Bucket | Case |
|---|---|
| Happy | a declared widening under a forbidding parent passes |
| Boundary | the same tree without the `widens` line breaks the rule |
| Degradation | a `widens` written as a list is loaded with empty reasons and refused |
| Hostile | a manifest whose YAML does not parse is skipped with a warning, the rest still judged |
"""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

from specweaver.assurance.graph.boundary_rule import Breach, breaches
from specweaver.graph.topology.topology import load_nodes

_PARENT = "name: domain\narchetype: pure-logic\nconsumes: [lib]\nforbids: [box/*]\n"


def _manifest(folder: Path, body: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "context.yaml").write_text(body, encoding="utf-8")


def test_a_declared_widening_under_a_forbidding_parent_passes(tmp_path: Path) -> None:
    _manifest(tmp_path / "domain", _PARENT)
    _manifest(
        tmp_path / "domain" / "cli",
        "name: domain-cli\narchetype: orchestrator\nconsumes: [lib, box/exec]\n"
        "widens:\n  box/exec: runs git through the executor\n",
    )

    nodes, _ = load_nodes(tmp_path)

    assert breaches(nodes, tmp_path) == []


def test_without_the_widens_line_the_rule_breaks(tmp_path: Path) -> None:
    _manifest(tmp_path / "domain", _PARENT)
    _manifest(
        tmp_path / "domain" / "cli",
        "name: domain-cli\narchetype: orchestrator\nconsumes: [lib, box/exec]\n",
    )

    nodes, _ = load_nodes(tmp_path)

    assert breaches(nodes, tmp_path) == [
        Breach("domain/cli", "box/exec", "wider", "domain"),
        Breach("domain/cli", "box/exec", "uses-forbidden", "domain"),
    ]


def test_a_widens_list_is_refused_for_want_of_reasons(tmp_path: Path) -> None:
    _manifest(tmp_path / "domain", _PARENT)
    _manifest(
        tmp_path / "domain" / "cli",
        "name: domain-cli\nconsumes: [box/exec]\nwidens: [box/exec]\n",
    )

    nodes, warnings = load_nodes(tmp_path)

    assert Breach("domain/cli", "box/exec", "empty-reason", "domain") in breaches(nodes, tmp_path)
    assert warnings


def test_an_unparsable_manifest_is_skipped_and_the_rest_judged(tmp_path: Path) -> None:
    _manifest(tmp_path / "domain", _PARENT)
    _manifest(tmp_path / "domain" / "broken", "name: [unclosed\n")
    _manifest(tmp_path / "domain" / "cli", "name: domain-cli\nconsumes: [other]\n")

    nodes, warnings = load_nodes(tmp_path)

    assert any("broken" in w for w in warnings)
    assert breaches(nodes, tmp_path) == [Breach("domain/cli", "other", "wider", "domain")]
