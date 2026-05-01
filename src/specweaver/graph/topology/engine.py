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


class TopologyEngine:
    """Generic directed graph engine for topology math."""

    def __init__(self) -> None:
        import threading

        self._lock = threading.Lock()
        self._forward: dict[str, set[str]] = {}
        self._reverse: dict[str, set[str]] = {}
        self._nodes: set[str] = set()

    @property
    def nodes(self) -> set[str]:
        with self._lock:
            return set(self._nodes)

    def add_node(self, node: str) -> None:
        with self._lock:
            self._nodes.add(node)
            self._forward.setdefault(node, set())
            self._reverse.setdefault(node, set())

    def add_edge(self, source: str, target: str) -> None:
        with self._lock:
            self._nodes.add(source)
            self._nodes.add(target)
            self._forward.setdefault(source, set()).add(target)
            self._reverse.setdefault(source, set())
            self._reverse.setdefault(target, set()).add(source)
            self._forward.setdefault(target, set())

    def get_forward(self, node: str) -> set[str]:
        with self._lock:
            return set(self._forward.get(node, set()))

    def get_reverse(self, node: str) -> set[str]:
        with self._lock:
            return set(self._reverse.get(node, set()))

    def traverse(self, start: str, forward: bool = True) -> set[str]:
        """BFS/DFS traversal from start node."""
        with self._lock:
            adj = self._forward if forward else self._reverse
            visited: set[str] = set()
            queue = list(adj.get(start, set()))
            while queue:
                current = queue.pop()
                if current in visited:
                    continue
                visited.add(current)
                queue.extend(adj.get(current, set()) - visited)
            return visited

    def cycles(self) -> list[list[str]]:
        """Detect circular dependency chains using Tarjan's algorithm."""
        with self._lock:
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

    def neighbors_within(self, module: str, depth: int = 1) -> set[str]:
        """Return nodes within *depth* hops (forward + reverse)."""
        if depth < 1:
            return set()

        # RT-27: Enforce hard-coded maximum depth to prevent OOM
        actual_depth = min(depth, 5)

        with self._lock:
            visited: set[str] = set()
            frontier = {module}

            for _ in range(actual_depth):
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
