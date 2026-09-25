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
$env:QWEN_API_KEY = "your-qwen-key"
```

The default provider is `gemini`. Change it per project role with
`sw config set-provider <provider>` (`--role`, default `draft`; optional `--model`).

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
