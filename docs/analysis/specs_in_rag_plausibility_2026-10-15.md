# Can retrieval cover specs? A plausibility check (2026-10-15)

Asked while planning `B-FLOW-01` SF-H (FR-20, spec conflicts at review): can the planned retrieval
(`A-SENS-02` vectors, `B-FLOW-04` hybrid RAG) find related **specs**, not only code?

## Measured

`chunk_source` (`B-SENS-03`, built) with the built `MarkdownCodeStructure` parser, on
`B-FLOW-01_design.md` (33,350 characters):

| | |
|---|---|
| chunks | 31 |
| named by their heading path (`symbol` or `symbols`) | 29 |
| oversized sections | split into numbered parts (e.g. the FR table, 1/2 and 2/2) |
| unnamed | 2: the text before the first `##`, and a section that opens with a code block |

## Reading

- Specs can be chunked for a vector store today, with no new code; the two unnamed chunks are a
  gap to close in whichever capability first indexes specs.
- `A-SENS-02` and `B-FLOW-04` are unbuilt and have no design. `B-FLOW-04`'s entry named only code;
  it now names specs as well, so its design starts from this.
- `ADR-006` allows it: vectors nominate specs to read; the reviewer reads the real text and decides.
- Contracts are source files, already in the chunker's scope.
