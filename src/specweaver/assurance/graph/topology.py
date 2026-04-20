# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""TopologyGraph — in-memory directed dependency graph from context.yaml.

Loads all context.yaml files in a project, builds adjacency lists,
and provides queries for impact analysis, cycle detection, constraint
aggregation, and SLA mismatch warnings.

When a source directory is missing a context.yaml, the graph can
optionally auto-infer one using ContextInferrer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path  # noqa: TC003 — used at runtime in from_project() and dataclass fields

from ruamel.yaml import YAML

logger = logging.getLogger(__name__)


@dataclass
class OperationalMetadata:
    """Runtime/SLA characteristics from context.yaml operational section."""

    multi_tenant_ready: bool = False
    latency_critical: bool = False
    max_latency_ms: int | None = None
    data_freshness: str | None = None  # realtime | near-realtime | batch | static
    reliability_target: float | None = None
    async_ready: bool = False
    concurrency_model: str | None = None  # asyncio | threading | process | none


@dataclass
class TopologyNode:
    """A single boundary in the topology graph."""

    name: str
    level: str
    purpose: str
    archetype: str
    consumes: list[str] = field(default_factory=list)
    exposes: list[str] = field(default_factory=list)
    forbids: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    operational: OperationalMetadata | None = None
    yaml_path: Path | None = None


@dataclass(frozen=True)
class TopologyContext:
    """Structured context about a module for prompt injection.

    Produced by TopologyGraph.format_context_summary() and consumed
    by PromptBuilder.add_topology().
    """

    name: str
    purpose: str
    archetype: str
    relationship: str  # e.g. "direct dependency", "2-hop consumer"
    constraints: list[str] = field(default_factory=list)


def _pop_scc(root: str, stack: list[str], on_stack: set[str]) -> list[str]:
    """Pop a strongly connected component off the Tarjan stack."""
    scc: list[str] = []
    while True:
        w = stack.pop()
        on_stack.discard(w)
        scc.append(w)
        if w == root:
            break
    return scc


def _is_cycle(scc: list[str], forward: dict[str, set[str]]) -> bool:
    """Return True if the SCC represents a real cycle (size>1 or self-loop)."""
    if len(scc) > 1:
        return True
    return len(scc) == 1 and scc[0] in forward.get(scc[0], set())


class TopologyGraph:
    """In-memory directed graph built from context.yaml files.

    Provides structural queries over module dependencies:
    - consumers_of: who depends on a module (direct)
    - dependencies_of: what a module depends on (transitive)
    - impact_of: what's affected if a module changes (transitive reverse)
    - cycles: detect circular dependency chains
    - constraints_for: aggregate constraints from module + its consumers
    - operational_warnings: flag SLA mismatches
    """

    def __init__(
        self,
        nodes: dict[str, TopologyNode],
        warnings: list[str] | None = None,
        stale_nodes: set[str] | None = None,
    ) -> None:
        self._nodes = nodes
        self._warnings = list(warnings) if warnings else []
        self._stale_nodes = set(stale_nodes) if stale_nodes else set()

        # Build adjacency lists
        self._forward: dict[str, set[str]] = {}  # module → modules it consumes
        self._reverse: dict[str, set[str]] = {}  # module → modules that consume it

        for name in nodes:
            self._forward.setdefault(name, set())
            self._reverse.setdefault(name, set())

        for name, node in nodes.items():
            for dep in node.consumes:
                self._forward[name].add(dep)
                if dep in nodes:
                    self._reverse.setdefault(dep, set()).add(name)
                else:
                    self._warnings.append(
                        f"Module '{name}' consumes '{dep}' but no context.yaml found for '{dep}'."
                    )

    @property
    def nodes(self) -> dict[str, TopologyNode]:
        """All nodes in the graph."""
        return dict(self._nodes)

    @property
    def warnings(self) -> list[str]:
        """All warnings generated during graph construction."""
        return list(self._warnings)

    @property
    def stale_nodes(self) -> set[str]:
        """All nodes mathematically flagged as stale via the semantic cache."""
        return set(self._stale_nodes)

    @staticmethod
    def _calculate_stale_seeds(
        project_root: Path,
        nodes: dict[str, TopologyNode],
    ) -> set[str]:
        """Verify semantic hashes against cache and return natively stale nodes."""
        from specweaver.assurance.graph.hasher import DependencyHasher
        from specweaver.workspace.analyzers.factory import AnalyzerFactory

        hasher = DependencyHasher(project_root, AnalyzerFactory)
        cache = hasher.load_cache()

        manifest_paths = [n.yaml_path for n in nodes.values() if n.yaml_path]
        new_hashes = hasher.compute_hashes(manifest_paths)

        stale_seeds: set[str] = set()
        if not cache:
            return set(nodes.keys())

        for node_name, node in nodes.items():
            if not node.yaml_path:
                continue
            dir_path = node.yaml_path.parent.relative_to(project_root).as_posix()
            if dir_path not in cache or dir_path not in new_hashes:
                stale_seeds.add(node_name)
                continue
            if cache[dir_path].get("merkle_root") != new_hashes[dir_path].get("merkle_root"):
                stale_seeds.add(node_name)

        for node_name, node in nodes.items():
            for dep in node.consumes:
                if dep not in nodes:
                    stale_seeds.add(node_name)

        return stale_seeds

    @classmethod
    def from_project(
        cls,
        project_root: Path,
        *,
        auto_infer: bool = True,
    ) -> TopologyGraph:
        """Scan a project for context.yaml files and build the graph.

        Args:
            project_root: Root directory to scan.
            auto_infer: If True, auto-generate context.yaml for source
                directories missing one (using ContextInferrer).

        Returns:
            TopologyGraph with all discovered boundaries.
        """
        yaml = YAML()
        nodes: dict[str, TopologyNode] = {}
        warnings: list[str] = []
        logger.debug(
            "TopologyGraph.from_project: scanning '%s' (auto_infer=%s)", project_root, auto_infer
        )

        for ctx_file in sorted(project_root.rglob("context.yaml")):
            try:
                data = yaml.load(ctx_file)
            except Exception as exc:
                logger.warning("TopologyGraph: failed to parse '%s': %s", ctx_file, exc)
                warnings.append(f"Failed to parse {ctx_file}: {exc}")
                continue

            if data is None:
                logger.warning("TopologyGraph: empty context.yaml at '%s'", ctx_file)
                warnings.append(f"Empty context.yaml at {ctx_file}")
                continue

            name = data.get("name", "")
            if not name:
                logger.warning("TopologyGraph: missing 'name' in '%s'", ctx_file)
                warnings.append(f"Missing 'name' in {ctx_file}")
                continue

            # Parse operational metadata
            op_data = data.get("operational")
            operational = None
            if isinstance(op_data, dict):
                operational = OperationalMetadata(
                    multi_tenant_ready=op_data.get("multi_tenant_ready", False),
                    latency_critical=op_data.get("latency_critical", False),
                    max_latency_ms=op_data.get("max_latency_ms"),
                    data_freshness=op_data.get("data_freshness"),
                    reliability_target=op_data.get("reliability_target"),
                    async_ready=op_data.get("async_ready", False),
                    concurrency_model=op_data.get("concurrency_model"),
                )

            node = TopologyNode(
                name=name,
                level=data.get("level", ""),
                purpose=data.get("purpose", ""),
                archetype=data.get("archetype", ""),
                consumes=data.get("consumes", []) or [],
                exposes=data.get("exposes", []) or [],
                forbids=data.get("forbids", []) or [],
                constraints=data.get("constraints", []) or [],
                operational=operational,
                yaml_path=ctx_file,
            )
            nodes[name] = node

        if auto_infer:
            cls._auto_infer_missing(project_root, nodes, warnings)

        graph = cls(nodes, warnings)

        stale_seeds = cls._calculate_stale_seeds(project_root, nodes)

        final_stale_nodes = set(stale_seeds)
        for seed in stale_seeds:
            final_stale_nodes.update(graph.impact_of(seed))

        graph._stale_nodes = final_stale_nodes

        logger.info(
            "TopologyGraph: built graph with %d nodes, %d warnings. %d stale nodes.",
            len(nodes),
            len(warnings),
            len(graph._stale_nodes),
        )
        return graph

    @staticmethod
    def _auto_infer_missing(
        project_root: Path,
        nodes: dict[str, TopologyNode],
        warnings: list[str],
    ) -> None:
        """Auto-generate context.yaml for source directories missing one."""
        from specweaver.workspace.analyzers.factory import AnalyzerFactory
        from specweaver.workspace.context.inferrer import ContextInferrer

        inferrer = ContextInferrer(analyzer_factory=AnalyzerFactory)
        known_dirs = {n.yaml_path.parent for n in nodes.values() if n.yaml_path is not None}

        for subdir in sorted(project_root.rglob("*")):
            if not subdir.is_dir():
                continue
            if subdir in known_dirs:
                continue
            # Skip hidden directories and common non-source dirs
            if any(part.startswith(".") for part in subdir.relative_to(project_root).parts):
                continue

            result = inferrer.infer_and_write(subdir)
            if result.was_generated and result.node is not None:
                node = TopologyNode(
                    name=result.node.name,
                    level=result.node.level,
                    purpose=result.node.purpose,
                    archetype=result.node.archetype,
                    exposes=result.node.exposes,
                    yaml_path=result.node.yaml_path,
                )
                nodes[result.node.name] = node
                warnings.extend(result.warnings)

    # -- Query methods -------------------------------------------------

    def consumers_of(self, module: str) -> set[str]:
        """Direct consumers of a module (one hop reverse)."""
        return set(self._reverse.get(module, set()))

    def dependencies_of(self, module: str) -> set[str]:
        """All modules transitively depended on by `module`."""
        return self._traverse(module, self._forward)

    def impact_of(self, module: str) -> set[str]:
        """All modules transitively affected by changes to `module`."""
        return self._traverse(module, self._reverse)

    def cycles(self) -> list[list[str]]:
        """Detect circular dependency chains using Tarjan's algorithm."""
        index_counter = [0]
        stack: list[str] = []
        on_stack: set[str] = set()
        indices: dict[str, int] = {}
        lowlinks: dict[str, int] = {}
        result: list[list[str]] = []

        def _strongconnect(v: str) -> None:
            indices[v] = index_counter[0]
            lowlinks[v] = index_counter[0]
            index_counter[0] += 1
            stack.append(v)
            on_stack.add(v)

            for w in self._forward.get(v, set()):
                if w not in self._nodes:
                    continue  # skip dangling references
                if w not in indices:
                    _strongconnect(w)
                    lowlinks[v] = min(lowlinks[v], lowlinks[w])
                elif w in on_stack:
                    lowlinks[v] = min(lowlinks[v], indices[w])

            if lowlinks[v] == indices[v]:
                scc = _pop_scc(v, stack, on_stack)
                if _is_cycle(scc, self._forward):
                    result.append(sorted(scc))

        for node_name in self._nodes:
            if node_name not in indices:
                _strongconnect(node_name)

        return result

    def constraints_for(self, module: str) -> list[str]:
        """Aggregate constraints from the module and all its consumers."""
        all_constraints: list[str] = []

        # Module's own constraints
        if module in self._nodes:
            all_constraints.extend(self._nodes[module].constraints)

        # Constraints from all consumers (they impose requirements)
        for consumer in self._traverse(module, self._reverse):
            if consumer in self._nodes:
                all_constraints.extend(self._nodes[consumer].constraints)

        return all_constraints

    def operational_warnings(self, module: str) -> list[str]:
        """Flag SLA mismatches between a module and its dependencies."""
        warnings: list[str] = []
        node = self._nodes.get(module)
        if node is None or node.operational is None:
            return warnings

        op = node.operational

        # Check each dependency for SLA mismatches
        for dep_name in node.consumes:
            dep = self._nodes.get(dep_name)
            if dep is None or dep.operational is None:
                continue

            dep_op = dep.operational

            # Latency-critical consuming batch data source
            if op.latency_critical and dep_op.data_freshness == "batch":
                warnings.append(
                    f"SLA mismatch: '{module}' is latency-critical but "
                    f"consumes '{dep_name}' which has batch data freshness."
                )

            # Max latency mismatch
            if (
                op.max_latency_ms is not None
                and dep_op.max_latency_ms is not None
                and dep_op.max_latency_ms > op.max_latency_ms
            ):
                warnings.append(
                    f"SLA mismatch: '{module}' requires ≤{op.max_latency_ms}ms "
                    f"but consumes '{dep_name}' which allows ≤{dep_op.max_latency_ms}ms."
                )

        return warnings

    # -- Neighbourhood & constraint queries -----------------------------

    def neighbors_within(self, module: str, depth: int = 1) -> set[str]:
        """Return modules within *depth* hops (forward + reverse).

        depth=1 gives direct dependencies + consumers.
        depth=2 adds their neighbours, etc.
        """
        if depth < 1:
            return set()

        visited: set[str] = set()
        frontier = {module}

        for _ in range(depth):
            next_frontier: set[str] = set()
            for node in frontier:
                fwd = self._forward.get(node, set())
                rev = self._reverse.get(node, set())
                next_frontier |= (fwd | rev) - visited - {module}
            visited |= next_frontier
            frontier = next_frontier
            if not frontier:
                break

        return visited

    def modules_sharing_constraints(self, module: str) -> set[str]:
        """Return modules that share at least one constraint with *module*."""
        node = self._nodes.get(module)
        if node is None or not node.constraints:
            return set()

        my_constraints = set(node.constraints)
        result: set[str] = set()
        for name, other in self._nodes.items():
            if name == module:
                continue
            if my_constraints & set(other.constraints):
                result.add(name)
        return result

    def format_context_summary(
        self,
        module: str,
        related: set[str],
    ) -> list[TopologyContext]:
        """Build structured context for a set of related modules.

        Args:
            module: The target module (used to determine relationship labels).
            related: Module names to include in the summary.

        Returns:
            List of TopologyContext, one per related module that exists
            in the graph. Unknown modules are silently skipped.
        """
        direct_deps = self._forward.get(module, set())
        direct_consumers = self._reverse.get(module, set())
        contexts: list[TopologyContext] = []

        for name in sorted(related):
            node = self._nodes.get(name)
            if node is None:
                continue

            # Determine relationship label
            if name in direct_deps and name in direct_consumers:
                relationship = "mutual dependency"
            elif name in direct_deps:
                relationship = "direct dependency"
            elif name in direct_consumers:
                relationship = "direct consumer"
            else:
                relationship = "transitive neighbour"

            contexts.append(
                TopologyContext(
                    name=name,
                    purpose=node.purpose,
                    archetype=node.archetype,
                    relationship=relationship,
                    constraints=list(node.constraints),
                )
            )

        return contexts

    # -- Internal helpers ----------------------------------------------

    @staticmethod
    def _traverse(start: str, adj: dict[str, set[str]]) -> set[str]:
        """BFS/DFS traversal from start node through adjacency map."""
        visited: set[str] = set()
        queue = list(adj.get(start, set()))
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            queue.extend(adj.get(current, set()) - visited)
        return visited
