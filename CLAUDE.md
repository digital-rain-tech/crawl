# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Crawl is a pre-migration intelligence tool for enterprise data infrastructure. It extracts business logic from stored procedures, ETL jobs, and warehouse views before migration. It is **Step 0** — runs before tools like Datafold, Lakebridge, dbt, or SnowConvert.

Early-stage project (Pre-Alpha). First target: Oracle Data Integrator (ODI) parser.

## Commands

```bash
# Install in dev mode
pip install -e ".[dev,llm]"

# Run CLI
crawl --help
crawl scan --source "odi://host:1521/repo"       # ODI live DB
crawl scan --source "odi-export:./export.zip"     # ODI Smart Export XML
crawl scan --source "pctr-export:./workflow.xml"  # PowerCenter XML export
crawl scan --source "postgres://host/db"          # PostgreSQL (planned)
crawl extract
crawl triage
crawl export --format json|dbt-docs|markdown

# Tests
pytest                    # run all tests
pytest tests/test_foo.py  # single file
pytest -k "test_name"     # single test by name

# Lint
ruff check .
ruff format .
```

## Architecture

**Pipeline:** `scan → extract → triage → diff → export`

```
src/crawl/
├── cli.py              # Click CLI (entry point: crawl.cli:main)
├── models.py           # Common IR: DataObject, BusinessRule, Dependency, Contradiction, ScanResult
├── parsers/
│   ├── __init__.py     # BaseParser ABC
│   ├── registry.py     # Source string → parser resolution (odi://, odi-export:, postgres://, etc.)
│   ├── odi/            # Oracle Data Integrator
│   │   ├── db.py       # Live DB mode: queries against SNP_ tables (allowlisted SQL)
│   │   └── xml.py      # Offline mode: Smart Export ZIP/XML parsing
│   └── powercenter/    # Informatica PowerCenter
│       └── xml.py      # Offline mode: POWERMART XML export parsing
├── extraction/         # Hybrid AST (sqlglot) + LLM business logic extraction
├── triage/             # Criticality/complexity/risk scoring engine
└── export/             # Output formatters (dbt-docs YAML, JSON, Markdown)
```

### Key Design Patterns

- **Common IR (models.py):** All parsers produce `ScanResult` containing `DataObject`, `Dependency`, `BusinessRule`, `Contradiction`. Downstream layers (extraction, triage, export) are source-agnostic.
- **Dual ingestion modes:** Each ETL source can have a live DB parser and an offline export parser. Offline mode ("just give us an export file") is critical for enterprise sales where DB access is restricted.
- **Registry (parsers/registry.py):** Resolves `--source` strings to the right parser. Scheme determines parser: `odi://` → OdiDbParser, `odi-export:` → OdiXmlParser, `pctr-export:` → PctrXmlParser.
- **Query allowlisting (parsers/odi/db.py):** All SQL queries are hardcoded constants at module top-level. No dynamic SQL. This is a safety invariant — see SAFETY.md.

### ODI Parser Notes

ODI stores metadata in SNP_ tables (from "Sunopsis", original company). Two schema versions coexist:
- **12c:** `SNP_MAPPING` → `SNP_MAP_COMP` → `SNP_MAP_CP` → `SNP_MAP_CONN` (component graph)
- **11g:** `SNP_POP` → `SNP_POP_COL` → `SNP_POP_MAPPING` (interface definitions)
Parser auto-detects which are present. Reference: Oracle Support Doc ID 1903225.1.

## Safety Model (SAFETY.md)

This is critical — Crawl connects to enterprise databases. All code must enforce:

1. **Read-only always** — no writes/DDL/DML, read-only transaction mode enforced
2. **Catalog-only access** — only system catalog queries (pg_catalog, ALL_SOURCE, SNP_ tables, etc.), never user table contents
3. **Query allowlisting** — all SQL is hardcoded, no dynamic SQL, no user-provided queries
4. **Non-production recommended** — warn on prod connection strings, require `--i-know-this-is-prod` to override
5. **No connection hammering** — single connection, rate-limited, batched, with timeouts
6. **LLM redaction** — strip credentials/connection strings before sending source code to LLM

## Key Dependencies

- **click** — CLI framework
- **sqlglot** — SQL AST parsing (vendor-neutral)
- **rich** — terminal output
- **ruff** — linter/formatter (line-length 100, target Python 3.10)

## Build System

Uses **Hatchling** (PEP 517). Package name: `crawl-data`, packages in `src/crawl`. Requires Python ≥3.10.

## Documentation: Public vs Internal

This is a **public open-source repo**. Be careful about what goes where.

### Public ADRs (`docs/adr/`)
Technical architecture decisions only. These are committed and visible on GitHub.
- Parser design choices, data model decisions, tooling tradeoffs
- Example: ADR-001 (KM taxonomy), ADR-003 (Excalidraw vs Mermaid)

### Internal docs (`docs/internal/`) — GITIGNORED
Strategy, competitive analysis, customer context, and anything with names of people we work with (other than Augustin Chan). This directory is in `.gitignore` and never pushed.
- Market sizing, vendor prioritization, go-to-market strategy
- Customer names, deal context, demo readiness assessments
- Competitive analysis (which vendor to target next and why)

### Rule of thumb
Before creating an ADR, ask: "Would I put this on a slide at a conference?" If yes → `docs/adr/`. If it's more like an internal strategy memo → `docs/internal/`.

### Privacy
- **Augustin Chan's name** is fine in public docs (founder, About section)
- **No other personal names** in public-facing content (customers, collaborators, contacts)
