import glob

annotations = {
    "api": {
        "specweaver/cli": "The REST API is a parallel entry point to the CLI. They must remain decoupled to ensure the API doesn't rely on terminal-specific utilities.",
        "specweaver/loom/*": "The loom boundary isolates execution (git, filesystem, processes). High-level adapters must never bypass the flow engine to natively execute raw processes.",
    },
    "cli": {
        "specweaver/loom/*": "The loom boundary isolates execution (git, filesystem, processes). High-level orchestrators must never bypass the flow engine to natively execute raw processes."
    },
    "commons": {
        "specweaver/*": "Commons is the lowest leaf node; it contains fundamental utilities and shouldn't import any domain logic."
    },
    "config": {
        "specweaver/loom/*": "Pure logic leaf node for configuration, cannot touch execution layers."
    },
    "context": {
        "specweaver/loom/*": "UI/interactive contracts must remain strictly decoupled from the execution sandbox."
    },
    "drafting": {
        "specweaver/loom/*": "Orchestrator restricts raw execution to the engine/pipeline layers."
    },
    "flow": {
        "specweaver/loom/tools/*": "Flow orchestrates high-level tasks but must not execute intent-gated agent tools directly (only via actors/dispatcher).",
        "specweaver/loom/commons/*": "Flow must not execute raw executors directly; it must use atoms.",
        "specweaver/drafting": "Forbidden because flow is the automated state-machine. It must remain perfectly headless and cannot rely on interactive terminal drafts.",
        "specweaver/context": "Forbidden because flow is the automated state-machine. It must remain perfectly headless and cannot rely on terminal prompts.",
    },
    "graph": {
        "specweaver/loom/*": "The graph module handles pure topological determinism. It must avoid linking to any generative AI tasks to guarantee speed and mathematical correctness.",
        "specweaver/llm": "Graph is pure deterministic modeling; injecting an LLM compromises topological certainty.",
        "specweaver/drafting": "Graph models must not depend on interactive text generation.",
        "specweaver/implementation": "Graph models must not depend on code generation.",
    },
    "llm": {
        "specweaver/loom/*": "LLM adapter is purely structural/transport and must not execute code."
    },
    "llm/adapters": {
        "specweaver/loom/*": "Vendor SDK wrappers must remain completely agnostic of the domain engine or quality pipeline.",
        "specweaver/validation": "Adapters should not import quality pipeline objects natively.",
        "specweaver/drafting": "Adapters should not depend on drafting logic.",
    },
    "llm/mention_scanner": {"specweaver/loom/*": "Scanner should not rely on engine executors."},
    "planning": {
        "specweaver/loom/*": "High-level orchestrators must never bypass the flow engine to natively execute raw processes."
    },
    "project": {
        "specweaver/loom/*": "High-level adapters must never bypass the flow engine to natively execute raw processes.",
        "specweaver/llm": "Project discovery is a procedural adapter and shouldn't use LLMs directly.",
    },
    "review": {
        "specweaver/loom/*": "High-level orchestrators must never bypass the flow engine to natively execute raw processes."
    },
    "standards": {
        "specweaver/loom/*": "High-level orchestrators must never bypass the flow engine to natively execute raw processes."
    },
    "validation": {
        "specweaver/loom/*": "High-level orchestrators must never bypass the flow engine to natively execute raw processes.",
        "specweaver/llm": "Validation core logic should not depend on LLMs.",
    },
    "validation/rules": {
        "specweaver/loom/*": "Rules must remain perfectly fast, deterministic static checks without invoking the agent Sandbox.",
        "specweaver/llm": "Rules must remain perfectly fast, deterministic static checks without invoking LLMs.",
        "specweaver/drafting": "Rules must remain perfectly fast, deterministic static checks without invoking dynamic drafts.",
    },
    "validation/rules/code": {
        "specweaver/loom/*": "Rules must remain perfectly fast, deterministic static checks without invoking the agent Sandbox.",
        "specweaver/llm": "Rules must remain perfectly fast, deterministic static checks without invoking LLMs.",
        "specweaver/drafting": "Rules must remain perfectly fast, deterministic static checks without invoking dynamic drafts.",
    },
    "validation/rules/spec": {
        "specweaver/loom/*": "Rules must remain perfectly fast, deterministic static checks without invoking the agent Sandbox.",
        "specweaver/llm": "Rules must remain perfectly fast, deterministic static checks without invoking LLMs.",
        "specweaver/drafting": "Rules must remain perfectly fast, deterministic static checks without invoking dynamic drafts.",
    },
    "implementation": {
        "specweaver/loom/*": "High-level orchestrators must never bypass the flow engine to natively execute raw processes."
    },
    "loom/atoms": {
        "specweaver/loom/tools/*": "Atoms are internal engine logic and must not use intent-gated agent tools."
    },
    "loom/atoms/filesystem": {
        "specweaver/loom/tools/*": "Atoms are internal engine logic and must not use intent-gated agent tools."
    },
    "loom/atoms/git": {
        "specweaver/loom/tools/*": "Atoms are internal engine logic and must not use intent-gated agent tools."
    },
    "loom/atoms/qa_runner": {
        "specweaver/loom/tools/*": "Atoms are internal engine logic and must not use intent-gated agent tools."
    },
    "loom/commons": {
        "specweaver/loom/tools/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
        "specweaver/loom/atoms/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
    },
    "loom/commons/filesystem": {
        "specweaver/loom/tools/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
        "specweaver/loom/atoms/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
    },
    "loom/commons/git": {
        "specweaver/loom/tools/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
        "specweaver/loom/atoms/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
    },
    "loom/commons/language": {
        "specweaver/loom/tools/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
        "specweaver/loom/atoms/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
    },
    "loom/commons/qa_runner": {
        "specweaver/loom/tools/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
        "specweaver/loom/atoms/*": "Raw executors (commons) are foundational leaves and cannot import the layers above them.",
    },
    "loom/tools": {
        "specweaver/loom/atoms/*": "Agent-facing tools must not access internal unrestricted engine atoms."
    },
    "loom/tools/filesystem": {
        "specweaver/loom/atoms/*": "Agent-facing tools must not access internal unrestricted engine atoms."
    },
    "loom/tools/git": {
        "specweaver/loom/atoms/*": "Agent-facing tools must not access internal unrestricted engine atoms."
    },
    "loom/tools/qa_runner": {
        "specweaver/loom/commons/*": "QA Runner tools facade intent, but delegate downwards properly."
    },
    "loom/tools/web": {
        "specweaver/loom/atoms/*": "Agent-facing tools must not access internal unrestricted engine atoms."
    },
}

for f in glob.glob("src/**/context.yaml", recursive=True):
    # Normalize path key
    module_name = f.replace("\\\\", "/").replace("src/specweaver/", "").replace("/context.yaml", "")

    if module_name not in annotations:
        # Fallback for dynamic logic
        for key in annotations:
            if module_name.startswith(key):
                module_name = key
                break

    with open(f, encoding="utf-8") as file:
        lines = file.readlines()

    out_lines = []
    in_forbids = False

    for _i, line in enumerate(lines):
        if line.startswith("forbids:"):
            in_forbids = True
            out_lines.append(line)
        elif in_forbids and line.strip() == "":
            in_forbids = False
            out_lines.append(line)
        elif in_forbids and line.strip().startswith("-"):
            rule_value = line.split("-")[1].strip()
            # remove existing comments
            if "#" in rule_value:
                rule_value = rule_value.split("#")[0].strip()

            comment = annotations.get(module_name, {}).get(rule_value, "")
            if not comment:
                # Fallback to broader match if possible
                pass

            if comment:
                idx = line.find("-")
                indent = line[:idx]
                out_lines.append(f"{indent}- {rule_value}  # {comment}\\n")
            else:
                out_lines.append(line)
        elif in_forbids and not line.startswith(" ") and not line.startswith("-"):
            in_forbids = False
            out_lines.append(line)
        else:
            out_lines.append(line)

    with open(f, "w", encoding="utf-8") as file:
        file.writelines(out_lines)

print("Annotated context.yaml files.")
