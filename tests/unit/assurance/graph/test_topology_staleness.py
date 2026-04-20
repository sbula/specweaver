# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path

from specweaver.assurance.graph.topology import TopologyGraph, TopologyNode
from specweaver.workspace.analyzers.factory import AnalyzerFactory


class TestStaleNodes:
    """Test stale nodes initialization and properties."""

    def test_default_empty_stale_nodes(self, single_node: Path) -> None:
        """By default, no nodes are stale if not provided to constructor."""
        node = TopologyNode(name="a", level="", purpose="", archetype="")
        graph = TopologyGraph({"a": node})
        assert graph.stale_nodes == set()

    def test_stale_nodes_injected(self) -> None:
        """Passing stale_nodes correctly exposes them via the property."""
        graph = TopologyGraph({}, stale_nodes={"core", "api"})  # type: ignore[arg-type]
        assert graph.stale_nodes == {"core", "api"}

    def test_stale_nodes_is_frozen(self) -> None:
        """The stale_nodes property should return a copy or be immutable."""
        graph = TopologyGraph({}, stale_nodes={"a"})  # type: ignore[arg-type]
        stale = graph.stale_nodes
        stale.add("b")
        assert "b" not in graph.stale_nodes

    def test_missing_cache_fallback_marks_all_stale(self, linear_chain: Path) -> None:
        """If there is no cache loaded, the graph must mark every discovered node as stale."""
        # Using the real from_project which should initialize the hasher
        # Since linear_chain creates physically mapped contexts but no cache,
        # it should default to 100% stale correctly.
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.stale_nodes == {"a", "b", "c"}

    def test_mutated_node_cascades_upstream(self, linear_chain: Path) -> None:
        """A mutated node must cleanly flag its direct/transitive upstream consumers."""
        # Setup: compute initial hashes and actively save cache to mock "clean state"
        from specweaver.assurance.graph.hasher import DependencyHasher

        hasher = DependencyHasher(linear_chain, AnalyzerFactory)
        manifests = [linear_chain / n / "context.yaml" for n in ["a", "b", "c"]]
        initial_state = hasher.compute_hashes(manifests)
        hasher.save_cache(initial_state)

        # At this point, running from_project should return exactly 0 stale nodes!
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert graph.stale_nodes == set()

        # Mutate 'c' (the leaf node) by altering its context file physically
        (linear_chain / "c" / "context.yaml").write_text(
            "name: c\nlevel: mutated\npurpose: changed\n"
        )

        # 'c' is consumed by 'b', and 'b' is consumed by 'a'
        # So evaluating from_project should mark 'c' as the seed,
        # and Tarjan reverse explosion marks 'b' and 'a'.
        graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
        assert "c" in graph.stale_nodes
        assert "b" in graph.stale_nodes
        assert "a" in graph.stale_nodes
        assert graph.stale_nodes == {"a", "b", "c"}

    def test_mutated_node_cascades_only_upstream(self, diamond: Path) -> None:
        """Testing exact isolation of impact_of bounds."""
        from specweaver.assurance.graph.hasher import DependencyHasher

        hasher = DependencyHasher(diamond, AnalyzerFactory)
        manifests = [diamond / n / "context.yaml" for n in ["a", "b", "c", "d"]]
        initial_state = hasher.compute_hashes(manifests)
        hasher.save_cache(initial_state)

        # Diamond: A depends on B and C. B and C depend on D
        # Mutate C
        (diamond / "c" / "context.yaml").write_text("name: c\nconsumes: [d]\nlevel: mutated\n")

        graph = TopologyGraph.from_project(diamond, auto_infer=False)
        # Should flag C (self) and A (consumer of C).
        # Should NOT flag B (sibling) or D (dependency of C).
        assert "c" in graph.stale_nodes
        assert "a" in graph.stale_nodes
        assert "b" not in graph.stale_nodes
        assert "d" not in graph.stale_nodes

    def test_topologygraph_never_writes_cache(self, linear_chain: Path) -> None:
        """The crawler ONLY calculates staleness, it NEVER auto-saves the cache."""
        # Clean state
        from unittest.mock import patch

        from specweaver.assurance.graph.hasher import DependencyHasher

        hasher = DependencyHasher(linear_chain, AnalyzerFactory)
        manifests = [linear_chain / n / "context.yaml" for n in ["a", "b", "c"]]
        initial_state = hasher.compute_hashes(manifests)
        hasher.save_cache(initial_state)

        # Mutate 'c'
        (linear_chain / "c" / "context.yaml").write_text("name: c\nlevel: mutated2\n")

        # The cache-flush dilemma: verify save_cache is NOT called!
        with patch.object(DependencyHasher, "save_cache") as mock_save:
            graph = TopologyGraph.from_project(linear_chain, auto_infer=False)
            assert graph.stale_nodes == {"a", "b", "c"}
            mock_save.assert_not_called()

    def test_deleted_node_cascades_upstream(self, diamond: Path) -> None:
        """A module that is physically deleted must flag its historical consumers as stale."""
        import shutil

        from specweaver.assurance.graph.hasher import DependencyHasher

        hasher = DependencyHasher(diamond, AnalyzerFactory)
        manifests = [diamond / n / "context.yaml" for n in ["a", "b", "c", "d"]]
        initial_state = hasher.compute_hashes(manifests)
        hasher.save_cache(initial_state)

        # Diamond: a -> b,c; b,c -> d
        # Delete module 'c' entirely from the workspace
        shutil.rmtree(diamond / "c")

        graph = TopologyGraph.from_project(diamond, auto_infer=False)
        # 'c' is gone, but 'a' still has `consumes: [b, c]`.
        # 'a' should be flagged as stale due to the dangling reference.
        assert "a" in graph.stale_nodes
        # 'b' and 'd' are unaffected
        assert "b" not in graph.stale_nodes
        assert "d" not in graph.stale_nodes

    def test_dynamic_node_graceful_skip(self, tmp_path: Path) -> None:
        """Nodes injected virtually without a yaml_path should bypass crawler cache crashing."""
        from unittest.mock import patch

        def mock_auto_infer(*args, **kwargs) -> None:
            nodes_dict = args[1]
            # Inject a fully virtual module
            nodes_dict["virtual"] = TopologyNode(
                name="virtual", level="module", purpose="X", archetype="Y", yaml_path=None
            )

        with patch.object(TopologyGraph, "_auto_infer_missing", side_effect=mock_auto_infer):
            graph = TopologyGraph.from_project(tmp_path, auto_infer=True)
            # The crawler should complete safely without crashing on yaml_path.parent
            assert "virtual" in graph.nodes
            # Virtual node with no disk presence is not technically "stale" from cache diffing,
            # but since there is no cache at all, it gets zero-trust marked stale anyway.
            # Point is it doesn't crash!
            assert "virtual" in graph.stale_nodes
