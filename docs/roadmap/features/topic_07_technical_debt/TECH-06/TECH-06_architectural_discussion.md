# ARCHITECTURAL DISCUSSION: Domain Models vs. Prompt Adapters (TECH-06 SF-2)

This document outlines the architectural trade-offs, options, and proposals regarding pluggable context sources, domain models, and prompt adapters.

---

## 1. Domain Models vs. Prompt Adapters

### Question
Should the domain model (e.g., `TopologyContext`) natively implement the prompt protocol (`get_prompt_content()` and `get_prompt_label()`), or should we use separate wrapper adapters in the LLM package?

### Option A: Native Conformance (Combined)
* **Description**: `TopologyContext` in `assurance/graph/topology.py` directly implements the `PromptContentSource` protocol.
* **Pros**:
  * **Zero Boilerplate**: No need to write, import, or instantiate separate wrapper classes.
  * **Simplicity**: Fewer files to manage and maintain in the codebase.
* **Cons**:
  * **Layer Pollution**: The domain layer contains presentation-specific formatting logic (e.g., formatting context lists as bullet points) tailored for LLM consumption.
* **Impact**: Low. Since `TopologyContext` is already a prompt-oriented DTO rather than a pure mathematical domain entity, formatting it here is highly pragmatic.

### Option B: Separate Domain Model & LLM Adapter
* **Description**: `TopologyContext` remains a pure data container. We define a `TopologyPromptAdapter` wrapper inside `llm/prompt/adapter/topology.py` that implements the protocol.
* **Pros**:
  * **Hexagonal Separation**: The domain layer has zero knowledge of how it is presented to an LLM.
  * **Flexibility**: Different adapters can format the same domain object differently depending on the LLM profile.
* **Cons**:
  * **Indirection**: Callers must wrap the domain object before passing it, or the builder must map it.
  * **More Boilerplate**: Requires creating and maintaining separate adapter modules.

### Proposal
* **Rule**:
  * If a domain class is already a prompt-specific DTO (like `TopologyContext`), let it **natively conform** (Option A).
  * If the class is a core business entity (like a `Specification` or `CodeLineage` model), keep it pure and use a **separate adapter** (Option B) under `llm/prompt/adapter/`.

---

## 2. Generalizing Input Adapters (Strings, Files, Metadata)

### Question
Would it be useful or desirable to have adapters for plain strings, files, and metadata so that the `PromptBuilder` handles everything as a unified list of `PromptContentSource` objects?

### Option A: Fully Unified Pipeline (Internal Adapters)
* **Description**: The public API remains clean (`add_file`, `add_context`, etc.), but internally the builder wraps these inputs in:
  - `StringPromptSource`
  - `FilePromptSource`
  - `MetadataPromptSource`
* **Pros**:
  * **Polymorphic Rendering**: The rendering engine in `render.py` doesn't need complex `if/else` checks by kind; it simply calls the source methods.
  * **Refactoring Cleanliness**: Core logic is highly cohesive and easy to test.
* **Cons**:
  * **Metadata Loss**: File blocks need custom metadata (e.g., `language`, `role`, and `file_path`) to render XML attributes correctly. A generic protocol would need to support these or fall back to type-checking.

### Proposal
Keep the public API simple and convenient for developers. Internally, we can wrap raw string, file, and metadata blocks in class objects that implement `PromptContentSource` while retaining their specific attributes.

---

## Comments / Feedback

1. **User (Selection: Generalizing Input Adapters)**: 
   > "that is what the adapters are: the single place to handle a specific input and transform it to the exact output we can use 1:1 as input for the prompt builder! the API will select the correct adapter!!!"
   * **Resolution**: Consolidated all input adapters (`StringPromptAdapter`, `FilePromptAdapter`, `ProjectMetadataPromptAdapter`) and the selection factory `get_prompt_adapter()` into `src/specweaver/infrastructure/llm/prompt/adapter.py`. The adapters handle parsing and XML wrapping themselves, and the prompt builder uses the factory API to dynamically select the adapter.

2. **User (Selection: Rule for Native Conformance vs. Adapters)**:
   > "I am not happy with this one but still it seems to be better than the other one...."
   * **Resolution**: Keep `TopologyContext` natively conforming (Option A) to avoid circular boundary violations, but do not import LLM modules. Core domain classes will use Option B (adapters) to keep the domain clean.

3. **User (Selection: Option B for Builder API + Attribute/Semantic Injection)**:
   > "1.) option b is much more flexible and allows to be extending to more adapters easely. still, just trusting the label to decide is probably not the most secure way here. ahould we do some analysis / grepping the content? over kill?? any other ideas? we need to discuss this further
   > 2.) depends on decision from 1.)  we can also introduce one call for each adapter.... also noeeds to be discussed further"
   * **Resolution**:
     * **Mitigate Injection/Spoofing (Point 1)**: Instead of dynamic content scanning/grepping (which impairs performance and is fragile), we enforce:
       1. **XML Attribute Escaping**: Escape all attributes (like `label`, `path`, `language`, and `role`) using `escape_xml_attribute` before rendering. This completely neutralizes XML tag/attribute injection.
       2. **Label Character Validation**: Validate that custom label strings conform to a safe pattern (e.g., alphanumeric, dashes, underscores, dots, and slashes: `^[a-zA-Z0-9_\-\./]+$`) to prevent weird formatting breaks and spoofing.
       3. **CDATA Escaping**: Wrap string/file content within CDATA blocks to isolate data from system instructions.
     * **Explicit Builder API (Point 2 - Option B)**: Introduce explicit strongly-typed methods on `PromptBuilder` to map directly to each adapter, removing generic runtime type checking:
       * `add_context(source: PromptContentSource, **kwargs)`
       * `add_string_context(content: str, label: str, **kwargs)`
       * `add_file_context(path: Path, label: str = "", **kwargs)`
       * `add_project_metadata_context(metadata: ProjectMetadata, **kwargs)`

4. **Security Auditing (Safe Truncation choice)**:
   * **Question**: How do we ensure that slicing a content block at `char_limit` during dynamic budget truncation does not corrupt the pre-rendered XML markup and CDATA boundaries generated by adapters?
   * **Resolution**: Enhance `PromptContentSource` and the adapters to accept an optional `char_limit` parameter in `get_prompt_content(self, char_limit: int | None = None)`. During truncation, `PromptBuilder` will delegate to the source adapter to slice the raw payload *before* applying escaping and tag wrapping. The final output block is guaranteed to have clean XML/CDATA closing tags, completely preventing tag breakouts due to truncation slicing.


