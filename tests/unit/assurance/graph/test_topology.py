# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for TopologyGraph — in-memory dependency graph from context.yaml."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import pytest

from specweaver.assurance.graph.topology import (
    TopologyContext,
    TopologyGraph,
)
from specweaver.graph.topology.engine import TopologyEngine
from tests.unit.assurance.graph.conftest import _write_context

# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------


class TestFromProject:
    """Test graph construction from project directory."""

    def test_empty_project(self, empty_project: Path) -> None:
        graph = TopologyGraph.from_project(empty_project, TopologyEngine(), auto_infer=False)
        assert len(graph.nodes) == 0

    def test_single_node(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, TopologyEngine(), auto_infer=False)
        assert len(graph.nodes) == 1
        assert "alpha" in graph.nodes

    def test_linear_chain_nodes(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, TopologyEngine(), auto_infer=False)
        assert set(graph.nodes.keys()) == {"a", "b", "c"}

    def test_node_purpose(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, TopologyEngine(), auto_infer=False)
        assert graph.nodes["alpha"].purpose == "The only module."

    def test_node_mcp_fields(self, tmp_path: Path) -> None:
        _write_context(
            tmp_path / "gamma",
            name="gamma",
            purpose="MCP test.",
            mcp_servers={"localdb": {"command": "sqlite"}},
            consumes_resources=["mcp://localdb/users"],
        )
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        node = graph.nodes["gamma"]
        assert node.mcp_servers == {"localdb": {"command": "sqlite"}}
        assert node.consumes_resources == ["mcp://localdb/users"]


# ---------------------------------------------------------------------------
# Query tests - Delegation Integration
# ---------------------------------------------------------------------------


class TestQueryDelegation:
    """Test that queries are delegated properly to the engine."""

    def test_queries_terminate(self, diamond: Path) -> None:
        graph = TopologyGraph.from_project(diamond, TopologyEngine(), auto_infer=False)
        assert graph.consumers_of("d") == {"b", "c"}
        assert graph.dependencies_of("a") == {"b", "c", "d"}
        assert graph.impact_of("d") == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Constraints aggregation
# ---------------------------------------------------------------------------


class TestConstraintsFor:
    """Test constraint collection from module + consumers."""

    def test_module_own_constraints(self, with_constraints: Path) -> None:
        graph = TopologyGraph.from_project(with_constraints, TopologyEngine(), auto_infer=False)
        constraints = graph.constraints_for("engine")
        assert "All functions must be pure" in constraints

    def test_includes_consumer_constraints(self, with_constraints: Path) -> None:
        graph = TopologyGraph.from_project(with_constraints, TopologyEngine(), auto_infer=False)
        constraints = graph.constraints_for("engine")
        # engine is consumed by api, so api's constraints propagate
        assert "No blocking calls" in constraints

    def test_leaf_with_no_constraints(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, TopologyEngine(), auto_infer=False)
        assert graph.constraints_for("alpha") == []


# ---------------------------------------------------------------------------
# Operational warnings (SLA mismatch)
# ---------------------------------------------------------------------------


class TestOperationalWarnings:
    """Test SLA mismatch detection."""

    def test_latency_consuming_batch_warns(self, sla_mismatch: Path) -> None:
        graph = TopologyGraph.from_project(sla_mismatch, TopologyEngine(), auto_infer=False)
        warnings = graph.operational_warnings("fast")
        assert len(warnings) > 0
        assert any("batch" in w.lower() or "latency" in w.lower() for w in warnings)

    def test_matching_sla_no_warnings(self, sla_ok: Path) -> None:
        graph = TopologyGraph.from_project(sla_ok, TopologyEngine(), auto_infer=False)
        warnings = graph.operational_warnings("fast")
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test missing references and unknown modules."""

    def test_dangling_consumes_warning(self, dangling_consumes: Path) -> None:
        graph = TopologyGraph.from_project(dangling_consumes, TopologyEngine(), auto_infer=False)
        assert len(graph.warnings) > 0
        assert any("ghost" in w for w in graph.warnings)

    def test_unknown_module_returns_empty(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, TopologyEngine(), auto_infer=False)
        assert graph.consumers_of("nonexistent") == set()
        assert graph.dependencies_of("nonexistent") == set()
        assert graph.impact_of("nonexistent") == set()

    def test_malformed_yaml_warns_not_crashes(self, tmp_path: Path) -> None:
        """A context.yaml with invalid YAML should produce a warning, not crash."""
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        (bad_dir / "context.yaml").write_text("name: [unbalanced\n")
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        assert len(graph.warnings) > 0

    def test_empty_yaml_file_warns(self, tmp_path: Path) -> None:
        """An empty context.yaml (null parse) should produce a warning."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        (empty_dir / "context.yaml").write_text("")
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        assert len(graph.warnings) > 0
        assert any("Empty" in w or "empty" in w.lower() for w in graph.warnings)

    def test_missing_name_field_warns(self, tmp_path: Path) -> None:
        """context.yaml without 'name' should be skipped with a warning."""
        no_name = tmp_path / "no_name"
        no_name.mkdir()
        (no_name / "context.yaml").write_text("level: module\npurpose: Has no name.\n")
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        assert len(graph.nodes) == 0
        assert any("name" in w.lower() for w in graph.warnings)

    def test_duplicate_names_last_wins(self, tmp_path: Path) -> None:
        """Two directories with the same name — last one scanned wins."""
        _write_context(tmp_path / "dir_a", name="shared", purpose="First")
        _write_context(tmp_path / "dir_b", name="shared", purpose="Second")
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        assert "shared" in graph.nodes
        # One of them wins (deterministic since we sort)

    def test_self_referencing_consumes(self, tmp_path: Path) -> None:
        """A module that consumes itself should not cause infinite loop."""
        _write_context(tmp_path / "self_ref", name="self_ref", consumes=["self_ref"])
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
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
            tmp_path / "root_ctx" / "child",
            name="child",
            level="module",
            consumes=["root"],
        )
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
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

        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=True)
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
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        warnings = graph.operational_warnings("tight")
        assert len(warnings) > 0
        assert any("50" in w and "500" in w for w in warnings)

    def test_no_operational_section_no_warnings(self, single_node: Path) -> None:
        """Module without operational section should produce no SLA warnings."""
        graph = TopologyGraph.from_project(single_node, TopologyEngine(), auto_infer=False)
        assert graph.operational_warnings("alpha") == []

    def test_queries_on_cyclic_graph_terminate(self, cycle_abc: Path) -> None:
        """dependencies_of and impact_of should terminate on cyclic graphs."""
        graph = TopologyGraph.from_project(cycle_abc, TopologyEngine(), auto_infer=False)
        # These should NOT hang — BFS with visited set should handle cycles
        deps = graph.dependencies_of("a")
        assert "b" in deps
        assert "c" in deps
        impact = graph.impact_of("a")
        assert "b" in impact
        assert "c" in impact


# ---------------------------------------------------------------------------
# modules_sharing_constraints tests
# ---------------------------------------------------------------------------


class TestModulesSharingConstraints:
    """Test constraint overlap detection."""

    def test_shared_constraint(self, tmp_path: Path) -> None:
        """Two modules with overlapping constraint lists."""
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
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        assert graph.modules_sharing_constraints("a") == {"b"}

    def test_no_shared_constraints(self, with_constraints: Path) -> None:
        """api and engine have different constraints."""
        graph = TopologyGraph.from_project(with_constraints, TopologyEngine(), auto_infer=False)
        assert graph.modules_sharing_constraints("api") == set()

    def test_no_constraints_returns_empty(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, TopologyEngine(), auto_infer=False)
        assert graph.modules_sharing_constraints("alpha") == set()

    def test_unknown_module_returns_empty(self, single_node: Path) -> None:
        graph = TopologyGraph.from_project(single_node, TopologyEngine(), auto_infer=False)
        assert graph.modules_sharing_constraints("nonexistent") == set()

    def test_multiple_shared(self, tmp_path: Path) -> None:
        """Module shares constraints with multiple others."""
        _write_context(tmp_path / "x", name="x", constraints=["auth-required"])
        _write_context(tmp_path / "y", name="y", constraints=["auth-required"])
        _write_context(tmp_path / "z", name="z", constraints=["auth-required"])
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        assert graph.modules_sharing_constraints("x") == {"y", "z"}


# ---------------------------------------------------------------------------
# format_context_summary tests
# ---------------------------------------------------------------------------


class TestFormatContextSummary:
    """Test structured context assembly."""

    def test_direct_dependency_label(self, linear_chain: Path) -> None:
        """A consumes B: relationship = 'direct dependency'."""
        graph = TopologyGraph.from_project(linear_chain, TopologyEngine(), auto_infer=False)
        contexts = graph.format_context_summary("a", {"b"})
        assert len(contexts) == 1
        assert contexts[0].name == "b"
        assert contexts[0].relationship == "direct dependency"

    def test_direct_consumer_label(self, linear_chain: Path) -> None:
        """B is consumed by A: from B's view, A is 'direct consumer'."""
        graph = TopologyGraph.from_project(linear_chain, TopologyEngine(), auto_infer=False)
        contexts = graph.format_context_summary("b", {"a"})
        assert len(contexts) == 1
        assert contexts[0].relationship == "direct consumer"

    def test_transitive_label(self, linear_chain: Path) -> None:
        """A->B->C: C is not direct from A, so 'transitive neighbour'."""
        graph = TopologyGraph.from_project(linear_chain, TopologyEngine(), auto_infer=False)
        contexts = graph.format_context_summary("a", {"c"})
        assert len(contexts) == 1
        assert contexts[0].relationship == "transitive neighbour"

    def test_mutual_dependency_label(self, cycle_ab: Path) -> None:
        """A->B and B->A: mutual dependency."""
        graph = TopologyGraph.from_project(cycle_ab, TopologyEngine(), auto_infer=False)
        contexts = graph.format_context_summary("a", {"b"})
        assert len(contexts) == 1
        assert contexts[0].relationship == "mutual dependency"

    def test_includes_purpose_and_archetype(self, tmp_path: Path) -> None:
        _write_context(
            tmp_path / "svc",
            name="svc",
            purpose="Auth service.",
            archetype="adapter",
            constraints=["no-direct-db"],
        )
        _write_context(tmp_path / "cli", name="cli", consumes=["svc"])
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        contexts = graph.format_context_summary("cli", {"svc"})
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.purpose == "Auth service."
        assert ctx.archetype == "adapter"
        assert ctx.constraints == ["no-direct-db"]

    def test_includes_mcp_servers_and_resources(self, tmp_path: Path) -> None:
        """Verify MCP server mappings correctly serialize into TopologyContext."""
        _write_context(
            tmp_path / "mcp_target",
            name="mcp_target",
            mcp_servers={"db": {"command": "sqlite"}},
            consumes_resources=["mcp://db/users"],
        )
        _write_context(tmp_path / "cli", name="cli", consumes=["mcp_target"])
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        contexts = graph.format_context_summary("cli", {"mcp_target"})
        assert len(contexts) == 1
        ctx = contexts[0]
        assert ctx.mcp_servers == {"db": {"command": "sqlite"}}
        assert ctx.consumes_resources == ["mcp://db/users"]

    def test_unknown_module_skipped(self, single_node: Path) -> None:
        """Unknown modules in the related set are silently skipped."""
        graph = TopologyGraph.from_project(single_node, TopologyEngine(), auto_infer=False)
        assert graph.format_context_summary("alpha", {"ghost"}) == []

    def test_empty_related_set(self, linear_chain: Path) -> None:
        graph = TopologyGraph.from_project(linear_chain, TopologyEngine(), auto_infer=False)
        assert graph.format_context_summary("a", set()) == []

    def test_sorted_output(self, diamond: Path) -> None:
        """Output is sorted alphabetically by module name."""
        graph = TopologyGraph.from_project(diamond, TopologyEngine(), auto_infer=False)
        contexts = graph.format_context_summary("a", {"d", "c", "b"})
        names = [c.name for c in contexts]
        assert names == ["b", "c", "d"]

    def test_topology_context_is_frozen(self, linear_chain: Path) -> None:
        """TopologyContext should be immutable (frozen dataclass)."""
        graph = TopologyGraph.from_project(linear_chain, TopologyEngine(), auto_infer=False)
        contexts = graph.format_context_summary("a", {"b"})
        with pytest.raises(AttributeError):
            contexts[0].name = "changed"  # type: ignore[misc]

    def test_topology_context_dataclass_fields(self) -> None:
        """Verify TopologyContext can be constructed directly."""
        ctx = TopologyContext(
            name="mod",
            purpose="Does things.",
            archetype="pure-logic",
            relationship="direct dependency",
            constraints=["no-io"],
        )
        assert ctx.name == "mod"
        assert ctx.constraints == ["no-io"]


# ---------------------------------------------------------------------------
# Auto-infer edge cases
# ---------------------------------------------------------------------------


class TestAutoInferEdgeCases:
    """Edge cases for auto_infer=True behavior."""

    def test_auto_infer_skips_hidden_directories(self, tmp_path: Path) -> None:
        """Hidden directories (.git, .env, etc.) should be skipped."""
        _write_context(tmp_path / "known", name="known")
        # Create a hidden directory with Python code
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "__init__.py").write_text('"""Should not be inferred."""\n')
        (git_dir / "hook.py").write_text("x = 1\n")
        # Another hidden dir
        env_dir = tmp_path / ".env"
        env_dir.mkdir()
        (env_dir / "__init__.py").write_text('"""Environment."""\n')

        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=True)
        # Hidden dirs should NOT appear as inferred modules
        assert ".git" not in graph.nodes
        assert ".env" not in graph.nodes

    def test_auto_infer_all_dirs_already_have_context(self, tmp_path: Path) -> None:
        """When all directories have context.yaml, no inference needed."""
        _write_context(tmp_path / "a", name="a")
        _write_context(tmp_path / "b", name="b")
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=True)
        assert set(graph.nodes.keys()) == {"a", "b"}
        # No auto-infer warnings (only auto-infer produces inferred warnings)
        infer_warnings = [w for w in graph.warnings if "infer" in w.lower()]
        assert len(infer_warnings) == 0

    def test_auto_infer_mixed_manual_and_inferred(self, tmp_path: Path) -> None:
        """Mix of manual context.yaml + inferred modules merge correctly."""
        _write_context(tmp_path / "manual", name="manual", consumes=["inferred"])
        # inferred dir: Python code but no context.yaml
        inferred_dir = tmp_path / "inferred"
        inferred_dir.mkdir()
        (inferred_dir / "__init__.py").write_text('"""Inferred module."""\n')
        (inferred_dir / "code.py").write_text("def helper(): pass\n")

        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=True)
        assert "manual" in graph.nodes
        assert "inferred" in graph.nodes
        # The consumes edge should be resolved
        assert graph.consumers_of("inferred") == {"manual"}

    def test_auto_infer_dir_without_python_skipped(self, tmp_path: Path) -> None:
        """Directories without Python files should not be inferred."""
        _write_context(tmp_path / "known", name="known")
        # Create dir with non-Python files only
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Documentation\n")

        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=True)
        assert "docs" not in graph.nodes


# ---------------------------------------------------------------------------
# Operational warnings - additional boundary cases
# ---------------------------------------------------------------------------


class TestOperationalWarningsBoundary:
    """Boundary cases for operational SLA checks."""

    def test_dependency_with_none_operational(self, tmp_path: Path) -> None:
        """Consumer has operational, dependency has none — no crash."""
        _write_context(
            tmp_path / "consumer",
            name="consumer",
            consumes=["provider"],
            operational={"latency_critical": True, "max_latency_ms": 50},
        )
        _write_context(tmp_path / "provider", name="provider")  # no operational
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        # Should not crash; no warnings or at most non-latency warnings
        warnings = graph.operational_warnings("consumer")
        assert isinstance(warnings, list)

    def test_neither_has_operational(self, tmp_path: Path) -> None:
        """Neither consumer nor dependency has operational — no warnings."""
        _write_context(
            tmp_path / "a",
            name="a",
            consumes=["b"],
        )
        _write_context(tmp_path / "b", name="b")
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        assert graph.operational_warnings("a") == []

    def test_unknown_module_operational_warnings(self, tmp_path: Path) -> None:
        """operational_warnings for a nonexistent module — empty or no crash."""
        _write_context(tmp_path / "a", name="a")
        graph = TopologyGraph.from_project(tmp_path, TopologyEngine(), auto_infer=False)
        result = graph.operational_warnings("nonexistent")
        assert isinstance(result, list)


# Extracted to test_topology_staleness.py to satisfy file size constraints
