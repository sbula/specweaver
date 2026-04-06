# SpecWeaver Quick-Start Guide

Get from zero to a completed pipeline run in under 5 minutes.

SpecWeaver supports two spec levels: **feature specs** (cross-cutting features) and **component specs** (isolated implementable units). This guide shows both.

## Container Deployment (Alternative)

Skip the Python install — run SpecWeaver with Podman or Docker:

```bash
# Copy and configure the env file
cp .env.example .env
# Edit .env with your GEMINI_API_KEY

# Run with your project mounted
podman run --env-file .env -v ./my-project:/projects -p 8000:8000 ghcr.io/sbula/specweaver

# Dashboard at http://localhost:8000/dashboard
```

See the [README](../README.md#container-deployment) for Docker Compose and advanced options.

---

## Prerequisites

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/) package manager
- A [Gemini API key](https://aistudio.google.com/apikey) (free tier works)

## 1. Install SpecWeaver

```bash
git clone https://github.com/sbula/specweaver.git
cd specweaver
uv sync --all-extras
```

## 2. Set Your API Key

SpecWeaver defaults to Gemini, but also supports OpenAI, Anthropic, Mistral, and Qwen via auto-discovery.

```bash
# Set the key for your preferred provider:
export GEMINI_API_KEY="your-gemini-key"
# export OPENAI_API_KEY="your-openai-key"
# export ANTHROPIC_API_KEY="your-anthropic-key"
# export MISTRAL_API_KEY="your-mistral-key"
# export QWEN_API_KEY="your-qwen-key"
```

*Note: For Windows PowerShell, use `$env:GEMINI_API_KEY="your-key-here"`.*

If you use a non-Gemini provider, configure it in step 3.

## 3. Initialize a Project

```bash
sw init my-app --path ./my-project
```

This will:
- Register `my-app` in SpecWeaver's database
- Create `.specweaver/` marker directory
- Scaffold `context.yaml`, `specs/`, and templates
- Set `my-app` as the active project

You should see:

```
✔ Project 'my-app' initialized at ./my-project
```

### 3b. Configure a Different Provider (Optional)

If you are not using Gemini, tell the project to use your preferred provider constraint:

```bash
sw config set-provider openai
sw config set-model gpt-5.4-mini
```

## 4. Draft a Spec

```bash
sw draft greet_service --project ./my-project
```

The LLM will interactively help you write a spec with the 6-section structure:
**Purpose** -> **Contract** -> **Protocol** -> **Policy** -> **Boundaries** -> **Risk Assessment (DAL)**

The result is saved to `specs/greet_service_spec.md`.

## 5. Validate the Spec

```bash
sw check specs/greet_service_spec.md --level component --project ./my-project
```

This runs 11 spec rules (S01-S11) against your spec:

```
Spec validation — 11 rules
  ✔ S01 One-Sentence Test        PASS
  ✔ S02 Single Test Setup        PASS
  ✔ S03 Stranger Test            PASS
  ...
Result: 11 passed, 0 warnings, 0 failed
```

Use `--strict` to treat warnings as failures, or `--set S08.fail_threshold=5` for one-off threshold overrides.

## 5b. Validate at Feature Level (Optional)

If you're working on a feature spec (cross-cutting feature with `## Intent` instead of `## 1. Purpose`):

```bash
sw check specs/onboarding.md --level feature --project ./my-project
```

Feature-level validation differs from component-level:

| Rule | Component Level | Feature Level |
|------|----------------|---------------|
| S01 | Looks for `## 1. Purpose` | Looks for `## Intent` |
| S03 | Counts external references | Detects abstraction leaks (file paths, class.method refs) |
| S04 | Validates dependency direction | Skipped (N/A for features) |
| S05/S08 | Standard thresholds | Lenient thresholds |

The override cascade: code defaults → kind presets → project DB overrides → `--set` flags.

## 5c. Validate Artifact Lineage (Optional)

You can scan the project to ensure no Python files are missing their `# sw-artifact:` traceability tags:

```bash
sw check --lineage --project ./my-project
```

## 5d. Tag and Trace Lineage (Optional)

Inject missing traceability tags or log manual edits directly:

```bash
sw lineage tag src/my_app/core.py --author human
```

View the upstream spec origins and downstream modifications of any artifact:

```bash
sw lineage tree src/my_app/core.py
```

## 6. Review the Spec with AI

```bash
sw review specs/greet_service_spec.md --project ./my-project
```

The LLM reviews your spec and returns **ACCEPTED** or **DENIED** with structured findings.

## 7. Generate Code + Tests

```bash
sw implement specs/greet_service_spec.md --project ./my-project
```

This generates:
- `src/greet_service.py` — implementation
- `tests/test_greet_service.py` — test file

*(If a spec contains UI requirements, SpecWeaver will automatically attempt to generate a visual mockup via the Google Stitch MCP if `stitch_mode` is set to `auto` or `prompt`)*

## 8. Validate Generated Code

```bash
sw check src/greet_service.py --level code --project ./my-project
```

Runs 9 code rules (C01-C09): syntax, tests exist, tests pass, coverage, import direction, no bare except, no orphan TODO, type hints, traceability.

## 9. Review Code Against Spec

```bash
sw review src/greet_service.py --spec specs/greet_service_spec.md --project ./my-project
```

The LLM verifies the code matches the spec and returns ACCEPTED/DENIED.

---

## Running Pipelines

Once you're comfortable with individual commands, use pipelines to chain them:

```bash
# List available pipelines
sw pipelines

# Run a full pipeline
sw run new_feature greet_service --project ./my-project

# Run the feature decomposition pipeline
sw run feature_decomposition specs/onboarding.md --project ./my-project

# Run with verbose output
sw run validate_only specs/calculator.md --verbose

# Machine-readable output
sw run validate_only specs/calculator.md --json
```

The `feature_decomposition` pipeline runs: **draft feature** → **validate at feature level** → **decompose into components**. HITL gates pause for human approval between steps.

If a pipeline pauses (e.g. waiting for human review), resume it:

```bash
sw resume           # resume the latest run
sw resume <run_id>  # resume a specific run
```

## Logging

Logs are written per-project to `~/.specweaver/logs/<project>/specweaver.log`:

```bash
# Check current log level
sw config get-log-level

# Set log level (debug, info, warning, error)
sw config set-log-level debug
```

File logs capture **DEBUG** level (JSON formatted); console output shows only **WARNING+** (Rich formatted).

## Managing Multiple Projects

```bash
sw projects            # List all registered projects
sw use other-project   # Switch active project
sw remove old-project  # Unregister (files stay on disk)
sw update my-app path /new/path  # Update project path
sw scan                # Auto-generate missing context.yamls & sync tach.toml
```

## Constitution Management

Every project gets a `CONSTITUTION.md` file (created by `sw init`). This is a project-wide governing document — coding principles, testing standards, UX guidelines — that is automatically injected into every LLM call (review, implement, pipeline).

```bash
# View the current constitution
sw constitution show --project ./my-project

# Validate constitution against size limits
sw constitution check --project ./my-project

# Reset/create a fresh constitution template
sw constitution init --project ./my-project
sw constitution init --force --project ./my-project  # overwrite existing

# Configure max allowed size (per project)
sw config set-constitution-max-size 16384
sw config get-constitution-max-size
```

Edit `CONSTITUTION.md` directly to customize your project's rules. The content is sent to the LLM as context during review and implementation, ensuring AI-generated output follows your project's standards.

### Auto-Bootstrap from Standards

After running `sw standards scan`, you can auto-generate a `CONSTITUTION.md` from the discovered coding conventions:

```bash
# Generate CONSTITUTION.md from discovered standards
sw constitution bootstrap --project ./my-project

# Force overwrite even if user has edited the constitution
sw constitution bootstrap --force --project ./my-project

# Configure auto-bootstrap behavior (off, prompt, auto)
sw config set-auto-bootstrap prompt  # ask after each scan (default)
sw config set-auto-bootstrap auto    # auto-generate after scan
sw config set-auto-bootstrap off     # never auto-generate
```

The generated constitution includes a tech stack section, language-specific conventions, and coding standards extracted from your codebase.

## Standards Auto-Discovery

SpecWeaver can analyze your codebase (Python, JavaScript, TypeScript) to automatically discover coding standards (naming conventions, error handling, docstrings/JSDoc/TSDoc, import patterns, test patterns, async patterns). Discovered standards are injected into LLM prompts alongside the constitution.

```bash
# Scan the project for coding standards (with interactive HITL review)
sw standards scan --project ./my-project

# Scan without review (CI mode — auto-accepts all findings)
sw standards scan --no-review --project ./my-project

# Force LLM comparison against industry best practices
sw standards scan --compare --project ./my-project

# View discovered standards
sw standards show --project ./my-project

# View scope summary (for monorepos)
sw standards scopes --project ./my-project

# Clear and re-scan
sw standards clear --project ./my-project
sw standards scan --project ./my-project
```

**Multi-scope support**: For monorepos, SpecWeaver detects sub-projects (2-level directory scan) and discovers standards per scope. Standards from a specific scope are prioritized over root-level standards when reviewing files in that scope.

**HITL review**: By default, each discovered standard category is presented for human review. Options: **(a)ccept**, **(r)eject**, **(e)dit** (modify JSON), **(A)ccept All** (remaining in scope), **(S)kip Scope**. Use `--no-review` for CI or automated pipelines.

## Validation Pipelines

Customize rule thresholds exclusively through YAML pipelines via your active domain profile:

Create `.specweaver/pipelines/validation_spec_custom.yaml`:
```yaml
name: validation_spec_custom
type: validation_pipeline
extends: validation_spec_default
target: spec
remove:
  - 's05_day_test'        # Disable Day Test rule
override:
  's08_ambiguity':        # Fail on >3 ambiguous words
    params:
      fail_threshold: 3
```

Then assign it to your project:
```bash
sw config set-profile custom
sw config list                       # Show all resolved rules and thresholds
```
## Next Steps

- Read the full [README](../README.md) for detailed feature documentation
- Explore [architecture docs](architecture/methodology_index.md) for the spec methodology
- Check the [roadmap](proposals/specweaver_roadmap.md) for what's coming next
