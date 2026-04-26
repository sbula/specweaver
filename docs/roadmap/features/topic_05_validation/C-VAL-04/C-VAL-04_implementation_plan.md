# Implementation Plan: Automated Traceability Matrix [SF-1: Traceability Engine]
- **Feature ID**: 3.21
- **Sub-Feature**: SF-1 — Traceability Engine
- **Design Document**: docs/roadmap/features/topic_05_validation/C-VAL-04/C-VAL-04_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_05_validation/C-VAL-04/C-VAL-04_implementation_plan.md
- **Status**: APPROVED

## 1. Goal Description
Implement `C09_traceability.py`, a pure logic validation rule that ensures every Functional Requirement (FR) and Non-Functional Requirement (NFR) documented in an L3 Spec is explicitly covered by a target implementation/test file using autonomous, language-agnostic `# @trace(req_id)` or `// @trace(req_id)` abstract syntax tree (AST) meta-comments.

## 2. HITL Approvals & Caveats (Phase 4 Merge)
* **Language-Agnostic File Discovery**: The rule will NOT assume python. It will crawl up to the project root (mirroring `C04_coverage`) and dispatch the workspace files to the respective `tree-sitter` language analyzers (Python, JS/TS, etc.) to extract `comment` nodes from the AST.
* **Greedy Requirement Extraction**: The rule will parse the `spec_text` using a stateless regex (`(?:N)?FR-\d+`) to capture the aggregate set of requirement IDs safely, rather than relying on brittle Markdown table constraints. 

> [!NOTE]
> **Scope Clarification**: This feature strictly checks the *mathematical presence* of the trace link to prove it was addressed mechanically by the orchestrator. Verification of whether the requirement is *really* implemented is handled by **Feature 3.29**, where a completely independent scenario pipeline runs hidden, "black box" tests against the generated code. If the coding agent hallucinates the coverage, the hidden tests fail at the JOIN gate.

## 3. Proposed Changes

### 3.1 Traceability Source Parsing (Validation Rules)
The core engine for traceability extraction, safely bound in the `validation/rules/code` module without side effects.

#### [NEW] src/specweaver/validation/rules/code/c09_traceability.py
- **Class**: `TraceabilityRule(Rule)`
- **`rule_id`**: `"C09"`
- **`name`**: `"Traceability Matrix"`
- **`check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult`**:
  1. **Extract Requirements**: Use `re.findall(r"\b(?:N)?FR-\d+\b", spec_text)` to build the target set. Pass early if the set is empty.
  2. **Find Project Root**: Use standard upward crawl (e.g., finding `pyproject.toml`, `package.json`, or `.git`) stopping at a safe limit, identical to `C04`.
  3. **Discover & Parse AST**: Instantiate available language-specific Tree-Sitter parsers. Recursively walk test directories (or all files, depending on language configuration) to extract nodes of type `comment`.
  4. **Intersect Requirements**: Scan the text of AST comment nodes for the `@trace(FR-x)` pattern. Keep a set of successfully mapped IDs.
  5. **Validation Delta**: Subtract `mapped_ids` from `target_ids`. If any target IDs are missing, yield a `_fail()` rule result listing exactly which `FR-X` are unmapped. Otherwise, `_pass()`.

#### [MODIFY] src/specweaver/validation/rules/code/register.py
- Import `TraceabilityRule` from `.c09_traceability`.
- Register the rule with the global registry: `_reg.register("C09", TraceabilityRule, "code")`

---

### 3.2 Default Code Pipeline Injection
Integrating the C09 Rule into the standard pipeline YAML so all code generations default to traceability checking.

#### [MODIFY] src/specweaver/pipelines/validation_code_default.yaml
- Prepend the `c09_traceability` step to the `- --- Static analysis (no subprocess) ---` section of the rules list.
- Keep the `rule: C09` configuration without specific parameters (defaults are pure).

---

### 3.3 Test Suite Updates 
Validate the purity and correctness of the new rule context.

#### [NEW] tests/validation/rules/code/test_c09_traceability.py
- **Behavior tests**:
  - `test_passes_when_all_frs_mapped()`: Give it a mocked `spec_text` with FR-1, FR-2 and feed it a mocked AST containing both trace targets.
  - `test_fails_with_missing_frs()`: Feed it FR-1, FR-2, FR-3 but only mock FR-1 and FR-2 trace targets. Ensure output specifies `FR-3 is unmapped`.
  - `test_passes_when_no_frs_found()`: Empty spec text correctly yields a PASS.
  - `test_ignored_false_positives()`: Ensure that `@trace(FR-x)` embedded in a mocked string literal node (not a comment node) fails to register as a mapped requirement.

## 4. Open Questions
There are no remaining open questions.

## 5. Verification Plan

### Automated Tests
```bash
# Run isolated C09 matrix tests
poetry run pytest tests/validation/rules/code/test_c09_traceability.py -v

# Run the full pipeline test suite to verify YAML defaults remain intact
poetry run pytest tests/validation/test_pipeline_loader.py -v
```

### Manual Verification
1. Run `sw invoke` or `sw validate` on a mocked `spec` locally.
2. Confirm the CLI outputs the `C09: Traceability Matrix` phase as either `PASS` or `FAIL`. 
3. Remove a `# @trace` from one of the generated tests and confirm that the C09 validation physically rejects the build and highlights the missing FR.
