#!/usr/bin/env python3
"""Run LLM extraction on the top 10 most complex PowerCenter mappings."""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Force the model before any crawl imports read env
MODEL = os.environ.get("CRAWL_LLM_MODEL", "anthropic/claude-sonnet-4")
os.environ["CRAWL_LLM_MODEL"] = MODEL

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from crawl.parsers.powercenter.xml import PctrXmlParser
from crawl.llm import call_llm

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_prompt(mapping_name, source_tables, target_tables, expressions):
    """Build the same prompt as explain_mapping but return it for direct call_llm use."""
    system_prompt = (
        "You are a data engineering expert analyzing ETL mappings for a migration assessment. "
        "Given a mapping's source tables, target tables, and transformation expressions, "
        "explain what business logic this mapping implements in 2-3 clear sentences. "
        "Focus on WHAT the mapping does (business purpose), not HOW (technical details). "
        "If you can identify the business domain (e.g., customer analytics, sales reporting), mention it. "
        "Be specific about calculations, aggregations, and data transformations."
    )

    expr_text = "\n".join(f"  - {e}" for e in expressions[:30])
    prompt = (
        f"Mapping: {mapping_name}\n"
        f"Source tables: {', '.join(source_tables)}\n"
        f"Target tables: {', '.join(target_tables)}\n"
        f"Transformation expressions:\n{expr_text}\n\n"
        f"Explain what business logic this mapping implements:"
    )
    return system_prompt, prompt


def main():
    print(f"Model: {MODEL}")
    print(f"Parsing confidential exports...")

    parser = PctrXmlParser(str(REPO_ROOT / "confidential"))
    result = parser.scan()

    # Filter to mappings only
    from crawl.models import ObjectType
    mappings = [obj for obj in result.objects if obj.object_type == ObjectType.MAPPING]
    print(f"Found {len(mappings)} mappings total")

    # Sort by expression count descending
    mappings.sort(key=lambda m: len(m.expressions), reverse=True)

    top10 = mappings[:10]
    print(f"\nTop 10 by expression count:")
    for i, m in enumerate(top10, 1):
        print(f"  {i}. {m.name} ({len(m.expressions)} exprs, {len(m.source_tables)} src, {len(m.target_tables)} tgt)")

    results = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_time_ms = 0

    for i, m in enumerate(top10, 1):
        print(f"\n[{i}/10] Calling LLM for {m.name}...")
        system_prompt, prompt = build_prompt(m.name, m.source_tables, m.target_tables, m.expressions)

        try:
            resp = call_llm(
                prompt=prompt,
                system_prompt=system_prompt,
                use_case="explain_mapping",
                max_tokens=2048,
            )
            results.append({
                "rank": i,
                "name": m.name,
                "expr_count": len(m.expressions),
                "src_count": len(m.source_tables),
                "tgt_count": len(m.target_tables),
                "source_tables": m.source_tables,
                "target_tables": m.target_tables,
                "explanation": resp.text.strip(),
                "prompt_tokens": resp.prompt_tokens,
                "completion_tokens": resp.completion_tokens,
                "total_tokens": resp.total_tokens,
                "response_time_ms": resp.response_time_ms,
            })
            total_prompt_tokens += resp.prompt_tokens
            total_completion_tokens += resp.completion_tokens
            total_time_ms += resp.response_time_ms
            print(f"    Done ({resp.prompt_tokens}+{resp.completion_tokens} tokens, {resp.response_time_ms}ms)")
        except Exception as e:
            print(f"    ERROR: {e}")
            results.append({
                "rank": i,
                "name": m.name,
                "expr_count": len(m.expressions),
                "src_count": len(m.source_tables),
                "tgt_count": len(m.target_tables),
                "source_tables": m.source_tables,
                "target_tables": m.target_tables,
                "explanation": f"*Error: {e}*",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "response_time_ms": 0,
            })

        # Brief pause between calls to avoid rate limiting
        if i < 10:
            time.sleep(1)

    # Cost estimate for Claude Sonnet 4 via OpenRouter
    # Input: $3/M tokens, Output: $15/M tokens (OpenRouter pricing)
    input_cost = total_prompt_tokens * 3.0 / 1_000_000
    output_cost = total_completion_tokens * 15.0 / 1_000_000
    total_cost = input_cost + output_cost

    # Generate markdown
    md_lines = [
        "# LLM Explanations: Top 10 Most Complex PowerCenter Mappings",
        "",
        f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"> Model: `{MODEL}`",
        "",
        "## Summary",
        "",
        "| # | Mapping | Expressions | Sources | Targets |",
        "|---|---------|-------------|---------|---------|",
    ]
    for r in results:
        md_lines.append(
            f"| {r['rank']} | `{r['name']}` | {r['expr_count']} | {r['src_count']} | {r['tgt_count']} |"
        )

    md_lines.extend(["", "---", ""])

    for r in results:
        md_lines.extend([
            f"## {r['rank']}. `{r['name']}`",
            "",
            f"**Expressions:** {r['expr_count']} | "
            f"**Sources:** {', '.join(r['source_tables'])} | "
            f"**Targets:** {', '.join(r['target_tables'])}",
            "",
            r["explanation"],
            "",
            f"*Tokens: {r['prompt_tokens']} prompt + {r['completion_tokens']} completion = {r['total_tokens']} total | {r['response_time_ms']}ms*",
            "",
            "---",
            "",
        ])

    md_lines.extend([
        "## Cost Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Model | `{MODEL}` |",
        f"| Total prompt tokens | {total_prompt_tokens:,} |",
        f"| Total completion tokens | {total_completion_tokens:,} |",
        f"| Total tokens | {total_prompt_tokens + total_completion_tokens:,} |",
        f"| Total response time | {total_time_ms / 1000:.1f}s |",
        f"| Estimated input cost | ${input_cost:.4f} |",
        f"| Estimated output cost | ${output_cost:.4f} |",
        f"| **Estimated total cost** | **${total_cost:.4f}** |",
        "",
        "*Cost estimate based on OpenRouter pricing for Claude Sonnet 4: $3/M input, $15/M output tokens.*",
    ])

    md_content = "\n".join(md_lines) + "\n"

    # Save to docs/internal/powercenter/
    output_path = REPO_ROOT / "docs" / "internal" / "powercenter" / "llm-explanations-top10.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md_content)
    print(f"\nSaved to {output_path}")
    print(f"\nTotal: {total_prompt_tokens + total_completion_tokens:,} tokens, ${total_cost:.4f} estimated cost")


if __name__ == "__main__":
    main()
