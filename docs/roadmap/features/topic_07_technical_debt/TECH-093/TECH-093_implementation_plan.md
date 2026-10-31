# Implementation Plan: Three Code Checks Read Every Language as Python
- **Feature ID**: TECH-093
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-093/TECH-093_design.md
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-093/TECH-093_implementation_plan.md
- **Status**: APPROVED

## Findings (Phase 4)

No finding is CRITICAL or HIGH. The user accepted every proposal below on 2026-10-31.

### F-1 (MEDIUM, backward compatibility): about 20 unit tests call `rule.check(code)` with no path
- Where: `tests/unit/assurance/validation/rules/code/test_code_rules.py` (C01, C06, C08 classes)
  and `tests/unit/assurance/validation/rules/test_c01_c02_c03.py` (C01). After FR-2 they get SKIP.
- Options: (a) give each a `Path("x.py")`; (b) keep a Python default for no path.
- (b) breaks FR-2 `[agreed 2026-10-31]`. Impact of (a): test edits only.
- **Proposal**: (a). Other tests that reach the rules with no path show up in the first full run
  and get the same edit.

> Comment:

### F-2 (MEDIUM, testing): the CLI table can cut the SKIP message
- `sw check` prints a Rich table; the probe on 2026-10-31 showed messages cut at about 35
  characters ("Syntax error at line 1: invalid"). A test that looks for `kotlin` in the output
  could fail on width, not on behaviour.
- Options: (a) assert with `tests/rendering.py` `shows(output, needle)` and a short message that
  puts the language first; (b) read the results from the executor instead of the output.
- (b) does not prove what the user sees.
- **Proposal**: (a). The message starts with the language: `kotlin: C01 checks Python only`.
  For an unknown language: `language unknown: C01 checks Python only`.

> Comment:

### F-3 (LOW, architecture): where the shared check lives
- Options: (a) a function in a new `rules/code/_python_only.py`; (b) a method on the `Rule` base
  class in `assurance/validation/models.py`.
- (b) puts a Python-only idea into every rule, spec rules included.
- **Proposal**: (a). `python_only(rule_id: str, spec_path: Path | None) -> str | None` returns the
  SKIP reason, or `None` for a Python file. Each rule calls it first and returns
  `self._skip(reason)` when it is not `None`, so no code outside a rule calls its `_skip`
  (red/blue R1).

> Comment:

### F-4 (LOW, testing): proof tier of FR-3 and FR-4
- FR-3 goes through the CLI, the hydrator, the executor and the rules; FR-4 through the API. Both
  stay inside validation.
- **Proposal**: integration, in-process: `CliRunner` for FR-3 (as `test_cli_check.py`) and
  `TestClient` with a registered project for FR-4 (as `test_api_check_profile.py`).

> Comment:

### F-5 (LOW, scope): `sw implement` is not touched
- `ValidateCodeHandler._test_rules_only` already removes C01, C06 and C08 for a non-Python file.
- **Proposal**: no change and no new test there; `test_validate_code_languages.py` already pins it.

> Comment:

### F-6 (LOW, documentation)
- `docs/user_guides/1_installation_and_setup.md:334` names only `sw implement`.
- **Proposal**: add one sentence: `sw check` and the API show C01, C06 and C08 as SKIP for another
  language. Recount README numbers with `scripts/readme_counts.py`.

> Comment:

### F-7 (LOW, proof): mutants
- **Proposal**: a new `TECH-093_mutants.json`:
  - FR-1 `language-check-removed`: the helper always returns `None` (every language parsed as
    Python);
  - FR-1 `c01-skips-the-check`, `c06-skips-the-check`, `c08-skips-the-check`: one rule's call to
    the helper removed;
  - FR-2 `unknown-language-parsed`: the helper returns `None` when the language is unknown.

> Comment:

## Phase 3: Architecture Verification

- `rules/code/` is `pure-logic`, consumes `specweaver/assurance/validation`. The helper adds no
  I/O: it reads only the path's ending.
- `specweaver.commons` is a tach `utility = true` module (`tach.toml:172`) with no dependencies;
  `rules/spec/s12_archetype_spec_bounds.py` imports it already. No new edge, no cycle.
- No `forbids` entry is touched (`sandbox/*`, `infrastructure/llm`, `workflows/drafting`).

## Research Notes

- `language_of(path: str | PurePath) -> str | None` (`commons/languages.py:39`): `.py`, `.pyi` →
  `python`; `.kt`, `.kts` → `kotlin`; `.java`, `.rs`, `.ts`, `.tsx`, `.js` named; others `None`.
- `Rule._skip(self, message: str = "") -> RuleResult` (`assurance/validation/models.py:172`).
- `Rule.check(self, spec_text: str, spec_path: Path | None = None) -> RuleResult`; callers:
  `runner.py:66`, `executor.py:206`.
- The CLI summary (`interfaces/cli.py:_print_summary`) counts FAIL and WARN only; out of scope
  `[agreed 2026-10-31]`.

## Commit Boundaries

One boundary: the change is three call sites and one helper. It closes the feature, so it stops
for the user's acceptance.

### CB-1 — C01, C06 and C08 judge Python only (FR-1, FR-2, FR-3, FR-4), kind `bugfix`

Order (red first, each red recorded with its reason):

1. **Seam tests first** (the interface exists, the behaviour does not):
   - `tests/integration/assurance/validation/test_code_checks_skip_other_languages.py` [NEW]
     (FR-3): `sw check --level code` on a valid `Cart.kt` in `tmp_path`. Expect C01, C06, C08 as
     SKIP with `kotlin` shown, and no C01 FAIL. **Red today**: C01 FAIL "Syntax error at line 1".
   - `tests/integration/interfaces/api/test_api_check_other_languages.py` [NEW] (FR-4):
     `POST /api/v1/check`, `level: code`, a `.kt` file in a registered project. Expect the three
     rows `skip` and none counted in `failed`. **Red today**: C01 `fail`.
2. **Rule tests** `tests/unit/assurance/validation/rules/code/test_python_only.py` [NEW]:
   - Happy: a `.py` file keeps today's PASS/FAIL/WARN for each rule (NFR-1).
   - Boundary: `.pyi` is checked; `.kt`, `.java`, `.rs`, `.ts` give SKIP naming the language;
     a TypeScript text that parses as Python (`x = 1`) gives SKIP, not PASS.
   - Degradation: a `.py` file with a syntax error keeps C01 FAIL with the line, C06 and C08
     SKIP "Cannot parse file (syntax error)" (NFR-2).
   - Hostile: `spec_path=None`, `bin/tool` (no ending) and `notes.txt` give SKIP "language
     unknown", and the text is never parsed (a text that would FAIL C01 still gives SKIP).
   **Red today**: every non-Python case.
3. **Green**: `rules/code/_python_only.py` [NEW] with `python_only`; `c01_syntax_valid.py`,
   `c06_no_bare_except.py`, `c08_type_hints.py` [MODIFY] call it before `ast.parse`.
   Pseudocode:
   ```
   language = language_of(spec_path) if spec_path else None
   if language == "python": return None
   return f"{language or 'language unknown'}: {rule_id} checks Python only"
   # in each rule, first line of check(): reason = python_only(self.rule_id, spec_path)
   ```
4. **Fallout**: the path-less tests (F-1) get `Path("x.py")`.
5. **Docs**: the user guide sentence (F-6); README counts; `context.yaml` description stays.
6. **Mutants**: `TECH-093_mutants.json` (F-7), each killed.

**Done when**: `scripts/tests.py cb TECH-093 --kind bugfix` green; the 5 mutants killed;
`check_fr_coverage.py TECH-093` cites FR-1..FR-4.

## Phase 5: Consistency and Red/Blue

- Every FR (1-4) and NFR (1-2) has a test in CB-1; AD-1 (one language table), AD-2 (the rule
  decides) and AD-3 (one helper) are steps 3 and F-3.
- Red/Blue, 2 cycles:
  - R1 (LOW) the helper called `rule._skip` from outside the class. Fixed: it returns the reason.
  - R2 (LOW) `.kts` scripts are Kotlin by `language_of`; they skip like `.kt`. No change.
  - R3 (LOW) the empty-text C01 case on a `.py` path keeps its PASS (NFR-1). Pinned in step 2.
  - Cycle 2: challenged F-2 (could the language name still be cut?). No: it is the first word,
    and `shows()` joins wrapped lines. No new finding.

## Backlog

- `sw check`'s summary counts SKIP rows: the next TECH ticket started `[agreed 2026-10-31]`
  (`.agents/STATE.md`).
