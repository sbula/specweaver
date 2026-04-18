# User Handbook 2: Drafting Effective Specs

Traditional Natural Language prompts result in flaky LLM reasoning. SpecWeaver enforces a strict **Specification-Driven Development** loop. If the spec logic is flawed, your generated source code will break predictably.

## 1. The 6-Section L3 Component Spec Structure
SpecWeaver is bound to a strict 6-section template layout that the `sw check` mathematically assesses utilizing static regex thresholds and contextual semantic NLP.

1. **Purpose:** The objective of the file. (Must pass S01 One-Sentence Test)
2. **Contract:** External interactions and class shapes. (Must pass S06 Concrete Example)
3. **Protocol:** How communication occurs across the boundary.
4. **Policy:** Business logic configurations, mappings, or restrictions.
5. **Boundaries/Errors:** Known constraints, failure states. (Must pass S09 Error Path)
6. **Safety/DAL:** Risk assignment determining validation thresholds.

## 2. Interactive LLM Co-Authoring (`sw draft`)
Do not draft complex protocols by hand. Let SpecWeaver iteratively prompt you.
```bash
sw draft greet_service --project ./my-app
```
The agent will recursively ask you contextualizing questions about inputs to fill out the 6-sections safely.

## 3. Strict Quality Control Pipeline (`sw check`)
Before an Implementation pipeline can run, SpecWeaver will execute rigorous tests against your `.md` file.

**Component Level Validation (Strict)** - Used for implementation specs:
```bash
sw check specs/greet_service_spec.md --level component
```
- Will **FAIL** if you use "weasel words" like *maybe, should, potentially* (Rules S08, S11).
- Will **FAIL** if abstraction boundaries leak (Rule S03).
- Will **FAIL** if complexity suggests more than 1 day of physical labor (Rule S05).

**Feature Level Validation (Lenient)** - Used for high-level L2 architectural planning:
```bash
sw check specs/onboarding-feature.md --level feature
```

## 4. Lineage Tracking via `%traces`
When code is finally generated via `sw implement`, SpecWeaver physically assigns semantic tags across all tests asserting what capability trace it belongs to.
If you manually delete an implementation file without updating its `.md` parent trace, the Ast Drift component will block repository commits automatically indicating the project architecture is out of phase!
