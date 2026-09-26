# User Guide: Configuring The Model Context Protocol (MCP)

Use when: the agent needs data from an external system (a PostgreSQL schema, Jira tickets, GitHub
graphs) through the **Model Context Protocol (MCP)**.

## How it works

The LLM does not browse external APIs itself; that costs tokens and time. SpecWeaver uses the
**Pre-Fetched Context Envelope** pattern instead:

1. In `.specweaver/context.yaml` you declare the MCP servers and the URIs to read.
2. Before generation, SpecWeaver starts each server in a container, reads the resources, and puts
   the text into the agent's context.
3. Generation runs on that text. The LLM does not call the servers itself.

## Steps

### 1. Define servers

List them in the `mcp_servers` dictionary of your target project's `context.yaml`. Or run
`sw init my-app --mcp postgres` to scaffold the container binding:

```yaml
mcp_servers:
  postgres-schema-analyzer:
    command: ["docker", "run", "-i", "--rm", "anthropic/mcp-postgres"]
    env:
      DB_CONNECTION_STRING: "${vault:PROD_DB_URL}"
```

Secrets live in `.specweaver/vault.env`. The `--mcp postgres` scaffold passes it to the container
with `--env-file`, and adds it to `.gitignore`. A run aborts if `vault.env` is tracked by Git.
Secret values of 8+ characters are replaced with `***RESTRICTED***` in what the server returns.

### 2. Bind the resources to read

List the `resources/read` URIs in the `consumes_resources` array of `context.yaml`:

```yaml
consumes_resources:
  - "postgres://public/users"
  - "postgres://public/orders"
```

The fetcher accepts only URIs of the form `mcp://<server>/<resource>`, where `<server>` is a key
of `mcp_servers`. Any other URI is inserted as an error line instead of content.

## Rules

- **Container only (Docker or Podman).** The command must start with `docker` or `podman`, e.g.
  `docker run -i --rm`. SpecWeaver will not start a bare `node` process on your machine. Any other
  executable stops the run with an `NFR-2 Boundary Violation`.
- **No escape flags.** `--privileged`, host networking/PID/IPC/UTS/user namespaces, `--cap-add`,
  `--security-opt`, `--device`, and mounts of `/`, `/etc`, `/root` or the Docker socket are refused.
- **Only the L2 Architect browses MCP.** The `MCPExplorerTool` exposes the MCP JSON-RPC endpoints.
  The ToolDispatcher grants its `ArchitectMCPInterface` (list servers, list resources, read
  resource) only to the **L2 Architect Role**. Implementation and validation loops get the
  pre-fetched text only. The explorer applies the same container rules as above before it starts
  anything, and redacts configured secrets (8+ characters) from what it returns.
