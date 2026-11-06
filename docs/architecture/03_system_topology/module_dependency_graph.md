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
`core/flow/engine/run_profile.py`, which returns the profile the run builder decided
(`commons.project_profile`, read by `workspace/project`, `TECH-079`). The flow handlers
keep the run: they read and write the files, pick the model and log the lineage.

**Arbitration (`TECH-082`):** when a dual run's scenario tests fail, `workflows/arbitration` asks the
model who is at fault and guards what each side may read: no scenario word reaches the coder, no
code reaches the scenario side. It reads text only; the flow handler builds the stack trace filter,
checks the evidence and routes the verdict.

**The boundary rule (`TECH-082`):** `assurance/graph/boundary_rule.py` builds each folder's
effective rule from every `context.yaml` up the tree. `sandbox/language/core/boundary_check.py`
judges one code file with it, the same way in all 9 languages: the parser lists the imports, the
language's resolver (`workspace/ast/refactor/imports.py`) names the project file each reaches. A
library meets only `forbids`, by its written name. The stricter tools a project configures (tach,
dependency-cruiser, go-arch-lint) run beside it from one table in `boundary_extras.py`.
