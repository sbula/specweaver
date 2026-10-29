# Module Dependency Graph

Which module may import which. A hand-drawn graph here went stale, so this page does not draw one.
`tach.toml` is the graph, and the `tach` gate fails any import that leaves it. The rules and their
checks: [Hard Dependency Rules](hard_dependency_rules.md).

To see the live graph:

```bash
python -m tach show --mermaid -o .tmp/module_graph.mmd
```

The top level of `src/specweaver/` is grouped into `assurance/`, `commons/`, `core/`, `graph/`,
`infrastructure/`, `interfaces/`, `sandbox/`, `workflows/` and `workspace/`.

**Run setup (`TECH-077`):** `interfaces/run_setup` builds every run's context for the CLI and the
API (rule file, standards, settings sections, isolation, model router, topology). It sits beside
the doors, not in the engine, so `core/flow` keeps its rule of never using `workspace/project`.

**The shell and the CLIs (`TECH-081`):** `interfaces/cli` is the shell; it imports every domain
CLI, and no domain CLI imports it. The helpers the CLIs share live in `interfaces/cli_kit`, and the
code that starts a run from a command lives in `interfaces/run_doors`.
