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
specweaver/
├── src/specweaver/
│   ├── cli.py              # Typer CLI (sw command)
│   ├── config/             # Settings, YAML config
│   ├── context/            # Context providers (HITL)
│   ├── drafting/           # Interactive spec drafter
│   ├── implementation/     # Code generator
│   ├── llm/                # Gemini adapter, models, errors
│   ├── project/            # Scaffold, discovery
│   ├── review/             # AI reviewer
│   └── validation/         # Rules engine (S01-S10, C01-C08)
├── tests/
│   ├── unit/               # 270 unit tests
│   └── e2e/                # 17 E2E lifecycle tests
├── docs/                   # Architecture & methodology docs
└── pyproject.toml
```

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
