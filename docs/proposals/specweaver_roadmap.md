# SpecWeaver Roadmap

> **Date**: 2026-03-08
> **Status**: ACTIVE
> **Context**: Step-by-step plan for SpecWeaver development. Fresh start from scratch, informed by [flowManager](https://github.com/sbula/flowManager) learnings. MVP-first approach: prove the concept, then expand feature by feature.

> [!IMPORTANT]
> **The Core Principle**: MVP first → Prove it works → Isolate & implement features one by one → Full functionality.
> Every phase must produce something *runnable*. No phase is "just spec work."

---

## Current State (updated 2026-03-10)

**What exists:**
- ✅ Repo: `sbula/specweaver` — fresh, clean
- ✅ Documentation: MVP feature definition, methodology, architecture, lifecycle layers
- ✅ Decision log: Python, Typer CLI, Gemini API, deployment isolation
- ✅ Project scaffold: `pyproject.toml`, CLI shell, `sw init`
- ✅ Loom layer: Filesystem tools, atoms, and interfaces (**183 tests**, fully linted + type-checked)
- ❌ Validation engine, LLM adapter, drafting, review, implementation — not started

**What we're building** (see [mvp_feature_definition.md](mvp_feature_definition.md)):
- A CLI tool (`sw`) that operates ON projects, not within them
- Core loop: Draft → Validate Spec → Review Spec → Implement → Validate Code → Review Code
- 7 features (F1–F7), ~25 Python files, ~2500–4000 LOC

---

## Phase 1: MVP — Prove the Concept

> **Goal**: A runnable CLI that demonstrates the Core Loop end-to-end. Static validation works. LLM integration works (at least for one feature). You can `sw validate spec` a real spec and get real results.

### Step 1: Project Scaffold + CLI Shell

> **Goal**: `sw --help` works. Project structure is real.

- [x] `pyproject.toml` with Typer dependency
- [x] `src/specweaver/__init__.py`, `cli.py` — F1: CLI entry point with subcommands (stubs)
- [ ] `src/specweaver/config/settings.py` — project path resolution (`--project` / `SW_PROJECT`)
- [x] `src/specweaver/project/scaffold.py` — `sw init` creates `.specweaver/` in target
- [x] Tests: CLI dispatch, settings resolution, scaffold creation
- [x] **Runnable**: `sw init --project ./test-project` creates the directory structure

**Estimated effort**: 1–2 sessions. ✅ Largely completed.

---

### Step 1b: Loom — Filesystem Tools & Atoms ✅ COMPLETED

> **Goal**: Agents and Engine have secure, role-gated filesystem access. Agents see only whitelisted boundaries.

- [x] `loom/commons/filesystem/executor.py` — `FileExecutor` + `EngineFileExecutor` (path traversal, symlinks, protected patterns, atomic writes)
- [x] `loom/tools/filesystem/tool.py` — `FileSystemTool` with role-intent gating, `FolderGrant` boundary enforcement, `../` security fix
- [x] `loom/tools/filesystem/interfaces.py` — 3 role interfaces + factory
- [x] `loom/atoms/filesystem/atom.py` — 5 intents: scaffold, backup, restore, aggregate_context, validate_boundaries
- [x] `context.yaml` boundary manifests for filesystem modules
- [x] 183 tests (780 total passing), ruff + mypy clean
- [x] **Security audited**: `../` bypass, backslash normalization, trailing slashes, empty grants

---

### Step 2: Validation Engine + First Spec Rules

> **Goal**: `sw validate spec path/to/spec.md` runs rules and reports results. This is the highest-leverage MVP feature — it proves the core concept without LLM cost.

- [ ] `src/specweaver/validation/models.py` — Rule, RuleResult, Finding interfaces
- [ ] `src/specweaver/validation/runner.py` — runs all rules, collects results
- [ ] Spec rules (static-only first):
  - [ ] `s01_one_sentence.py` — conjunction density in Purpose
  - [ ] `s02_single_setup.py` — environment category count
  - [ ] `s05_day_test.py` — complexity score heuristic
  - [ ] `s06_concrete_example.py` — code block presence
  - [ ] `s08_ambiguity.py` — weasel word scan
  - [ ] `s09_error_path.py` — error/failure keyword search
  - [ ] `s10_done_definition.py` — verification section check
- [ ] Test fixtures: `good_spec.md`, `bad_spec_ambiguous.md`, `bad_spec_no_examples.md`, `bad_spec_too_big.md`
- [ ] Tests: per-rule tests, runner integration test
- [ ] **Runnable**: `sw validate spec good_spec.md` → all PASS. `sw validate spec bad_spec_ambiguous.md` → S08 FAIL.

**Estimated effort**: 2–3 sessions. This is the "product exists" moment.

---

### Step 3: LLM Adapter + Remaining Spec Rules

> **Goal**: LLM adapter works. The 2 LLM-dependent spec rules (S03, S07) are implemented. The dependency-direction rule (S04) is wired.

- [ ] `src/specweaver/llm/adapter.py` — LLMAdapter abstract interface
- [ ] `src/specweaver/llm/gemini_adapter.py` — Gemini API concrete adapter
- [ ] `s03_stranger.py` — LLM: summarize from Purpose alone
- [ ] `s04_dependency_dir.py` — static: cross-reference direction scan
- [ ] `s07_test_first.py` — LLM: generate test from Contract alone
- [ ] Tests: adapter unit tests (with mocked responses), rule tests
- [ ] **Runnable**: All 10 spec validation rules operational.

**Estimated effort**: 2–3 sessions.

---

### Step 4: Spec Review (F4) + Spec Drafting (F2)

> **Goal**: LLM-powered features. `sw review spec` produces semantic judgment. `sw draft` co-authors a spec interactively.

- [ ] `src/specweaver/review/reviewer.py` — F4: unified review engine
- [ ] `src/specweaver/review/prompts/spec_review.md` — review prompt template
- [ ] `src/specweaver/context/provider.py` — ContextProvider interface
- [ ] `src/specweaver/context/hitl_provider.py` — HITL interactive context
- [ ] `src/specweaver/drafting/drafter.py` — F2: interactive spec drafting
- [ ] `src/specweaver/config/templates/component_spec.md` — 5-section template
- [ ] Tests: reviewer prompt construction, drafter flow (mocked LLM)
- [ ] **Runnable**: `sw draft greet_service` → interactive session → `greet_service_spec.md` produced.

**Estimated effort**: 2–3 sessions.

---

### Step 5: Implementation + Code Validation + Code Review (F5, F6, F7)

> **Goal**: The full loop works. Spec → code → tests → validation → review.

- [ ] `src/specweaver/implementation/generator.py` — F5: code generation from spec
- [ ] `src/specweaver/implementation/test_generator.py` — F5: test generation from spec
- [ ] Code validation rules:
  - [ ] `c01_syntax_valid.py` — import check
  - [ ] `c02_tests_exist.py` — test file presence
  - [ ] `c03_tests_pass.py` — pytest execution
  - [ ] `c04_coverage.py` — coverage ≥ 70%
  - [ ] `c05_import_direction.py` — upward import scan
  - [ ] `c06_no_bare_except.py` — AST scan
  - [ ] `c07_no_orphan_todo.py` — TODO/FIXME grep
  - [ ] `c08_type_hints.py` — AST annotation check
- [ ] `src/specweaver/review/prompts/code_review.md` — code review prompt
- [ ] Integration test: `test_full_loop.py` — F2→F3→F4→F5→F6→F7
- [ ] **Runnable**: Full core loop demonstrated on a real spec.

**Estimated effort**: 3–4 sessions.

---

### Step 6: Dogfooding — SpecWeaver Validates Its Own Specs

> **Goal**: Use SpecWeaver on its own documentation. This is the "product works" moment.

- [ ] Run `sw validate spec` on `mvp_feature_definition.md` and architecture docs
- [ ] Run `sw draft` to create a real Component Spec for one of SpecWeaver's own modules
- [ ] Run the full loop on a small, real feature
- [ ] Fix any issues discovered during dogfooding
- [ ] **Milestone**: SpecWeaver has been used on a real project (itself).

**Estimated effort**: 1–2 sessions.

---

## Phase 2: Stabilize & Harden

> **Goal**: MVP is solid. Tests are comprehensive. Per-layer configuration works. Ready for external use.

- [ ] Per-layer rule configuration (`.specweaver/config.yaml` with layer-specific thresholds)
- [ ] CLI polish: colored output, progress indicators, `--verbose` / `--json` flags
- [ ] Error handling: graceful LLM failures, network timeouts, API quota
- [ ] Documentation: README, `sw --help` for all commands, quick-start guide
- [ ] Test coverage target: 70–90%
- [ ] **Milestone**: Someone else could install and use SpecWeaver.

**Estimated effort**: 2–3 sessions.

---

## Phase 3: Feature Isolation & Incremental Expansion

> **Goal**: Take each major capability from the architecture docs, isolate it as a self-contained feature, and implement it one by one. Each feature is proposed → approved → implemented → tested → merged.

Order will be based on value and dependencies. Likely sequence:

| Priority | Feature | Source Doc | Why This Order |
|:---|:---|:---|:---|
| **3.1** | Feature Spec layer (L2 decomposition) | `lifecycle_layers.md` | Enables multi-layer workflows |
| **3.2** | Domain profiles for threshold calibration | `future_capabilities_reference.md` §19 | Quick win — just config |
| **3.3** | Additional context providers (FileSearch, WebSearch) | `mvp_feature_definition.md` | Enhances drafting and review quality |
| **3.4** | Multi-model LLM support (model routing per task) | `future_capabilities_reference.md` §9, §15 | Cross-model shadow review |
| **3.5** | Spec-to-code traceability | `future_capabilities_reference.md` §17 | Bidirectional linking |
| **3.6** | Automated spec decomposition | `future_capabilities_reference.md` §18 | Agent proposes, HITL approves |
| **3.7** | Constitution enforcement | `constitution_template.md` | Project-wide constraint checking |

**Process for each feature**:
1. Write an isolation proposal (what, inputs, outputs, interfaces, scope)
2. HITL approves the proposal
3. Implement with tests
4. Dogfood on SpecWeaver itself
5. Merge

---

## Phase 4: Advanced Capabilities

> **Goal**: The features from `future_capabilities_reference.md` that require significant engineering.

| Priority | Feature | Source |
|:---|:---|:---|
| **4.1** | Symbol index + anti-hallucination gate | `future_capabilities_reference.md` §11 |
| **4.2** | AST-based semantic chunking (RAG foundation) | `future_capabilities_reference.md` §3 |
| **4.3** | RAG context provider | `rag_architecture.md` via §1, §5 |
| **4.4** | Tiered access rights (zero-trust knowledge) | `future_capabilities_reference.md` §1 |
| **4.5** | Agent isolation patterns (multi-agent review) | `future_capabilities_reference.md` §6 |
| **4.6** | Verification gates (mutation testing, assertion density) | `future_capabilities_reference.md` §13, §14 |
| **4.7** | Blast radius / locality enforcement | `future_capabilities_reference.md` §16 |
| **4.8** | Containerized deployment (Podman) | `mvp_feature_definition.md` |

---

## Phase 5: External Validation

> **Goal**: SpecWeaver is used on a real project that isn't SpecWeaver itself.

- [ ] Identify a target project (small-to-medium Python project)
- [ ] Run the full workflow: `sw init` → `sw draft` → `sw validate spec` → `sw implement` → `sw validate code` → `sw review code`
- [ ] Document the experience: what worked, what didn't, what's missing
- [ ] **Milestone**: SpecWeaver is **useful** on real-world projects.

---

## Timeline Estimate (Spare-Time + AI Agents)

```
Phase 1: MVP (Steps 1-6)     ████████████████████████████     (~6-8 weeks)
Phase 2: Stabilize            ████████                         (~2-3 weeks)
Phase 3: Feature Expansion    ████████████████████████████████ (~open-ended, feature by feature)
Phase 4: Advanced             ████████████████████████████████ (~open-ended)
Phase 5: External             ████████                         (~2 weeks)
                              ─────────────────────────────────────────────
                              Week 1    Week 4    Week 8    Week 12    ...
```

> [!TIP]
> **Agent leverage**: Steps 2-3 (validation rules) are prime candidates for AI-assisted implementation — each rule is a small, self-contained function with clear inputs/outputs. Steps 4-5 (LLM features) require more human judgment on prompt design.

---

## Success Criteria

**MVP is PROVEN when you can:**
1. ✅ `sw init --project ./my-app` creates the project structure
2. ✅ `sw validate spec some_spec.md` reports PASS/FAIL with findings
3. ✅ `sw draft greet_service` produces a real spec via HITL interaction
4. ✅ `sw implement greet_service_spec.md` generates code + tests
5. ✅ `sw validate code greet_service.py` checks syntax, tests, coverage
6. ✅ `sw review code greet_service.py` provides LLM semantic judgment

**Product is USEFUL when additionally:**
7. ✅ You've used it on SpecWeaver itself (dogfooding)
8. ✅ You've used it on an external project
9. ✅ Features can be added without restructuring (interface extensibility confirmed)

---

## Superseded Document

This roadmap replaces the original `specweaver_roadmap.md` from flowManager, which described evolving the flowManager engine (recursive flow execution, atoms, sub-flows, state persistence, crash recovery). That approach was abandoned in favor of a fresh start — see [ORIGINS.md](../ORIGINS.md) for the full history.
