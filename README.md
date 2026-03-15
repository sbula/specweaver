# SpecWeaver

**Specification-driven development lifecycle tool.**

SpecWeaver enforces a spec-first workflow: write a spec, validate it, review it with AI, then generate code and tests — all from the CLI.

```
sw init <name> → sw draft → sw check → sw review → sw implement → sw check → sw review
```

## Features

- **Interactive spec drafting** — Co-author specs with an LLM, section by section
- **Static validation** — 19 built-in rules (11 spec + 8 code) catch issues before review
- **AI-powered review** — LLM reviews specs and code, returning ACCEPTED/DENIED with findings
- **Code generation** — Generate implementation + test files from a validated spec
- **Pipeline definitions** — YAML-defined workflows with configurable gates, retries, and feedback loops
- **Spec methodology** — Enforces a 5-section structure: Purpose, Contract, Protocol, Policy, Boundaries
- **Context & topology** — `context.yaml` boundary manifests + dependency graph for module-level architecture enforcement
- **Role-based agent tools** — LLM agents get MCP-like interfaces (git, filesystem) restricted to their role and granted paths

## Quickstart

### Prerequisites

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- A [Gemini API key](https://aistudio.google.com/apikey) (free tier works)

### Install

```bash
git clone https://github.com/sbula/specweaver.git
cd specweaver
uv sync --all-extras
```

### Set up your API key

```bash
# Linux/macOS
export GEMINI_API_KEY="your-key-here"

# Windows (PowerShell)
$env:GEMINI_API_KEY = "your-key-here"
```

### Run the pipeline

```bash
# 1. Initialize and register a project
sw init my-app --path ./my-project

# 2. Draft a spec interactively
sw draft greet_service --project ./my-project

# 3. Validate the spec
sw check specs/greet_service_spec.md --level component --project ./my-project

# 4. Review the spec with AI
sw review specs/greet_service_spec.md --project ./my-project

# 5. Generate code + tests from the spec
sw implement specs/greet_service_spec.md --project ./my-project

# 6. Validate the generated code
sw check src/greet_service.py --level code --project ./my-project

# 7. Review the code against the spec
sw review src/greet_service.py --spec specs/greet_service_spec.md --project ./my-project
```

## CLI Commands

### Spec Pipeline

| Command | Description |
|---|---|
| `sw init <name>` | Register project in DB + scaffold dirs and templates |
| `sw draft <name>` | Interactively draft a component spec |
| `sw check <file> --level component` | Validate a spec against S01–S11 rules |
| `sw check <file> --level code` | Validate code against C01–C08 rules |
| `sw check --strict` | Treat warnings as failures (exit code 1) |
| `sw check --set RULE.FIELD=VALUE` | One-off threshold override (e.g. `S08.fail_threshold=5`) |
| `sw review <file>` | AI-powered spec or code review |
| `sw implement <spec>` | Generate code + tests from a spec |

### Project Management

| Command | Description |
|---|---|
| `sw init <name> --path <path>` | Register a project (name + directory) in the DB |
| `sw use <name>` | Switch the active project |
| `sw projects` | List all registered projects (marks active) |
| `sw remove <name>` | Unregister a project (files stay on disk) |
| `sw update <name> path <path>` | Update a project's root path |
| `sw scan` | Auto-generate missing `context.yaml` files |

### Validation Configuration

| Command | Description |
|---|---|
| `sw config set <rule> --warn/--fail/--enabled` | Set a per-project rule override |
| `sw config get <rule>` | Show the current override for a rule |
| `sw config list` | List all overrides for the active project |
| `sw config reset <rule>` | Remove an override (revert to defaults) |
| `sw config set-log-level <level>` | Set the log level for the active project |
| `sw config get-log-level` | Show current log level and log file path |

### Pipeline Execution

| Command | Description |
|---|---|
| `sw run <pipeline> <spec_or_module>` | Execute a pipeline against a spec file or module |
| `sw run <pipeline> <spec> --verbose` | Show detailed handler output + tracebacks |
| `sw run <pipeline> <spec> --json` | Output NDJSON event stream (machine-readable) |
| `sw resume` | Resume the latest parked/failed pipeline run |
| `sw resume <run_id>` | Resume a specific run by ID |
| `sw pipelines` | List available pipeline templates |

## Validation Rules

### Spec Rules (S01–S11)

| Rule | Name | What it checks | Configurable |
|---|---|---|---|
| S01 | One-Sentence Test | Purpose is focused (low conjunction count) | ✅ warn/fail conjunctions, max_h2 |
| S02 | Single Test Setup | No complex multi-environment setup | — |
| S03 | Stranger Test | External references and undefined terms | ✅ warn/fail threshold |
| S04 | Dependency Direction | Cross-reference direction + dead-link detection | ✅ warn/fail threshold |
| S05 | Day Test | Complexity ≤ 1 day of work | ✅ warn/fail threshold |
| S06 | Concrete Example | Contract has code examples | — |
| S07 | Test-First | Contract testability scoring | ✅ warn/fail score |
| S08 | Ambiguity Test | No weasel words (should, might, etc.) | ✅ warn/fail threshold |
| S09 | Error Path | Error handling is specified | — |
| S10 | Done Definition | Verifiable completion criteria exist | — |
| S11 | Terminology | Inconsistent casing + undefined domain terms | ✅ warn/fail threshold |

### Code Rules (C01–C08)

| Rule | Name | What it checks |
|---|---|---|
| C01 | Syntax Valid | Code parses without syntax errors |
| C02 | Tests Exist | Corresponding test file exists |
| C03 | Tests Pass | `pytest` passes (subprocess) |
| C04 | Coverage | Coverage meets threshold (subprocess) |
| C05 | Import Direction | No upward imports (layer violations) |
| C06 | No Bare Except | No `except:` without exception type |
| C07 | No Orphan TODO | No TODOs without ticket references |
| C08 | Type Hints | Public functions have type annotations |

## Project Structure

```
~/.specweaver/
    specweaver.db               # SQLite: projects, LLM profiles, active state

├── src/specweaver/
│   ├── cli.py                  # Typer CLI (sw command)
│   ├── logging.py              # Logging setup (RotatingFileHandler, per-project logs)
│   ├── config/                 # SQLite database, settings, migrations
│   ├── context/                # Context providers (HITL, inferrer, analyzers)
│   ├── drafting/               # Interactive spec drafter
│   ├── flow/                   # Pipeline engine: models, parser, runner, state, handlers, store
│   ├── graph/                  # TopologyGraph, dependency selectors
│   ├── implementation/         # Code generator
│   ├── llm/                    # Gemini adapter, models, errors
│   ├── loom/                   # Dev environment interaction layer
│   │   ├── atoms/              # Engine-level building blocks
│   │   │   ├── filesystem/     # Filesystem atom (engine-level)
│   │   │   └── git/            # Git atom (checkpoint, integrate, publish)
│   │   ├── commons/            # Shared infrastructure (executors)
│   │   │   ├── filesystem/     # FileExecutor
│   │   │   └── git/            # GitExecutor, EngineGitExecutor
│   │   └── tools/              # Agent-facing tools
│   │       ├── filesystem/     # Filesystem tool (grants, roles, intents)
│   │       └── git/            # Git tool (intents, interfaces, roles)
│   ├── pipelines/              # Bundled pipeline templates (YAML)
│   ├── project/                # Scaffold, discovery
│   ├── review/                 # AI reviewer
│   └── validation/             # Rules engine (S01-S11, C01-C08)
├── tests/                      # 1696+ tests (unit, integration, E2E)
├── docs/                       # Architecture & methodology docs
└── pyproject.toml
```

## Context & Topology

Every module in a SpecWeaver project can have a `context.yaml` boundary manifest — a structured file that declares the module's identity, dependencies, and architectural constraints.

```yaml
# src/billing/context.yaml
name: billing
level: module
purpose: Calculate invoice totals and apply discounts.
archetype: pure-logic
consumes: [pricing, customers]
constraints: [no-direct-db, stateless]
```

**TopologyGraph** builds a project-wide dependency graph from all `context.yaml` files:

```python
from specweaver.graph.topology import TopologyGraph

graph = TopologyGraph.from_project(project_path, auto_infer=True)
graph.dependencies_of("billing")     # → {"pricing", "customers"}
graph.impact_of("pricing")           # → {"billing"} (who would break)
graph.operational_warnings("billing") # → latency SLA mismatches
```

- **Auto-infer** (`sw scan`): generates `context.yaml` for Python packages that lack one, using docstrings, imports, and heuristics
- **Operational warnings**: detects SLA mismatches (e.g., a 50ms-latency module depending on a 500ms dependency)
- **Constraint sharing**: finds modules with overlapping constraints for cross-cutting concern analysis

See [context_yaml_spec.md](docs/architecture/context_yaml_spec.md) for the full specification.

## Agent Tools

SpecWeaver provides role-restricted tools for LLM agents, inspired by the [flowManager](https://github.com/sbula/flowManager) atoms & tools architecture.

### FileSystemTool

Grant-based file access for agents. Each agent receives a set of `FolderGrant` objects that define which directories it can read, write, or execute — with path traversal prevention built in.

```python
from specweaver.loom.tools.filesystem.tool import FileSystemTool, FolderGrant, AccessMode

grants = [FolderGrant("src/billing", AccessMode.WRITE, recursive=True)]
tool = FileSystemTool(executor=executor, role="implementer", grants=grants)

tool.read_file("src/billing/calc.py")           # ✅ within grant
tool.create_file("src/billing/utils.py", code)  # ✅ write access
tool.read_file("src/auth/secrets.py")           # ❌ outside grant
tool.read_file("src/billing/../../etc/passwd")  # ❌ path traversal blocked
```

| Intent | Description |
|---|---|
| `read_file` | Read file contents (with line range support) |
| `create_file` | Create a new file |
| `edit_file` | Replace a specific section of a file |
| `delete_file` | Remove a file |
| `list_directory` | List directory contents |
| `search_content` | Regex search across files |
| `find_placement` | Suggest where to place new code (uses `context.yaml`) |

**Security:** All paths are normalized via `posixpath.normpath`, absolute paths are rejected, and `..` traversal beyond grant boundaries returns an error.

### GitTool

High-level git operations that agents call by intent, not raw commands. Each intent maps to a safe sequence of git commands executed on the target project directory (never SpecWeaver's own repo).

```python
from specweaver.loom.tools.git.interfaces import create_git_interface

# Agent gets only the methods its role allows
git = create_git_interface("implementer", project_path)
git.commit("feat: add login endpoint")    # ✅ stages, validates, commits
git.history()                              # ❌ AttributeError — not on this interface
```

| Role | Allowed Intents |
|---|---|
| **Implementer** | commit, inspect_changes, discard, uncommit, start_branch, switch_branch |
| **Reviewer** | history, show_commit, blame, compare, list_branches |
| **Debugger** | history, file_history, show_old, search_history, reflog, inspect_changes |
| **Drafter** | commit, inspect_changes, discard |
| **Conflict Resolver** | list_conflicts, show_conflict, mark_resolved, abort_merge, complete_merge |

> The `conflict_resolver` role is hidden — only the Engine can activate it temporarily when a merge conflict occurs during `integrate`.

### GitAtom

Flow-level git operations for the Engine. Unlike GitTool (agent-facing, role-restricted), GitAtom handles orchestrator-driven tasks using `EngineGitExecutor` (no blocked commands).

```python
from specweaver.loom.atoms.git import GitAtom

atom = GitAtom(cwd=project_path)
result = atom.run({"intent": "checkpoint", "message": "flow step complete"})
result = atom.run({"intent": "integrate", "source": "feat/login", "target": "main"})
```

| Intent | Purpose | Git commands |
|---|---|---|
| **checkpoint** | Semantic commit after flow step | add, diff, commit |
| **isolate** | Create isolation branch for flow | switch -c |
| **restore** | Return to original branch | switch |
| **discard_all** | Clean working tree | restore . |
| **rollback** | Undo last checkpoint | reset --soft HEAD~1 |
| **publish** | Push flow results to remote | push |
| **integrate** | Merge branch into target | checkout, merge |
| **sync** | Pull latest from remote | fetch, pull |
| **tag** | Mark release/milestone | tag |

**Built-in guardrails:**
- Conventional commit messages enforced (`feat:`, `fix:`, `docs:`, ...)
- Branch naming enforced (`feat/`, `fix/`, `docs/`, ...)
- `push`, `pull`, `merge`, `rebase`, `tag` are permanently blocked
- Auto-stash on branch switch

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run linter
uv run ruff check src/ tests/

# Run tests with coverage
uv run pytest --cov=specweaver --cov-report=term-missing
```

## Tech Stack

| Component | Choice |
|---|---|
| Language | Python ≥ 3.11 |
| Package manager | uv |
| CLI framework | Typer + Rich |
| LLM SDK | google-genai (Gemini) |
| Config store | SQLite (WAL mode) + Pydantic |
| Legacy config | ruamel.yaml (migration only) |
| Testing | pytest + pytest-asyncio |
| Linting | Ruff |

## License

MIT — see [LICENSE](LICENSE).
