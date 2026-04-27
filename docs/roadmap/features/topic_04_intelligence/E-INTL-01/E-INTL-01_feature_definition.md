# E-INTL-01 — LLM Adapter

### LLM Adapter Pattern
```
LLMAdapter (interface)
  ├── generate(prompt, config) → response
  └── supports(capability) → bool

MVP: ONE concrete adapter (Gemini).
Later: Multiple adapters, model routing per task type.
```
Adapter interface defined and used everywhere. Swapping backends = no caller changes.
