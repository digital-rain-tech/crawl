# Informatica PowerCenter

**Status:** Working (offline XML)
**Source scheme:** `pctr-export:` (offline XML)

## Ingestion Mode

### Offline Export Mode

```bash
crawl scan --source "pctr-export:./workflow_export.xml"
crawl scan --source "pctr-export:./directory_of_exports/"
```

Parses POWERMART XML exports produced by PowerCenter's Repository Manager (File → Export Objects). No database or server access needed — just export the workflow and hand Crawl the XML. Handles `.xml` and `.XML` extensions.

## What Gets Extracted

From each XML export, Crawl extracts the full POWERMART hierarchy:

| XML Element | Crawl Object Type | What It Contains |
|---|---|---|
| `MAPPING` | `mapping` | Transformation logic, source/target tables, expressions, filter conditions, lookup conditions, router groups |
| `SESSION` | `session` | Runtime config binding a mapping to connection parameters |
| `WORKFLOW` | `workflow` | Orchestration DAG of sessions and tasks with execution links and variables |

### Transformation Types Recognized

Expression, Filter, Aggregator, Lookup Procedure, Source Qualifier, Router, Sequence Generator, Stored Procedure, Update Strategy, Joiner, Sorter, Union, Normalizer, and all other PowerCenter transformation types.

### Business Logic Captured

For each mapping, Crawl captures:

- **Expression fields** — computed columns (e.g., `LOG_CODE = 62`, `WF_NAME = $PMWorkflowName`)
- **Filter conditions** — row filtering logic (e.g., `BASE_RATE <= DISCOUNT_RATE OR BASE_RATE <= 0`)
- **Lookup conditions** — join logic against reference tables
- **SQL overrides** — custom SQL queries, pre/post SQL, user-defined joins
- **Router groups** — conditional routing with named groups and expressions
- **Sequence generators** — surrogate key generation

### Dependencies Captured

| Dependency Type | Meaning |
|---|---|
| `data_flow` | Port-to-port data movement within a mapping (from CONNECTORs) |
| `references` | Session references its underlying mapping |
| `contains` | Workflow contains a session |
| `executes_after` | Task execution ordering within a workflow (from WORKFLOWLINKs) |
| `executes_after(condition)` | Conditional execution (e.g., on session failure) |

## XML Structure Reference

PowerCenter exports follow the `powrmart.dtd` schema:

```
POWERMART
  └── REPOSITORY (name, version, codepage, databasetype)
      └── FOLDER (name, owner, uuid)
          ├── SOURCE (table/file definition with SOURCEFIELDs)
          ├── TARGET (table definition with TARGETFIELDs)
          ├── MAPPLET (reusable transformation fragment)
          ├── MAPPING (transformation logic)
          │   ├── TRANSFORMATION (Expression, Filter, Lookup, etc.)
          │   ├── INSTANCE (placed copy of transformation/source/target)
          │   └── CONNECTOR (port-to-port data flow)
          ├── SESSION (runtime config for a mapping)
          └── WORKFLOW (orchestration DAG)
              ├── TASK (Event Wait, Control, Email, etc.)
              ├── TASKINSTANCE (placed session/task in the DAG)
              └── WORKFLOWLINK (execution dependency with optional condition)
```

## Usage

```bash
# Single file
crawl scan --source "pctr-export:./wf_LOAD.xml"

# Directory of exports
crawl scan --source "pctr-export:./exports/"
```

The parser accepts individual workflow XML files or a directory containing multiple exports. Each file is parsed independently and results are merged into a single `ScanResult`.
