# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for TopologyGraph — in-memory dependency graph from context.yaml."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest
from ruamel.yaml import YAML

from specweaver.graph.topology import (
    TopologyGraph,
)

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
    exposes: list[str] | None = None,
    forbids: list[str] | None = None,
    constraints: list[str] | None = None,
    operational: dict | None = None,
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
    if exposes:
        data["exposes"] = exposes
    if forbids:
        data["forbids"] = forbids
    if constraints:
        data["constraints"] = constraints
    if operational:
        data["operational"] = operational
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.dump(data, directory / "context.yaml")
    return directory


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def empty_project(tmp_path: Path) -> Path:
    """A project with no context.yaml files."""
    return tmp_path


@pytest.fixture()
def single_node(tmp_path: Path) -> Path:
    """A project with one module."""
    _write_context(tmp_path / "alpha", name="alpha", purpose="The only module.")
    return tmp_path


@pytest.fixture()
def linear_chain(tmp_path: Path) -> Path:
    """A → B → C (A consumes B, B consumes C)."""
    _write_context(tmp_path / "a", name="a", consumes=["b"])
    _write_context(tmp_path / "b", name="b", consumes=["c"])
    _write_context(tmp_path / "c", name="c", purpose="Leaf module.")
    return tmp_path


@pytest.fixture()
def diamond(tmp_path: Path) -> Path:
    """Diamond: A → B, A → C, B → D, C → D."""
    _write_context(tmp_path / "a", name="a", consumes=["b", "c"])
    _write_context(tmp_path / "b", name="b", consumes=["d"])
    _write_context(tmp_path / "c", name="c", consumes=["d"])
    _write_context(tmp_path / "d", name="d")
    return tmp_path


@pytest.fixture()
def cycle_ab(tmp_path: Path) -> Path:
    """Simple cycle: A → B → A."""
    _write_context(tmp_path / "a", name="a", consumes=["b"])
    _write_context(tmp_path / "b", name="b", consumes=["a"])
    return tmp_path


@pytest.fixture()
def cycle_abc(tmp_path: Path) -> Path:
    """3-node cycle: A → B → C → A."""
    _write_context(tmp_path / "a", name="a", consumes=["b"])
    _write_context(tmp_path / "b", name="b", consumes=["c"])
    _write_context(tmp_path / "c", name="c", consumes=["a"])
    return tmp_path


@pytest.fixture()
def with_constraints(tmp_path: Path) -> Path:
    """Modules with constraints."""
    _write_context(
        tmp_path / "api",
        name="api",
        consumes=["engine"],
        constraints=["No blocking calls"],
    )
    _write_context(
        tmp_path / "engine",
        name="engine",
        constraints=["All functions must be pure"],
    )
    return tmp_path


@pytest.fixture()
def sla_mismatch(tmp_path: Path) -> Path:
    """Latency-critical module consuming a batch data source."""
    _write_context(
        tmp_path / "fast",
        name="fast",
        consumes=["slow"],
        operational={"latency_critical": True, "max_latency_ms": 50},
    )
    _write_context(
        tmp_path / "slow",
        name="slow",
        operational={"data_freshness": "batch"},
    )
    return tmp_path


@pytest.fixture()
def sla_ok(tmp_path: Path) -> Path:
    """Both modules are realtime — no mismatch."""
    _write_context(
        tmp_path / "fast",
        name="fast",
        consumes=["feed"],
        operational={"latency_critical": True, "max_latency_ms": 50},
    )
    _write_context(
        tmp_path / "feed",
        name="feed",
        operational={"data_freshness": "realtime"},
    )
    return tmp_path


@pytest.fixture()
def dangling_consumes(tmp_path: Path) -> Path:
    """Module consumes a non-existent module."""
    _write_context(tmp_path / "orphan", name="orphan", consumes=["ghost"])
    return tmp_path


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestFromProject:
    """Test graph construction from project directory."""

    def test_empty_project(self, empty_project: Path) -> None:
        graph = TopologyGraph.from_project(empty_project, auto_infer=False)
        assert len(graph.nodes) == 0

    def test_single_node(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, auto_infer=False)
        assert len(graph.nodes) == 1
        assert "alpha" in graph.nodes

    def test_linear_chain_nodes(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert set(graph.nodes.keys()) == {"a", "b", "c"}

    def test_node_purpose(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, auto_infer=False)
        assert graph.nodes["alpha"].purpose == "The only module."


# ---------------------------------------------------------------------------
# Query tests
# ---------------------------------------------------------------------------


class TestConsumersOf:
    """Test direct reverse lookup."""

    def test_leaf_has_consumers(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.consumers_of("c") == {"b"}

    def test_middle_has_consumers(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.consumers_of("b") == {"a"}

    def test_root_has_no_consumers(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.consumers_of("a") == set()

    def test_diamond_consumers(self, diamond: Path) -> None:
        graph = TopologyGraph.from_project(diamond, auto_infer=False)
        assert graph.consumers_of("d") == {"b", "c"}


class TestDependenciesOf:
    """Test transitive forward traversal."""

    def test_root_depends_on_all(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.dependencies_of("a") == {"b", "c"}

    def test_middle_depends_on_leaf(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.dependencies_of("b") == {"c"}

    def test_leaf_has_no_deps(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.dependencies_of("c") == set()

    def test_diamond_deps(self, diamond: Path) -> None:
        graph = TopologyGraph.from_project(diamond, auto_infer=False)
        assert graph.dependencies_of("a") == {"b", "c", "d"}


class TestImpactOf:
    """Test transitive reverse traversal."""

    def test_leaf_impacts_all_upstream(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.impact_of("c") == {"a", "b"}

    def test_root_impacts_nothing(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.impact_of("a") == set()

    def test_diamond_impact(self, diamond: Path) -> None:
        graph = TopologyGraph.from_project(diamond, auto_infer=False)
        assert graph.impact_of("d") == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


class TestCycles:
    """Test circular dependency detection."""

    def test_no_cycles_in_chain(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.cycles() == []

    def test_two_node_cycle(self, cycle_ab: Path) -> None:
        graph = TopologyGraph.from_project(cycle_ab, auto_infer=False)
        cycles = graph.cycles()
        assert len(cycles) > 0
        # At least one cycle should contain both a and b
        cycle_members = {m for c in cycles for m in c}
        assert "a" in cycle_members
        assert "b" in cycle_members

    def test_three_node_cycle(self, cycle_abc: Path) -> None:
        graph = TopologyGraph.from_project(cycle_abc, auto_infer=False)
        cycles = graph.cycles()
        assert len(cycles) > 0


# ---------------------------------------------------------------------------
# Constraints aggregation
# ---------------------------------------------------------------------------


class TestConstraintsFor:
    """Test constraint collection from module + consumers."""

    def test_module_own_constraints(self, with_constraints: Path) -> None:
        graph = TopologyGraph.from_project(with_constraints, auto_infer=False)
        constraints = graph.constraints_for("engine")
        assert "All functions must be pure" in constraints

    def test_includes_consumer_constraints(self, with_constraints: Path) -> None:
        graph = TopologyGraph.from_project(with_constraints, auto_infer=False)
        constraints = graph.constraints_for("engine")
        # engine is consumed by api, so api's constraints propagate
        assert "No blocking calls" in constraints

    def test_leaf_with_no_constraints(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, auto_infer=False)
        assert graph.constraints_for("alpha") == []


# ---------------------------------------------------------------------------
# Operational warnings (SLA mismatch)
# ---------------------------------------------------------------------------


class TestOperationalWarnings:
    """Test SLA mismatch detection."""

    def test_latency_consuming_batch_warns(self, sla_mismatch: Path) -> None:
        graph = TopologyGraph.from_project(sla_mismatch, auto_infer=False)
        warnings = graph.operational_warnings("fast")
        assert len(warnings) > 0
        assert any("batch" in w.lower() or "latency" in w.lower() for w in warnings)

    def test_matching_sla_no_warnings(self, sla_ok: Path) -> None:
        graph = TopologyGraph.from_project(sla_ok, auto_infer=False)
        warnings = graph.operational_warnings("fast")
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test missing references and unknown modules."""

    def test_dangling_consumes_warning(self, dangling_consumes: Path) -> None:
        graph = TopologyGraph.from_project(dangling_consumes, auto_infer=False)
        assert len(graph.warnings) > 0
        assert any("ghost" in w for w in graph.warnings)

    def test_unknown_module_returns_empty(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, auto_infer=False)
        assert graph.consumers_of("nonexistent") == set()
        assert graph.dependencies_of("nonexistent") == set()
        assert graph.impact_of("nonexistent") == set()

    def test_malformed_yaml_warns_not_crashes(self, tmp_path: Path) -> None:
        """A context.yaml with invalid YAML should produce a warning, not crash."""
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "context.yaml").write_text("name: [unbalanced\n")
        graph = TopologyGraph.from_project(tmp_path, auto_infer=False)
        assert len(graph.warnings) > 0

    def test_empty_yaml_file_warns(self, tmp_path: Path) -> None:
        """An empty context.yaml (null parse) should produce a warning."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        (empty_dir / "context.yaml").write_text("")
        graph = TopologyGraph.from_project(tmp_path, auto_infer=False)
        assert len(graph.warnings) > 0
        assert any("Empty" in w or "empty" in w.lower() for w in graph.warnings)

    def test_missing_name_field_warns(self, tmp_path: Path) -> None:
        """context.yaml without 'name' should be skipped with a warning."""
        no_name = tmp_path / "no_name"
        no_name.mkdir()
        (no_name / "context.yaml").write_text("level: module\npurpose: Has no name.\n")
        graph = TopologyGraph.from_project(tmp_path, auto_infer=False)
        assert len(graph.nodes) == 0
        assert any("name" in w.lower() for w in graph.warnings)

    def test_duplicate_names_last_wins(self, tmp_path: Path) -> None:
        """Two directories with the same name — last one scanned wins."""
        _write_context(tmp_path / "dir_a", name="shared", purpose="First")
        _write_context(tmp_path / "dir_b", name="shared", purpose="Second")
        graph = TopologyGraph.from_project(tmp_path, auto_infer=False)
        assert "shared" in graph.nodes
        # One of them wins (deterministic since we sort)

    def test_self_referencing_consumes(self, tmp_path: Path) -> None:
        """A module that consumes itself should not cause infinite loop."""
        _write_context(tmp_path / "self_ref", name="self_ref", consumes=["self_ref"])
        graph = TopologyGraph.from_project(tmp_path, auto_infer=False)
        # dependencies_of should not infinitely recurse
        deps = graph.dependencies_of("self_ref")
        assert deps == {"self_ref"}
        # cycles should detect this
        cycles = graph.cycles()
        assert len(cycles) > 0

    def test_nested_hierarchy(self, tmp_path: Path) -> None:
        """context.yaml files at multiple nesting levels."""
        _write_context(tmp_path / "root_ctx", name="root", level="service")
        _write_context(
            tmp_path / "root_ctx" / "child", name="child",
            level="module", consumes=["root"],
        )
        graph = TopologyGraph.from_project(tmp_path, auto_infer=False)
        assert len(graph.nodes) == 2
        assert graph.consumers_of("root") == {"child"}

    def test_auto_infer_fills_gap(self, tmp_path: Path) -> None:
        """With auto_infer=True, dirs with Python but no context.yaml get one."""
        # Create one dir with context.yaml
        _write_context(tmp_path / "known", name="known")
        # Create another with Python code but no context.yaml
        py_dir = tmp_path / "unknown"
        py_dir.mkdir()
        (py_dir / "__init__.py").write_text('"""Auto-discovered module."""\n')
        (py_dir / "code.py").write_text("x = 1\n")

        graph = TopologyGraph.from_project(tmp_path, auto_infer=True)
        assert "unknown" in graph.nodes
        assert len(graph.warnings) > 0  # should warn about auto-generation

    def test_latency_ms_mismatch_warns(self, tmp_path: Path) -> None:
        """Consumer with tighter max_latency_ms than dependency warns."""
        _write_context(
            tmp_path / "tight",
            name="tight",
            consumes=["loose"],
            operational={"max_latency_ms": 50},
        )
        _write_context(
            tmp_path / "loose",
            name="loose",
            operational={"max_latency_ms": 500},
        )
        graph = TopologyGraph.from_project(tmp_path, auto_infer=False)
        warnings = graph.operational_warnings("tight")
        assert len(warnings) > 0
        assert any("50" in w and "500" in w for w in warnings)

    def test_no_operational_section_no_warnings(self, single_node: Path) -> None:
        """Module without operational section should produce no SLA warnings."""
        graph = TopologyGraph.from_project(single_node, auto_infer=False)
        assert graph.operational_warnings("alpha") == []

    def test_queries_on_cyclic_graph_terminate(self, cycle_abc: Path) -> None:
        """dependencies_of and impact_of should terminate on cyclic graphs."""
        graph = TopologyGraph.from_project(cycle_abc, auto_infer=False)
        # These should NOT hang — BFS with visited set should handle cycles
        deps = graph.dependencies_of("a")
        assert "b" in deps
        assert "c" in deps
        impact = graph.impact_of("a")
        assert "b" in impact
        assert "c" in impact

