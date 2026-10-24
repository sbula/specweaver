# User Handbook 1: Installation & Setup

Use when: installing SpecWeaver and registering your first project.

## 1. Prerequisites

- [uv](https://docs.astral.sh/uv/) installed globally.
- Python 3.11+.
- An LLM API key (e.g., Gemini AI Studio). Supported providers: Gemini, OpenAI, Anthropic, Mistral,
  Qwen.

## 2. Installation

SpecWeaver is not published on PyPI. Install from source.

```bash
git clone https://github.com/sbula/specweaver.git
cd specweaver
uv sync
# Optional: install specific providers
# uv sync --extra openai --extra anthropic --extra mistral --extra qwen
```

## 3. Providing Credentials

Keys live in one file, `~/.specweaver/keys.env`, outside every repository. Each server in
`settings.toml` names its key's variable in `api_key_env`; the key itself is only in `keys.env`.
SpecWeaver reads keys from nowhere else — not from the shell, not from a project.

```bash
# ~/.specweaver/keys.env — only you may read it: chmod 600 ~/.specweaver/keys.env
GEMINI_API_KEY=your-gemini-key
ANTHROPIC_API_KEY=your-anthropic-key
TAVILY_API_KEY=your-tavily-key      # optional: web search for the agents
```

SpecWeaver refuses `keys.env` if other users can read it. Everything else about models lives in
`settings.toml`.

## 3a. Choosing models: `~/.specweaver/settings.toml`

There is no built-in model and no built-in limit. Every LLM command reads this file and refuses,
naming the missing key, until a server, a role and the three `[brake]` values are set:

```toml
[servers.anthropic]
kind = "anthropic"            # gemini, openai, anthropic, mistral, qwen, openai-compatible
api_key_env = "ANTHROPIC_API_KEY"   # the variable that holds this server's key; required for cloud servers
private = false               # true for a server you run yourself
max_parallel = 3              # calls at once on this server

[servers.gb10]                # a local vLLM server
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]                       # draft, review, plan, implement, scenario, validate, check
default = "claude-sonnet-5@anthropic"   # the one fallback for every role left unset
implement = "qwen3-coder-next@gb10"
scenario = "claude-sonnet-5@anthropic"  # the scenario agent; keep it apart from `implement`

[brake]                       # required; no defaults
hosted_spend_per_run = 20     # the run's money limit, in your [currency]
tokens_per_run = 20000000     # the run's token limit
agent_turns = 30              # rounds one tool loop may take

[models."qwen3-coder-next"]   # optional per-model limits, beside the price
tokens_per_run = 2000000      # this model's own limit; the lower one always wins

[currency]                    # optional; without it every amount is USD
code = "CHF"
per_usd = 0.80
rate_date = 2026-09-26
```

- `sw config set-role <role> <model@server>` writes a role; `--project` writes it into the active
  project's `specweaver.toml` instead, where `[llm] private_only = true` refuses any cloud server.
- `sw config show` prints every value with the file and line it came from.
- Before each call, and before each tool round, the brake adds that call's worst case (the prompt
  with a 25% margin plus the full output cap); each limit warns once at 80%. Cloud servers count
  money, private servers (`private = true`) count tokens.
- If a limit could be crossed and you are at a terminal, the run asks. `y` raises that limit by
  as many of its own steps as the call needs (20 → 40); anything else, Enter included, parks the
  run. Without a terminal it parks straight away. Raise the limit in `settings.toml` if you like,
  then continue with `sw run --resume <id>`: the run keeps what it already spent, and a limit is
  the higher of the file's value and the one you raised. Over the REST API a request at a limit
  gets HTTP 402 with `error_code` `SPEND_LIMIT`.
- **See it work:** set `hosted_spend_per_run = 0.001` and run `sw review <spec>`. The run names
  `brake.hosted_spend_per_run`, sends nothing, and `sw costs` shows no new spend.
- A model (`[models."<id>"]`) may carry `spend_per_run` or `tokens_per_run` too; the lowest
  limit that applies wins. Only the machine file may set limits. A tool loop that reaches
  `agent_turns` stops with an error naming it.
- **Step limits** (optional): with `[step_limits] percentile = 90` and `min_steps = 10`, a step may
  spend the 90% value of the last 10 passed steps of the same kind of task, model and DAL; once it
  has, it asks before its next call. While there are fewer than 10, there is no step limit. Without
  the section, step limits are off; `sw config show` says so. A target with no DAL in any
  `context.yaml` uses its project's default DAL, `DAL_C`.
- A cloud model needs a known price, or the command stops at the start and names the key.
  SpecWeaver ships prices for about ten common models; for any other, set them under
  `[models."<id>"]`. Without `thinking_in_output_cap = true`
  (its output limit also bounds its thinking) the command runs, with one warning.
- `--model <model@server>` on `sw implement`, `sw run` and `sw resume` gives every step of that
  one run the same model; the files stay unchanged. The server must be in `settings.toml`, and
  `private_only` still applies. The `scenario` role is the one exception: it keeps its own model,
  so a scenario run's two sides stay apart. Such a run refuses one model for both sides when your
  settings name more than one, and warns when they name only one.
- `sw costs` shows each role's model, its price per 1M tokens and this month's spend;
  `sw costs set <model> <input> <output>` corrects a price, in your currency.
  `sw costs set <kind>/<model> ...` (e.g. `anthropic/claude-sonnet-5`) prices it on one kind of
  server only; a bare model name prices it on every kind.
- Prices follow the providers by themselves: the first command of a day that calls a model fetches
  them from models.dev (waiting at most 5 seconds) for the models your roles use, and says which
  price changed. `sw costs refresh` does it now. Offline, the last prices stay, with a warning. A
  price in your settings file always wins. A hosted `openai-compatible` server (Together,
  Fireworks) is refreshed only if its entry names its models.dev provider:
  `models_dev = "togetherai"`. Cached input has its own prices too: `usd_per_million_cached_read`
  and `usd_per_million_cache_write`, and `sw usage` shows the cached tokens. A vLLM server reports
  them only when started with `--enable-prompt-tokens-details`; without it SpecWeaver says so once.
- A `qwen` server needs its `base_url` (DashScope's addresses carry your workspace).
- Every cloud server names its key variable in `api_key_env`; a key goes only to the server that
  names it. A server that needs no key is `kind = "openai-compatible"`.
- **Web search** (optional): `[search]` with `api_key_env = "TAVILY_API_KEY"` gives the review and
  code-writing agents `web_search` (Tavily; the free plan has 1,000 searches a month) and
  `read_url`. Without the section they get neither. If `keys.env` lacks the variable, every LLM
  command stops at the start and names `search.api_key_env`. `read_url` reads only `http` and
  `https` pages on public addresses: never `localhost`, a private network or `169.254.169.254`.
- **The API and dashboard** (`sw serve`, needs `specweaver[serve]`): every request needs the token
  `sw serve` makes at each start. Open the dashboard address it prints, which carries the token once;
  a program reads the token from `~/.specweaver/serve.token` (readable by you only) and sends it as
  `Authorization: Bearer <token>`. Runs started through the API need `[serve] max_runs = <n>`, how
  many may run at once; without it a run is refused, naming the key.
  A run's `spec` and every `file` field must land inside the project (links are followed first);
  one outside answers 400 `PATH_TRAVERSAL` and starts nothing. A pipeline is named by a bare name:
  the project's own `.specweaver/pipelines/<name>.yaml`, else a built-in one. A project path is
  stored as the full, real folder. A run on a project whose `[sandbox]`, `[standards]` or
  `.specweaver/dal_definitions.yaml` is broken answers 500 `SANDBOX_SETTINGS`, `STANDARDS_SETTINGS`
  or `DAL_DEFINITIONS`, naming the file, key and line, and starts nothing. An API run is set up as
  `sw run` sets it up: the rule file, the standards, the project's sections, the topology slice
  (`selector`, default `direct`) and isolation by the code's DAL. `new_feature` takes a module name
  as its `spec` and drafts `specs/<name>_spec.md`; with no interactive channel it parks for a gate
  answer. `POST /implement` runs what `sw implement` runs (the bundled `implement_spec`
  pipeline): code, tests, lint fix, the tests with up to two loops back to generation, validation.
  It waits for all of it, so a request takes minutes. It answers the task's code and test files in
  the project's language and `status`: `completed`, or `failed` when the tests still fail after the
  loops (still 200), with the test counts, the lint errors left and the validation result. A spec
  whose `Package` line is not a package answers 400 `SPEC_INVALID`. `POST /implement` on a high-DAL
  project that is not a git repository answers 409
  `WORKTREE_UNAVAILABLE`; a background run there ends `failed`, naming the worktree.
  To see the refusal:
  `curl -X POST http://127.0.0.1:8000/api/v1/pipelines/validate_only/run -H "Authorization: Bearer $(cat ~/.specweaver/serve.token)" -H "Content-Type: application/json" -d '{"project":"<name>","spec":"../outside.md"}'`

## 4. Initializing your First Project

SpecWeaver keeps projects, configuration and artifact lineage in an embedded SQLite database.
Register each project before working on it.

```bash
# Register a project locally 
sw init my-app --path ./my-project

# Or scaffold alongside an external Model Context Protocol integration
sw init my-app --path ./my-project --mcp postgres
```

`sw init` creates, inside the target path:

| Created | Purpose |
|---|---|
| `.specweaver/` | Project directory; `sw init` also sets it as the active project |
| `CONSTITUTION.md`, `.specweaverignore` | Starter templates |
| `.specweaver/scripts/` (with a placeholder `README.md`) | Scripts referenced by `action: bash` pipeline steps |
| `src/context.yaml` (archetype `pure-logic`) | Boundary for your project's core code |
| `tests/context.yaml` (archetype `adapter`) | Boundary for your tests |

The two `context.yaml` files keep the project's core isolated from unauthorized engine access.

Run `sw scan` once after `sw init`, and again when a `context.yaml` changes: it writes the
`tach.toml` that the import-direction check (C05) needs. `sw check src/x.py --level code` then
runs the code rules C01–C08, including the file's own test from `tests/test_x.py`, which may
import `x` by name.

Name what kind of project it is, and its specs get that kind's limits: `sw config profiles` lists
`web-app`, `data-pipeline`, `library`, `microservice` and `ml-model`; `sw config show-profile
library` shows the limits; `sw config set-profile library` applies them to `sw check` and to runs;
`sw config reset-profile` goes back to the defaults. A folder whose archetype brings its own
pipeline keeps that one.

Switch between registered projects:

```bash
sw projects    # View all tracked projects (active has an asterisk)
sw use web-api # Switch active project bounds
```

## 5. Container Deployment (Zero-Install)

Run SpecWeaver without a local Python install, with Podman or Docker:

```bash
podman run --env-file .env \
  -v ./my-project:/projects \
  -p 8000:8000 \
  ghcr.io/sbula/specweaver
```

Trap: SQLite needs a local disk. Network-attached volumes (like CIFS) do not work with WAL mode
unless you configure exceptions.

## 6. Scan Exclusions (`.specweaverignore`)

SpecWeaver parses your source files (all supported languages) to map the project. Two layers keep it
out of files it should not scan:

1. **Built-in exclusions per language:** known compiler and dependency artifacts (e.g. `*.pyc`,
   `*.jar`, `node_modules/`, `target/`).
2. **Your override:** a `.specweaverignore` in the project root, in `.gitignore` syntax.

```bash
# Example .specweaverignore implementation:
build/
docs/legacy_drafts/
!important_cache.pyc
```

## 6a. Which docs agents may change (`[docs]` in `specweaver.toml`)

By default no agent changes `README.md` or anything under `docs/`. Your project's
`specweaver.toml` can open parts of them:

```toml
[[docs.rule]]
paths = ["docs/user_guides/**"]
access = "open"                 # human | open | step

[[docs.rule]]
paths = ["docs/api/**"]
access = "step"
steps = ["update_api_docs"]     # pipeline step names
```

- `human`: no agent changes these paths. `open`: any agent step may. `step`: only the named steps.
- The last rule that matches a path decides, as in `.gitignore`. `*` stays in one folder, `**`
  spans folders. Your rules come after the built-in ones, so a path you do not name stays closed.
- `context.yaml`, `.env`, `.git` and `.specweaver` are never writable, whatever a rule says.
- A doc change a step may not make is not lost: the merge keeps it as a proposal (its diff) in
  `doc_updates.md` at the project root, and the run goes on.
- A broken `[docs]` section stops `sw run`, `sw resume`, `sw implement` and the API, naming the line.

**Generated blocks.** A `bash` step can keep one marked part of a file current, such as the test
counts in a README:

```toml
[[docs.block]]
file = "README.md"
name = "counts"
step = "update_counts"           # a bash step; its output fills the block
```

```markdown
<!-- sw:block counts -->
(the script's output goes here)
<!-- sw:end counts -->
```

- SpecWeaver writes the block from the script's output. The rest of the file stays human.
- One step fills one block. Only a `bash` step may: a block whose step is an LLM step stops the run.
- A missing marker, an output that holds a marker, or an output over 1 MiB fails the step, and
  nothing is written.

## 6b. Agentic steps (`[autonomy]` in `specweaver.toml`)

A code or tests generation step may run **agentic**: the coder reads the project and writes its
file through tools, correcting itself, instead of answering once.

```toml
[autonomy]
mode = "oneshot"            # oneshot | agentic — the default for this project's generate steps
agentic_max_dal = "DAL_D"   # the riskiest DAL agentic work may run at; no default
```

A pipeline step can ask for it itself: `mode: agentic` on a `generate` step with target `code` or
`tests`. Any other step with `mode: agentic` does not load.

- **No ceiling, no agentic.** Until `agentic_max_dal` is set, a run with an agentic step stops
  before its first step and names the setting.
- **Riskier code stays one-shot.** A target whose DAL is above the ceiling runs one-shot, and the
  step's result says why (`agentic_refused`). A target with no DAL marker is `DAL_C`.
- **Two walls.** The coder writes only its own target file (the code step its module, the tests
  step its test file), within the `[docs]` rules above. It always works in a git worktree, and the
  merge keeps only what may land. A project that is not a git repo cannot run agentic steps.
- **No new dependencies.** A change to `pyproject.toml`, a lock file or another manifest becomes a
  proposal in `doc_updates.md`. SpecWeaver installs from the manifests; the coder never does.
- **Bounded.** `[brake] agent_turns` in `settings.toml` limits the coder's tool rounds; reaching it
  fails the step. The spend limits apply as to every call.
- **`sw implement` follows the dial.** With `mode = "agentic"`, its code and tests steps run the
  coder. Each lands its file through the merge, as commits on your current branch, so the working
  tree must be clean: otherwise the run stops and says "commit or stash first".

## 6c. Languages (`[implement]` in `specweaver.toml`)

SpecWeaver works out your project's language from its manifests: `package.json` → TypeScript,
`Cargo.toml` → Rust, a Gradle or Maven build → Kotlin when the project has Kotlin sources or the
Kotlin plugin, else Java; otherwise Python. A mixed repository names its language:

```toml
[implement]
language = "java"   # python | java | kotlin | typescript | rust
```

A spec `greet_service_spec.md` is the module `greet_service`; its files are:

| Language | Code | Tests |
|---|---|---|
| Python | `src/greet_service.py` | `tests/test_greet_service.py` |
| Java | `src/main/java/<pkg>/GreetService.java` | `src/test/java/<pkg>/GreetServiceTest.java` |
| Kotlin | `src/main/kotlin/<pkg>/GreetService.kt` | `src/test/kotlin/<pkg>/GreetServiceTest.kt` |
| TypeScript | `src/greet_service.ts` | `tests/greet_service.test.ts` |
| Rust | `src/greet_service.rs` (+ `pub mod greet_service;` in `src/lib.rs`) | `tests/greet_service.rs` |

The Java/Kotlin package is the spec's `> **Package**: com.example.greet` header line, else the package
your existing sources share, else the build's `groupId`/`group`.

A Rust crate with only `src/main.rs` gets a `src/lib.rs` beside it: tests in `tests/` can only reach a
library crate. `main.rs` is not changed.

The model is asked for code in that language and told where the file goes: the Java/Kotlin package
and class, the Rust crate and module, the TypeScript import path and test tool. Java tests use JUnit 5,
Kotlin tests `kotlin.test`. To change what the model is told, copy a file from
`src/specweaver/workflows/languages/` to `.specweaver/languages/<language>.md` and edit it; keep its
`name:` line and its five `#` sections (`Code`, `Tests`, `Code role`, `Tests role`, `Coder role`).

Lint repair asks the model to fix "this Java file" (in the project's language). Code validation's
rules (C01–C13) are Python's: for another language `sw implement` prints `no code rules for java`
and goes on, unless the folder's archetype brings rules for that language (Spring Boot does).

**Frameworks.** The model also gets the framework's idioms and test style for Spring, Spring Boot,
Quarkus, NestJS, Actix-web and FastAPI. The framework is the folder's `context.yaml` `archetype`
when a framework file of that name exists for the project's language; else it is read from the
build file (`io.quarkus`, `spring-boot`, `org.springframework` in `pom.xml` / Gradle; `@nestjs/core`
in `package.json`; `actix-web` in `Cargo.toml`; `fastapi` in `pyproject.toml` or
`requirements*.txt`). `sw implement` prints `Framework: spring-boot (build file)`. To change one,
or to add one (say `micronaut`, named by an archetype), write `.specweaver/frameworks/<name>.md`
with `name:` and `languages:` lines and two `#` sections, `Code` and `Tests`; the shipped files are
in `src/specweaver/workflows/frameworks/`.

## 7. Model Context Protocol (MCP) & Vault Configuration

SpecWeaver can pre-fetch context from external tools (e.g. Postgres databases or Atlassian APIs)
over the Model Context Protocol (Feature 3.32c).

### Setting Up Vault Credentials

Pipelines that declare `mcp_servers` mappings inside `.specweaver/pipelines` need runtime
credentials. Keep them in `.specweaver/vault.env`, never in the codebase.

1. `sw init <name> --mcp postgres` creates `.specweaver/vault.env` and appends it to your root
   `.gitignore`.
2. Or create `.specweaver/vault.env` yourself and add it to `.gitignore` immediately.

Rule: if `.specweaver/vault.env` is tracked by Git, the pipeline aborts before running, to prevent
credential leakage.

Nothing secret reaches a model: every value of 8 or more characters in `vault.env` and in
`~/.specweaver/keys.env` is replaced with `***RESTRICTED***` in prompts and tool results.

## 8. Telemetry & Logs

| Output | Where | Default level |
|---|---|---|
| Alerts and formatted stack traces | Console (stderr), rendered with Rich | `WARNING` |
| JSON lines, rotated | `~/.specweaver/logs/<project_name>/specweaver.log` | `DEBUG` |

Both levels are per project:

```bash
sw config set-log-level INFO              # the log file
sw config set-log-level --console INFO    # the console
sw config get-log-level                   # shows both, and the log file's path
```

A warning on the console means a result changed because something could not be read — a report
lost its findings, a `context.yaml` was skipped. Use the log file for post-mortem auditing and agent
debugging.
