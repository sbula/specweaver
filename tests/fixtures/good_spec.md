# Sample Component Spec - Greeter Service

> **Status**: VALIDATED
> **Date**: 2026-03-08
> **Layer**: Component (L2)
> **Parent Feature**: User Onboarding

---

## 1. Purpose

The Greeter Service generates personalized welcome messages for new users based on their profile data.

---

## 2. Contract

### 2.1 Data Models

```python
class UserProfile(BaseModel):
    name: str
    locale: str = "en"

class Greeting(BaseModel):
    message: str
    locale: str
```

### 2.2 Interface

```python
def greet(profile: UserProfile) -> Greeting:
    """Generate a personalized greeting."""
```

### 2.3 Examples

**Valid input -> expected output:**
```python
greet(UserProfile(name="Alice", locale="en"))
# -> Greeting(message="Welcome, Alice!", locale="en")

greet(UserProfile(name="Bob", locale="de"))
# -> Greeting(message="Willkommen, Bob!", locale="de")
```

**Invalid input -> expected behavior:**
```python
greet(UserProfile(name="", locale="en"))
# raises ValueError("Name must not be empty")
```

---

## 3. Protocol

1. Validate the input profile (name must not be empty).
2. Look up the greeting template for the given locale.
3. If locale is not supported, fall back to "en".
4. Render the template with the user's name.
5. Return the Greeting object.

---

## 4. Policy

### 4.1 Error Handling

| Error Condition | Behavior |
|:---|:---|
| Empty name | Raise `ValueError` with message "Name must not be empty" |
| Unsupported locale | Fall back to "en" locale, log a warning |
| Template rendering failure | Raise `TemplateError` with the original exception |

### 4.2 Limits

| Parameter | Default | Range |
|:---|:---|:---|
| Max name length | 100 | 1-500 |
| Supported locales | en, de, fr, es | Configurable |

---

## 5. Boundaries

| Concern | Owned By |
|:---|:---|
| User authentication | AuthService |
| Locale detection | LocaleDetector |
| Message persistence | MessageStore |

---

## Done Definition

- [ ] All public methods have unit tests
- [ ] Examples from 2.3 pass as test cases
- [ ] Error cases from 4.1 have test coverage
- [ ] Coverage >= 70%
- [ ] `sw check --level=component` passes
