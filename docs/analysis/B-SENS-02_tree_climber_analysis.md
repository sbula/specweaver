# Architectural Analysis: bstee615/tree-climber

## Context
This document analyzes the [tree-climber](https://github.com/bstee615/tree-climber) repository to extract mathematical models and architectural patterns for SpecWeaver's upcoming `B-SENS-02: Persistent Knowledge Graph Builder`.

We are specifically **not** adopting `tree-climber` as a direct dependency due to its limited polyglot support (C/Java only), visualization bloat, and low bus-factor. Instead, we are adopting its theoretical dataflow models.

## 1. The CFG (Control Flow Graph) Builder Pattern
The `tree-climber` AST utility translates raw Tree-Sitter Concrete Syntax Trees (CST) into Control Flow Graphs using the **Visitor Pattern**.

**How it works:**
*   It traverses the AST.
*   When it hits a branch (e.g., `if` statement), it explicitly creates two edges: a `True` edge to the conditional block, and a `False` edge bypassing it.
*   It filters out "anonymous nodes" (like semicolons or parenthesis) keeping only semantic nodes.

**SpecWeaver Takeaway for B-SENS-02:**
We already have `D-SENS-02` which extracts the skeleton. To build the Knowledge Graph, we must implement a similar Visitor Pattern in Python that maps execution flow (Edges) between the Tree-Sitter AST nodes (Vertices), specifically ensuring we capture conditional branching.

## 2. Iterative Dataflow Solver (Round-Robin)
The most valuable asset in `tree-climber` is its `RoundRobinSolver` (`src/tree_climber/dataflow/solver.py`). It implements Kildall's iterative dataflow analysis framework.

**How it works:**
*   It calculates the properties of a program by maintaining two mathematical sets for every node: `IN` facts and `OUT` facts.
*   **The Loop:** It iterates through every node in the graph over and over again.
*   **The Meet Operator:** It merges the `OUT` facts of all predecessor nodes to calculate the current node's `IN` facts.
*   **Convergence:** It stops looping when a full pass results in `changed = False` (meaning the equations have stabilized).

**SpecWeaver Takeaway for B-SENS-02:**
This is how we will calculate **Def-Use Chains** (Variable Definition to Variable Usage). We will write our own `DataflowSolver` using this exact `IN/OUT` set convergence math, but we will store the resulting links as Edges in our `specweaver.db` SQLite database so it persists across sessions.

## 3. Value Numbering (Deduplication)
To prevent the graph from exploding in size, `tree-climber` uses structural hashing. If two sub-expressions compute the exact same thing, they are merged into a single vertex in the DAG.

**SpecWeaver Takeaway for B-SENS-02:**
This maps directly to SpecWeaver's existing `A-SENS-01: Deep Semantic Hashing`. When inserting a Node into the SQLite database, we will use its Semantic Hash as its Primary Key. If the hash exists, we draw an Edge to the existing node rather than inserting a duplicate.

## Conclusion
The `tree-climber` repository proves that building a robust, language-agnostic Control Flow Graph on top of Tree-Sitter is completely viable in pure Python. By adapting their Round-Robin Dataflow Solver and Visitor patterns to target our SQLite backend, we can implement `B-SENS-02` safely without incurring third-party technical debt.
