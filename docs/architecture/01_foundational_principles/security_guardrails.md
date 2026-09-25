# Guardrails — How Safety Is Built and Assured

SpecWeaver enforces safety at **every layer**, each with its own mechanism. The summary is at
[How Guardrails Compose](#how-guardrails-compose).

## Layer 1: Boundary Manifests (`context.yaml` & `tach.toml`)

Every directory declares its allowed dependencies, forbidden imports, and archetype. AST analysis
detects violations (free, no LLM needed).

SpecWeaver is a **PEP-420 Implicit Namespace Package**: packages omit `__init__.py` proxy files, and
`Tach` (Rust) enforces the module boundaries. Five `__init__.py` files remain today (for example
`sandbox/execution/__init__.py`).

| Enforcement Field | Mechanism |
|-------------------|-----------|
| `tach.toml` | Globally enforced strict boundaries preventing domain upward dependencies |
| `consumes` | Whitelist of allowed imports (`context.yaml`) |
| `forbids` | Explicit deny list (overrides parent) |
| `archetype` | Structural pattern validation |
| `constraints` | Free-form rules for veto agent |

## Layer 2: Tool Security Stack (3 layers deep)

Detail: [atoms_vs_tools.md](atoms_vs_tools.md).

```text
Executor ─── transport-level: whitelist commands, block path traversal, block symlinks
   │
  Tool ───── intent-level: ROLE_INTENTS gating, FolderGrant enforcement, mode checks
   │
Interface ── method-level: unauthorized methods physically absent (not just blocked)
```

## Layer 3: Pipeline Gates

Every pipeline step can have a gate that blocks progression:

- **Auto gates**: machine-evaluated (`all_passed`, `accepted`)
- **HITL gates**: require human approval before proceeding
- **Loop-back**: failed review → loops back to draft/generate with feedback
- **Bounded retries**: `max_retries` prevents infinite loops

## Layer 4: 12-Test Battery (Spec Quality)

Static rules (S01-S12, C01-C09, C12, C13) catch structural and completeness issues before any LLM
is involved:

| Category | Rules | Examples |
|----------|-------|---------|
| Structure (S01-S05) | One sentence, single setup, size budget, dependency direction, conjunction count | Detects "god specs" |
| Completeness (S06-S11) | Weasel words, examples, error paths, done definition, scenarios | Detects ambiguity |
| Code (C01-C09, C12, C13) | Generated code quality, framework archetype constraints, contract drift | Detects spec deviations and abstraction drift |

S12 checks archetype bounds in specs.

## Layer 5: LLM Semantic Review

`Reviewer` and `Planner` use LLM function-calling to research the codebase (via tools) and produce
structured verdicts (ACCEPTED/DENIED with findings). This catches semantic issues static rules miss.

## Layer 6: Constitution

`CONSTITUTION.md` is a project-level policy file:

- **Read-only for agents** — agents MUST read it before any work
- **Overrides specs** — if a spec conflicts with the constitution, the constitution wins
- **Injected into prompts** via `PromptBuilder.add_constitution()`
- **Protected by the filesystem tool** — `_PROTECTED_PATTERNS` blocks agent writes to
  `context.yaml`, `.env`, `.git` and `.specweaver`

## Layer 7: Standards Auto-Discovery

The `standards/` module (`assurance/standards/`) parses the codebase (AST) to extract naming
conventions, error handling patterns, type hint usage, etc. These go into LLM prompts so generated
code matches existing style.

## Layer 8: Sandbox Validation (Worktree Bouncer)

The `PipelineRunner` runs LLM modifications in a separate git worktree. A per-step `use_worktree=True`
(or `False`) wins; `None` defers to the isolation policy (`[sandbox].enforce_worktree_isolation`).
Before code leaves isolation, `_intent_strip_merge` merges with `-X ours` (human wins), strips every
file outside `allowed_paths`, and hard-blocks `README.md` and `docs/` regardless.

## How Guardrails Compose

```text
Constitution ──▶ injected into every LLM prompt
Standards ──────▶ injected into every LLM prompt
context.yaml ───▶ pre-code: validates placement + imports
10-test battery ▶ post-draft: validates spec quality
Pipeline gates ─▶ post-step: controls flow (auto/HITL)
Tool stack ─────▶ runtime: enforces agent permissions
Sandbox Diff ───▶ pre-merge: violently enforces physical constraints
```

The "10-test battery" line predates S11/S12; the battery is 12 spec rules today (Layer 4).

## Updating 3rd Party Software and Protocols within SpecWeaver

Rule: external compilation/debugging schemas (DAP, SARIF, etc.) must NEVER be consumed directly by
LLM Agents or the flow engine. An **Adapter Pattern** insulates SpecWeaver from their breaking changes.

1. **Protocol Insulation**: all external protocol outputs map into strictly typed internal models
   (`CompileError`, `CompileRunResult`, `OutputEvent`, etc.) in `commons/qa.py`.
   Since moved (noted 2026-09-25): these were in `sandbox/qa_runner/interface.py`.
2. **Deprecation Strategy**: temporary fallback adaptors (e.g. the `PythonQARunner` stub implementing
   `run_compiler` as a no-op) must be documented and explicitly deleted once the target domain
   migration completes.
