# LLM Extraction

Crawl can use an LLM to explain what each mapping does in plain English business terms. This helps stakeholders understand the transformation logic without reading raw SQL expressions.

The `explain_mapping()` function in `src/crawl/llm.py` is **source-agnostic** — it works for any ETL platform (ODI, PowerCenter, etc.).

## Setup

```bash
pip install -e ".[llm]"
export OPENROUTER_API_KEY="sk-or-v1-..."  # Get free key at https://openrouter.ai/keys
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | (required) | API key from OpenRouter |
| `CRAWL_LLM_MODEL` | `arcee-ai/trinity-large-preview:free` | Model to use |
| `CRAWL_LLM_BASE_URL` | `https://openrouter.ai/api/v1` | API endpoint override |

## Usage

Run the extraction script on the top N most complex mappings:

```bash
python scripts/llm_top10.py --help
python scripts/llm_top10.py  # Default: top 10 by complexity score
```

The script:

1. Parses exports from `confidential/` (PowerCenter) or connects to DB (ODI)
2. Sorts mappings by expression count (proxy for complexity)
3. Calls `explain_mapping()` on the top N
4. Saves results to `docs/internal/<source>/llm-explanations-top10.md`

### How It Works

The `explain_mapping()` function in `src/crawl/llm.py`:

1. Takes a mapping's name, source tables, target tables, and transformation expressions
2. Sends to the LLM with a system prompt asking for business logic explanation
3. Returns a 2-3 sentence plain English description of what the mapping does

Example output:

```
A - Load Movies (Sqoop)
  → Loads movie data from Oracle into Hive for downstream analytics

C - Calc Ratings (Hive - Pig - Spark)
  → Calculates aggregate movie ratings by joining movie metadata with
    clickstream data, computing average ratings per movie

G - Sessionize Data (Pig)
  → Sessionizes user click logs and calculates session duration metrics
    grouped by customer country
```

## Audit Logging

All LLM requests are logged to `crawl_llm_log.db` (SQLite) with:

- Request ID, model, use case
- Full prompt and response text
- Token count (prompt/completion/total)
- Response time in milliseconds
- Raw request/response JSON for debugging

This enables cost tracking and audit trails for customer reports.

## Customization

To run LLM extraction on a different source or different top N:

1. Modify `scripts/llm_top10.py` to use a different parser (e.g., `OdiDbParser` or `OdiXmlParser`)
2. Adjust the sort criteria (expression count, complexity score, etc.)
3. Change the `--limit` parameter to control how many mappings to explain
