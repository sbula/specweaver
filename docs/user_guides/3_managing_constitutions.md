# User Handbook 3: Managing Constitutions & Coding Standards

Use when: setting the project rules (code standards, naming, test frameworks) that every agent
prompt receives.

Those rules live in `CONSTITUTION.md`, which SpecWeaver injects into agent prompts.

## 1. Viewing the Project Rules

```bash
sw constitution show
```

## 2. Bootstrapping a New Constitution

Generate the rules from your existing code instead of writing them by hand. The scanners are
deterministic parsers for Python, JS and TS.

**Scan the existing codebase:**

```bash
sw standards scan --scope "backend"
# Agent analyzes imports, typing standards, exception handlers internally without uploading to an LLM.
```

**Generate the Markdown ruleset:**

```bash
sw constitution bootstrap
```

This writes the discovered standards into the `CONSTITUTION.md` template.

### Adaptive Standards Configuration

An empty project gives the scanner nothing to find (0 standards). To start from best-practice
defaults instead, add to your root `specweaver.toml`:

```toml
[standards]
mode = "best_practice" # defaults to "mimicry" (strict topology analysis only)
```

In `best_practice` mode, `sw standards scan` on an empty directory initializes best-practice
baselines (such as Python `snake_case` or TypeScript `camelCase`) for generated code.

## 3. Enforcing Constitution Bounds

A large constitution costs tokens on every LLM step. Set the limits:

```bash
sw config set-auto-bootstrap auto
sw config set-constitution-max-size 15000 
```

| Command | Effect |
|---|---|
| `sw config set-auto-bootstrap <mode>` | After `sw standards scan`: `off` prints a hint, `prompt` asks (default), `auto` bootstraps silently |
| `sw config set-constitution-max-size <bytes>` | Size limit for `CONSTITUTION.md` (default 5120 bytes) |

Above the limit (here `15,000` bytes), `sw constitution check` fails. Split generic project rules
from explicit framework constraints (DAL) to get back under it.
