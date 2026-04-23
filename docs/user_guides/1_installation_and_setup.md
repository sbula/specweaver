# User Handbook 1: Installation & Setup

SpecWeaver requires Python 3.11+ and the fast package manager `uv`. It interacts directly with LLMs (Gemini, OpenAI, Anthropic) via API keys provided in your environment.

## 1. Prerequisites
- [uv](https://docs.astral.sh/uv/) installed globally.
- Python 3.11+.
- An LLM API key (e.g., Gemini AI Studio).

## 2. Installation
To install SpecWeaver from source:
```bash
git clone https://github.com/sbula/specweaver.git
cd specweaver
uv sync --all-extras
```

## 3. Providing Credentials
SpecWeaver seamlessly routes tasks out to external LLMs. Ensure your CLI has access to the appropriate credentials.
```powershell
# Windows PowerShell
$env:GEMINI_API_KEY = "your-api-key-here"
$env:OPENAI_API_KEY = "optional-openai-key"
```

## 4. Initializing your First Project
SpecWeaver relies on an embedded SQLite database to mathematically track your artifact lineages, configurations, and contexts. When you start working on a project, you must register it.

```bash
# Register a project locally 
sw init my-app --path ./my-project

# Or scaffold alongside an external Model Context Protocol integration
sw init my-app --path ./my-project --mcp postgres
```
This command physically scaffolds `.specweaver/` directories inside the target path, sets up the active connection, and automatically seeds starter templates for `CONSTITUTION.md` and `.specweaverignore`. Furthermore, it dynamically scaffolds native topological bounds (`src/context.yaml` targeting `pure-logic` and `tests/context.yaml` targeting `adapter`) to permanently isolate your project's architectural core from unauthorized Engine access.

If you have multiple projects, you can hot-swap the active context mapping:
```bash
sw projects    # View all tracked projects (active has an asterisk)
sw use web-api # Switch active project bounds
```

## 5. Container Deployment (Zero-Install)
If you prefer not to install Python or packages natively, SpecWeaver is fully containerized.

Using Podman or Docker:
```bash
podman run --env-file .env \
  -v ./my-project:/projects \
  -p 8000:8000 \
  ghcr.io/sbula/specweaver
```
*Note: SQLite requires standard disk boundaries. You cannot map network-attached volumes (like CIFS) over strict WAL modes without configuring exceptions.*

## 6. Smart Scan Exclusions (`.specweaverignore`)
SpecWeaver's pipeline engines utilize deep polyglot AST traversal to map your project topology. To prevent SpecWeaver from unnecessarily scanning generated binaries, dependency files, or proprietary logic, it inherently restricts scope via an intelligent fallback sequence:

1. **Native Polyglot Exclusions:** The parser implicitly avoids known compiler artifacts mathematically mapd by Language type (e.g. `*.pyc`, `*.jar`, `node_modules/`, `target/`).
2. **User Override:** You can strictly override these settings mathematically by creating a `.specweaverignore` physically within your project's root directory, matching the classic `.gitignore` syntax logic precisely.

```bash
# Example .specweaverignore implementation:
build/
docs/legacy_drafts/
!important_cache.pyc
```

## 7. Model Context Protocol (MCP) & Vault Configuration
Starting with Feature 3.32c, SpecWeaver supports context pre-fetching against live external tools (e.g. Postgres databases or Atlassian APIs) utilizing the Model Context Protocol.

### Setting Up Vault Credentials
If your pipelines declare `mcp_servers` mappings inside `.specweaver/pipelines`, they will require physical runtime credentials. **It is incredibly dangerous to store database proxies natively inside codebases**. SpecWeaver protects you using the isolated Vault map. 

To inject credentials without causing a pipeline abortion:
1. Use `sw init <name> --mcp postgres`. This automatically spins up `.specweaver/vault.env` and implicitly appends it to your root `.gitignore`.
2. Alternatively, create `.specweaver/vault.env` yourself and ensure you immediately add it to your global `.gitignore` scope. 

**The Pipeline Orchestrator actively scans this protection boundary. If the Vault configuration file is mathematically tracked inside your Git commit scope, SpecWeaver will dictate an immediate interpreter crash to prevent accidental credentials leakage.**
