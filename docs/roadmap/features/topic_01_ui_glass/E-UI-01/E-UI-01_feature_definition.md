# E-UI-01 — CLI Scaffold

### F1: CLI Entry Point (`sw`)

| Command | Purpose | Phase |
|---------|---------|-------|
| `sw init --project <path>` | Set up target project | Setup |
| `sw draft <name>` | Start collaborative spec writing | Drafting |
| `sw validate spec <spec.md>` | Run spec validation rules | Spec QA |
| `sw review spec <spec.md>` | Run spec review (LLM) | Spec QA |
| `sw implement <spec.md>` | Generate code + tests | Implementation |
| `sw validate code <file>` | Run code validation rules | Code QA |
| `sw review code <file>` | Run code review (LLM) | Code QA |
