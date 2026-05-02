from specweaver.graph.topology.engine import TopologyEngine


class TestCycles:
    def test_no_cycles_in_chain(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.cycles() == []

    def test_two_node_cycle(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "a")
        cycles = engine.cycles()
        assert len(cycles) > 0
        cycle_members = {m for c in cycles for m in c}
        assert "a" in cycle_members
        assert "b" in cycle_members

    def test_three_node_cycle(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        engine.add_edge("c", "a")
        cycles = engine.cycles()
        assert len(cycles) > 0


class TestTraverse:
    def test_root_depends_on_all(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.traverse("a", forward=True) == {"b", "c"}

    def test_middle_depends_on_leaf(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.traverse("b", forward=True) == {"c"}

    def test_leaf_has_no_deps(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.traverse("c", forward=True) == set()

    def test_diamond_deps(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("a", "c")
        engine.add_edge("b", "d")
        engine.add_edge("c", "d")
        assert engine.traverse("a", forward=True) == {"b", "c", "d"}

    def test_leaf_impacts_all_upstream(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.traverse("c", forward=False) == {"a", "b"}

    def test_root_impacts_nothing(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.traverse("a", forward=False) == set()

    def test_queries_on_cyclic_graph_terminate(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        engine.add_edge("c", "a")
        deps = engine.traverse("a", forward=True)
        assert "b" in deps
        assert "c" in deps
        impact = engine.traverse("a", forward=False)
        assert "b" in impact
        assert "c" in impact

    def test_hostile_missing_node(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        assert engine.traverse("ghost", forward=True) == set()
        assert engine.traverse("ghost", forward=False) == set()


class TestNeighborsWithin:
    def test_depth_1_linear(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.neighbors_within("b", depth=1) == {"a", "c"}

    def test_depth_1_root(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.neighbors_within("a", depth=1) == {"b"}

    def test_depth_1_leaf(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.neighbors_within("c", depth=1) == {"b"}

    def test_depth_2_linear(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        engine.add_edge("b", "c")
        assert engine.neighbors_within("a", depth=2) == {"b", "c"}

    def test_depth_0_returns_empty(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        assert engine.neighbors_within("a", depth=0) == set()

    def test_isolated_node(self):
        engine = TopologyEngine()
        engine.add_node("alpha")
        assert engine.neighbors_within("alpha", depth=1) == set()

    def test_hostile_missing_node(self):
        engine = TopologyEngine()
        engine.add_edge("a", "b")
        assert engine.neighbors_within("ghost", depth=1) == set()

    def test_rt27_max_depth_enforced(self):
        engine = TopologyEngine()
        # Build a chain of 10 nodes: 0->1->2->3->4->5->6->7->8->9
        for i in range(9):
            engine.add_edge(str(i), str(i + 1))

        # Requesting depth 100 should be capped at 5
        # From node 0, depth 5 goes to 1, 2, 3, 4, 5
        neighbors = engine.neighbors_within("0", depth=100)
        assert neighbors == {"1", "2", "3", "4", "5"}


class TestThreadSafety:
    def test_rt18_thread_safety(self):
        import threading

        engine = TopologyEngine()

        def worker(thread_id: int):
            for i in range(100):
                engine.add_edge(f"root_{thread_id}", f"child_{thread_id}_{i}")

        threads = []
        for i in range(10):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(engine.nodes) == 10 + 1000  # 10 roots, 1000 children
