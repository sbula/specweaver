# SpecWeaver Quick-Start Guide

Get from zero to a completed pipeline run in under 5 minutes.

SpecWeaver supports two spec levels: **feature specs** (cross-cutting features) and **component specs** (isolated implementable units). This guide shows both.

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

```bash
# Linux/macOS
export GEMINI_API_KEY="your-key-here"

# Windows (PowerShell)
$env:GEMINI_API_KEY = "your-key-here"
```

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

## 4. Draft a Spec

```bash
sw draft greet_service --project ./my-project
```

The LLM will interactively help you write a spec with the 5-section structure:
**Purpose** -> **Contract** -> **Protocol** -> **Policy** -> **Boundaries**

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

## 8. Validate Generated Code

```bash
sw check src/greet_service.py --level code --project ./my-project
```

Runs 8 code rules (C01-C08): syntax, tests exist, tests pass, coverage, import direction, no bare except, no orphan TODO, type hints.

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

File logs capture **DEBUG** level (full detail); console output shows only **WARNING+**.

## Managing Multiple Projects

```bash
sw projects            # List all registered projects
sw use other-project   # Switch active project
sw remove old-project  # Unregister (files stay on disk)
sw update my-app path /new/path  # Update project path
```

## Validation Overrides

Customize rule thresholds per project:

```bash
sw config set S08 --fail 3           # Fail on >3 ambiguous words
sw config set C04 --fail 80          # Require 80% coverage
sw config set S05 --enabled false    # Disable Day Test rule
sw config list                       # Show all overrides
sw config reset S08                  # Revert to defaults
```

## Next Steps

- Read the full [README](../README.md) for detailed feature documentation
- Explore [architecture docs](architecture/methodology_index.md) for the spec methodology
- Check the [roadmap](proposals/specweaver_roadmap.md) for what's coming next
