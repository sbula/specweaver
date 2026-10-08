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

SpecWeaver reads provider keys from the environment.

```powershell
# Windows PowerShell
$env:GEMINI_API_KEY = "your-gemini-key"
$env:OPENAI_API_KEY = "your-openai-key"
$env:ANTHROPIC_API_KEY = "your-anthropic-key"
$env:MISTRAL_API_KEY = "your-mistral-key"
$env:DASHSCOPE_API_KEY = "your-qwen-key"
```

Keys stay in the environment; everything else about models lives in one file.

## 3a. Choosing models: `~/.specweaver/settings.toml`

There is no built-in model and no built-in limit. Every LLM command reads this file and refuses,
naming the missing key, until a server, a role and the three `[brake]` values are set:

```toml
[servers.anthropic]
kind = "anthropic"            # gemini, openai, anthropic, mistral, qwen, openai-compatible
private = false               # true for a server you run yourself
max_parallel = 3              # calls at once on this server

[servers.gb10]                # a local vLLM server
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]                       # draft, review, plan, implement, validate, check
default = "claude-sonnet-5@anthropic"   # the one fallback for every role left unset
implement = "qwen3-coder-next@gb10"

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
- A model (`[models."<id>"]`) and a role may carry `spend_per_run` or `tokens_per_run` too; the
  lowest limit that applies wins. Only the machine file may set limits. A tool loop that reaches
  `agent_turns` stops with an error naming it.
- A cloud model needs a known price and `thinking_in_output_cap = true` (its output limit also
  bounds its thinking). The model list has both for OpenAI, Anthropic and Gemini; for any other
  cloud model, set them under `[models."<id>"]`, or the command stops at the start and names the key.
- `--model <model@server>` on `sw implement`, `sw run` and `sw resume` gives every step of that
  one run the same model; the files stay unchanged. The server must be in `settings.toml`, and
  `private_only` still applies.
- `sw costs` shows each role's model, its price per 1M tokens and this month's spend;
  `sw costs set <model> <input> <output>` corrects a price, in your currency.
- A `qwen` server needs its `base_url` (DashScope's addresses carry your workspace).
- A provider's own key (`OPENAI_API_KEY` and the like) is sent only to that provider's own
  address. Point `kind = "openai"` at another host and you must name that host's key in
  `api_key_env`; a server that needs no key is `kind = "openai-compatible"`.

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

## 8. Telemetry & Logs

| Output | Where |
|---|---|
| `WARNING` level alerts and formatted stack traces | Console, rendered with Rich |
| Verbose `DEBUG` logs, JSON lines, rotated | `~/.specweaver/logs/<project_name>/specweaver.log` |

Use the log file for post-mortem auditing and agent debugging.
