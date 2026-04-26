# Feature 3.32b Sub-Feature 5: Dependency Injection Remediation

The purpose of this sub-feature is to rectify the Integration Debt identified across the Orchestrator boundaries, thoroughly decoupling the `AnalyzerFactory` globals that bypassed the DI constraints established in SF-4.

## Proposed Changes

### 1. Engine Core Context
We must elevate the structural awareness of the `AnalyzerFactoryProtocol` into the flow layer iteratively so the orchestrator can securely pipe it downward.

#### [MODIFY] `RunContext` (file:///C:/development/pitbula/specweaver/src/specweaver/core/flow/handlers/base.py)
- **Change:** Add `analyzer_factory: Any = None` to the `RunContext` Pydantic model. This establishes the structural contract allowing `PipelineRunner` to push the Polyglot DI objects across all discrete nodes.

#### [MODIFY] `PipelineRunner` (file:///C:/development/pitbula/specweaver/src/specweaver/core/flow/engine/runner.py)
- **Change:** During Step Handler execution (in the `execute` or loop mappings), inject `self._analyzer_factory` explicitly into the instantiated `RunContext`.

### 2. FileSystem Token Exclusions (Agent Dispatcher)
The LLM dispatcher is fundamentally violating the architectural boundary rules by globally importing `AnalyzerFactory`.

#### [MODIFY] `ToolDispatcher` (file:///C:/development/pitbula/specweaver/src/specweaver/core/loom/dispatcher.py)
- **Change:** Add `analyzer_factory: Any = None` to `ToolDispatcher.factory()`.
- **Change:** Remove the static global import of `AnalyzerFactory`. Only dynamically add `exclude_dirs` or `exclude_patterns` if the `analyzer_factory` instance is robustly defined via parameter payload.

### 3. Traceability Validation Boundaries
The validation orchestration was failing to transport the Factory parameters down natively to `rule.context`.

#### [MODIFY] `executor.py` (file:///C:/development/pitbula/specweaver/src/specweaver/assurance/validation/executor.py)
- **Change:** Update `execute_validation_pipeline` signature to cleanly accept `context: dict[str, Any] | None = None`. 
- **Change:** Set `rule.context = context` iteratively before `rule.check()` executes.

#### [MODIFY] `validation.py` (file:///C:/development/pitbula/specweaver/src/specweaver/core/flow/handlers/validation.py)
- **Change:** Within `ValidateSpecHandler.execute` and `ValidateCodeHandler.execute`, derive `analyzer_factory = context.analyzer_factory` and pack it downward explicitly into the threads triggering `_run_validation`, resulting in a safe parameter transmission directly to the rules.

#### [MODIFY] `C09TraceabilityRule` (file:///C:/development/pitbula/specweaver/src/specweaver/assurance/validation/rules/code/c09_traceability.py)
- **Change:** Purge `from specweaver.workspace.analyzers.factory import AnalyzerFactory`.
- **Change:** Abstract `_find_and_parse_tests()` to extract the implementation from `self.context.get("analyzer_factory")`. For unit testing backwards compatibility with no orchestrator, use a fallback mock or dynamically re-require it without global binds.

## Next Steps / Execution Plan
1. Apply the structural `RunContext` upgrades.
2. Unhook the global `dispatcher.py`.
3. Chain the `executor.py` DI flow and upgrade `c09_traceability.py`.
4. Validate these steps passing without breaking backwards integration testing.

## Open Questions
- Should `ToolDispatcher` strictly fail execution if `analyzer_factory` is structurally missing, or gracefully degrade, ignoring file-exclusion optimization? (Fallback pattern suggested to preserve pure unit test resilience.)
