# SpecWeaver

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

An experimental harness for spec-driven, verifiable AI code generation — built to develop a
trading system reliably with small local LLMs.

**Status:** experimental, under active development, not production-ready. Not on PyPI — install
from source.

## Why it exists

I am building Quantivista, a trading system. I want to build it with small language models that
run on my own hardware (an NVIDIA GB10-class machine), not only with large hosted models. Small
models make more mistakes, so the process around them has to catch those mistakes before they
land. SpecWeaver is that process: a spec comes first, deterministic checks judge it, the model
works in an isolated copy of the repository, and only permitted changes come back.

## Core ideas

- **Deterministic code over LLM work.** Anything a program can decide, a program decides. The
  12-rule spec battery (`sw check`, rules S01–S12) is plain Python: no model, no API key, the same
  answer every time.
- **Check the spec before implementation.** `sw check` scores a spec for ambiguity, missing error
  paths, missing examples, untestable contracts and hidden dependencies. `sw implement` is meant to
  run on a spec that has passed.
- **Verify the implementation against the spec.** `sw review --spec` has an LLM compare code with its
  spec and answer `ACCEPTED` or `DENIED`. `sw drift` detects when code has moved away from the spec it was generated from.
- **Change protection.** Generated code is written in an ephemeral git worktree. At the end of the
  run, changes outside the paths the step may touch are stripped before anything is merged back.
  Agents only get the tools their role allows.
- **Design Assurance Levels (DAL).** Borrowed from DO-178C (avionics): each part of a project
  declares how critical it is, from `DAL_A` (mission-critical) to `DAL_E` (prototype), in its
  `context.yaml`. Stricter levels change what the checks accept. Example: at `DAL_A` and `DAL_B`
  a warning is a failure — the same spec that passes with two warnings at `DAL_E` fails
  (exit code 1) at `DAL_A`. Auto-discovered coding standards also need more confidence at stricter
  levels (0.95 at `DAL_A`, 0.50 at `DAL_E`).
- **Module boundaries are enforced, not described.** Each module has a `context.yaml` that says what
  it may depend on.

## What it does not do yet

- **No evidence yet for the core claim.** There is no benchmark that shows a small local model
  performs better with SpecWeaver than without it. That comparison is planned.
- **No local-model adapter.** Supported providers today: Gemini, OpenAI, Anthropic, Mistral, Qwen
  (hosted). Local models are the goal, not a tested path.
- **Mutation testing for your project is not built.** Mutation testing exists for SpecWeaver's own
  test suite (see below); the product gate for user projects is on the roadmap.

## Try it

Needs Python 3.11+, [uv](https://docs.astral.sh/uv/) and git. This example needs no API key.

```bash
git clone https://github.com/sbula/specweaver.git
cd specweaver
uv sync
source .venv/bin/activate

# A new project to point SpecWeaver at
mkdir ../demo && cd ../demo && git init
sw init demo --path .          # scaffolds context.yaml, specs/, CONSTITUTION.md

# Check a spec with the 12-rule battery (deterministic, no LLM)
cp .specweaver/templates/component_spec.md specs/greeter_spec.md
sw check specs/greeter_spec.md
```

`sw init` registers the project in a local SQLite database under `~/.specweaver/`.

The LLM commands — `sw draft`, `sw review`, `sw implement` — need a provider key, for example
`GEMINI_API_KEY`. Other providers: `uv sync --extra all-llm`. See the
[installation guide](docs/user_guides/1_installation_and_setup.md).

## Testing

**9,100 tests** (pytest, parametrized cases counted): 7,888 unit, 940 integration, 256 e2e and
16 manual. 31 of them call real LLM APIs and are skipped by default, so a plain `pytest` run
collects 9,069.

| Tier | Scope | Mocks |
|---|---|---|
| unit | one function or class | everything outside it |
| integration | two or more real parts | external services only |
| e2e | a whole user path | nothing |

Static checks: **ruff** (lint), **mypy** in strict mode, **tach** (module-boundary rules), plus
complexity, coupling, file-size and duplication checks. `scripts/quality.py` bundles them into gates
that run before every commit.

**Mutation testing.** `scripts/mutation.py` runs every night over 13 corpora with 220 hand-written
mutants. Each mutant breaks one line that a requirement depends on — for example, it changes the
API server's bind address from `127.0.0.1` to `0.0.0.0` — and at least one test must fail. Each
mutant ends as `PROTECTED`, `UNPROTECTED` or `UNMEASURED` (a hang is never counted as a pass).
`mutation.py --gate` is read each morning; feature work waits while a finding is open.

```bash
uv sync
export PATH="$PWD/.venv/bin:$PATH"
python -m pytest -n auto -q          # the suite
python scripts/quality.py cb         # the commit gate
```

## How it's built

Spec-first. Each capability has a design with a numbered requirement table and an implementation
plan before code is written. Scripts then check that every requirement is planned and cited by a
test, and that a story's prerequisites are actually green in the code.

Most of the code was written with Claude Code, working under the same gates: test first, the commit
gate before every commit, the nightly mutation run, and decisions about cost, security and scope
left to the human.

## Documentation

- [Installation & setup](docs/user_guides/1_installation_and_setup.md)
- [Writing good specs](docs/user_guides/2_drafting_effective_specs.md)
- [Architecture overview](docs/architecture/README.md)
- [Development framework](docs/dev_guides/development_framework.md) — the gates and how they run
- [Roadmap](docs/roadmap/master_story_roadmap.md) — what is built and what is planned

## License

Apache License 2.0 — see [LICENSE](LICENSE).
