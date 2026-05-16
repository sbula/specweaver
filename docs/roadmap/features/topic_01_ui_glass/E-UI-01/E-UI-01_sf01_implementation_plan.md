# E-UI-01 — CLI Scaffold (Implementation Plan)

### Step 1: Project Scaffold + CLI Shell (1-2 sessions)

**Create:**
- [x] `pyproject.toml` (uv, PEP 621, core deps)
- [x] `src/specweaver/__init__.py` + `cli.py` (Typer app with stubs)
- [ ] `src/specweaver/config/settings.py` (path resolution)
- [x] `src/specweaver/project/discovery.py` + `scaffold.py` (`sw init`)
- [x] Tests: CLI dispatch, settings, scaffold

**Copy from FM:** Nothing yet.

**Runnable:** `sw --help`, `sw init --project ./test-project`

> [!NOTE]
> CLI uses level-oriented commands: `sw check --level=component spec.md` replaces the earlier `sw validate spec`. MVP supports `--level=component` (spec) and `--level=code` only. Future: `--level=feature`, `--level=class`, `--level=function`, and language-specific code rules.

---
