# What ten languages declare, what the parsers report, and what the graph can hold

**2026-08-25.** A record, not a plan. Every table here was extracted from the tree rather than
recalled, and the extraction command is named beside each one so it can be re-run.

Written because the classifier turned out to read *"declares no supertype"* as *"is not a type"*,
and the question that followed — *does this work for languages that are not object-oriented?* —
turned out to be much larger than the classifier.

---

## 1. The measurement

Every parser holds **two independent lists**: the symbol query naming what it reports, and
`TYPE_DECLARATION_NODES` naming what counts as a type. They were written apart. **Nothing asserts
they agree**, and they have drifted in both directions.

| Language | Declaration nodes reported | Counted as a type | Consequence |
|---|---|---|---|
| **c** | struct, enum, union, function | *(none)* | struct/enum/union → **PROCEDURE** |
| **cpp** | class, struct, enum, union, namespace, function | class, struct | enum/union/namespace → **PROCEDURE** |
| **go** | type_spec, function, method | type_spec | correct |
| **java** | class, interface, enum, method | class, interface | enum → **PROCEDURE** |
| **kotlin** | class, object, function | class | object → **PROCEDURE** |
| **markdown** | section / heading | *(none)* | every heading → **PROCEDURE** |
| **python** | class, function | class | correct |
| **rust** | struct, trait, impl, function | struct, enum, union, trait, impl | **enum/union are types nobody reports** |
| **sql** | table, view, function | *(none)* | table/view → **PROCEDURE** |
| **typescript** | class, function, method, arrow-const | class | **interface / enum / type alias never reported at all** |

Two distinct failures, and Rust proves they are independent:

- **Reported, mis-filed.** C structs, C++ enums and namespaces, Java enums, Kotlin objects, SQL
  tables, markdown headings. A node exists and claims to be a procedure.
- **Never reported.** TypeScript interfaces, enums and type aliases; Rust enums and unions. **No
  node at all** — not wrong, absent. For TypeScript, where interfaces carry most of the contract,
  that is most of the meaning gone.

> Re-run: extract each parser's `SCM_SYMBOL_QUERY` node names and subtract `TYPE_DECLARATION_NODES`.

---

## 2. What the families actually have

Grouping by paradigm shows which concepts the ontology must carry, and which are one family's
private business.

| Concept | Who has it | In the graph today |
|---|---|---|
| **Class** | python, java, kotlin, typescript, cpp | ✅ `DATA_STRUCTURE` |
| **Struct / record** | c, cpp, go, rust, java, kotlin | ⚠️ only go, cpp, rust |
| **Interface / trait** | java, kotlin, typescript, go, rust | ⚠️ typescript missing entirely |
| **Enum** | c, cpp, java, kotlin, typescript, rust | ❌ nowhere correct |
| **Union / sum type** | c, cpp, rust | ❌ |
| **Type alias** | typescript, rust, go | ❌ |
| **Table / view** | sql | ❌ classified as procedure |
| **Function** | every code language | ✅ `PROCEDURE` |
| **Method** | the OO five, go, rust | ✅ `PROCEDURE` |
| **Namespace / package / module** | cpp, java, kotlin, go, python, rust, sql | ❌ `MODULE` reachable in theory, `NAMESPACE` never emitted |
| **Constant / global / field / column** | all of them | ❌ `STATE` exists and is never emitted |
| **Description / doc comment** | every parser defines a comment query | ❌ never read by the graph adapter |

**The paradigm split matters less than expected.** A trait, an interface, a struct, a record and a
table are all *"a named shape other things refer to"* — one concept, five spellings. `DATA_STRUCTURE`
already holds them honestly. The ontology was never object-oriented; the **adapter** is, in its two
strings `class_definition` / `function_definition`.

**Where the split does matter** is composition. Inheritance (python, java, kotlin, ts, cpp),
interface implementation (java, kotlin, ts, rust), structural satisfaction (go — *no syntax at
all*), embedding (go), trait bounds (rust). `EXTENDS` and `IMPLEMENTS` cover the syntactic ones. Go's
implicit interface satisfaction has **no AST expression whatsoever** and can never be a syntactic
edge — it needs type resolution the parsers do not do.

---

## 3. What the ontology can express, and what it reaches

`NodeKind` declares **11** kinds. The mapper can emit **5**.

| Reachable | Dead |
|---|---|
| `FILE` · `MODULE` · `DATA_STRUCTURE` · `PROCEDURE` · `GHOST` | `SYSTEM` · `MICROSERVICE` · `NAMESPACE` · `STATE` · `API_CONTRACT` · `MESSAGE_QUEUE` |

`EdgeKind` declares **9**. Five are emitted — `CONTAINS`, `IMPORTS`, `CALLS`, `EXTENDS`,
`IMPLEMENTS`. Four are not: `CONSUMES`, `FULFILLS`, `PUBLISHES`, `SUBSCRIBES`, which `ADR-006`
assigns to `B-SENS-08`.

So **six node kinds and four edge kinds are vocabulary with no writer.** That is not automatically
waste — `ADR-006` names owners for the four edges — but nothing owns `STATE` or `NAMESPACE`, and
both name concepts every language in the list has.

---

## 4. What is lost between the parser and the store

Three losses compound, and each was found separately:

1. **Classification** — the two-list drift above.
2. **Identity.** `graph_nodes` has no `kind` and no `name` column. `_extract_nodes` reads
   `clone_hash, file_id, package_name, metadata` and drops the rest. **Once persisted, a node is an
   anonymous hash with a file path.** It cannot be told from any other node in the same file.
3. **Description.** Every parser defines `SCM_COMMENT_QUERY`. The graph adapter never calls it.
   Node `metadata` is `{}` for every node a real build writes.

Nobody has noticed any of this because **nothing reads the graph.** `ADR-006` names eight readers;
all eight are `🔜`/`🔮` with no design document.

---

## 4b. A call resolves only when its bare name is globally unique

Cross-file, cross-folder and cross-module resolution **does** work: `procedure_index` is built from
every collected file. The rule is one line in `_callee_target`:

```python
declared_in = procedure_index.get(name, set())
if len(declared_in) == 1:      # resolve
return _ghost(...)             # zero, or two or more
```

**Bare-name matching, no type information.** Measured on this repo's Python alone:

| | |
|---|---|
| Distinct procedure names | 1,374 |
| Declared exactly once — a call *can* resolve | 1,141 |
| Declared more than once — every call **ghosts** | 233 |
| **Declarations behind a duplicated name** | **1,088 of 2,229 — 48%** |

`__init__` ×131 · `check` ×26 · `execute` ×25 · `run` ×14. The index is **global across languages**,
so a Java `execute` and a Python `execute` collide with each other.

**The ghost rate understates it.** When a bare name IS unique it resolves — even where `thing.save()`
and that lone `save` are unrelated. A unique name is not the same as the right target, and nothing
tracks what `thing` is.

What is missing here is **type resolution**: knowing the receiver's type is what turns `save()` into
*"`OrderRepository.save`"*. No parser here does it, and it is **static work, not dynamics**.

## 4c. Framework binding produces no edges

Where the wiring is an annotation or a config file rather than a call site — Spring injection, HTTP
routes, event listeners — the graph sees nothing. This is still static: the binding **is** written
down, just not where the call is.

The vocabulary is ready and unused: `CONSUMES`, `FULFILLS`, `PUBLISHES`, `SUBSCRIBES` have **no
writer**, and `extract_framework_markers` returns `{}` on the declarative tier.

That is `B-SENS-08`, which `ADR-006` calls *"a precondition, not an enhancement"* for every reader.
`🔜`, no design document.

## 4d. So: three gaps, and only one is dynamics

| Gap | What it needs | Status |
|---|---|---|
| A call resolves only on a globally unique bare name | **type resolution** | static, not built, unowned |
| Framework binding yields no edges | **framework semantics** | static, `B-SENS-08`, planned |
| What actually ran | tracing, stack traces | dynamic, `A-SENS-05`, planned |

The graph today models *"the text says `save()`"* — not *"this object's `save` is that method."*

## 5. What would actually be needed — derived, not invented

There is no reader, so "needed" cannot be measured. It can only be derived from the three questions
`ADR-006` says the graph exists to answer. Doing that honestly:

| Question | Needs | Have |
|---|---|---|
| **Locate** — *"where is the code that does X?"* | a symbol's **name** and **kind** | ❌ both dropped at persistence |
| **Contextualize** — *"what does that code touch?"* | callers, callees, contracts | ⚠️ `CALLS`/`IMPORTS` yes; interfaces missing for TypeScript |
| **Verify** — *"did the change break a dependent?"* | dependency edges + what a symbol promises | ⚠️ edges yes; the promise (signature, description) never captured |

**Locate fails on the store as it stands.** That is the first thing to fix, and it is the smallest:
two columns.

---

## 6. The order the evidence suggests

Not a plan — a reading of what blocks what.

1. **Persist `kind` and `name`.** Everything else is unusable without it, and no reader can be built
   on a store of anonymous hashes.
2. **Make the two lists agree.** One guard: every declaration node a parser reports is accounted
   for — declared a type, or deliberately a procedure. That guard is what was missing, not the
   individual fixes; it would have caught all six mis-filings and both absences at once.
3. **Then the individual languages** — C, C++, Java, Kotlin, TypeScript, Rust, SQL, markdown.
4. **`STATE`, `NAMESPACE`, descriptions: not yet.** Every language has constants and doc comments,
   and nothing would read them. Building them now repeats the mistake this repo retired a capability
   for on 2026-08-23.

## 7. Scope — analysis is broad, implementation is not

**Analysis** covers whatever a target project contains: the ten parsed today, plus markdown, HTML,
config and schema formats. Understanding a concept is cheap; a family that is understood and not yet
parsed costs nothing.

**Implementation focuses on eight** `[agreed 2026-08-25]`:

| Language | Parser | Classification today |
|---|---|---|
| Java | ✅ built | `enum` mis-filed |
| Kotlin | ✅ built | `object` mis-filed |
| Python | ✅ built | correct |
| Rust | ✅ built | `enum`/`union` declared as types but never reported |
| TypeScript | ✅ built | `interface`/`enum`/type alias never reported |
| SQL | ✅ built | `TABLE`/`VIEW` mis-filed |
| markdown | ✅ built | every heading mis-filed; symbols are for the **editor**, not the graph |
| **proto** | ❌ **does not exist** | — |

`proto` is anticipated but unbuilt: `tiers.py` shaped its declarative tier around it — *"a
declarative language **with real imports** — `proto` does"* — and no parser directory exists.

**Out of implementation focus: C, C++, Go.** All three are built. Go is one of only two languages
classifying correctly today; C and C++ carry the mis-filings recorded in §1 and keep them for now.

## What this record does not claim

That any of it is urgent. The graph has no consumer, and its build cost has only ever been measured
against SpecWeaver's own source rather than a target project. This says what is broken and in what
order it would have to be fixed — not that it should be fixed now.
