# C-VAL-04 SF-01 — Traceability Engine

**Status**: APPROVED · **FRs owned**: FR-1, FR-2, FR-3, FR-4 · **Depends on**: none · **Feature ID**:
3.21 · Design: [C-VAL-04_design.md](C-VAL-04_design.md) §Sub-features → SF-01

FR ownership recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-22-MIG` — the plan
predates the FR ledger.

## Goal

`C09_traceability.py`: a pure-logic validation rule that checks every FR and NFR in an L3 Spec is
covered by a test file through a language-agnostic `# @trace(req_id)` or `// @trace(req_id)` AST
meta-comment.

It checks only that the trace link is **present**. Whether the requirement is really implemented is
**Feature 3.29**'s job: an independent scenario pipeline runs hidden, "black box" tests against the
generated code; if the coding agent hallucinates coverage, the hidden tests fail at the JOIN gate.

## Decisions (HITL)

- **Language-agnostic file discovery**: does NOT assume Python. Crawls up to the project root
  (mirroring `C04_coverage`) and dispatches workspace files to the matching `tree-sitter` language
  analyzers (Python, JS/TS, etc.), which extract `comment` nodes from the AST.
- **Greedy requirement extraction**: a stateless regex (`(?:N)?FR-\d+`) over the `spec_text` collects
  the requirement IDs, instead of relying on Markdown table structure.

## Changes

1. **`[NEW] src/specweaver/validation/rules/code/c09_traceability.py`** — `TraceabilityRule(Rule)`,
   `rule_id` `"C09"`, `name` `"Traceability Matrix"`.
   `check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult`:
   1. **Extract requirements**: `re.findall(r"\b(?:N)?FR-\d+\b", spec_text)` builds the target set.
      Empty set → pass.
   2. **Find project root**: upward crawl (`pyproject.toml`, `package.json` or `.git`) with a safe
      limit, identical to `C04`.
   3. **Discover & parse AST**: instantiate the available Tree-Sitter parsers; walk test directories
      (or all files, per language config) and extract `comment` nodes.
   4. **Intersect**: scan comment text for `@trace(FR-x)`; collect `mapped_ids`.
   5. **Delta**: `target_ids − mapped_ids`. Any missing → `_fail()` listing exactly which `FR-X` are
      unmapped; else `_pass()`.
2. **`[MODIFY] src/specweaver/validation/rules/code/register.py`** — import `TraceabilityRule` from
   `.c09_traceability`; `_reg.register("C09", TraceabilityRule, "code")`.
3. **`[MODIFY] src/specweaver/pipelines/validation_code_default.yaml`** — prepend a
   `c09_traceability` step to the `- --- Static analysis (no subprocess) ---` section; `rule: C09`, no
   parameters, so every code generation runs traceability by default.

## Tests

`[NEW] tests/validation/rules/code/test_c09_traceability.py`:

| Test | Case |
|---|---|
| `test_passes_when_all_frs_mapped()` | mocked `spec_text` with FR-1, FR-2 + a mocked AST with both trace targets → pass |
| `test_fails_with_missing_frs()` | FR-1, FR-2, FR-3, only FR-1 and FR-2 traced → output says `FR-3 is unmapped` |
| `test_passes_when_no_frs_found()` | empty spec text → PASS |
| `test_ignored_false_positives()` | `@trace(FR-x)` inside a string-literal node (not a comment) is not counted |

```bash
# Run isolated C09 matrix tests
poetry run pytest tests/validation/rules/code/test_c09_traceability.py -v

# Run the full pipeline test suite to verify YAML defaults remain intact
poetry run pytest tests/validation/test_pipeline_loader.py -v
```

Manual: run `sw invoke` or `sw validate` on a mocked `spec`; the CLI shows `C09: Traceability Matrix`
as `PASS` or `FAIL`. Remove one `# @trace` from a generated test → C09 rejects the build and names the
missing FR.

## As built

- Proof and mutants: `tests/unit/assurance/validation/rules/code/test_c09_traceability.py`. FR-3 and
  FR-4 are tested separately on purpose: a rule that compares nothing and a rule that compares then
  declines to fail look identical from outside; one mutant each tells them apart.
- **Since moved**: rule → `src/specweaver/assurance/validation/rules/code/`; pipeline →
  `src/specweaver/workflows/pipelines/validation_code_default.yaml`.
- Differs from the plan (read from the code): targets come from every `specs/**/*.md` under the project
  root, not from `spec_text`; the root crawl also accepts `.specweaver`; test tags come from each
  analyzer's `extract_test_mapped_requirements` (`AnalyzerFactory`, injectable via the rule context).
