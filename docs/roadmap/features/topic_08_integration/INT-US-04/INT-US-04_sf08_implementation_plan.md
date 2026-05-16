# Implementation Plan: Context-Aware Flow Orchestration Integration [SF-08: Configurable Prompt Render Profiles Integration]
- **Feature ID**: INT-US-04
- **Sub-Feature**: SF-08 — Configurable Prompt Render Profiles Integration
- **Design Document**: docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-08
- **Implementation Plan**: docs/roadmap/features/topic_08_integration/INT-US-04/INT-US-04_sf08_implementation_plan.md
- **Status**: DRAFT (Hardened — RT/BT Rounds 1–5, 39 findings resolved)
- **Commit Boundary**: Single atomic commit (RT-10)
- **Dependency Note**: SF-01 dependency is inherited from the design doc's blanket structure but is **functionally vacuous** — SF-08 requires zero DB interactions and can be implemented independently (RT-08).

## Goal Description

Integrating the C-INTL-05 `RenderProfile` capabilities into the pipeline orchestration layer via Step Parameter Injection and a `ProfileRegistry`.
This allows pipeline authors to dynamically override the prompt slots generated for specific handlers (e.g., using `MINIMAL` instead of `FULL` to save tokens) directly from the `pipeline.yaml`.

### Usage Example (RT-18)

```yaml
steps:
  - name: decompose_feature
    action: decompose
    target: feature
    params:
      feature_name: "auth_module"
      render_profile: "MINIMAL"   # Override default profile for this step
```

## Functional Requirements
*   **FR-1**: Expose `render_profile` dynamically in `PipelineStep.params`.
*   **FR-2**: Provide a `ProfileRegistry` mapping string identifiers (e.g., `"MINIMAL"`) to `RenderProfile` objects.
*   **FR-3**: Update all handlers that call `_build_base_prompt` to resolve dynamic profiles before fallback to their handler-specific default.

## Non-Functional Requirements (RT-07)
*   **NFR-1 (Performance)**: `resolve_profile` must be a pure O(1) dictionary lookup. No DB, no I/O.
*   **NFR-2 (Backward Compatibility)**: All existing pipeline YAML files must continue to work without modification. Zero `render_profile` param = handler's existing default behavior.
*   **NFR-3 (Test Stability)**: All existing tests in `test_profiles.py` and `test_build_base_prompt_profiles.py` must pass without modification.
*   **NFR-4 (API Stability)**: The `_build_base_prompt(profile=RenderProfile)` signature remains backward compatible. Direct `RenderProfile` object passing is unaffected (RT-24).
*   **NFR-5 (Performance — Inherited)**: Profiles that exclude `AGENT_MEMORY` (MINIMAL, ARBITER) also skip the memory hydration DB query in `_build_base_prompt`, providing a latency benefit beyond token savings (RT-36).

## Architectural Decisions
*   **AD-1 (Phase 4 Resolution)**: `ProfileRegistry` Placement. The registry will be built inside `core.flow.handlers._profiles.py` (where `FULL` and `MINIMAL` are already defined) to strictly preserve the Mechanism vs Policy DDD boundary. `infrastructure.llm` will continue to provide the domain-agnostic `RenderProfile` mechanism.
*   **AD-2 (Phase 4 Resolution)**: `PipelineStep` YAML Schema. We will rely on dynamic `step.params.get("render_profile")` rather than extending the core `PipelineStep` Pydantic model with LLM-specific fields, preventing domain leakage into the generic pipeline runner.
*   **AD-3 (Phase 4 Resolution)**: Error Handling. The `ProfileRegistry` will fail-fast with a `ValueError` if a non-existent profile string is requested via YAML, preventing silent misconfigurations.
*   **AD-4 (RT-01 Resolution — Injection Point)**: Profile resolution happens in each **concrete handler's `execute()` method**, NOT inside `_build_base_prompt()`. Each handler calls `resolve_profile(step.params.get("render_profile"), default=<HANDLER_DEFAULT>)` before passing the result to `_build_base_prompt(profile=resolved)`. The `_build_base_prompt` function signature is unchanged.
*   **AD-5 (RT-11 Resolution — `_profiles.py` Cohesion)**: `_profiles.py` remains a pure-policy declarative module with NO engine imports. `resolve_profile()` accepts a `str | None` name, not a `PipelineStep` — the `step.params.get()` extraction stays in each handler.
*   **AD-6 (RT-34 Resolution — Error Containment)**: Each handler wraps the `resolve_profile()` call in a `try/except ValueError` and returns `_error_result(str(e), started)` instead of letting the exception propagate to the runner. This prevents retry loops on gated steps with invalid profiles.

## Handler-Specific Default Table (RT-02)

Each handler retains its existing static default profile. The `resolve_profile` `default` argument MUST match the handler's current hardcoded profile:

| Handler | File | Current Profile | `default=` arg |
|---------|------|----------------|---------------|
| `GenerateCodeHandler` | `generation.py` | `FULL` | `FULL` |
| `GenerateTestsHandler` | `generation.py` | `FULL` | `FULL` |
| `PlanSpecHandler` | `generation.py` | `FULL` | `FULL` |
| `ReviewSpecHandler` | `review.py` | `FULL` | `FULL` |
| `ReviewCodeHandler` | `review.py` | `FULL` | `FULL` |
| `DraftSpecHandler` | `draft.py` | `INTERACTIVE` | `INTERACTIVE` |
| `DecomposeFeatureHandler` | `decompose.py` | `MINIMAL` | `MINIMAL` |
| `ArbitrateVerdictHandler` | `arbiter.py` | `ARBITER` | `ARBITER` |

## Scope Boundary (RT-20)

`render_profile` ONLY applies to the 8 handlers listed above — those that call `_build_base_prompt`. The following handlers do NOT use `_build_base_prompt` and will **silently ignore** any `render_profile` param:

`ValidateSpecHandler`, `ValidateCodeHandler`, `ValidateTestsHandler`, `LintFixHandler`, `EnrichStandardsHandler`, `GenerateScenarioHandler`, `ConvertScenarioHandler`, `ArbitrateDualPipelineHandler`, `DriftCheckHandler`

## Proposed Changes

### `core/flow/handlers/_profiles.py`
Summary: Add the Profile Registry and resolver function. The file remains a pure-policy declarative module with no engine imports (AD-5).
#### [MODIFY] _profiles.py
- Add `from types import MappingProxyType` (immutable registry — matches `frozen=True` on `RenderProfile`, RT-03).
- Export a new `PROFILE_REGISTRY: MappingProxyType[str, RenderProfile]` dictionary mapping `"FULL"`, `"MINIMAL"`, `"INTERACTIVE"`, `"ARBITER"` to their respective `RenderProfile` objects.
- Create a helper function `resolve_profile(name: str | None, default: RenderProfile) -> RenderProfile`:
    1. If `name` is `None` or empty/whitespace-only → return `default` (RT-14).
    2. If `name` is not a `str` → raise `ValueError` with type info (RT-22 — YAML type coercion: `true` → bool, `42` → int).
    3. Normalize: `normalized = name.strip().upper()` (RT-04 — case-insensitive).
    4. If `normalized` is in `PROFILE_REGISTRY` → log `logger.info("Profile override: '%s' → %s", name, ...)` (RT-21) and return the mapped profile.
    5. If not found → raise `ValueError(f"Unknown render profile '{name}'. Valid profiles: {sorted(PROFILE_REGISTRY.keys())}")` (AD-3 Fail-Fast).
- Update module docstring to document new exports (RT-26).

### `core/flow/handlers/generation.py`
Summary: Update 3 call sites to resolve profile dynamically from `step.params`.
#### [MODIFY] generation.py
At each of the 3 call sites (`GenerateCodeHandler`, `GenerateTestsHandler`, `PlanSpecHandler`), add the following **before** the `_build_base_prompt` call:

```python
from specweaver.core.flow.handlers._profiles import FULL, resolve_profile

try:
    profile = resolve_profile(step.params.get("render_profile"), default=FULL)
except ValueError as e:
    return _error_result(str(e), started)

base_prompt = await _build_base_prompt(context, INSTRUCTIONS, profile=profile, ...)
```

Replace the existing `from specweaver.core.flow.handlers._profiles import FULL` line at each call site.

### `core/flow/handlers/review.py`
Summary: Update 2 call sites (`ReviewSpecHandler`, `ReviewCodeHandler`).
#### [MODIFY] review.py
Same pattern as `generation.py`, using `default=FULL`.

### `core/flow/handlers/draft.py`
Summary: Update 1 call site (`DraftSpecHandler`).
#### [MODIFY] draft.py
Same pattern, using `default=INTERACTIVE`.

### `core/flow/handlers/decompose.py`
Summary: Update 1 call site (`DecomposeFeatureHandler`).
#### [MODIFY] decompose.py
Same pattern, using `default=MINIMAL`.

### `core/flow/handlers/arbiter.py`
Summary: Update 1 call site (`ArbitrateVerdictHandler`).
#### [MODIFY] arbiter.py
Same pattern, using `default=ARBITER`.

### Documentation
Summary: Document YAML parameter injection for pipeline authors and developers.
#### [NEW] docs/user_guides/8_prompt_render_profiles.md (RT-05)
- Explain the concept of prompt render profiles.
- Document how to pass `render_profile: "MINIMAL"` inside a step's `params` block.
- Document that profile names are case-insensitive.
- Include the list of available profiles with a brief description.
- Document which handlers support `render_profile` and which ignore it (Scope Boundary).
- Document that `render_profile` does NOT cascade to child pipelines in fan-out/dual-pipeline orchestrations (RT-28).
- Note the distinction between "render profiles" (prompt verbosity) and "execution profiles" (pipeline configuration) (RT-30).

#### [MODIFY] docs/dev_guides/adding_prompt_slots.md (RT-16)
- Add "Step 2b: Register in the Profile Registry" — when adding a new profile, register it in `PROFILE_REGISTRY`.
- Add note: when adding a new `PromptSlot`, also add it to `_STANDARD_ORDER` in `_profiles.py`.

## Verification Plan

### Automated Tests

**Test location** (RT-15):
- Registry unit tests → add to `tests/unit/core/flow/handlers/test_profiles.py`
- Handler integration tests → add to `tests/unit/core/flow/handlers/test_build_base_prompt_profiles.py`

**Test cases:**

1. **Backward-compat (RT-06 — HIGHEST PRIORITY)**: `params={}` (no `render_profile` key) → each handler uses its static default profile. `GenerateCodeHandler` → `FULL`, `DecomposeFeatureHandler` → `MINIMAL`, `DraftSpecHandler` → `INTERACTIVE`, `ArbitrateVerdictHandler` → `ARBITER`.
2. **Happy path**: `params={"render_profile": "MINIMAL"}` → resolves to `MINIMAL` profile inside the prompt builder.
3. **Case insensitivity (RT-04)**: `params={"render_profile": "minimal"}` → resolves to `MINIMAL`.
4. **Fail-fast (AD-3)**: `params={"render_profile": "INVALID_TYPO"}` → handler returns `StepResult(status=ERROR)` with descriptive message. Does NOT raise.
5. **Empty string (RT-14)**: `params={"render_profile": ""}` → falls back to handler default.
6. **Type coercion (RT-22)**: `params={"render_profile": True}` → handler returns `StepResult(status=ERROR)` with type error message.
7. **Registry immutability (RT-03)**: `PROFILE_REGISTRY["CUSTOM"] = ...` → raises `TypeError`.
8. **Existing tests green (NFR-3)**: Full suite `pytest tests/unit/core/flow/handlers/ -v` passes without modification.

### Manual Verification
- Execute `sw run` on a pipeline yaml containing `render_profile` overrides and verify via `--verbose` that the omitted slots (e.g. `CONSTITUTION`) do not appear in the prompt payloads sent to the LLM.

---

## Profile Compatibility Matrix (RT-19, RT-27)

> **WARNING**: Profile overrides affect ALL `add_*` calls on the PromptBuilder — including those made by downstream workflow modules (`Generator.generate_code()`, `Reviewer.review_spec()`, etc.). A profile that excludes `FILE` will cause the reviewer to never see the spec it's reviewing.

| Profile | INSTRUCTIONS | FILE | CONTEXT | TOPOLOGY | PLAN | CONSTITUTION | STANDARDS | MEMORY | DICTATOR | Safe For |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|---------|
| **FULL** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All handlers |
| **INTERACTIVE** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | Draft, Generate, Review |
| **MINIMAL** | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Decompose, Plan ONLY |
| **ARBITER** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Arbitrate ONLY |

> **CAUTION**: Using `MINIMAL` or `ARBITER` on `GenerateCodeHandler` or `ReviewSpecHandler` will silently drop the spec file, plan, and dictator overrides from the prompt. This will produce degraded or hallucinated LLM output.

---

## Known Limitations & Future Work (Tier 2 — RT/BT audit)

| ID | Category | Description |
|----|----------|-------------|
| RT-09 | Error type | `ValueError` is generic; a custom `ProfileResolutionError` subclass would improve programmatic handling. |
| RT-13 | Security | Profile overrides can remove safety-critical slots (`CONSTITUTION`, `DICTATOR_OVERRIDES`). A future allow-list mechanism per handler could mitigate this. |
| RT-17 | Testing | No integration/E2E test is specified. A PipelineRunner-level test with mock handlers would catch wiring issues. |
| RT-28 | Propagation | `render_profile` does NOT cascade to child pipelines in fan-out/dual-pipeline orchestrations. Each child step must declare it individually. |
| RT-29 | SF-09 compat | The static `MappingProxyType` registry may need a `ProfileResolver` protocol for DSPy-style dynamic profile generation. The `resolve_profile()` function signature is already compatible. |
| RT-31 | Telemetry | The telemetry schema does not track which profile was used. Relevant for SF-09 performance analysis. |
| RT-32 | Serialization | `RenderProfile` is a frozen dataclass, not JSON-serializable. External interfaces should use the profile name string. |
| RT-37 | Pattern | `_build_base_prompt` uses pre-flight profile checks only for expensive operations (DB) while relying on PromptBuilder gating for cheap operations (string formatting). This is correct but undocumented. |

---

## Post-Approval Housekeeping (RT-25)

- Update `INT-US-04_design.md` Progress Tracker: SF-08 row, "Impl Plan" column → ✅
- Update `INT-US-04_design.md` Session Handoff to: "Run `/dev` for SF-08 implementation"

---

## Final Consistency Check (Phase 5 — Revised per RT-33)

**5.1. Open questions:**
All decisions are resolved and documented inline in the plan based on the Phase 4 resolutions and the 5-round RT/BT audit (39 findings, 16 Tier-1 merged, 23 Tier-2 documented).
*Agent Handoff Risk*: Low — mitigated by explicit handler-default table, complete file inventory (6 production files), scope boundary documentation, profile compatibility matrix, and concrete code patterns for each handler.

**5.2. Architecture and future compatibility:**
The plan respects all `context.yaml` boundaries. `_profiles.py` remains a pure-policy module with no engine imports (AD-5). `core.flow.handlers` is safely allowed to define workflow policy matrices. No circular dependencies are introduced. Forward compatibility with SF-09 is acknowledged (RT-29).

**5.3. Internal consistency:**
The plan is internally consistent. All `[MODIFY]` tags map to existing files. `[NEW]` tags create files following existing conventions. The fallback strategy (Fail-fast) matches the described exception (`ValueError`) caught at the handler level (AD-6). No database migrations are required.
