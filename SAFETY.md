# Crawl Safety Model

Crawl connects to enterprise databases to extract business logic from stored procedures, views, and functions. This document defines the safety guarantees that govern how Crawl interacts with your data infrastructure.

## Core Guarantees

### 1. Read-Only. Always.

Crawl **never writes, modifies, creates, or deletes** anything in your database. All connections are opened in read-only mode where the database supports it. There are no INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, or TRUNCATE statements anywhere in the codebase.

Implementation:
- Connections use read-only transaction mode (`SET TRANSACTION READ ONLY` / `default_transaction_read_only`)
- The connection user should be granted SELECT-only permissions — Crawl will never ask for more
- All queries are allowlisted — only catalog/metadata queries are permitted (see below)

### 2. Catalog-Only Access

Crawl reads **metadata and source code from system catalogs**, not your actual data. It never queries user tables, views, or materialized views for their *contents* — only for their *definitions*.

What Crawl reads:

| Database | Catalog Views Used |
|----------|-------------------|
| PostgreSQL | `pg_catalog.pg_proc`, `pg_catalog.pg_views`, `information_schema.routines`, `pg_catalog.pg_depend` |
| Oracle | `ALL_SOURCE`, `ALL_PROCEDURES`, `ALL_OBJECTS`, `ALL_DEPENDENCIES`, `ALL_TAB_COLUMNS` (schema only, not data) |
| SQL Server | `sys.sql_modules`, `sys.procedures`, `sys.objects`, `sys.dependencies`, `INFORMATION_SCHEMA.ROUTINES` |
| Snowflake | `INFORMATION_SCHEMA.PROCEDURES`, `INFORMATION_SCHEMA.VIEWS`, `INFORMATION_SCHEMA.FUNCTIONS` |

What Crawl **never** reads:
- Row data from any user table or view
- Actual values, records, or business data
- Credentials, secrets, or configuration tables
- Temporary tables or session data

### 3. Connect to Non-Production

Crawl recommends connecting to **staging, QA, or development** environments — never directly to production. The stored procedure source code and view definitions are identical across environments; there is no reason to connect to prod.

Implementation:
- `crawl scan` emits a warning if the connection string contains keywords suggesting production (`prod`, `production`, `prd`, `live`)
- `--i-know-this-is-prod` flag required to override (explicit opt-in, never silent)
- Documentation and onboarding always recommend staging-first

### 4. No Connection Hammering

Crawl is designed to be gentle on your database:

- **Single connection** by default — no connection pooling or parallelism unless explicitly configured
- **Rate limiting** — configurable delay between catalog queries (default: 100ms)
- **Batch size limits** — reads stored procedures in batches (default: 50 at a time), not all at once
- **Connection timeout** — connections are closed after configurable idle timeout (default: 5 minutes)
- **No long-running queries** — all catalog queries are simple SELECTs with reasonable result sets

### 5. Query Allowlisting

Crawl maintains a strict allowlist of SQL queries it will execute. Every query is:
- Hardcoded in the parser module (not dynamically generated)
- Limited to system catalog views
- SELECT-only
- Auditable in the source code

Crawl **never** executes:
- Dynamically constructed SQL
- User-provided SQL strings
- Queries against user-defined tables
- DDL or DML statements of any kind

### 6. Full Audit Trail

Every action Crawl takes is logged:
- Connection events (connect, disconnect, with timestamp and target)
- Every catalog query executed (full SQL text)
- Number of objects discovered and extracted
- Any warnings or errors
- LLM calls (what was sent for analysis — source code only, never data)

Logs are written to a local file (`crawl.log`) and can be provided to your DBA for review before and after any scan.

### 7. LLM Data Handling

When Crawl sends stored procedure source code to an LLM for business logic interpretation:

- **Local-first**: Ollama/vLLM supported out of the box — code never leaves your machine
- **Cloud LLM opt-in**: External APIs (OpenAI, Anthropic) require explicit `--llm-provider` flag
- **No data sent**: Only stored procedure/view *source code* is sent to the LLM, never table contents or row data
- **Redaction**: Connection strings, credentials, and comments containing sensitive patterns are stripped before LLM submission

### 8. Recommended Database User Setup

Create a dedicated read-only user for Crawl with minimal permissions:

**PostgreSQL:**
```sql
CREATE ROLE crawl_reader WITH LOGIN PASSWORD 'your-password';
GRANT USAGE ON SCHEMA public TO crawl_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA pg_catalog TO crawl_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA information_schema TO crawl_reader;
-- DO NOT grant SELECT on user tables
```

**Oracle:**
```sql
CREATE USER crawl_reader IDENTIFIED BY "your-password";
GRANT CREATE SESSION TO crawl_reader;
GRANT SELECT ON ALL_SOURCE TO crawl_reader;
GRANT SELECT ON ALL_PROCEDURES TO crawl_reader;
GRANT SELECT ON ALL_OBJECTS TO crawl_reader;
GRANT SELECT ON ALL_DEPENDENCIES TO crawl_reader;
-- DO NOT grant SELECT ANY TABLE
```

**SQL Server:**
```sql
CREATE LOGIN crawl_reader WITH PASSWORD = 'your-password';
CREATE USER crawl_reader FOR LOGIN crawl_reader;
GRANT VIEW DEFINITION TO crawl_reader;
GRANT SELECT ON sys.sql_modules TO crawl_reader;
-- DO NOT grant db_datareader or broader permissions
```

## Verification

The safety model is enforced through:
1. **Code review** — all PRs are reviewed for adherence to the safety model
2. **Automated tests** — test suite verifies read-only behavior and query allowlisting
3. **This document** — any change to the safety model requires updating SAFETY.md and a dedicated review

## Reporting Issues

If you discover any behavior that violates these safety guarantees, please report it immediately via [GitHub Issues](https://github.com/digital-rain-tech/crawl/issues) or email security@digitalrain.studio.
