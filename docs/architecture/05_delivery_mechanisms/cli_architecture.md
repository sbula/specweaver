# CLI Architecture: Native Healer & Rescue Core

The SpecWeaver CLI acts as the system's "Rescue Core." 

Because SpecWeaver employs a decentralized plugin architecture where domains expose their own CLI commands, a syntax error or fatal bug in one domain's `interfaces/cli` module could theoretically bring down the entire tool, preventing the agent from using SpecWeaver to fix SpecWeaver.

## The Try/Except Plugin Loader
To solve this, `interfaces/cli/main.py` dynamically loads plugins using isolated `try/except` blocks. If a plugin crashes during import, the CLI still boots up successfully, displaying a red error message for the failed module, but keeping the core Rescue Commands (`sw run`, `sw implement`) online so the agent can heal the broken module.

```mermaid
graph LR
    User([Developer / Agent]) --> CLI[interfaces/cli/main.py]
    
    CLI -->|Hardcoded Boot| Core[Rescue Core Commands<br>sw run / sw implement]
    CLI -->|Hardcoded Boot| FST[FileSystemTool<br>ALWAYS ONLINE]
    
    CLI -.->|Try/Except Load| Plug1[infrastructure/llm/interfaces/cli.py]
    CLI -.->|Try/Except Load| Plug2[sandbox/git/interfaces/cli.py<br>💥 SyntaxError]
    
    Core -.->|Uses FST to fix| Plug2
```
