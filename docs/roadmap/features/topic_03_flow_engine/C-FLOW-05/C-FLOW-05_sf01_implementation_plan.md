# C-FLOW-05 SF-01 — Interactive Gate Variables

**Status**: COMPLETE · **FRs owned**: FR-1, FR-2 (recorded 2026-08-17 under `specweaver-dev` §3.2c,
from `INT-US-04-SF05-MIG`; the plan predates the FR ledger) · **Depends on**: none · **Legacy ID**:
3.26c · Design: [C-FLOW-05_design.md](C-FLOW-05_design.md) §Sub-features → SF-01

Proof and mutants: `tests/unit/infrastructure/llm/test_prompt_builder_overrides.py` (FR-1 — renaming
the `dictator-overrides` slot kills it) and `tests/unit/core/flow/handlers/test_handlers.py` (FR-2 —
collapsing human remarks and automated findings into one stream kills it).

## Goal

Isolate HITL rejection remarks and inject them into loop-back prompts at Priority 0, above lint
failures, inside a `<dictator-overrides>` boundary so standard truncation cannot drop them.

**Since moved** (noted 2026-09-25): `add_dictator_overrides` lives in
`src/specweaver/infrastructure/llm/prompt/adders.py`; the handlers in
`src/specweaver/core/flow/handlers/generation.py`. Paths below are as of the plan.

## Changes

1. **`PromptBuilder`** (`llm` adapter layer) · `src/specweaver/infrastructure/llm/prompt_builder.py` —
   add `add_dictator_overrides(self, overrides: list[str]) -> PromptBuilder`, appending an XML block
   with `priority=0`:
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
2. **Render order** · `src/specweaver/infrastructure/llm/_prompt_render.py` — in `ordered_tags`, insert
   `"dictator-overrides"` right after `"instructions"` (so the section follows `<instructions>`); the
   section loop does the formatting.
3. **Generator bridge** · `src/specweaver/workflows/implementation/generator.py` —
   `Generator.generate_code` & `Generator.generate_tests` gain (the approach called the second one
   `automated_findings`)
   `dictator_overrides: list[str] | None = None`, `validation_findings: str | None = None`. Where the
   `PromptBuilder` is chained:
    ```python
    if dictator_overrides:
        prompt.add_dictator_overrides(dictator_overrides)
    if validation_findings:
        prompt.add_context(validation_findings, "validation_errors", priority=2)
    ```
4. **Handlers** · `src/specweaver/core/flow/_generation.py` — `GenerateCodeHandler` and
   `GenerateTestsHandler`, in `execute`: read `context.feedback.get(step_name, {})`, take `remarks` when
   `hitl_verdict` is reject, format `results` lint failures as `priority=2` warnings, then consume the
   entry so loops do not go stale:
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
   Pass `dictator_overrides` and `validation_findings` to `generator.generate_code()` (or
   `generate_tests`).

Research notes: `Gates.py` checks for `hitl_verdict`; the CLI injects these dict keys directly into
the `findings`. `_prompt_render.py` handles `ordered_tags` elements containing dashes without XML
formatting errors.

## Tests

| Tier | File | Case |
|---|---|---|
| Unit | `tests/infrastructure/llm/test_prompt_builder.py` | `#add_dictator_overrides` operates at priority 0 |
| Integration | `tests/core/flow/test_generation.py` | mocked context feedback dict matching UI CLI behavior → `dictator_overrides` reaches the Generation class bridge without raising validation limits |

## Risks

| Risk | Mitigation |
|---|---|
| **Token overhead**: `<dictator-overrides>` is out-of-band at priority 0; large human texts could crowd `max_tokens` | Human entry lengths are small in practice |
| **Schema adherence** | Dictionary access with defaults only; no schema-mismatch parsing exceptions |
