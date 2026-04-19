# User Handbook 3: Managing Constitutions & Coding Standards

Agent hallucinations drop precipitously when forced to adhere to contextually injected project rules (Code standards, variable namings, test frameworks). SpecWeaver manages this entirely through the `CONSTITUTION.md`.

## 1. Viewing the Project Reality
The active project tracks standards internally. You can physically display the running truth:
```bash
sw constitution show
```

## 2. Bootstrapping a New Constitution
If you do not have rules defined, do not write them by hand. SpecWeaver contains deterministic Parsers that scan thousands of lines of your source code (Python, JS, TS) looking for existing logical trends.

**Scan the existing codebase:**
```bash
sw standards scan --scope "backend"
# Agent analyzes imports, typing standards, exception handlers internally without uploading to an LLM.
```

**Generate the Markdown ruleset:**
```bash
sw constitution bootstrap
```
This forces the CLI to compile discovered standards directly into the `CONSTITUTION.md` template file, guaranteeing the agent writes code identical to your senior engineers.

### Adaptive Standards Configuration
If you are initializing a completely empty project, the scanner will typically find 0 standards to map. However, you can configure SpecWeaver to inject polyglot `best_practice` primitive defaults automatically.
Simply add the following to your root `specweaver.toml`:

```toml
[standards]
mode = "best_practice" # defaults to "mimicry" (strict topology analysis only)
```
With `best_practice` mode invoked, running `sw standards scan` on an empty directory will immediately initialize best-practice baselines (such as Python `snake_case` or TypeScript `camelCase` constraints) for agentic generations unconditionally.

## 3. Enforcing Constitution Bounds
By default, Constitution files can inflate quickly, costing massive token budgets during pipeline executions containing LLMs. You can throttle the strictness of the framework:

```bash
sw config set-auto-bootstrap mode a
sw config set-constitution-max-size 15000 
```
If you surpass `15,000` bytes, `sw constitution check` will mathematically reject the pipeline enforcing you logically break down generic project rules against explicit framework constraints (DAL).
