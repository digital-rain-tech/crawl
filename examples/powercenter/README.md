# PowerCenter demo: fictional retail warehouse

`retail_nightly.xml` is a PowerCenter repository export for a made-up retail chain. Use it for
demos, screenshots and videos. The company, tables and rules are invented. No part of it
comes from a customer export.

## What is in it

One folder (`RETAIL_EDW`) and one nightly workflow that loads a three-layer warehouse:

| Layer | Mappings | What they do |
|---|---|---|
| ODS | 4 | Load point-of-sale lines, stores, items and a returns flat file. Convert currency to USD. |
| DW | 5 | Type 2 store and product dimensions. Sales and returns facts. A history reload for sales, run by hand. |
| DM | 3 | Daily store revenue, weekly product margin, loyalty segments. |
| Legacy | 1 | `m_LEGACY_PROMO_EXTRACT`. No session runs it. |

The business rules in it are the kind that nobody wrote down:

- **Fiscal calendar:** the year starts on 1 February, with 4-4-5 periods (`m_DW_LOAD_FACT_SALES`).
- **Loyalty discount:** members get 2% off orders above $100. The rule sits inside the net amount
  calculation (`m_DW_LOAD_FACT_SALES`).
- **Restocking fee:** 15% on opened items returned after 14 days, unless the item is defective.
  No refund after 90 days (`m_DW_LOAD_FACT_RETURNS`).
- **Loyalty tiers:** fixed spend and visit thresholds in a Router (`m_DM_LOAD_MEMBER_SEGMENT`).
- **Two margin definitions:** `FACT_SALES.MARGIN_AMT` uses net amount. `AGG_PRODUCT_MARGIN`
  uses gross amount. The two numbers do not agree.
- **A reload that drifted:** `m_DW_RELOAD_FACT_SALES_HIST` writes the same `FACT_SALES` table
  as the nightly load, but uses ISO weeks for `FISCAL_WEEK` and leaves out the loyalty discount
  in `NET_AMT`. Back-filled history does not match daily data.
- **Oracle-only SQL:** `SYSDATE`, `NVL`, `DECODE`, `ROWNUM`, `(+)` outer joins, `DBMS_STATS`.

## What Crawl reports

| Finding | Result |
|---|---|
| Objects | 13 mappings, 12 sessions, 1 workflow |
| Contradictions | 2: `FACT_SALES.NET_AMT` and `FACT_SALES.FISCAL_WEEK` (nightly load vs. history reload) |
| Oracle-specific SQL | 27 flags across 11 mappings |
| Most complex mapping | `m_DW_LOAD_FACT_SALES` |
| Unscheduled mapping | `m_LEGACY_PROMO_EXTRACT` has no session (visible in the scan table, not yet flagged by the report) |

Crawl does not find the two margin definitions. They write to different columns, and the
contradiction check compares one column at a time. The LLM explanations describe both.

## Run it

```bash
pip install -e ".[dev]"
crawl scan --source pctr-export:examples/powercenter/retail_nightly.xml
```

With an OpenRouter key, Crawl can also explain the most complex mappings in plain English:

```bash
export OPENROUTER_API_KEY=...
python scripts/llm_top10.py examples/powercenter/retail_nightly.xml --output /tmp/retail-top10.md
```

## Change it

Edit `generate_retail_demo.py`, then regenerate the XML:

```bash
python examples/powercenter/generate_retail_demo.py
```
