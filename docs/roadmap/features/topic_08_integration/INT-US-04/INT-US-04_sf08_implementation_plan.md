# INT-US-04 SF-08 — Configurable Prompt Render Profiles Integration

**Status**: DELIVERED 2026-05-16 in `e2ac7e6e` (was `DRAFT (Hardened — RT/BT Rounds 1–5, 39 findings
resolved)`; corrected 2026-08-14 — the plan shipped and its `Status:` was never moved) · **FRs
owned**: FR-1, FR-2, FR-3 (SF-08's own) · **Depends on**: SF-01 nominally — **functionally vacuous**,
SF-08 needs zero DB interactions (RT-08) · **Commit boundary**: single atomic commit (RT-10) · Design:
[INT-US-04_design.md](INT-US-04_design.md) §Sub-features → SF-08

## Goal

Integrate C-INTL-05 `RenderProfile` into the pipeline orchestration layer via Step Parameter
Injection and a `ProfileRegistry`. Pipeline authors override the prompt slots for specific handlers
(e.g., `MINIMAL` instead of `FULL` to save tokens) directly from `pipeline.yaml`.

Usage (RT-18):

```yaml
steps:
  - name: decompose_feature
    action: decompose
    target: feature
    params:
      feature_name: "auth_module"
      render_profile: "MINIMAL"   # Override default profile for this step
```

| # | Requirement |
|---|---|
| FR-1 | Expose `render_profile` dynamically in `PipelineStep.params`. |
| FR-2 | Provide a `ProfileRegistry` mapping string identifiers (e.g., `"MINIMAL"`) to `RenderProfile` objects. |
| FR-3 | Update all handlers that call `_build_base_prompt` to resolve dynamic profiles before fallback to their handler-specific default. |
| NFR-1 (Performance) | `resolve_profile` is a pure O(1) dictionary lookup. No DB, no I/O. (RT-07) |
| NFR-2 (Backward Compatibility) | All existing pipeline YAML files work without modification. No `render_profile` param = the handler's existing default. |
| NFR-3 (Test Stability) | All existing tests in `test_profiles.py` and `test_build_base_prompt_profiles.py` pass without modification. |
| NFR-4 (API Stability) | `_build_base_prompt(profile=RenderProfile)` stays backward compatible; direct `RenderProfile` passing is unaffected (RT-24). |
| NFR-5 (Performance — Inherited) | Profiles without `AGENT_MEMORY` (MINIMAL, ARBITER) also skip the memory hydration DB query in `_build_base_prompt` (RT-36). |

## Where it plugs in

Each handler keeps its static default; the `resolve_profile` `default` argument MUST match the
handler's current hardcoded profile (RT-02):

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

Scope boundary (RT-20): `render_profile` applies ONLY to these 8 handlers — those that call
`_build_base_prompt`. These **silently ignore** it: `ValidateSpecHandler`, `ValidateCodeHandler`,
`ValidateTestsHandler`, `LintFixHandler`, `EnrichStandardsHandler`, `GenerateScenarioHandler`,
`ConvertScenarioHandler`, `ArbitrateDualPipelineHandler`, `DriftCheckHandler`.

## Changes

1. **`core/flow/handlers/_profiles.py`** `[MODIFY]` — stays a pure-policy declarative module with no
   engine imports (AD-5).
   - `from types import MappingProxyType` (immutable registry — matches `frozen=True` on
     `RenderProfile`, RT-03).
   - Export `PROFILE_REGISTRY: MappingProxyType[str, RenderProfile]` mapping `"FULL"`, `"MINIMAL"`,
     `"INTERACTIVE"`, `"ARBITER"` to their `RenderProfile` objects.
   - `resolve_profile(name: str | None, default: RenderProfile) -> RenderProfile`:
     1. `name` is `None` or empty/whitespace-only → return `default` (RT-14).
     2. `name` is not a `str` → raise `ValueError` with type info (RT-22 — YAML type coercion:
        `true` → bool, `42` → int).
     3. Normalize: `normalized = name.strip().upper()` (RT-04 — case-insensitive).
     4. `normalized` in `PROFILE_REGISTRY` → log `logger.info("Profile override: '%s' → %s", name, ...)`
        (RT-21) and return the mapped profile.
     5. Not found → raise `ValueError(f"Unknown render profile '{name}'. Valid profiles: {sorted(PROFILE_REGISTRY.keys())}")`
        (AD-3 Fail-Fast).
   - Module docstring documents the new exports (RT-26).
2. **`core/flow/handlers/generation.py`** `[MODIFY]` — 3 call sites (`GenerateCodeHandler`,
   `GenerateTestsHandler`, `PlanSpecHandler`). Before each `_build_base_prompt` call, replacing the
   existing `from specweaver.core.flow.handlers._profiles import FULL` line:

   ```python
   from specweaver.core.flow.handlers._profiles import FULL, resolve_profile

   try:
       profile = resolve_profile(step.params.get("render_profile"), default=FULL)
   except ValueError as e:
       return _error_result(str(e), started)

   base_prompt = await _build_base_prompt(context, INSTRUCTIONS, profile=profile, ...)
   ```

3. Same pattern, `[MODIFY]`: **`core/flow/handlers/review.py`** — 2 call sites (`ReviewSpecHandler`,
   `ReviewCodeHandler`), `default=FULL`; **`core/flow/handlers/draft.py`** — `DraftSpecHandler`, `default=INTERACTIVE`;
   **`core/flow/handlers/decompose.py`** — `DecomposeFeatureHandler`, `default=MINIMAL`; **`core/flow/handlers/arbiter.py`** — `ArbitrateVerdictHandler`, `default=ARBITER`.
4. **`[NEW] docs/user_guides/8_prompt_render_profiles.md`** (RT-05): the concept; passing
   `render_profile: "MINIMAL"` inside a step's `params` block; names are case-insensitive; available
   profiles with a brief description; which handlers support it and which ignore it; no cascade to
   child pipelines in fan-out/dual-pipeline orchestrations (RT-28); "render profiles" (prompt
   verbosity) vs "execution profiles" (pipeline configuration) (RT-30).
5. **`[MODIFY] docs/dev_guides/adding_prompt_slots.md`** (RT-16): "Step 2b: Register in the Profile
   Registry" — a new profile goes into `PROFILE_REGISTRY`; a new `PromptSlot` also goes into
   `_STANDARD_ORDER` in `_profiles.py`.

6 production files. No database migrations.

### Profile compatibility matrix (RT-19, RT-27)

Profile overrides affect ALL `add_*` calls on the PromptBuilder — including downstream workflow
modules (`Generator.generate_code()`, `Reviewer.review_spec()`, etc.). A profile that excludes `FILE`
means the reviewer never sees the spec it reviews.

| Profile | INSTRUCTIONS | FILE | CONTEXT | TOPOLOGY | PLAN | CONSTITUTION | STANDARDS | MEMORY | DICTATOR | Safe For |
|---------|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|---------|
| **FULL** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | All handlers |
| **INTERACTIVE** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | Draft, Generate, Review |
| **MINIMAL** | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | Decompose, Plan ONLY |
| **ARBITER** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | Arbitrate ONLY |

> **CAUTION**: `MINIMAL` or `ARBITER` on `GenerateCodeHandler` or `ReviewSpecHandler` silently drops
> the spec file, plan, and dictator overrides from the prompt — degraded or hallucinated LLM output.

## Tests

Registry unit tests → `tests/unit/core/flow/handlers/test_profiles.py`; handler integration tests →
`tests/unit/core/flow/handlers/test_build_base_prompt_profiles.py` (RT-15).

| # | Case | Input → expected |
|---|---|---|
| 1 | **Backward-compat (RT-06 — HIGHEST PRIORITY)** | `params={}` → each handler's static default (below) |
| 2 | Happy path | `params={"render_profile": "MINIMAL"}` → `MINIMAL` inside the prompt builder |
| 3 | Case insensitivity (RT-04) | `params={"render_profile": "minimal"}` → `MINIMAL` |
| 4 | Fail-fast (AD-3) | `params={"render_profile": "INVALID_TYPO"}` → `StepResult(status=ERROR)` with a descriptive message; does NOT raise |
| 5 | Empty string (RT-14) | `params={"render_profile": ""}` → handler default |
| 6 | Type coercion (RT-22) | `params={"render_profile": True}` → `StepResult(status=ERROR)` with a type error message |
| 7 | Registry immutability (RT-03) | `PROFILE_REGISTRY["CUSTOM"] = ...` → `TypeError` |
| 8 | Existing tests green (NFR-3) | `pytest tests/unit/core/flow/handlers/ -v` passes without modification |

Case 1 defaults: `GenerateCodeHandler` → `FULL`, `DecomposeFeatureHandler` → `MINIMAL`,
`DraftSpecHandler` → `INTERACTIVE`, `ArbitrateVerdictHandler` → `ARBITER`.

Manual: `sw run` on a pipeline yaml with `render_profile` overrides; `--verbose` shows the omitted
slots (e.g. `CONSTITUTION`) absent from the prompt payloads sent to the LLM.

## Decisions (audit)

- **AD-1** — `ProfileRegistry` lives in `core.flow.handlers._profiles.py`, where `FULL` and
  `MINIMAL` are defined. `infrastructure.llm` keeps providing the domain-agnostic `RenderProfile`
  mechanism. *Why:* Mechanism vs Policy DDD boundary.
- **AD-2** — Read `step.params.get("render_profile")`; do not add LLM-specific fields to the
  `PipelineStep` Pydantic model. *Why:* No domain leakage into the generic pipeline runner.
- **AD-3** — The registry fails fast with `ValueError` on an unknown profile string. *Why:* No
  silent misconfiguration.
- **AD-4 (RT-01)** — Resolution happens in each **concrete handler's `execute()`**, NOT inside
  `_build_base_prompt()`: `resolve_profile(step.params.get("render_profile"),
  default=<HANDLER_DEFAULT>)`, then `_build_base_prompt(profile=resolved)`. *Why:*
  `_build_base_prompt`'s signature is unchanged.
- **AD-5 (RT-11)** — `_profiles.py` stays pure-policy with NO engine imports; `resolve_profile()`
  takes a `str | None`, not a `PipelineStep`. *Why:* The `step.params.get()` extraction stays in
  each handler.
- **AD-6 (RT-34)** — Each handler wraps `resolve_profile()` in `try/except ValueError` and returns
  `_error_result(str(e), started)`. *Why:* Prevents retry loops on gated steps with invalid
  profiles.

AD-1..AD-3 were Phase 4 resolutions. The 5-round RT/BT audit raised 39 findings: 16 Tier-1 merged
into this plan, 23 Tier-2 documented; the open ones:

| ID | Category | Description |
|----|----------|-------------|
| RT-09 | Error type | `ValueError` is generic; a custom `ProfileResolutionError` subclass would improve programmatic handling. |
| RT-13 | Security | Profile overrides can remove safety-critical slots (`CONSTITUTION`, `DICTATOR_OVERRIDES`). A per-handler allow-list could mitigate this. |
| RT-17 | Testing | No integration/E2E test is specified. A PipelineRunner-level test with mock handlers would catch wiring issues. |
| RT-28 | Propagation | `render_profile` does NOT cascade to child pipelines in fan-out/dual-pipeline orchestrations. Each child step must declare it. |
| RT-29 | SF-09 compat | The static `MappingProxyType` registry may need a `ProfileResolver` protocol for DSPy-style dynamic profiles; `resolve_profile()`'s signature fits. |
| RT-31 | Telemetry | The telemetry schema does not track which profile was used. Relevant for SF-09 performance analysis. |
| RT-32 | Serialization | `RenderProfile` is a frozen dataclass, not JSON-serializable. External interfaces should use the profile name string. |
| RT-37 | Pattern | `_build_base_prompt` pre-checks the profile only for expensive operations (DB); cheap ones (string formatting) rely on PromptBuilder gating. Correct but undocumented. |

Architecture: respects all `context.yaml` boundaries; `core.flow.handlers` may define workflow policy
matrices; no circular dependencies (RT-33 consistency check).

## As built

Shipped in `e2ac7e6e` (2026-05-16). Evidence and the 50 passing tests are in the design, §Sub-features
→ SF-08. SF-09, which RT-29/RT-31 anticipated, is RETIRED → `B-INTL-10`.
