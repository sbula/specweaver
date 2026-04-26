# Implementation Plan: Refactoring Phase 3 Optimizations [SF-2: Impact-Aware Testing & DAL Enforcements]
- **Feature ID**: 3.32d
- **Sub-Feature**: SF-2 — Impact-Aware Testing & DAL Enforcements
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/C-FLOW-06/C-FLOW-06_design.md
- **Status**: FINAL
- **Approvals**: HITL Phase 4 Approved

## Proposed Changes

### src/specweaver/commons/enums/dal.py
- Add mapping to translate `DALLevel` into `strictness_level` or confidence thresholds (e.g. `DAL_A` implies absolute strictness, `DAL_E` implies high tolerance).
- Implement `is_strictly_enforced(dal_level: DALLevel) -> bool` or similar threshold helpers.

### src/specweaver/core/flow/engine/runner.py
- Update `PipelineRunner` to intrinsically load the `DALLevel` of the execution target by calling `DALResolver`.
- Inject the resolved `DALLevel` into the execution context so that handlers can adapt their strictness natively based on the safety boundary of the file being processed.

### src/specweaver/interfaces/cli/validation.py
- Refactor the `sw check` command to implement a **Fail-at-end** UX pattern.
- Rather than exiting immediately upon the first failure, execute the complete validation pipeline across all targeted files.
- Aggregate all warnings and errors into a final console report.
- If the aggregated results contain any violations that breach the target's `DALLevel` strictness, emit a non-zero exit code (`typer.Exit(code=1)`) at the absolute end of the command.

### tests/unit/interfaces/cli/test_cli_standards.py
- Remove the `TestScanCiMode` test class, as the `--ci` flag concept was rejected during the architectural audit.

### tests/unit/interfaces/cli/test_cli_validation.py
- Add tests to verify the Fail-at-end behavior in `sw check`.
- Add tests to ensure that a `DAL_A` target correctly converts warnings to hard failures resulting in `exit_code == 1`.
- Add tests to ensure that a `DAL_E` target correctly exits with `0` despite minor warnings.

## Research & Audit Notes
- **DAL Native Enforcement**: The Phase 4 architectural audit determined that hiding safety constraints behind a CLI `--ci` flag is an anti-pattern. Instead, `DALResolver` bounds will be injected deeply into `PipelineRunner` so that strictness is enforced natively on the developer's machine and the CI server equally.
- **Fail-at-end**: To prevent poor developer UX (having to fix errors one-by-one), pipelines will complete their full run, aggregate all violations, print a comprehensive summary, and then evaluate the final exit code.
- **CLI Architecture Debt**: The confusion over `sw scan` vs `sw check` revealed significant technical debt in the CLI verb architecture. A new backlog item has been added to isolate Discovery commands from Validation commands in a future refactor.
