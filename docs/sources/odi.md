# Oracle Data Integrator (ODI)

**Status:** Working
**Source schemes:** `odi://` (live DB), `odi-export:` (offline XML)

## Ingestion Modes

The ODI parser supports two ways in:

### Live DB Mode

```bash
crawl scan --source "odi://host:1521/repo"
```

Connects read-only to the ODI repository database and queries SNP_ catalog tables (from "Sunopsis", ODI's original company name). Auto-detects schema version:

- **12c:** `SNP_MAPPING` → `SNP_MAP_COMP` → `SNP_MAP_CP` → `SNP_MAP_CONN` (component graph)
- **11g:** `SNP_POP` → `SNP_POP_COL` → `SNP_POP_MAPPING` (interface definitions)

All queries are hardcoded constants — no dynamic SQL. See [SAFETY.md](../../SAFETY.md).

### Offline Export Mode

```bash
crawl scan --source "odi-export:./my-export.zip"
```

Parses a Smart Export XML file. No database access needed — just export from ODI Studio and hand Crawl the ZIP. Critical for enterprise sales where DB access is restricted.

Extracts from XML element classes:
- `SnpMapping` → 12c mappings
- `SnpMapComp` → mapping components (DATASTORE, JOIN, FILTER, EXPRESSION, etc.)
- `SnpPop` → 11g interfaces
- `SnpTrt` → Knowledge Modules (IKM, LKM, CKM, RKM, JKM)
- `SnpLineTrt` → KM steps with SQL and technology references
- `SnpTechno` → technology definitions

## What Gets Extracted

| Artifact | Description |
|----------|-------------|
| Mappings | 12c mappings and 11g interfaces with source/target tables |
| Expressions | Transformation logic (`AVG(@{R0})`, `SYSDATE`, etc.) |
| Dependencies | Source → target data lineage across all datastores |
| Knowledge Modules | IKM, LKM, CKM, RKM taxonomy with step-level SQL |
| Complexity scores | Per-mapping score based on expression count, source/target count, KM complexity |

## Example: ODI Movie Pipeline

Crawl scanned the Oracle Big Data Lite demo repository and produced this visual lineage:

![ETL Pipeline Lineage](../diagrams/etl-pipeline-lineage.png)

**What Crawl found that ODI Studio can't show you:**

- 8 mappings across 4 technologies (Oracle, Hive, Pig, Spark)
- 5 cross-platform data hops — each one a migration risk
- Vendor-specific syntax (`SYSDATE`, `NVL`, `DECODE`) that needs translation
- 0 execution history on any mapping — potential dead code
- 3 terminal targets, 5 external sources — data lineage boundaries

### Business Rules Extracted

```
C - Calc Ratings (Hive → Pig → Spark) (confidence: HIGH)
├── Rule: Calculates average movie ratings grouped by movie ID
├── Sources: HiveMovie.movie, HiveMovie.movieapp_log_odistage
├── Target: HiveMovie.movie_rating
└── Risk: ⚠️ Cross-platform hop (Hive → Pig → Spark) — vendor-specific aggregation

G - Sessionize Data (Pig) (confidence: HIGH)
├── Rule: Sessionizes click data, computes max/avg session duration by country
├── Expressions: ROUND(@{R0} * 1000), MAX(@{R0}), AVG(@{R0})
└── Risk: ⚠️ Pig Latin expressions need translation for target platform
```

### Migration Risks Detected

| Severity | Count | Examples |
|----------|-------|---------|
| High | 4 | Cross-platform data movement (Oracle ↔ Hive, HDFS → Hive) |
| Medium | 1 | Oracle `SYSDATE` needs target-specific date function |
| Low | 8 | No execution history on any mapping (dead code risk) |

### Sample Report

See [sample-odi-report.md](../sample-odi-report.md) for the full migration intelligence report generated from this scan.

## ODI-Specific Notes

- **Knowledge Module taxonomy** is documented in [ADR-001](../adr/001-odi-knowledge-module-taxonomy.md)
- **`@{R0}` references** in expressions are ODI template variables pointing to source columns. Resolving these to actual column names is a planned enhancement.
- ODI stores metadata across two schema generations (11g and 12c). The parser auto-detects which tables are present and adapts accordingly. Reference: Oracle Support Doc ID 1903225.1.
