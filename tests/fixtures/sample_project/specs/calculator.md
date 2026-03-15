# Calculator Service Spec

> **Status**: VALIDATED
> **Date**: 2026-03-15
> **Layer**: Component (L2)
> **Parent Feature**: Core Utilities

---

## 1. Purpose

The Calculator Service provides basic arithmetic operations with input validation
and error handling. Used as an integration test fixture.

---

## 2. Contract

### 2.1 Data Models

```python
class CalcResult(BaseModel):
    value: float
    operation: str
```

### 2.2 Interface

```python
def calculate(a: float, b: float, op: str) -> CalcResult:
    """Perform an arithmetic operation."""
```

### 2.3 Examples

**Valid input -> expected output:**
```python
calculate(2.0, 3.0, "add")      # -> CalcResult(value=5.0, operation="add")
calculate(10.0, 4.0, "subtract") # -> CalcResult(value=6.0, operation="subtract")
```

**Invalid input -> expected behavior:**
```python
calculate(1.0, 0.0, "divide")   # raises ZeroDivisionError
calculate(1.0, 2.0, "modulo")   # raises ValueError("Unsupported operation")
```

---

## 3. Protocol

1. Validate that `op` is one of: "add", "subtract", "multiply", "divide".
2. If `op` is "divide" and `b` is zero, raise `ZeroDivisionError`.
3. Perform the calculation.
4. Return a `CalcResult` with the value and operation name.

---

## 4. Policy

### 4.1 Error Handling

| Error Condition | Behavior |
|:---|:---|
| Unknown operation | Raise `ValueError` with message listing valid operations |
| Division by zero | Raise `ZeroDivisionError` with descriptive message |

### 4.2 Limits

| Parameter | Default | Range |
|:---|:---|:---|
| Input values | - | IEEE 754 float range |
| Operations | 4 | add, subtract, multiply, divide |

---

## 5. Boundaries

| Concern | Owned By |
|:---|:---|
| Input parsing | CLI layer |
| Result formatting | Display layer |

---

## Done Definition

- [ ] All public methods have unit tests
- [ ] Examples from 2.3 pass as test cases
- [ ] Error cases from 4.1 have test coverage
- [ ] Coverage >= 70%
- [ ] `sw check --level=component` passes
