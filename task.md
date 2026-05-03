[Workflow: /dev] Task Breakdown - TECH-01 SF-2
Commit Boundary 1: Core Config & Graph Domain Decentralization

[x] Task 1: Extract get_db and bootstrap_database to src/specweaver/core/config/cli_db_utils.py and update existing imports.
[x] Task 2: Move config.py and config_routing.py to src/specweaver/core/config/interfaces/cli.py and create context.yaml. Update tach.toml.
[x] Task 3: Move _load_topology from _helpers.py to graph. Move graph.py and lineage.py to src/specweaver/graph/interfaces/cli.py. Create core/context.yaml and interfaces/context.yaml. Update tach.toml.
Commit Boundary 2: Assurance & Infrastructure Domains

[x] Task 4: Move _display_results and _print_summary from _helpers.py. Move drift.py and validation.py to src/specweaver/assurance/validation/interfaces/cli.py. Create contexts and update tach.toml.
[x] Task 5: Move standards.py to src/specweaver/assurance/standards/interfaces/cli.py. Create contexts and update tach.toml.
[x] Task 6: Move cost_commands.py and usage_commands.py to src/specweaver/infrastructure/llm/interfaces/cli.py. Create contexts and update tach.toml.
Commit Boundary 3: Workflows, Workspace, and Flow Domains

[ ] Task 7: Move implement.py to src/specweaver/workflows/implementation/interfaces/cli.py. Create contexts and update tach.toml.
[ ] Task 8: Move review.py to src/specweaver/workflows/review/interfaces/cli.py. Create contexts and update tach.toml.
[ ] Task 9: Move _run_workspace_op from _helpers.py. Move projects.py, constitution.py, hooks.py to src/specweaver/workspace/project/interfaces/cli.py. Create contexts and update tach.toml.
[ ] Task 10: Move pipelines.py to src/specweaver/core/flow/interfaces/cli.py. Create contexts and update tach.toml.
Commit Boundary 4: Global CLI Layer Clean-up & Wiring

[ ] Task 11: Move serve.py to src/specweaver/interfaces/cli/routers/serve_router.py.
[ ] Task 12: Delete legacy L6 files (_helpers.py, _db_utils.py, etc.) ensuring no orphan imports remain.
[ ] Task 13: Refactor src/specweaver/interfaces/cli/main.py to dynamically mount all decentralized Typer apps and use ctx.obj for state injection where applicable.
[ ] Task 14: Update all test imports in tests/unit/interfaces/cli/ to target their new domain locations, ensuring the full suite remains green.
