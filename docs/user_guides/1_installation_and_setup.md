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
```
This command physically scaffolds `.specweaver/` directories inside the target path and sets up the active connection.

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
