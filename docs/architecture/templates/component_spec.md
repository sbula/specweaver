# {{ component_name }} — Component Spec

> **Status**: DRAFT
> **Date**: {{ date }}
> **Layer**: Component (L2)
> **Parent Feature**: {{ parent_feature | default("N/A") }}

---

## 1. Purpose

_One paragraph. What this component does and why it exists. If this paragraph contains "and" connecting two unrelated responsibilities, the component needs splitting._

{{ purpose | default("TODO: Describe the single responsibility of this component in one sentence.") }}

---

## 2. Contract

_What this component promises. The public interface — data shapes, invariants, examples._

### 2.1 Data Models

```python
# TODO: Define input/output types with concrete field names, types, and constraints
```

### 2.2 Interface

```python
# TODO: Define public functions/methods with full signatures and return types
```

### 2.3 Validation Rules

- TODO: What constraints are enforced at load time (before runtime)?
- TODO: What inputs are considered invalid?

### 2.4 Examples

**Valid input → expected output:**
```
Input:  TODO
Output: TODO
```

**Invalid input → expected behavior:**
```
Input:  TODO
Result: TODO (exception type, error message)
```

---

## 3. Protocol

_What steps happen at runtime, and in what order._

### 3.1 Execution Sequence

1. TODO: Step 1
2. TODO: Step 2
3. TODO: Step 3

### 3.2 State Transitions

_If this component has states (e.g., IDLE → PROCESSING → DONE), define the transitions and their triggers here. Omit if stateless._

### 3.3 Integration Points

- **Depends on**: TODO (list components this one calls, by interface name)
- **Called by**: TODO (list components that call this one)

---

## 4. Policy

_Configurable constraints and tunable parameters that alter behavior without code changes._

### 4.1 Configuration

```yaml
# .specweaver/config.yaml (or equivalent)
# TODO: Define configurable parameters with defaults
```

### 4.2 Error Handling

| Error Condition | Behavior | Configurable? |
|:---|:---|:---|
| TODO: condition 1 | TODO: what happens | Yes/No |
| TODO: condition 2 | TODO: what happens | Yes/No |

### 4.3 Limits & Thresholds

| Parameter | Default | Range | Rationale |
|:---|:---|:---|:---|
| TODO | TODO | TODO | TODO |

---

## 5. Boundaries

_What this component does NOT do. This is the most important section — it prevents scope creep._

### 5.1 Explicitly NOT This Component's Responsibility

| Concern | Owned By | Why Not Here |
|:---|:---|:---|
| TODO: concern 1 | TODO: which component | TODO: rationale |
| TODO: concern 2 | TODO: which component | TODO: rationale |

### 5.2 Future Considerations

_Ideas that might belong to this component in the future, but are explicitly OUT OF SCOPE for the current version._

- TODO: Future idea 1
- TODO: Future idea 2

---

## Done Definition

_Unambiguous, verifiable completion criteria._

- [ ] All public methods have unit tests
- [ ] All examples from §2.4 pass as test cases
- [ ] All error cases from §4.2 have test coverage
- [ ] Coverage ≥ 70% for this component's source files
- [ ] `sw check --level=component` passes on this spec
- [ ] TODO: additional acceptance criteria
