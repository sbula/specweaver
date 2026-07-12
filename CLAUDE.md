# SpecWeaver

> Specification-driven development lifecycle tool. Enforces spec quality through a 12-test battery and manages AI agents via role-restricted tool interfaces.

## Tech Stack

- **Language:** Python 3.11+ (strict mypy, ruff lint)
- **Package Manager:** uv (NOT pip)
- **Test Runner:** pytest (markers: `live`, `integration`, `e2e`)
- **Boundary Enforcement:** tach (module dependency boundaries in `tach.toml`)
- **Architecture:** DDD + Hexagonal. Pure domain logic; I/O at the edges via adapters.

## Project Map

```
src/specweaver/
├── core/               # Domain kernel
│   ├── config/         # Pydantic settings + SQLite DB
│   └── flow/           # Pipeline engine (models, runners, gates, handlers)
├── graph/              # In-Memory Knowledge Graph (NetworkX)
│   ├── lineage/        # Change lineage tracking
│   └── interfaces/     # CLI bindings for graph commands
├── sandbox/            # Execution engine (3-layer)
│   ├── tools/          # Agent-facing capability providers
│   ├── atoms/          # Engine-internal workflow ops
│   └── commons/        # Shared executors + helpers
├── infrastructure/     # External adapters
│   └── llm/            # LLM provider abstraction + adapters
├── interfaces/         # Delivery mechanisms
│   ├── cli/            # Typer CLI (`sw` command)
│   └── api/            # FastAPI REST server
├── workflows/          # Business processes
│   ├── drafting/       # LLM-assisted spec drafting
│   ├── implementation/ # Code generation from specs
│   ├── planning/       # Implementation plan generation
│   └── review/         # LLM-based spec/code review
├── workspace/          # Project discovery, AST, analyzers
├── assurance/          # Quality enforcement
│   ├── validation/     # 12-test spec quality battery
│   └── standards/      # Codebase standards auto-discovery
└── commons/            # Cross-cutting shared utilities

specs/                  # YAML spec definitions (input to validation battery)
```

## Test Commands

```bash
# Module-scoped (preferred — fast feedback)
python -m pytest tests/unit/core/ -v --tb=short
python -m pytest tests/unit/sandbox/ -v --tb=short
python -m pytest tests/unit/graph/ -v --tb=short

# By tier
python -m pytest tests/unit/ -v --tb=short -q
python -m pytest tests/integration/ -v --tb=short -q
python -m pytest tests/e2e/ -v --tb=short -q

# Full suite (before commit)
python -m pytest -v --tb=short -q

# Quality checks
ruff check src/ tests/
mypy src/
tach check
```

## Critical Rules

1. **No subprocess.** Use `SubprocessExecutor` from `specweaver.sandbox.execution.executor`.
2. **No cross-layer imports.** Respect `tach.toml` boundaries. Run `tach check` to verify.
3. **No guessing.** If anything is unclear, STOP and ask. Never assume.
4. **TDD always.** Red → Green → Refactor. Every change starts with a failing test.
5. **Re-read before edit.** Always read a file immediately before modifying it.
6. **Context files.** Read `context.yaml` in any module before modifying it.

## Commit Convention

Format: `<type>(<scope>): <description>`
Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
Scope: module name (e.g., `flow`, `sandbox`, `graph`, `config`)
Example: `feat(flow): add handover persistence for pipeline state`

## Architecture Reference

For deep architecture docs: `docs/architecture/README.md`
For dev guides: `docs/dev_guides/`
For engineering standards (Antigravity agent): `.agents/AGENTS.md`

## Session Strategy

- **Default (Sonnet):** Use for ~80% of work — coding, tests, refactoring, debugging.
- **Opus (`/model opus` or `claude --model opus`):** Reserve for complex architectural reasoning, multi-module refactors, deep debugging.
- **`opusplan`:** Use when you want Opus for the planning phase and automatic switch to Sonnet for execution.
- **`/compact` at ~60%:** Run proactively before context gets stale. Save state to CLAUDE.md or docs first.
- **`/clear` or new session:** Use when the session has drifted badly, debugging loops are circular, or you're switching to a completely different feature.
- **Subdirectory anchoring:** Launch `claude` from `src/specweaver/core/` (or whichever module you're working on) to limit blast radius. Claude walks up to find this root CLAUDE.md automatically.

<!-- Last verified: 2026-07-12 -->
