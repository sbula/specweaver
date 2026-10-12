# E-INTL-01 SF-01 — LLM Adapter: as built

**Design**: [E-INTL-01_design.md](E-INTL-01_design.md)

| File (`src/specweaver/infrastructure/llm/`) | Holds | FRs |
|:---|:---|:---|
| `adapters/base.py` | `LLMAdapter`: `generate`, `generate_stream`, `generate_with_tools`, `count_tokens` | FR-1 |
| `adapters/gemini.py` | `GeminiAdapter` | FR-2 |
| `redaction.py` | masks every known secret in messages and tool results | FR-3 |
