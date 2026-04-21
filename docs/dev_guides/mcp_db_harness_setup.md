# Setup your Project DB Harness

SpecWeaver utilizes Model Context Protocol (MCP) to safely interface with external infrastructure such as Postgres databases. Because database schemas and content are sensitive, SpecWeaver executes MCP connections through local, ephemeral Docker containers governed by a strict `vault.env` isolation layer.

This guide explains how to initialize and configure an MCP Database harness for your repository.

## 1. Scaffold the Harness

Within your target repository, use the `sw init` command with the `--mcp` flag to scaffold the required directory boundaries:

```bash
sw init my-project-name --mcp postgres
```

This command will:
1. Append `.specweaver/vault.env` to your project's `.gitignore` file to guarantee credentials are never source-controlled.
2. Initialize `.specweaver/vault.env` with boilerplate environment keys.
3. Scaffold `.specweaver_mcp/postgres/context.yaml`, which defines the isolation boundaries and runtime engine payload.

## 2. Configure Least-Privilege Access

SpecWeaver requires read access to your database schema in order to synthesize `Architecture` limits, perform `Data` validation checks, and enrich the Context Assembler with true schema representations. 

> [!CAUTION]
> **Least Privilege Mandate**: You must never provide write-level or administrative credentials to the `vault.env` file. SpecWeaver AI Agents act probabilistically; protecting your database against accidental `DROP TABLE` or `UPDATE` statements is entirely enforced by database user authorization boundaries.

Create a read-only role on your Postgres instance explicitly for SpecWeaver:

```sql
CREATE ROLE specweaver_reader WITH LOGIN PASSWORD 'your_secure_password';
GRANT CONNECT ON DATABASE my_db TO specweaver_reader;
GRANT USAGE ON SCHEMA public TO specweaver_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO specweaver_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO specweaver_reader;
```

## 3. Inject Credentials into the Vault

Open the automatically generated `.specweaver/vault.env` file and supply the newly created credentials:

```env
# Secure Vault - Explicitly excluded from source control tracking.
# MCP Target: Postgres

POSTGRES_USER=specweaver_reader
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=my_db
```

These values will be dynamically injected into the ephemeral Node 20 Docker boundaries during `MCPAtom.run()`.

## 4. Telemetry Scrubbing

SpecWeaver implements automated telemetry scrubbing to ensure these credentials never leak. During operation:
- All RPC boundaries returning database URIs will automatically mutate matching strings into `***RESTRICTED***`.
- This ensures your Datadog streams, `specweaver.log` files, and terminal standard output remain untainted by password strings.
