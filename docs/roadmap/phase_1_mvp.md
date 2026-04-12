# Phase 1: MVP — Prove the Concept

> **Status**: ✅ COMPLETE (Steps 1–5) | Step 6 ⏸ DEFERRED
> **Goal**: A runnable CLI that demonstrates the Core Loop end-to-end. Static validation works. LLM integration works (at least for one feature). You can `sw check` a real spec and get real results.

---

## Step 1: Project Scaffold + CLI Shell ✅

> **Goal**: `sw --help` works. Project structure is real.

- [x] `pyproject.toml` with Typer dependency
- [x] `src/specweaver/__init__.py`, `cli.py` — F1: CLI entry point with subcommands (stubs)
- [x] `src/specweaver/config/settings.py` — project path resolution (`--project` / `SW_PROJECT`)
- [x] `src/specweaver/project/scaffold.py` — `sw init` creates `.specweaver/` in target
- [x] Tests: CLI dispatch, settings resolution, scaffold creation
- [x] **Runnable**: `sw init --project ./test-project` creates the directory structure

**Estimated effort**: 1–2 sessions. ✅ Largely completed.

---

## Step 1b: Loom — Filesystem Tools & Atoms ✅

> **Goal**: Agents and Engine have secure, role-gated filesystem access. Agents see only whitelisted boundaries.

- [x] `loom/commons/filesystem/executor.py` — `FileExecutor` + `EngineFileExecutor` (path traversal, symlinks, protected patterns, atomic writes)
- [x] `loom/tools/filesystem/tool.py` — `FileSystemTool` with role-intent gating, `FolderGrant` boundary enforcement, `../` security fix
- [x] `loom/tools/filesystem/interfaces.py` — 3 role interfaces + factory
- [x] `loom/atoms/filesystem/atom.py` — 5 intents: scaffold, backup, restore, aggregate_context, validate_boundaries
- [x] `context.yaml` boundary manifests for filesystem modules
- [x] 183 tests (780 total passing), ruff + mypy clean
- [x] **Security audited**: `../` bypass, backslash normalization, trailing slashes, empty grants

---

## Step 2: Validation Engine + First Spec Rules ✅

> **Goal**: `sw check path/to/spec.md` runs rules and reports results. This is the highest-leverage MVP feature — it proves the core concept without LLM cost.

- [x] `src/specweaver/validation/models.py` — Rule, RuleResult, Finding interfaces
- [x] `src/specweaver/validation/runner.py` — runs all rules, collects results
- Spec rules (static-only first):
  - [x] `s01_one_sentence.py` — conjunction count in Purpose ✅
  - [x] `s02_single_setup.py` — environment category count ✅
  - [x] `s05_day_test.py` — complexity score heuristic ✅
  - [x] `s06_concrete_example.py` — code block presence in Contract ✅
  - [x] `s08_ambiguity.py` — weasel word scan ✅
  - [x] `s09_error_path.py` — error/failure keyword search ✅
  - [x] `s10_done_definition.py` — verification section check ✅
  - [x] `s11_terminology.py` — inconsistent casing + undefined domain term detection ✅ (2026-03-12)
- [x] Test fixtures: `good_spec.md`, `bad_spec_ambiguous.md`, `bad_spec_no_examples.md`, `bad_spec_too_big.md`
- [x] Tests: per-rule tests (5–11 cases each), runner integration test
- [x] **Runnable**: `sw check good_spec.md` → all PASS. `sw check bad_spec_ambiguous.md` → S08 FAIL.

**Status**: All 11 rules implemented and tested (851 tests, 93% coverage).

> [!NOTE]
> Formal spec definitions (dogfooding: writing SpecWeaver specs for SpecWeaver's own rules) are deferred until LLM-integrated validation is available. The rules work and are tested; dogfooding is a documentation task, not a functional blocker.

---

## Step 3: LLM Adapter + Remaining Spec Rules ✅

> **Goal**: LLM adapter works. The 2 LLM-dependent spec rules (S03, S07) are implemented. The dependency-direction rule (S04) is wired.

- [x] `src/specweaver/llm/adapter.py` — LLMAdapter abstract interface
- [x] `src/specweaver/llm/gemini_adapter.py` — Gemini API concrete adapter (with message conversion, error mapping, content filter handling)
- [x] `s03_stranger.py` — static heuristic: external refs + undefined term count ✅
- [x] `s04_dependency_dir.py` — static: cross-reference direction scan + dead-link detection (traceability extension, 2026-03-12) ✅
- [x] `s07_test_first.py` — static heuristic: contract testability scoring ✅
- [x] Tests: adapter unit tests (20+), rule tests (6 each for S03/S04/S07), error hierarchy, models

**Status**: All spec rules operational (11/11). LLM adapter ready.

---

## Step 4: Spec Review (F4) + Spec Drafting (F2) ✅

> **Goal**: LLM-powered features. `sw review spec` produces semantic judgment. `sw draft` co-authors a spec interactively.

- [x] `src/specweaver/review/reviewer.py` — F4: unified review engine (ACCEPTED/DENIED/ERROR verdicts, finding extraction, raw response preserved)
- [x] `src/specweaver/context/provider.py` — ContextProvider ABC
- [x] `src/specweaver/context/hitl_provider.py` — HITL interactive context (Rich prompts, section display)
- [x] `src/specweaver/drafting/drafter.py` — F2: interactive spec drafting (5-section template, LLM per section, TODO on skip)
- [x] Tests: reviewer (10 tests incl. parse edge cases), drafter (8 tests), context provider (4 tests), HITL (5 tests), behavioral tests (error propagation, boundary inputs)
- [x] **Runnable**: `sw draft greet_service` → interactive session → `greet_service_spec.md` produced.

**Estimated effort**: 2–3 sessions. ✅ Completed.

---

## Step 5: Implementation + Code Validation + Code Review (F5, F6, F7) ✅

> **Goal**: The full loop works. Spec → code → tests → validation → review.

- [x] `src/specweaver/implementation/generator.py` — F5: code generation + test generation (markdown fence cleaning, dir creation)
- [x] Code validation rules:
  - [x] `c01_syntax_valid.py` — `ast.parse` syntax check
  - [x] `c02_tests_exist.py` — test file presence
  - [x] `c03_tests_pass.py` — pytest subprocess (mocked, with timeout handling)
  - [x] `c04_coverage.py` — coverage ≥ threshold (configurable, default 70%)
  - [x] `c05_import_direction.py` — forbidden upward import scan
  - [x] `c06_no_bare_except.py` — AST scan
  - [x] `c07_no_orphan_todo.py` — TODO/FIXME/HACK/XXX grep
  - [x] `c08_type_hints.py` — AST annotation coverage check
- [x] Code review via `reviewer.review_code(code, spec)`
- [x] Integration test: `test_pipeline.py` — init → check spec → implement → check code
- [x] E2E test: `test_lifecycle.py` (972 lines) — full init → draft → check → review → implement → check → review
- [x] **Runnable**: Full core loop demonstrated on a real spec.

**Estimated effort**: 3–4 sessions. ✅ Completed.

---

## Step 6: Dogfooding — SpecWeaver Validates Its Own Specs ⏸ DEFERRED

> **Goal**: Use SpecWeaver on its own documentation. This is the "product works" moment.
> **Deferred**: Flow needs to be more stable and configurable with better validation integration before dogfooding provides meaningful feedback.

- [ ] Run `sw check` on `mvp_feature_definition.md` and architecture docs
- [ ] Run `sw draft` to create a real Component Spec for one of SpecWeaver's own modules
- [ ] Run the full loop on a small, real feature
- [ ] Fix any issues discovered during dogfooding
- [ ] **Milestone**: SpecWeaver has been used on a real project (itself).

**Estimated effort**: 1–2 sessions. Will be revisited after Phase 2 is finished.
