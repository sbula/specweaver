# {{ component_name }} - Component Spec

> **Status**: DRAFT
> **Date**: {{ date }}
> **Layer**: Component (L2)
> **Parent Feature**: {{ parent_feature | default("N/A") }}

---

## 1. Purpose

_One paragraph. What this component does and why it exists._

{{ purpose | default("TODO: Describe the single responsibility.") }}

---

## 2. Contract

_What this component promises. The public interface._

### 2.1 Data Models

```python
# TODO: Define input/output types
```

### 2.2 Interface

```python
# TODO: Define public functions/methods
```

### 2.3 Examples

**Valid input -> expected output:**
```
Input:  TODO
Output: TODO
```

---

## 3. Protocol

_What steps happen at runtime, and in what order._

1. TODO: Step 1
2. TODO: Step 2

---

## 4. Policy

_Configurable constraints and error handling._

### 4.1 Error Handling

| Error Condition | Behavior |
|:---|:---|
| TODO | TODO |

---

## 5. Boundaries

_What this component does NOT do._

| Concern | Owned By |
|:---|:---|
| TODO | TODO |

---

## Done Definition

- [ ] All public methods have unit tests
- [ ] Coverage >= 70%
- [ ] `sw check --level=component` passes
