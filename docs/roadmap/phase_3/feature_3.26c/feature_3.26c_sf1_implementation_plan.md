# Implementation Plan: Interactive Gate Variables [SF-1: Interactive Gate Variables]
- **Feature ID**: 3.26c
- **Sub-Feature**: SF-1 — Interactive Gate Variables
- **Design Document**: docs/roadmap/phase_3/feature_3.26c/feature_3.26c_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.26c/feature_3.26c_sf1_implementation_plan.md
- **Status**: COMPLETE

## 1. Scope & Objective

SF-1 extends the SpecWeaver flow engine and `PromptBuilder` to dynamically isolate and inject HITL rejection remarks. The primary objective is to grant human feedback strict promotional priority (Priority 0) over generalized lint failures during the loop-back mechanism, bypassing standard prompt truncations by placing the feedback inside a `<dictator-overrides>` boundary.

## 2. Approach

Based on the Phase 0 technical research, this plan modifies three domain-isolated components seamlessly:

1. **`PromptBuilder` Component updates (`llm` Adapter Layer)**
   - Expose a new method `.add_dictator_overrides(overrides: list[str])` appending an internal XML block with `priority=0`.
   - Update `_prompt_render` configurations (`ordered_tags`) to inject `<dictator-overrides>` immediately after `<instructions>`.

2. **Flow Handlers Update**
   - Update `GenerateCodeHandler` within `src/specweaver/core/flow/_generation.py`. Inspect `context.feedback.get(step_name, {})`. 
   - Parse `hitl_verdict` and cleanly extract `remarks`.
   - Similarly parse generalized `results` objects for automated lint failures to place as `priority=2` warnings.

3. **Generator Protocol Bridge**
   - Modify `Generator.generate_code` mapping (`src/specweaver/workflows/implementation/generator.py`) to accept optional `dictator_overrides` strings and `automated_findings` generic errors, bridging the state machine payload to the LLM construction mechanism.

## 3. Code Modifications

### 3.1. `src/specweaver/infrastructure/llm/prompt_builder.py`
- **Method Add**: `add_dictator_overrides(self, overrides: list[str]) -> PromptBuilder`
  - Implementation detail:
    ```python
    if not overrides: return self
    lines = [f"- {o}" for o in overrides]
    text_block = "\n".join(lines)
    self._blocks.append(_ContentBlock(
        text=text_block,
        priority=0,
        kind="dictator-overrides",
        label="dictator-overrides",
        tokens=self._count(text_block)
    ))
    return self
    ```

### 3.2. `src/specweaver/infrastructure/llm/_prompt_render.py`
- **Variable Modify**: `ordered_tags` list.
  - Insert `"dictator-overrides"` immediately following `"instructions"`. This handles all internal string formatting cleanly by leveraging the automated section loop.

### 3.3. `src/specweaver/workflows/implementation/generator.py`
- **Method Modify**: `Generator.generate_code` & `Generator.generate_tests`
  - Add to signature: `dictator_overrides: list[str] | None = None`, `validation_findings: str | None = None`.
  - Inside the method where `PromptBuilder` is chained:
    ```python
    if dictator_overrides:
        prompt.add_dictator_overrides(dictator_overrides)
    if validation_findings:
        prompt.add_context(validation_findings, "validation_errors", priority=2)
    ```

### 3.4. `src/specweaver/core/flow/_generation.py`
- **Class Modify**: `GenerateCodeHandler` and `GenerateTestsHandler`
  - Inside `execute`, extract loop-back feedback directed to `step.name` and format it unambiguously:
    ```python
    feedback = context.feedback.get(step.name, {}).get("findings", {})
    dictator_overrides: list[str] = []
    
    # 1. Extract specifically human remarks from HITL
    if feedback.get("hitl_verdict") == "reject" and "remarks" in feedback:
        dictator_overrides.append(feedback["remarks"])
        
    # 2. Extract standard validation linters into a formatted string
    validation_lines = []
    for res in feedback.get("results", []):
         if str(res.get("status")).upper() == "FAIL":
             validation_lines.append(f"[{res.get('rule_id')}] {res.get('message')}")
    validation_findings = "\n".join(validation_lines) if validation_lines else None
    
    # 3. Finally consume `context.feedback.pop(step.name, None)` to prevent stale loops.
    context.feedback.pop(step.name, None)
    ```
  - Supply `dictator_overrides` and `validation_findings` to `generator.generate_code()` (or `generate_tests`).

## 4. Test Strategy

1. **Unit Tests** `tests/infrastructure/llm/test_prompt_builder.py`: Validates `#add_dictator_overrides` operates at priority 0.
2. **Integration Tests** `tests/core/flow/test_generation.py`: Supply mocked context feedback dict matching UI CLI behavior to ensure `dictator_overrides` triggers inside the Generation class bridge without raising validation limits.

## 5. Security & Risk Assessment

1. **Tokens Overhead**: `<dictator-overrides>` acts out-of-band on priority 0. Massive blocks of human texts could crowd `max_tokens` limits. Realistically mitigated by manual human entry lengths.
2. **Schema Adherence**: Operates solely with dictionary access defaults cleanly sidestepping any schema mismatch parsing exceptions.

## 6. Research Notes
- `Gates.py` checks for `hitl_verdict`. CLI injects these dict keys directly into the `findings`.
- `_prompt_render.py` automatically parses `ordered_tags` list elements containing dashes, avoiding XML formatting errors natively.

*End Plan Documentation*
