# Guardrails — How Safety Is Built and Assured

SpecWeaver enforces safety at **every layer** through distinct mechanisms:

## Layer 1: Boundary Manifests (`context.yaml` & `tach.toml`)

Every directory declares its allowed dependencies, forbidden imports, and
archetype. Violations are detectable by AST analysis (free, no LLM needed).
Additionally, SpecWeaver is built as a **PEP-420 Implicit Namespace Package**, formally omitting `__init__.py` proxy files in favor of mathematically evaluated Rust boundaries using `Tach`.

| Enforcement Field | Mechanism |
|-------------------|-----------|
| `tach.toml` | Globally enforced strict boundaries preventing domain upward dependencies |
| `consumes` | Whitelist of allowed imports (`context.yaml`) |
| `forbids` | Explicit deny list (overrides parent) |
| `archetype` | Structural pattern validation |
| `constraints` | Free-form rules for veto agent |

## Layer 2: Tool Security Stack (3 layers deep)

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

Static validation rules (S01-S12, C01-C09, C12) catch structural and completeness
issues before any LLM is involved:

| Category | Rules | Examples |
|----------|-------|---------|
| Structure (S01-S05) | One sentence, single setup, size budget, dependency direction, conjunction count | Detects "god specs" |
| Completeness (S06-S11) | Weasel words, examples, error paths, done definition, scenarios | Detects ambiguity |
| Code (C01-C09, C12) | Generated code quality validation and native framework archetype constraints | Detects spec deviations and abstraction drift |

## Layer 5: LLM Semantic Review

`Reviewer` and `Planner` use LLM function-calling to research the codebase
(via tools) and produce structured verdicts (ACCEPTED/DENIED with findings).
This catches semantic issues that static rules miss.

## Layer 6: Constitution

The `CONSTITUTION.md` is a project-level policy file:
- **Read-only for agents** — agents MUST read it before any work
- **Overrides specs** — if a spec conflicts with the constitution, the constitution wins
- **Injected into prompts** — constitution content is added to LLM prompts
  via `PromptBuilder.add_constitution()`
- **Protected by filesystem tool** — `_PROTECTED_PATTERNS` blocks agent writes
  to `context.yaml` and similar sensitive files

## Layer 7: Standards Auto-Discovery

The `standards/` module analyzes the codebase via AST parsing to extract
naming conventions, error handling patterns, type hint usage, etc.
These are injected into LLM prompts so generated code matches existing style.

## Layer 8: Sandbox Validation (Worktree Bouncer)

The `PipelineRunner` forces LLM modifications (`use_worktree=True`) logically into separated physical Git Sandboxes. Before code is permitted out of isolation, an `_intent_strip_merge` mathematical patch diff strips any hunks modifying targets not explicitly inside `context.yaml` topological bounds, dropping hallucinations before `git apply`.

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

## Updating 3rd Party Software and Protocols within SpecWeaver

To insulate SpecWeaver from breaking changes in standard compilation/debugging schemas (like DAP and SARIF), we utilize an **Adapter Pattern** strategy. External schemas must NEVER be consumed directly by LLM Agents or the workflow flow engine.

1. **Protocol Insulation**: All external protocol outputs are rigorously mapped into strictly typed, internal data models (`CompileError`, `CompileRunResult`, `OutputEvent`, etc.) within `sandbox/qa_runner/interface.py`.
2. **Deprecation Strategy**: Temporary fallback adaptors (e.g., the `PythonQARunner` stub implementing `run_compiler` as a no-op) must be documented and explicitly deleted once the target domain migration completes.
