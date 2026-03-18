# ADR-003: Visual Lineage Diagrams with Excalidraw

**Date:** 2026-03-18
**Status:** Accepted
**Context:** Demo needs visual ETL pipeline diagrams to make migration complexity immediately tangible for customer presentations

## Problem

The text-only migration report (tables of dependencies, expressions, risk flags) is hard for a non-technical audience to absorb. Gloria's customer needs to see the complexity of their ODI pipeline at a glance — how data flows across Oracle, Hive, HDFS, Pig, and Spark — to understand why a migration is risky.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Mermaid** | Built-in to GitHub markdown rendering, simple syntax | Rigid auto-layout, no hand-drawn feel, limited styling |
| **Graphviz** | Powerful auto-layout, good for large graphs | Ugly defaults, requires separate install, no interactivity |
| **Excalidraw** | Hand-drawn aesthetic, editable in browser, JSON format easily generated from code | No pure-Node renderer (needs browser for export), larger file size |
| **D3.js / custom SVG** | Full control over rendering | Heavy engineering lift for one-off diagrams |

## Decision

**Use Excalidraw** for demo visual diagrams.

### Rationale

1. **Hand-drawn style sells the story** — looks like a whiteboard sketch, not a generated report. This lands better in a customer demo than a sterile auto-layout.
2. **JSON format is code-friendly** — Excalidraw files are plain JSON with positioned rectangles, arrows, and text. A Python script can generate them from `ScanResult` data.
3. **Editable after generation** — drag the `.excalidraw` file to excalidraw.com to tweak positioning, add annotations, or restyle before a specific customer demo.
4. **Export to SVG/PNG for embedding** — images can be dropped into slide decks, markdown reports, or HTML pages.

### Export Tooling

Excalidraw rendering depends on browser canvas (custom fonts, shape roughness). There is no pure Node.js or Python renderer. After evaluating several options:

| Tool | Works? | Notes |
|------|--------|-------|
| Kroki API (`POST /excalidraw/svg`) | No | 403 from our environment |
| `@excalidraw/utils` (Node.js) | No | Requires browser DOM (`window is not defined`) |
| `@excalidraw/excalidraw` npm + local HTML | No | ESM + React dependency, needs bundler |
| **`excalidraw-brute-export-cli`** | **Yes** | Automates excalidraw.com via Playwright+Firefox. Simple CLI. |
| Manual (drag to excalidraw.com → Export) | Yes | Fallback, takes ~10 seconds per diagram |

**Chosen: `excalidraw-brute-export-cli`** for automated export.

```bash
# Install (one-time)
npm install excalidraw-brute-export-cli
npx playwright install firefox

# Export
npx excalidraw-brute-export-cli -i diagram.excalidraw -o diagram.svg -f svg -s 2
npx excalidraw-brute-export-cli -i diagram.excalidraw -o diagram.png -f png -s 2

# Or use the wrapper script
python docs/diagrams/export_images.py
```

## Diagrams Created

### 1. ETL Pipeline Lineage (`etl-pipeline-lineage.excalidraw`)

The main demo visual. Shows the full ODI Movie Pipeline data flow:

- **Color-coded by platform**: amber = Oracle, blue = Hive/Hadoop, green = HDFS
- **8 mappings** (A through G + Populate) with directional arrows
- **Risk callouts** (red): SYSDATE translation, cross-platform hops, mixed-source queries
- **Terminal targets** marked with ★
- **Summary box**: key metrics (mappings, hops, vendor syntax, dead code risk)
- **Legend**: explains color scheme and symbols

### 2. Crawl Architecture (`crawl-architecture.excalidraw`)

Product explainer showing how Crawl works:

- **Pipeline flow**: `scan → extract → triage → export`
- **Parser registry**: ODI DB, ODI XML, PostgreSQL (planned)
- **Common IR**: ScanResult with all model types
- **Analysis engine**: sqlglot AST + LLM + risk detection
- **Export formats**: Markdown, JSON, dbt-docs YAML
- **Safety model** and **"What ODI Studio can't show"** callouts

## File Structure

```
docs/diagrams/
├── etl-pipeline-lineage.excalidraw   # Editable source (JSON)
├── etl-pipeline-lineage.svg          # Exported SVG (2x scale)
├── etl-pipeline-lineage.png          # Exported PNG (2x scale)
├── crawl-architecture.excalidraw     # Editable source (JSON)
├── crawl-architecture.svg            # Exported SVG (2x scale)
├── crawl-architecture.png            # Exported PNG (2x scale)
├── generate_diagrams.py              # Python generator (regenerate from scratch)
├── export_images.py                  # Export wrapper script
└── .gitignore                        # Excludes node_modules/, package*.json
```

## Future Work

1. **Auto-generate from ScanResult** — wire `generate_diagrams.py` logic into `crawl export` so every scan produces a lineage diagram automatically, positioned based on dependency graph topology.
2. **Embed in markdown report** — inline the SVG or reference the PNG from `report.py` output.
3. **Interactive HTML export** — embed the Excalidraw React component in an HTML report for pan/zoom/hover.

## Consequences

- `.excalidraw` files are committed to the repo (JSON, ~50-80 KB each)
- Exported SVG/PNG are also committed for convenience (no Node.js required to view)
- `node_modules/` stays gitignored — only needed for re-export
- The generator script (`generate_diagrams.py`) serves as documentation of the diagram structure and can be adapted for auto-generation
