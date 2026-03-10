# SpecWeaver

**Specification-driven development lifecycle tool.**

SpecWeaver enforces a spec-first workflow: write a spec, validate it, review it with AI, then generate code and tests — all from the CLI.

```
sw init → sw draft → sw check → sw review → sw implement → sw check → sw review
```

## Features

- **Interactive spec drafting** — Co-author specs with an LLM, section by section
- **Static validation** — 15 built-in rules (7 spec + 8 code) catch issues before review
- **AI-powered review** — LLM reviews specs and code, returning ACCEPTED/DENIED with findings
- **Code generation** — Generate implementation + test files from a validated spec
- **Spec methodology** — Enforces a 5-section structure: Purpose, Contract, Protocol, Policy, Boundaries
- **Role-based git access** — LLM agents get MCP-like interfaces restricted to their role (implementer, reviewer, debugger, drafter)

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
# 1. Initialize a project
sw init --project ./my-project

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

| Command | Description |
|---|---|
| `sw init` | Scaffold a new project (dirs, config, templates) |
| `sw draft <name>` | Interactively draft a component spec |
| `sw check <file> --level component` | Validate a spec against S01–S10 rules |
| `sw check <file> --level code` | Validate code against C01–C08 rules |
| `sw review <file>` | AI-powered spec or code review |
| `sw implement <spec>` | Generate code + tests from a spec |

## Validation Rules

### Spec Rules (S01–S10)

| Rule | Name | What it checks |
|---|---|---|
| S01 | One-Sentence Test | Purpose is focused (low conjunction count) |
| S02 | Single Test Setup | No complex multi-environment setup |
| S05 | Day Test | Complexity ≤ 1 day of work |
| S06 | Concrete Example | Contract has code examples |
| S08 | Ambiguity Test | No weasel words (should, might, etc.) |
| S09 | Error Path | Error handling is specified |
| S10 | Done Definition | Verifiable completion criteria exist |

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
├── src/specweaver/
│   ├── atoms/              # Flow building blocks (Engine-level)
│   │   └── git/            # Git atom (checkpoint, integrate, publish)
│   ├── cli.py              # Typer CLI (sw command)
│   ├── config/             # Settings, YAML config
│   ├── context/            # Context providers (HITL)
│   ├── drafting/           # Interactive spec drafter
│   ├── implementation/     # Code generator
│   ├── llm/                # Gemini adapter, models, errors
│   ├── project/            # Scaffold, discovery
│   ├── review/             # AI reviewer
│   ├── tools/              # Agent tools
│   │   └── git/            # Git tool (executor, interfaces, role access)
│   └── validation/         # Rules engine (S01-S10, C01-C08)
├── tests/
│   ├── unit/               # 506 unit tests
│   └── e2e/                # 17 E2E lifecycle tests
├── docs/                   # Architecture & methodology docs
└── pyproject.toml
```

## Agent Tools

SpecWeaver provides role-restricted tools for LLM agents, inspired by the [flowManager](https://github.com/sbula/flowManager) atoms & tools architecture.

### GitTool

High-level git operations that agents call by intent, not raw commands. Each intent maps to a safe sequence of git commands executed on the target project directory (never SpecWeaver's own repo).

```python
from specweaver.tools.git.interfaces import create_git_interface

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
from specweaver.atoms.git import GitAtom

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
| CLI framework | Typer |
| LLM SDK | google-genai (Gemini) |
| Config | ruamel.yaml + Pydantic |
| Testing | pytest + pytest-asyncio |
| Linting | Ruff |

## License

MIT — see [LICENSE](LICENSE).
