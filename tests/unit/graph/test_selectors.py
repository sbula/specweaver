# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for context selectors — strategy-based module selection."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest
from ruamel.yaml import YAML

from specweaver.graph.selectors import (
    ConstraintOnlySelector,
    DirectNeighborSelector,
    ImpactWeightedSelector,
    NHopConstraintSelector,
)
from specweaver.graph.topology import TopologyGraph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_context(
    directory: Path,
    *,
    name: str,
    level: str = "module",
    purpose: str = "Test module.",
    archetype: str = "pure-logic",
    consumes: list[str] | None = None,
    constraints: list[str] | None = None,
) -> Path:
    """Write a context.yaml to a directory."""
    directory.mkdir(parents=True, exist_ok=True)
    data: dict = {
        "name": name,
        "level": level,
        "purpose": purpose,
        "archetype": archetype,
    }
    if consumes:
        data["consumes"] = consumes
    if constraints:
        data["constraints"] = constraints
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.dump(data, directory / "context.yaml")
    return directory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def linear_chain(tmp_path: Path) -> Path:
    """A → B → C."""
    _write_context(tmp_path / "a", name="a", consumes=["b"])
    _write_context(tmp_path / "b", name="b", consumes=["c"])
    _write_context(tmp_path / "c", name="c")
    return tmp_path


@pytest.fixture()
def diamond(tmp_path: Path) -> Path:
    """A → B, A → C, B → D, C → D."""
    _write_context(tmp_path / "a", name="a", consumes=["b", "c"])
    _write_context(tmp_path / "b", name="b", consumes=["d"])
    _write_context(tmp_path / "c", name="c", consumes=["d"])
    _write_context(tmp_path / "d", name="d")
    return tmp_path


@pytest.fixture()
def shared_constraints(tmp_path: Path) -> Path:
    """Three modules with constraint overlap: A shares with B, not C."""
    _write_context(
        tmp_path / "a",
        name="a",
        constraints=["no-blocking", "stateless"],
    )
    _write_context(
        tmp_path / "b",
        name="b",
        constraints=["stateless", "idempotent"],
    )
    _write_context(
        tmp_path / "c",
        name="c",
        constraints=["idempotent"],
    )
    return tmp_path


@pytest.fixture()
def single_node(tmp_path: Path) -> Path:
    _write_context(tmp_path / "alpha", name="alpha")
    return tmp_path


# ---------------------------------------------------------------------------
# DirectNeighborSelector
# ---------------------------------------------------------------------------


class TestDirectNeighborSelector:
    """1-hop neighbours only."""

    def test_root_of_chain(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        result = DirectNeighborSelector().select(graph, "a")
        assert result == {"b"}

    def test_middle_of_chain(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        result = DirectNeighborSelector().select(graph, "b")
        assert result == {"a", "c"}

    def test_leaf_of_chain(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        result = DirectNeighborSelector().select(graph, "c")
        assert result == {"b"}

    def test_diamond(self, diamond: Path) -> None:
        graph = TopologyGraph.from_project(diamond, auto_infer=False)
        assert DirectNeighborSelector().select(graph, "a") == {"b", "c"}

    def test_isolated_node(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, auto_infer=False)
        assert DirectNeighborSelector().select(graph, "alpha") == set()

    def test_unknown_module(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, auto_infer=False)
        assert DirectNeighborSelector().select(graph, "nope") == set()


# ---------------------------------------------------------------------------
# NHopConstraintSelector
# ---------------------------------------------------------------------------


class TestNHopConstraintSelector:
    """N-hop neighbours + shared constraints."""

    def test_default_depth_2(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        result = NHopConstraintSelector().select(graph, "a")
        assert result == {"b", "c"}

    def test_depth_1(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        result = NHopConstraintSelector(depth=1).select(graph, "a")
        assert result == {"b"}

    def test_includes_shared_constraints(self, shared_constraints: Path) -> None:
        """Even if B is not a neighbour by edges, shared constraints include it."""
        graph = TopologyGraph.from_project(shared_constraints, auto_infer=False)
        result = NHopConstraintSelector(depth=1).select(graph, "a")
        # A has no edges, but shares "stateless" with B
        assert "b" in result

    def test_diamond_depth_2(self, diamond: Path) -> None:
        graph = TopologyGraph.from_project(diamond, auto_infer=False)
        result = NHopConstraintSelector(depth=2).select(graph, "a")
        assert result == {"b", "c", "d"}

    def test_depth_clamped_to_1(self, linear_chain: Path) -> None:
        """depth=0 should be clamped to 1."""
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        result = NHopConstraintSelector(depth=0).select(graph, "a")
        assert result == {"b"}  # 1-hop


# ---------------------------------------------------------------------------
# ConstraintOnlySelector
# ---------------------------------------------------------------------------


class TestConstraintOnlySelector:
    """Semantic-only: shared constraints, no graph edges."""

    def test_shared_constraint(self, shared_constraints: Path) -> None:
        graph = TopologyGraph.from_project(shared_constraints, auto_infer=False)
        result = ConstraintOnlySelector().select(graph, "a")
        assert result == {"b"}  # A shares "stateless" with B

    def test_no_shared_returns_empty(self, shared_constraints: Path) -> None:
        graph = TopologyGraph.from_project(shared_constraints, auto_infer=False)
        result = ConstraintOnlySelector().select(graph, "c")
        # C has "idempotent" shared with B
        assert result == {"b"}

    def test_no_constraints(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, auto_infer=False)
        assert ConstraintOnlySelector().select(graph, "alpha") == set()


# ---------------------------------------------------------------------------
# ImpactWeightedSelector
# ---------------------------------------------------------------------------


class TestImpactWeightedSelector:
    """2-hop neighbours + transitive impact (stub)."""

    def test_includes_neighbours_and_impact(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        result = ImpactWeightedSelector().select(graph, "c")
        # Neighbours within 2: {a, b}
        # Impact of c: {a, b} (transitive reverse)
        assert result == {"a", "b"}

    def test_leaf_impact(self, diamond: Path) -> None:
        graph = TopologyGraph.from_project(diamond, auto_infer=False)
        result = ImpactWeightedSelector().select(graph, "d")
        # D impacts: {a, b, c} (everyone consumes d transitively)
        # Neighbours within 2 from d: {b, c, a}
        assert result == {"a", "b", "c"}

    def test_root_no_impact(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        result = ImpactWeightedSelector().select(graph, "a")
        # Impact of a: empty (nothing depends on a)
        # Neighbours within 2: {b, c}
        assert result == {"b", "c"}

    def test_isolated_node(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, auto_infer=False)
        assert ImpactWeightedSelector().select(graph, "alpha") == set()


# ---------------------------------------------------------------------------
# ABC enforcement
# ---------------------------------------------------------------------------


class TestContextSelectorABC:
    """Verify ABC contract."""

    def test_cannot_instantiate_abc(self) -> None:
        from specweaver.graph.selectors import ContextSelector

        with pytest.raises(TypeError, match="abstract"):
            ContextSelector()  # type: ignore[abstract]
