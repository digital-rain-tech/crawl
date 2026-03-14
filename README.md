# Crawl

**Pre-migration intelligence for enterprise data infrastructure.**

Crawl extracts business logic from stored procedures, ETL jobs, and warehouse views — the undocumented rules buried in your data stack that block every migration project.

> They catalog your data. Crawl tells you what breaks when you migrate.

## The Problem

Every cloud migration hits the same wall: thousands of stored procedures and ETL jobs encoding business rules in vendor-specific dialects that nobody documented. Migration tools can *translate* your SQL, but they can't tell you what it *means* — or whether it's even still relevant.

Crawl is **Step 0**: the pre-migration intelligence layer that runs before you use Datafold, Lakebridge, dbt, or SnowConvert.

## What Crawl Does

```
crawl scan     Connect to a database and discover all stored procs, views, functions
crawl extract  Extract human-readable business rules using hybrid AST + LLM analysis
crawl triage   Score each object by criticality, complexity, and migration risk
crawl diff     Compare extracted logic between environments or time periods
crawl export   Output to dbt-docs YAML, JSON, or Markdown
```

### Example

**Input:** A 200-line stored procedure that nobody on the team wrote

**Output:**
```
sp_calculate_customer_churn (confidence: HIGH)
├── Rule 1: Customers inactive >90 days flagged as at-risk
├── Rule 2: Churn score weighted by lifetime value (table: dim_customer)
├── Rule 3: ⚠️ References dim_product_v2 — TABLE DROPPED 2022-06-14
├── Rule 4: Monthly aggregation via vendor-specific DATEADD syntax
└── Triage: CRITICAL (12 downstream dependencies) | MEDIUM migration risk

Contradictions found:
  └── Rule 2 conflicts with sp_calculate_ltv line 47 (different LTV formula)
```

## Design Principles

- **Step 0, not Step 1.** Crawl doesn't migrate your code — it tells you what you have so migration tools can do their job.
- **Vendor-neutral.** Works with any source database, any target platform. No lock-in.
- **Local-first LLM.** Enterprise code never needs to leave your environment. Supports Ollama and vLLM out of the box.
- **Open-source (Apache 2.0).** Your understanding of your data belongs to you, not a vendor.

## Supported Sources

| Source | Status |
|--------|--------|
| PostgreSQL stored procedures | Planned |
| Snowflake (views, UDFs, procs, tasks) | Planned |
| Informatica PowerCenter / IICS | Planned |
| SQL Server stored procedures | Planned |
| Oracle PL/SQL | Planned |
| dbt models | Planned |

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   crawl CLI                      │
│        scan | extract | triage | diff | export   │
├─────────────────────────────────────────────────┤
│              Orchestration Layer                  │
├──────────┬──────────┬──────────┬────────────────┤
│ Postgres │ Snowflake│ SQL Srv  │  Informatica   │
│ Parser   │ Parser   │ Parser   │  Parser        │
├──────────┴──────────┴──────────┴────────────────┤
│       AST (sqlglot) + LLM Extraction Layer       │
│  Deterministic parsing → Business rule interp.   │
│  → Confidence scoring → Contradiction detection  │
├─────────────────────────────────────────────────┤
│              Triage Engine                        │
│  Criticality · Dead code · Dependencies · Risk   │
├─────────────────────────────────────────────────┤
│           LLM Backend (pluggable)                │
│  Local: Ollama, vLLM  │  Cloud: OpenAI, Claude  │
└─────────────────────────────────────────────────┘
```

## Safety Model

Crawl is designed to connect to enterprise databases safely. See [SAFETY.md](SAFETY.md) for the full safety model. Key guarantees:

- **Read-only, always.** No writes, no DDL, no DML. Read-only transaction mode enforced.
- **Catalog-only access.** Reads stored procedure source code from system catalogs (`pg_catalog`, `ALL_SOURCE`, `sys.sql_modules`). Never queries user table contents.
- **Non-production recommended.** Warns on production connection strings. Stored procedure source code is identical in staging — there's no reason to connect to prod.
- **No hammering.** Single connection, rate-limited, batched queries, configurable timeouts.
- **Query allowlisting.** Every SQL query is hardcoded and auditable. No dynamic SQL.
- **Local-first LLM.** Enterprise code never needs to leave your environment. Cloud LLM is opt-in.
- **Full audit trail.** Every query logged for DBA review.

## Status

Early development. Star the repo to follow progress.

## License

Apache 2.0 — see [LICENSE](LICENSE).

## About

Built by [Digital Rain Technologies](https://digitalrain.studio). Founded by [Augustin Chan](https://augustinchan.dev), former Development Architect at Informatica (12 years, Fortune 500 data integration across APAC/MENA/Europe).

Part of the Digital Rain enterprise AI readiness platform, alongside [ARA-Eval](https://github.com/digital-rain-tech/ara-eval) (Agentic Readiness Assessment for regulated industries).
