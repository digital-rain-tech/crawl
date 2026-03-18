# ADR-002: Demo Readiness Assessment

**Date:** 2026-03-18
**Status:** Accepted (updated 2026-03-18)
**Context:** Evaluating demo readiness for Gloria Fung's customer (ODI → Azure Databricks migration)

## Current State: 7/10

One session produced a working end-to-end pipeline, now with visual lineage diagrams:

```
ODI Repository → Scan (DB or XML) → Analysis → LLM Extraction → Report + Diagrams
```

### What's Strong

- **Real ODI repo scanning** — both live DB (SNP_ tables) and offline XML (Smart Export) modes work against real data
- **Migration risks that ODI Studio can't show** — cross-platform data movement flags, vendor-specific syntax detection (SYSDATE, NVL, DECODE), dead code warnings, complexity ranking
- **LLM business rule extraction** — plain-English explanations via OpenRouter (arcee-ai/trinity-large-preview:free) turning `AVG(@{R0})` into "calculates average movie ratings grouped by movie ID"
- **Full data lineage** with source→target dependency tracking across Oracle, Hive, HDFS, Pig, Spark
- **Orphan detection** — terminal targets (final outputs) and external sources (data boundaries)
- **Audit trail** — every LLM call logged to SQLite with model, tokens, timing, full request/response
- **Clean architecture** — common IR, dual parser modes, pluggable LLM backend, source-agnostic analysis
- **Visual lineage diagrams** — Excalidraw hand-drawn style diagrams showing ETL pipeline flow and product architecture, exportable to SVG/PNG (see ADR-003)

### What's Missing to Reach 8-9

1. **No CLI `crawl extract` command** — LLM step is only callable from Python, not wired into the CLI pipeline as a proper command
2. ~~**Markdown-only report** — for a non-technical audience, a rendered HTML or PDF with a visual lineage diagram would land harder~~ **Partially addressed** — Excalidraw lineage diagram created (ADR-003), but not yet auto-generated from scan results or embedded in the markdown report
3. **Contradiction detection found 0** — the sample repo is too clean. Need either a seeded contradiction for the demo or a real messy customer repo where this shines
4. **No `crawl triage` command** — the analysis engine exists in code but isn't exposed as a CLI step
5. **Empty LLM explanations on some mappings** — free model rate limits cause empty responses. Need retry logic or a paid tier fallback
6. **`@{R0}` reference expressions are opaque** — showing raw ODI template references in the report. Resolving these to actual column names would make the expressions table readable

### What Would Make It a 10

1. ~~**Visual lineage diagram** — Mermaid or Graphviz → SVG showing the full pipeline flow~~ **Done** — Excalidraw diagrams created (ADR-003), hand-drawn style exported to SVG/PNG
2. **Auto-generated lineage from scan results** — wire diagram generation into `crawl export` so every scan produces a visual lineage automatically
3. **One killer contradiction example** — "these two mappings calculate revenue differently" is the moment that sells the tool
4. **Interactive mode** — "ask questions about your ETL" with conversational LLM over scan results
5. **Side-by-side comparison** — "here's what ODI Studio shows you" vs "here's what Crawl tells you"
6. **Resolved expressions** — replace `@{R0}` with actual source column names from the component graph

## Decision

Prioritize the following for demo readiness, in order:

1. Wire `crawl extract` and `crawl triage` CLI commands to the analysis + LLM engines
2. ~~Add Mermaid lineage diagram generation to the report~~ → Replaced with Excalidraw approach (ADR-003). Next step: auto-generate from ScanResult
3. Add LLM retry/fallback logic for empty responses
4. Resolve `@{R0}` references to actual column names
5. Seed or find a contradiction example for demo impact

Items 1 and 3 are blockers for a customer-facing demo. Items 4-5 are polish that significantly increase wow factor. Item 2 has a manual diagram available now; auto-generation is a stretch goal.
