# C-EXEC-02 SF-03 — Scaffold, Boundary Config, and Docs

**Status**: APPROVED. Implemented 2026-07-14. · **FRs owned**: FR-10 · **Depends on**: none ·
Design: [C-EXEC-02_design.md](C-EXEC-02_design.md) §Sub-features → SF-03

## Goal

- Create `.specweaver/scripts/` during project scaffolding (FR-10).
- Make SF-01's `BashActionAtom` a tach-legal import for SF-02: `tach.toml`'s sandbox interface
  expose-list and `core/flow/context.yaml`'s `consumes`.
- Correct two stale docs (`hard_dependency_rules.md`, `ORIGINS.md`) and extend the guide sections
  that are SF-03's.

Parallelizable: needs only the module *names* SF-01 introduced, not its code.

## Where it plugs in

| Fact | Where |
|---|---|
| No templating engine: each artifact is a module-level `_DEFAULT_*` string constant plus a `_scaffold_*(sw_dir, created)` helper — check `.exists()`, `mkdir(parents=True)` if missing (append `"<path>/"` to `created`), then check-and-`write_text()` the file (append its path). `_scaffold_templates()` (lines 257-266) is the template to clone. `created: list[str]` is returned via `ScaffoldResult.created`. `scaffold_project()` (lines 333-388) orchestrates; the new call goes at line 359, right after `_scaffold_templates(sw_dir, created)`, before `_scaffold_constitution(...)`. | `workspace/project/scaffold.py` (389 lines) |
| `sw init` output is generic: `for item in result.created: console.print(f"  Created: {item}")` — no CLI change. | `interfaces/cli.py:77-78` |
| The `[[interfaces]] from = ["specweaver.sandbox"]` block (lines 156-158) lacks `execution.core`. Each sandbox submodule `core.flow` consumes appears **twice** in `expose`: bare module (`"qa_runner.core"`) and leaf class (`"qa_runner.core.atom.QARunnerAtom"`); same for `git.core`/`git.core.atom.GitAtom`, `code_structure.core`/`code_structure.core.atom.CodeStructureAtom`. Add `"execution.core"` and `"execution.core.atom.BashActionAtom"` the same way. | `tach.toml` (204 lines) |
| `consumes:` (lines 18-31) lacks `specweaver/sandbox/execution/core`. Slash-separated style (`specweaver/sandbox/qa_runner/core`). New line after `- specweaver/sandbox/mcp/core` (line 29), keeping `sandbox/*` grouped before `dispatcher`/`security`. | `src/specweaver/core/flow/context.yaml` (59 lines) |
| SF-01's own `src/specweaver/sandbox/execution/core/context.yaml` is exactly `archetype: adapter` — untouched; SF-03 edits the *consumer's* list. | — |
| No test asserts a closed set of scaffolded files. `test_marker_dir_has_no_config` (`test_scaffold.py:283-289`) only asserts `"config.yaml" not in children`. | tests |
| Test templates: `test_creates_templates_dir_with_component_spec` (`test_scaffold.py:38-46`, creation + content), `test_does_not_overwrite_existing_template` (`test_scaffold.py:190-199`, idempotency), `test_init_creates_template` (`test_cli_projects.py:78-82`, `runner.invoke(app, ["init", ...])`). | tests |
| The `flow` row (line 12) lists Consumes `config, llm, review, implementation, planning, validation, sandbox/qa_runner, sandbox/dispatcher, sandbox/security, workspace/memory` — missing `sandbox/git`, `sandbox/code_structure`, `sandbox/mcp` (live in the real `context.yaml`) and `sandbox/execution`. | `docs/architecture/03_system_topology/hard_dependency_rules.md` (41 lines) |
| Archon section (lines 170-182): line 176 attributes "Native CLI Action Nodes", `action:` as a discriminator key, and "FolderGrant" to Archon; none exist in Archon's code. Archon uses `bash:`/`script:` node fields with a `script: analyze-metrics` → `.archon/scripts/analyze-metrics.py` bare-name convention, which `AD-6` does mirror. | `docs/ORIGINS.md` |
| The "Engine-Internal Script Execution (BashActionAtom)" section (lines 80-87, from SF-01's pre-commit) never says where `.specweaver/scripts/` comes from. `action: bash` syntax stays with SF-02 (Guide-1). | `docs/dev_guides/subprocess_execution.md` |
| No mention of `action: bash`/`.specweaver/scripts/` — left to SF-02. | `docs/dev_guides/pipeline_engine_guide.md` |
| §4 "Initializing your First Project" (lines 37-47) lists what `sw init` scaffolds (`.specweaver/`, `CONSTITUTION.md`, `.specweaverignore`, `src/context.yaml`, `tests/context.yaml`) — needs `.specweaver/scripts/`. | `docs/user_guides/1_installation_and_setup.md` |

## Changes

| File | Change | Purpose |
|------|--------|---------|
| `src/specweaver/workspace/project/scaffold.py` | `[MODIFY]` | New `_DEFAULT_SCRIPTS_README` constant + `_scaffold_scripts_dir()` helper + one new call in `scaffold_project()` |
| `tach.toml` | `[MODIFY]` | Add `"execution.core"` + `"execution.core.atom.BashActionAtom"` to the `specweaver.sandbox` interface's `expose` array |
| `src/specweaver/core/flow/context.yaml` | `[MODIFY]` | Add `- specweaver/sandbox/execution/core` to `consumes:` |
| `docs/architecture/03_system_topology/hard_dependency_rules.md` | `[MODIFY]` | Correct the stale `flow` row (Consumes/Forbids columns) |
| `docs/ORIGINS.md` | `[MODIFY]` | Correct line 176's Archon attribution |
| `docs/dev_guides/subprocess_execution.md` | `[MODIFY]` | One sentence in the BashActionAtom section: `.specweaver/scripts/` comes from the scaffold |
| `docs/user_guides/1_installation_and_setup.md` | `[MODIFY]` | One clause added to §4's scaffolding-artifact list |
| `tests/unit/workspace/project/test_scaffold.py` | `[MODIFY]` | New creation + idempotency tests |
| `tests/unit/workspace/project/interfaces/test_cli_projects.py` | `[MODIFY]` | New CLI-level creation test |

No new source files; nothing in `src/specweaver/sandbox/execution/core/`.

1. **`scaffold.py`** (FR-10)
   1. `_DEFAULT_SCRIPTS_README` constant (content below).
   2. `_scaffold_scripts_dir(sw_dir: Path, created: list[str]) -> None`, cloning `_scaffold_templates()`:
      if `sw_dir / "scripts"` is missing → `mkdir(parents=True)`, append `".specweaver/scripts/"`;
      if `sw_dir / "scripts" / "README.md"` is missing → `write_text(_DEFAULT_SCRIPTS_README)`,
      append `".specweaver/scripts/README.md"`.
   3. Call `_scaffold_scripts_dir(sw_dir, created)` right after `_scaffold_templates(sw_dir, created)` (line 359).
      `ScaffoldResult`, `scaffold_project()`'s signature and the CLI loop need no change.
2. **`hard_dependency_rules.md`** — `flow` Consumes becomes
   `config, llm, review, implementation, planning, validation, sandbox/git, sandbox/qa_runner, sandbox/code_structure, sandbox/mcp, sandbox/execution, sandbox/dispatcher, sandbox/security, workspace/memory`;
   Forbids gets `sandbox/execution` in its exception list.
3. **`ORIGINS.md` line 176** — drop the false attribution, keep the true one:

Before:
```
- **Native CLI Action Nodes** → Supporting `action: bash` deterministic steps in pipeline definitions to cleanly trigger pre-test scaffolding without involving the LLM. Enforces strict `FolderGrant` protection by physically restricting hooks to `.specweaver/scripts/`. (Phase 3.40b)
```

After:
```
- **Bash/Script DAG Nodes** → Inspired by Archon's `bash:`/`script:` node fields (e.g. `script: analyze-metrics` resolved to `.archon/scripts/analyze-metrics.py`), SpecWeaver's `action: bash` deterministic pipeline steps trigger pre-test scaffolding without involving the LLM, resolving bare script names against `.specweaver/scripts/`. "Native CLI Action Nodes" and "FolderGrant" are SpecWeaver's own coinages, not Archon terminology. (Phase 3.40b)
```

`.specweaver/scripts/README.md` (approved):

```markdown
# `.specweaver/scripts/`

Scripts referenced by `action: bash` pipeline steps (C-EXEC-02) live here.

Reference a script by **bare filename only** — `script: setup.sh`, never a
path. It is resolved as `.specweaver/scripts/<name>` and canonically
validated to stay inside this directory before every execution; anything
that would resolve outside it (traversal, symlink escape, absolute path)
is rejected.
```

## Tests

| Test | File | FR | Asserts |
|------|------|-----|---------|
| `test_creates_scripts_dir_with_readme` | `test_scaffold.py` (new, mirrors `test_creates_templates_dir_with_component_spec`) | FR-10 | `scaffold_project(tmp_path)` → `.specweaver/scripts/README.md` is a file; content mentions "bare filename" and `.specweaver/scripts/` |
| `test_does_not_overwrite_existing_scripts_readme` | `test_scaffold.py` (new, mirrors `test_does_not_overwrite_existing_template`) | FR-10 | Pre-seeded custom README is untouched after `scaffold_project()` (idempotency) |
| `test_marker_dir_has_no_config` (existing) | `test_scaffold.py` | — | Regression: adding `scripts/` does not trip the "no config.yaml in `.specweaver/`" assertion |
| `test_init_creates_scripts_dir` | `test_cli_projects.py` (new, mirrors `test_init_creates_template`) | FR-10 | `sw init` via CLI runner → `.specweaver/scripts/README.md` is a file |

Plus `tach check` after the config edits: it validates `tach.toml` against `context.yaml`
declarations repo-wide even before any code imports through the new path, so it catches a wrong
dotted path or missing declaration before SF-02 exists.

Coverage: FR-10 → `_scaffold_scripts_dir()` + its tests. No NFRs or ADs here — NFR-1 through NFR-10
and AD-1 through AD-6 are SF-01's `BashActionAtom`.

## Decisions (audit)

Both open questions answered by the user ("yes, both A"):

1. `docs/user_guides/1_installation_and_setup.md` §4 gets a clause for `.specweaver/scripts/`.
2. The `.specweaver/scripts/README.md` draft is approved as-is.

Red/Blue review (2 cycles, proportionate to the low risk):

- Call order vs. `_scaffold_templates` does not matter — disjoint paths; only cosmetic CLI output
  order changes.
- Fix only the `flow` row of `hard_dependency_rules.md` — a full audit of the doc is a separate
  cleanup.

Architecture check: no new Python imports (filesystem I/O in `scaffold.py`, config-only edits
elsewhere). `tach.toml`/`core/flow/context.yaml` edits are additive, matching the
`qa_runner`/`git`/`code_structure`/`mcp` precedent.

**Out of scope**: the `action: bash` section of `pipeline_engine_guide.md` (Guide-1, SF-02); the
actual `core/flow` import of `sandbox.execution.core.atom.BashActionAtom` (SF-02).

## As built (2026-07-14)

As planned — all 9 files, no deviations. Added `test_creates_readme_when_scripts_dir_already_exists`
(directory exists, README missing), per the Red/Blue review. 4 new tests (3 unit + 1 CLI), 0
regressions across the full 5086-test suite.
