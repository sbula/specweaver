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

**Validation orchestration (`TECH-082`):** the validation rules (`assurance/validation`) are pure.
The work around them lives in `assurance/validation/orchestration`: it picks a file's pipeline,
runs the sandbox atoms that hydrate the rules' context, resolves paths inside the project, and asks
the model for the drift root cause. The validation CLI, the API and the flow handlers all enter
there; none of them reaches into another's code for it. The module sits under a pure parent and
declares its use of the sandbox and the model in `widens`, as the boundary rule requires
(`context_yaml_spec.md` §Context inheritance).

**Implementation work (`TECH-082`):** what a task writes — its files, its framework, its contract
and the model's lint repair — lives in `workflows/implementation`. That code takes the language as
given and imports neither the flow engine nor the sandbox; callers get the run's language from
`core/flow/engine/run_language.py`, the one place that falls back to detection. The flow handlers
keep the run: they read and write the files, pick the model and log the lineage.
