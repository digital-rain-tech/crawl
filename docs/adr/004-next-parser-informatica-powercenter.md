# ADR-004: Next Parser Target — Informatica PowerCenter

**Date:** 2026-03-18
**Status:** Proposed
**Context:** Choosing the next ETL source to build a parser for after ODI

## Problem

Crawl currently supports Oracle Data Integrator only. To demonstrate vendor-neutrality and expand market reach, we need to prioritize which ETL platform to support next. The ideal candidate has: a queryable catalog database, an offline export format, a large installed base under active migration pressure, and alignment with our existing dual-mode architecture.

## Options Considered

| Vendor | Installed Base | Catalog DB | Offline Export | Migration Pressure | Crawl Fit |
|--------|---------------|------------|----------------|-------------------|-----------|
| **Informatica PowerCenter** | ~3,100 companies | OPB_ tables + MX views (500+ tables/views) | XML export | Very high — Informatica sunsetting PowerCenter, pushing IDMC | Best |
| **IBM DataStage** | ~1,500 companies | XMETA DB + DSODB operations tables | .dsx files (XML) | High — IBM pushing Watsonx/Cloud Pak | Good |
| **SSIS** | Very large (SQL Server ecosystem) | SSISDB catalog + msdb.sysssispackages | .dtsx packages (XML) | Moderate — many staying on SQL Server | Good |
| **Talend** | Medium | No central catalog DB — file-based project dirs | Project directory XML | Moderate — Qlik acquired Talend | Decent |
| **Ab Initio** | ~500 (high-end) | EME is proprietary, not SQL-queryable | Limited — graphs are binary | Low — very locked down ecosystem | Poor |

## Decision

**Informatica PowerCenter** is the next parser target.

### Rationale

1. **Largest active migration wave.** Informatica is actively pushing all ~3,100 PowerCenter customers to their cloud platform (IDMC). Some customers have 20,000+ PowerCenter assets. This is the biggest ETL migration wave in the industry right now.

2. **Excellent catalog database.** The PowerCenter repository stores all metadata in OPB_ tables:
   - `OPB_MAPPING` — mapping definitions with folder references
   - `OPB_SRC` / `OPB_TARG` — source and target table metadata
   - `OPB_WIDGET` — transformation definitions (Expression, Lookup, Joiner, etc.)
   - `OPB_TASK` / `OPB_SESSION` — workflow and session definitions
   - `OPB_SUBJECT` — folder/subject area hierarchy

   Informatica also provides MX views (REP_ prefixed) purpose-built for metadata queries. `REP_TBL_MAPPING` gives source/target/transformation lineage directly via SQL. Over 500 tables and views are documented.

3. **Same dual-mode pattern as ODI.** Live DB mode (query OPB_ tables, read-only) + offline XML export mode. This maps directly to our existing `BaseParser` architecture with `InfaDbParser` and `InfaXmlParser`.

4. **Founder credibility.** 12 years at Informatica means deep knowledge of these tables and the customer pain points. This is a natural first expansion.

5. **Direct customer overlap with ODI.** Enterprises running both PowerCenter and ODI are common (Oracle and Informatica are the two dominant traditional ETL vendors). A tool that scans both in one pipeline is a strong differentiator.

### Implementation Sketch

**Source schemes:**
- `infa://host:port/repo` — live DB mode against OPB_ tables
- `infa-export:./export.xml` — offline XML export mode

**Key catalog queries (allowlisted, read-only):**
```sql
-- Mappings with folder context
SELECT m.MAPPING_ID, m.MAPPING_NAME, s.SUBJ_NAME
FROM OPB_MAPPING m JOIN OPB_SUBJECT s ON m.SUBJECT_ID = s.SUBJ_ID;

-- Source/target lineage via MX views
SELECT MAPPING_NAME, SOURCE_NAME, TARGET_NAME, SUBJECT_AREA
FROM REP_TBL_MAPPING;

-- Transformation details
SELECT w.WIDGET_ID, w.WIDGET_NAME, w.WIDGET_TYPE, w.MAPPING_ID
FROM OPB_WIDGET w;
```

**Common IR mapping:**
- `OPB_MAPPING` → `DataObject(object_type=MAPPING)`
- `OPB_SRC` / `OPB_TARG` → `Dependency(source, target)`
- `OPB_WIDGET` expressions → `DataObject.expressions`
- Widget types (Expression, Lookup, Joiner, Filter, Router) → `BusinessRule` candidates for LLM extraction

### Runner-Up: IBM DataStage

DataStage is a strong #3 candidate after PowerCenter:
- ~1,500 companies under similar migration pressure (IBM pushing Watsonx)
- XMETA database tables are SQL-queryable (e.g., `DATASTAGEX_XMETAGEN_DSJOBDEFC2E76D84`)
- .dsx export files are XML-parseable
- Same dual-mode pattern applies

## References

- [Informatica OPB Tables Overview](https://dwbi.org/pages/106)
- [MX Views Reference (Informatica 10.4)](https://docs.informatica.com/data-integration/powercenter/10-4-0/repository-guide/mx-views-reference/mx-views-overview.html)
- [REP_TBL_MAPPING View](https://docs.informatica.com/data-integration/powercenter/10-4-0/repository-guide/mx-views-reference/mapping-and-mapplet-views/rep_tbl_mapping.html)
- [PowerCenter + ODI Repository Queries Compared](https://www.clearpeaks.com/build-and-use-repository-metadata-queries-in-informatica-powercenter-and-oracle-data-integrator-odi/)
- [PowerCenter Cloud Modernization](https://www.informatica.com/platform/powercenter-cloud-modernization.html)
- [3,124 Companies Using PowerCenter (Landbase)](https://landbase.ai/technology/informatica-powercenter/)
- [1,481 Companies Using DataStage (Landbase)](https://data.landbase.com/technology/ibm-infosphere-datastage/)
- [SSIS Catalog Reference (Microsoft)](https://learn.microsoft.com/en-us/sql/integration-services/catalog/ssis-catalog?view=sql-server-ver16)

## Consequences

- Parser registry gains `infa://` and `infa-export:` scheme resolution
- OPB_ table queries added to allowlisted SQL constants
- Safety model unchanged — same read-only, catalog-only, no-dynamic-SQL guarantees
- README Supported Sources table updates PowerCenter from "Planned" to "In Progress"
- Success here validates the Common IR / dual-mode architecture across a second vendor
