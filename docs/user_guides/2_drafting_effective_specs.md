# User Handbook 2: Drafting Effective Specs

Use when: writing or checking a component spec before code generation.

SpecWeaver follows **Specification-Driven Development**: code is generated from the spec, so a flawed
spec gives broken code.

## 1. The 6-Section L3 Component Spec Structure

`sw check` assesses every component spec against a 6-section template, using static regex
thresholds and LLM-based semantic checks.

1. **Purpose:** The objective of the file. (Must pass S01 One-Sentence Test)
2. **Contract:** External interactions and class shapes. (Must pass S06 Concrete Example)
3. **Protocol:** How communication occurs across the boundary.
4. **Policy:** Business logic configurations, mappings, or restrictions.
5. **Boundaries/Errors:** Known constraints, failure states. (Must pass S09 Error Path)
6. **Safety/DAL:** Risk assignment determining validation thresholds.

## 2. Interactive LLM Co-Authoring (`sw draft`)

Let SpecWeaver ask the questions instead of writing the spec by hand.

```bash
sw draft greet_service --project ./my-app
```

The agent asks about inputs and context until all 6 sections are filled.

**One command, whole loop (INT-US-02):** after co-authoring, `sw draft` runs the S-rule validation
battery and the LLM semantic review in the same command.

- Reviewer rejects → SpecWeaver re-drafts with the reviewer's findings injected (at most 2 retries),
  then shows the findings and exits non-zero.
- The outcome report shows the spec path, rules passed and the review verdict.
- A freshly drafted spec needs no manual `sw check`. Use `sw check` to re-validate specs you edit.

## 3. Quality Check (`sw check`)

An implementation pipeline runs only on a spec that passes these checks.

**Component level (strict)** — for implementation specs:

```bash
sw check specs/greet_service_spec.md --level component
```

| Fails when | Rule |
|---|---|
| Weasel words like *maybe, should, potentially* | S08, S11 |
| Abstraction boundaries leak | S03 |
| The work looks bigger than 1 day | S05 |

**Feature level (lenient)** — for high-level L2 architecture planning:

```bash
sw check specs/onboarding-feature.md --level feature
```

## 4. Lineage Tracking via `%traces`

When `sw implement` generates code, it tags the tests with the capability they trace to.
If you delete an implementation file without updating its `.md` parent trace, the AST drift check
blocks repository commits and reports the project architecture as out of phase.
