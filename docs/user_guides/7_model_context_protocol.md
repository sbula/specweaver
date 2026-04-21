# User Guide: Configuring The Model Context Protocol (MCP)

SpecWeaver allows your autonomous AI architecture to statically read from external systems (like PostgreSQL schemas, Jira tickets, and Github graphs) via the **Model Context Protocol (MCP)** seamlessly.

## How It Works

Instead of the LLM wandering off into external APIs autonomously (which causes token saturation and huge latency loops), SpecWeaver uses the **Pre-Fetched Context Envelope** pattern. 

In your project's `.specweaver/context.yaml`, you declare exactly which MCP servers your project relies on, and what specific URIs it should read. SpecWeaver will securely boot these resources inside isolated Docker containers, map the text natively into your Agent's context buffer, and run the generations in a zero-latency bubble!

## 1. Defining Servers

In your Target Project's `context.yaml`, define your external systems in the `mcp_servers` dictionary layer:

```yaml
mcp_servers:
  postgres-schema-analyzer:
    command: ["docker", "run", "-i", "--rm", "anthropic/mcp-postgres"]
    env:
      DB_CONNECTION_STRING: "${vault:PROD_DB_URL}"
```

*(Note: SpecWeaver securely intercepts `${vault:<key>}` tokens and injects them safely from your local `.specweaver/vault.env` ledger.)*

## 2. Binding Resource Consumption

To actually inject the text returned by the MCP endpoint into your current Workspace context, map the target `resources/read` URIs into the `consumes_resources` array natively in `context.yaml`:

```yaml
consumes_resources:
  - "postgres://public/users"
  - "postgres://public/orders"
```

## 3. Strict Execution Limits (Docker Required)

By architectural mandate, SpecWeaver refuses to boot native `node` processes blindly on your local OS to protect you from remote execution attacks. All target MCP servers must physically be packaged via `docker run -i --rm` or `podman`. SpecWeaver will rigidly trigger a validation halt if you attempt to bypass this isolation limit.
