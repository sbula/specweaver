# MCP Database Harness Setup

Use when: you connect a project's database (e.g. Postgres) to SpecWeaver through Model Context
Protocol (MCP).

SpecWeaver runs MCP connections in local, ephemeral Docker containers, isolated by a `vault.env`
file. Schemas and content are sensitive; credentials stay out of source control and logs.

## Steps

1. **Scaffold** in the target repository with `sw init` and the `--mcp` flag:

```bash
sw init my-project-name --mcp postgres
```

   This:
   - appends `.specweaver/vault.env` to the project's `.gitignore`, so credentials are never
     source-controlled;
   - initializes `.specweaver/vault.env` with boilerplate environment keys;
   - scaffolds `.specweaver_mcp/postgres/context.yaml`, which defines the isolation boundaries and
     runtime engine payload.

2. **Create a read-only role.** SpecWeaver reads the schema to synthesize `Architecture` limits, run
   `Data` validation checks, and give the Context Assembler the real schema.

> [!CAUTION]
> **Least Privilege Mandate**: You must never provide write-level or administrative credentials to
> the `vault.env` file. SpecWeaver AI Agents act probabilistically; protecting your database against
> accidental `DROP TABLE` or `UPDATE` statements is entirely enforced by database user authorization
> boundaries.

```sql
CREATE ROLE specweaver_reader WITH LOGIN PASSWORD 'your_secure_password';
GRANT CONNECT ON DATABASE my_db TO specweaver_reader;
GRANT USAGE ON SCHEMA public TO specweaver_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO specweaver_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO specweaver_reader;
```

3. **Fill the vault**: put the credentials into the generated `.specweaver/vault.env`:

```env
# Secure Vault - Explicitly excluded from source control tracking.
# MCP Target: Postgres

POSTGRES_USER=specweaver_reader
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=my_db
```

   `MCPAtom.run()` injects them into the ephemeral Node 20 Docker container.

## Telemetry scrubbing

RPC results containing database URIs have matching strings replaced by `***RESTRICTED***`, so
Datadog streams, `specweaver.log` files and terminal standard output never carry passwords.
