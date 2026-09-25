# User Handbook 6: AST Surgical Editing & Context Management

Use when: you want to know how agents read and edit large files without loading them whole.

Fixing one function in a 2,000-line `.java` or `.ts` file with `cat` or string replacement costs
two things:

1. **Context window bloat:** the whole file is sent as tokens.
2. **Forgetting:** thousands of lines before a small fix make the LLM lose track of the design.

SpecWeaver edits code through its AST (Abstract Syntax Tree) instead of as text.

## The CodeStructureTool

Tree-sitter parsers cover Python, Java, Kotlin, TypeScript (`.ts`, `.tsx`), Rust, C/C++, Go, SQL,
and Markdown. Plain JavaScript (`.js`) has no parser yet.

### 1. Minimal reads — `read_file_structure`

Agents use `read_file_structure` before a full `read_file`. It returns:

- imports, class structure and function signatures;
- no internal `{...}` bodies.

You see what the file does without paying for the parts you are not editing.

### 2. One symbol — `read_symbol`, `read_symbol_body`

To fix `calculateHash()`:

1. `list_symbols` finds its dot-notation scope, e.g. `CryptoUtils.calculateHash`.
2. `read_symbol` returns just that method.
3. `read_symbol_body` returns only the body. Signature and decorators (e.g. Spring Boot annotations)
   are left out, so the agent cannot reproduce them wrong.

### 3. Splicing — `replace_symbol_body`

`replace_symbol_body` replaces only the inside of a method:

- the method signature is **frozen**;
- decorators and macros are **frozen**;
- the new body is written at the AST byte offsets of the old one.

Spacing and imports outside the body cannot be broken, and there is no "search-and-replace failed"
retry loop.
