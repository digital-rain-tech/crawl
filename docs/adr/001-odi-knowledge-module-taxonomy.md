# ADR-001: ODI Knowledge Module Taxonomy

**Date:** 2026-03-17
**Status:** Accepted
**Context:** Parsing Oracle Data Integrator exports

## Context

Oracle Data Integrator (ODI) uses "Knowledge Modules" (KMs) as reusable templates that define *how* data is moved, validated, and transformed at each stage of an ETL pipeline. Understanding this taxonomy is essential for interpreting ODI exports correctly.

## ODI Object Hierarchy

An ODI ETL pipeline has two layers:

- **Mappings/Interfaces** define *what* — source tables, target tables, transformation expressions, join conditions, filters. This is where business logic lives ("churn = inactive > 90 days").
- **Knowledge Modules** define *how* — the loading strategy, integration method, validation approach. These are reusable templates applied to mappings.

A single mapping references multiple KMs:

```
Mapping: "Load Customer Dimension"
  ├── LKM SQL to SQL           (how to stage the source data)
  ├── IKM Oracle Incremental   (how to merge into the target)
  └── CKM Oracle               (how to validate constraints)
```

## Knowledge Module Types

| Type | Full Name | Stage | Purpose | Example |
|------|-----------|-------|---------|---------|
| **LKM** | Loading Knowledge Module | Source → Staging | Moves data from source to a staging area on the target or an intermediate server | `LKM SQL to SQL`, `LKM File to Oracle (SQLLDR)`, `LKM SQL to Oracle (DBLINK)` |
| **IKM** | Integration Knowledge Module | Staging → Target | Loads staged data into the final target table using a specific strategy (append, incremental update, SCD) | `IKM SQL to SQL Append`, `IKM Oracle Incremental Update`, `IKM SQL to MarkLogic` |
| **CKM** | Check Knowledge Module | Post-integration | Validates data quality by checking constraints (PK, FK, NOT NULL, conditions) and isolating rejected rows into error tables | `CKM Oracle`, `CKM SQL` |
| **RKM** | Reverse-engineering Knowledge Module | Metadata introspection | Reads source/target metadata (table structures, columns, keys, indexes) to populate ODI's data models | `RKM Oracle`, `RKM SQL`, `RKM SAP ERP` |
| **JKM** | Journalizing Knowledge Module | Change Data Capture | Tracks which rows have changed since the last extraction (CDC), enabling incremental loads | `JKM Oracle Consistent`, `JKM SQL` |
| **SKM** | Service Knowledge Module | Service exposure | Exposes data operations as web services | `SKM SQL to Web Service` |

## ODI Internal Representation

In the ODI repository (SNP_ tables) and Smart Export XML:

- KMs are stored as `SnpTrt` (treatment) objects with a `TrtType` field:
  - `KI` = IKM, `KL` = LKM, `KC` = CKM, `KR` = RKM, `KJ` = JKM, `KS` = SKM
- KM steps are stored as `SnpLineTrt` objects, each containing source SQL (`ColITxt`) and/or target SQL (`DefITxt`) with ODI template expressions like `snpRef.getColList()`, `snpRef.getTable()`
- KM options are stored as `SnpUserExit` objects (e.g., INSERT=Yes, TRUNCATE=No)

## Implications for Crawl

1. **KMs alone don't contain business logic** — they're templates. The real value is in mappings/interfaces that reference KMs.
2. **KM type tells us the data flow stage** — useful for triage (an IKM issue is higher risk than an RKM issue).
3. **KM steps contain vendor-specific SQL patterns** — these inform migration risk scoring (e.g., an IKM using Oracle-specific MERGE syntax is harder to migrate than one using standard INSERT-SELECT).
4. **KM choice signals loading strategy** — "IKM Oracle Incremental Update" means SCD Type 1; "IKM Oracle Slowly Changing Dimension" means SCD Type 2. This is useful metadata for migration planning.

## Decision

Crawl will:
- Parse all KM types and classify them by their role in the data flow
- Display human-readable KM type labels (not just acronyms) in CLI output
- Use KM type as a triage signal (IKM/LKM = higher criticality than RKM/CKM)
- Prioritize mapping/interface parsing over KM parsing for business rule extraction
