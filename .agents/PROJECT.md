# SpecWeaver — what it is and where things live

## What it is

A tool for building software from specifications.

It does three things:

1. **Writes and checks specs.** A 12-test battery scores whether a spec is good enough to build from.
2. **Runs pipelines.** YAML defines the steps: draft, review, generate, test, gate.
3. **Boxes in the agents.** Generated code runs in a sandbox with a limited set of tools.

## What it is aiming at

The platform is **proven** when a person can run `sw init`, `sw check`, `sw draft`,
`sw implement` and `sw review` end to end on a real project.

It is **enterprise-ready** when it has also been used on an external system that is not this one.

Full list: the Success Criteria section of `docs/roadmap/master_story_roadmap.md`.

## Where things live

| You want | Look in |
|---|---|
| The code | `src/specweaver/` |
| What is planned and what is done | `docs/roadmap/` |
| Why the code is shaped this way | `docs/architecture/` |
| How to do a task here | `.claude/skills/` |
| Traps that have cost real sessions | `docs/dev_guides/working_in_this_repo.md` |
| A map of all documentation | `docs/INDEX.md` |

Inside `src/specweaver/`:

| Package | Holds |
|---|---|
| `core/` | Config, database, the pipeline engine |
| `graph/` | The in-memory knowledge graph |
| `sandbox/` | Execution, tools, isolation |
| `infrastructure/` | Adapters to outside things, mainly LLMs |
| `interfaces/` | The `sw` CLI and the REST API |
| `workflows/` | Drafting, planning, implementation, review |
| `workspace/` | Project discovery, AST parsing, analysers |
| `assurance/` | The validation battery and standards discovery |
| `commons/` | Shared helpers |

## The stack

Python 3.11+. **uv**, not pip. pytest. mypy strict. ruff. **tach** enforces module boundaries.

Architecture is DDD and hexagonal: pure logic in the middle, all input and output at the edges.

## Documentation that is expected

Each capability keeps its papers in `docs/roadmap/features/<topic>/<ID>/`:

| File | Says |
|---|---|
| `<ID>_design.md` | What it must do. The FR table is the contract |
| `<ID>_implementation_plan.md` | How it will be built, and which FRs it owns |
| `<ID>_mutants.json` | Mutants the nightly run uses to check the tests are real |

A capability is also listed twice: in `docs/roadmap/capability_matrix.md` and in its topic file.
Both must agree with the code.

## Testing

Three tiers, and they are not swappable:

| Tier | Tests | Mocks |
|---|---|---|
| `tests/unit/` | One function or class | Everything outside it |
| `tests/integration/` | Two or more real parts together | Only external services |
| `tests/e2e/` | A whole user path | Nothing |

```bash
export PATH="$PWD/.venv/bin:$PATH"     # absolute, always

python -m pytest tests/unit/core/ -v          # one module: serial is faster
python -m pytest -n auto --tb=short -q        # everything: always parallel
python scripts/quality.py cb                  # the commit gate
python scripts/quality.py doc                 # the registry gate
```

**Use `.venv/bin/python`, never a bare `python`.** The system one can import `specweaver` and will
run the suite without `pytest-xdist`, so `-n auto` is silently ignored and every run is serial.

**A pipe hides the exit code.** `$?` after `| tail` is `tail`'s. Use
`python scripts/quality.py cb 2>&1 | tail -3; s=${PIPESTATUS[0]}`.

**There are no accepted deltas.** The suite is green. A failure you see is a failure you
caused — there is no list of known failures to file it under.

More traps, each one an incident: `docs/dev_guides/working_in_this_repo.md`.

## Sources

`ORIGINS.md` records where ideas came from — the tools and papers this design borrows from.
