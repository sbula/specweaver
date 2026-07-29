# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for the coupling / cycle guard (`scripts/check_coupling.py`).

The graph-building rules are tested against the real `src/` tree rather than synthetic files,
because the defect this check shipped with was a resolution rule, not an algorithm: it counted
`if TYPE_CHECKING:` imports and so reported three cycles that do not exist at runtime -- in code
that had already been fixed the correct way.

Tarjan and the metrics are pure, so those are exercised on hand-built graphs where the right
answer is obvious by inspection.

`scripts/` is not an importable package, so the module is loaded by path.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    assert path.exists(), f"script not found: {path}"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cp() -> ModuleType:
    return _load("check_coupling")


@pytest.fixture(scope="module")
def real_graph(cp: ModuleType) -> dict[str, set[str]]:
    return cp.build_graph(cp.iter_python_files([REPO_ROOT / "src"]))


# ---------------------------------------------------------------------------
# Which imports count
# ---------------------------------------------------------------------------


class TestRuntimeImportsOnly:
    def test_a_plain_import_counts(self, cp: ModuleType) -> None:
        tree = ast.parse("import specweaver.core\n")

        assert len(cp.iter_runtime_imports(tree)) == 1

    def test_a_from_import_counts(self, cp: ModuleType) -> None:
        tree = ast.parse("from specweaver.core import flow\n")

        assert len(cp.iter_runtime_imports(tree)) == 1

    def test_a_type_checking_import_does_not_count(self, cp: ModuleType) -> None:
        """The defect: these create no runtime edge and are the correct way to break a cycle."""
        tree = ast.parse(
            "from typing import TYPE_CHECKING\n"
            "if TYPE_CHECKING:\n"
            "    from specweaver.core import flow\n"
        )

        modules = [n.module for n in cp.iter_runtime_imports(tree) if hasattr(n, "module")]

        assert "specweaver.core" not in modules

    def test_a_dotted_type_checking_guard_is_also_excluded(self, cp: ModuleType) -> None:
        tree = ast.parse("import typing\nif typing.TYPE_CHECKING:\n    from specweaver import x\n")

        modules = [getattr(n, "module", None) for n in cp.iter_runtime_imports(tree)]

        assert "specweaver" not in modules

    def test_the_else_branch_of_a_type_checking_guard_still_counts(self, cp: ModuleType) -> None:
        """`else:` runs at runtime, so an import there is a real edge."""
        tree = ast.parse(
            "if TYPE_CHECKING:\n    from specweaver import a\nelse:\n    from specweaver import b\n"
        )

        names = [alias.name for n in cp.iter_runtime_imports(tree) for alias in n.names]

        assert names == ["b"]

    def test_a_function_level_import_still_counts(self, cp: ModuleType) -> None:
        """Deferring an import inside a function hides a cycle without removing it."""
        tree = ast.parse("def f():\n    from specweaver.core import flow\n    return flow\n")

        assert len(cp.iter_runtime_imports(tree)) == 1


class TestRealGraph:
    def test_the_runtime_edge_of_the_known_pair_is_present(
        self, real_graph: dict[str, set[str]]
    ) -> None:
        executor = "specweaver.sandbox.execution.executor"

        assert "specweaver.sandbox.execution.platform_limiter" in real_graph[executor]

    def test_the_type_only_back_edge_is_absent(self, real_graph: dict[str, set[str]]) -> None:
        """platform_limiter imports executor ONLY under TYPE_CHECKING — no cycle exists."""
        limiter = "specweaver.sandbox.execution.platform_limiter"

        assert "specweaver.sandbox.execution.executor" not in real_graph[limiter]

    def test_external_packages_are_not_nodes(self, real_graph: dict[str, set[str]]) -> None:
        assert not any(
            dep.startswith(("pydantic", "networkx", "typer"))
            for deps in real_graph.values()
            for dep in deps
        )

    def test_no_module_depends_on_itself(self, real_graph: dict[str, set[str]]) -> None:
        assert not [name for name, deps in real_graph.items() if name in deps]


class TestModuleNaming:
    def test_a_module_maps_to_its_dotted_path(self, cp: ModuleType) -> None:
        path = REPO_ROOT / "src" / "specweaver" / "sandbox" / "execution" / "executor.py"

        assert cp.module_name(path) == "specweaver.sandbox.execution.executor"

    def test_a_package_init_maps_to_the_package(self, cp: ModuleType) -> None:
        path = REPO_ROOT / "src" / "specweaver" / "sandbox" / "__init__.py"

        assert cp.module_name(path) == "specweaver.sandbox"


# ---------------------------------------------------------------------------
# Tarjan
# ---------------------------------------------------------------------------


class TestCycleDetection:
    def test_an_acyclic_graph_has_no_components(self, cp: ModuleType) -> None:
        graph = {"a": {"b"}, "b": {"c"}, "c": set()}

        assert cp.tarjan_scc(graph) == []

    def test_a_two_node_cycle_is_found(self, cp: ModuleType) -> None:
        graph = {"a": {"b"}, "b": {"a"}}

        assert cp.tarjan_scc(graph) == [["a", "b"]]

    def test_a_three_node_cycle_is_found(self, cp: ModuleType) -> None:
        graph = {"a": {"b"}, "b": {"c"}, "c": {"a"}}

        assert cp.tarjan_scc(graph) == [["a", "b", "c"]]

    def test_two_separate_cycles_are_both_found(self, cp: ModuleType) -> None:
        graph = {"a": {"b"}, "b": {"a"}, "c": {"d"}, "d": {"c"}}

        assert sorted(cp.tarjan_scc(graph)) == [["a", "b"], ["c", "d"]]

    def test_a_diamond_is_not_a_cycle(self, cp: ModuleType) -> None:
        """Shared dependencies are normal; only a round trip is a cycle."""
        graph = {"top": {"l", "r"}, "l": {"bottom"}, "r": {"bottom"}, "bottom": set()}

        assert cp.tarjan_scc(graph) == []

    def test_a_long_chain_does_not_blow_the_stack(self, cp: ModuleType) -> None:
        """Iterative on purpose — the real graph is deeper than the default recursion limit."""
        graph = {f"m{i}": {f"m{i + 1}"} for i in range(5000)}
        graph["m5000"] = set()

        assert cp.tarjan_scc(graph) == []


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_fan_out_counts_what_a_module_imports(self, cp: ModuleType) -> None:
        stats = cp.metrics({"a": {"b", "c"}, "b": set(), "c": set()})

        assert stats["a"][1] == 2

    def test_fan_in_counts_what_imports_a_module(self, cp: ModuleType) -> None:
        stats = cp.metrics({"a": {"c"}, "b": {"c"}, "c": set()})

        assert stats["c"][0] == 2

    def test_a_leaf_everyone_depends_on_is_maximally_stable(self, cp: ModuleType) -> None:
        stats = cp.metrics({"a": {"c"}, "b": {"c"}, "c": set()})

        assert stats["c"][2] == 0.0

    def test_a_module_nobody_depends_on_is_maximally_unstable(self, cp: ModuleType) -> None:
        stats = cp.metrics({"a": {"b"}, "b": set()})

        assert stats["a"][2] == 1.0

    def test_an_isolated_module_is_not_a_division_by_zero(self, cp: ModuleType) -> None:
        stats = cp.metrics({"lonely": set()})

        assert stats["lonely"] == (0, 0, 0.0)
