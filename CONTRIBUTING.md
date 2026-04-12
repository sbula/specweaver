# Contributing to SpecWeaver

Thank you for your interest in contributing! This guide covers the development workflow, conventions, and how to submit changes.

## Prerequisites

- Python ≥ 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- Git

## Dev Setup

```bash
git clone https://github.com/sbula/specweaver.git
cd specweaver
uv sync --all-extras
```

## Running Tests

```bash
# Full test suite
uv run pytest

# With coverage
uv run pytest --cov=specweaver --cov-report=term-missing

# Specific test file
uv run pytest tests/unit/config/test_database.py -v
```

Target coverage: **70–90%**.

## Linting & Formatting

```bash
# Lint check
uv run ruff check src/ tests/

# Auto-fix
uv run ruff check src/ tests/ --fix
```

## Commit Conventions

We use **conventional commits**. Every commit message must match:

```
<type>(<optional scope>): <description>
```

| Type | When to use |
|------|-------------|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Adding or updating tests |
| `refactor` | Code change that doesn't fix a bug or add a feature |
| `chore` | Build, CI, tooling changes |

Examples:
- `feat: add weasel word detection rule`
- `fix(cli): handle missing API key gracefully`
- `test: add path traversal edge cases`

## Branch Naming

Use the format `<type>/<description>`:

```
feat/add-topology-warnings
fix/cli-override-parsing
docs/update-readme
```

## Test Conventions

- **TDD**: Write tests before implementation when possible
- **Structure mirrors source**: `src/specweaver/config/database.py` → `tests/unit/config/test_database.py`
- **Three test layers**: `tests/unit/` (isolated), `tests/integration/` (cross-component), `tests/e2e/` (full lifecycle)
- **Descriptive names**: `test_empty_grant_does_not_match_files`, not `test_case_1`
- **Docstrings**: Every test should have a one-line docstring explaining the scenario

## Architecture Overview

See [docs/INDEX.md](docs/INDEX.md) for a guided tour of the documentation. Key entry points:

- **README.md** — Features, CLI reference, agent tools
- **docs/architecture/methodology_index.md** — Spec methodology (10-test battery, fractal decomposition)
- **docs/architecture/context_yaml_spec.md** — Context boundary manifest specification
- **docs/roadmap/specweaver_roadmap.md** — Roadmap and future plans

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`feat/your-feature`)
3. Write tests first, then implement
4. Run `uv run pytest` and `uv run ruff check src/ tests/` — both must pass
5. Commit using conventional commit format
6. Open a pull request with a clear description

## License

By contributing, you agree that your contributions will be licensed under the Apache License, Version 2.0.
