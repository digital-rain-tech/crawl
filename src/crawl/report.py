"""Report generator — produces Markdown from scan + analysis results."""

from __future__ import annotations

from crawl.analysis import AnalysisResult
from crawl.models import ScanResult


def generate_markdown(scan: ScanResult, analysis: AnalysisResult) -> str:
    """Generate a full Markdown migration intelligence report."""
    lines: list[str] = []

    # Header
    lines.append("# Crawl — Migration Intelligence Report")
    lines.append("")
    lines.append(f"**Objects discovered:** {analysis.summary['total_mappings']} mappings, "
                 f"{analysis.summary['total_expressions']} expressions, "
                 f"{analysis.summary['total_dependencies']} dependencies")
    lines.append("")

    # Executive summary
    lines.append("## Executive Summary")
    lines.append("")
    risks_high = analysis.summary.get("high_severity_risks", 0)
    contras = analysis.summary.get("contradictions_found", 0)
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    lines.append(f"| Migration risks | **{analysis.summary['migration_risks']}** "
                 f"({risks_high} high severity) |")
    lines.append(f"| Contradictions | **{contras}** |")
    lines.append(f"| Orphan datastores | {analysis.summary['orphan_datastores']} |")
    lines.append(f"| Average complexity score | {analysis.summary['avg_complexity']} |")
    lines.append("")

    # Migration Risks
    if analysis.risks:
        lines.append("## Migration Risks")
        lines.append("")
        high_risks = [r for r in analysis.risks if r.severity in ("high", "critical")]
        med_risks = [r for r in analysis.risks if r.severity == "medium"]
        low_risks = [r for r in analysis.risks if r.severity == "low"]

        if high_risks:
            lines.append("### High Severity")
            lines.append("")
            for r in high_risks:
                lines.append(f"- **{r.mapping_name}**: {r.description}")
            lines.append("")

        if med_risks:
            lines.append("### Medium Severity")
            lines.append("")
            for r in med_risks:
                lines.append(f"- **{r.mapping_name}**: {r.description}")
            lines.append("")

        if low_risks:
            lines.append("### Low Severity")
            lines.append("")
            for r in low_risks:
                lines.append(f"- **{r.mapping_name}**: {r.description}")
            lines.append("")

    # Contradictions
    if analysis.contradictions:
        lines.append("## Contradictions")
        lines.append("")
        lines.append("These target columns are written by multiple mappings with different logic:")
        lines.append("")
        for c in analysis.contradictions:
            lines.append(f"### {c.target_table}.{c.target_column}")
            lines.append("")
            lines.append("| Mapping | Expression |")
            lines.append("|---|---|")
            lines.append(f"| {c.mapping_a} | `{c.expression_a}` |")
            lines.append(f"| {c.mapping_b} | `{c.expression_b}` |")
            lines.append("")

    # Complexity ranking
    if analysis.complexity_scores:
        lines.append("## Migration Complexity Ranking")
        lines.append("")
        lines.append("Higher score = harder to migrate. Based on expression count, "
                     "number of sources, cross-platform hops, and KM dependencies.")
        lines.append("")
        lines.append("| Score | Mapping | Sources | Targets | Expressions |")
        lines.append("|---|---|---|---|---|")
        for name, score in sorted(analysis.complexity_scores.items(), key=lambda x: -x[1]):
            obj = next((o for o in scan.objects if o.name == name), None)
            if obj:
                src = ", ".join(obj.source_tables) or "—"
                tgt = ", ".join(obj.target_tables) or "—"
                lines.append(f"| **{score}** | {name} | {src} | {tgt} | {len(obj.expressions)} |")
        lines.append("")

    # Data lineage
    if scan.dependencies:
        lines.append("## Data Lineage")
        lines.append("")
        lines.append("| Source | Target | Via Mapping |")
        lines.append("|---|---|---|")
        for dep in sorted(scan.dependencies, key=lambda d: d.dependency_type):
            via = dep.dependency_type.replace("mapping:", "")
            lines.append(f"| {dep.source} | {dep.target} | {via} |")
        lines.append("")

    # Orphan analysis
    if analysis.orphans:
        terminals = [o for o in analysis.orphans if "terminal" in o.issue]
        externals = [o for o in analysis.orphans if "external" in o.issue]

        lines.append("## Datastore Analysis")
        lines.append("")
        if terminals:
            lines.append("### Terminal Targets (final outputs — never read by another mapping)")
            lines.append("")
            for o in terminals:
                lines.append(f"- **{o.table_name}**")
            lines.append("")

        if externals:
            lines.append("### External Sources (ingested but not produced by any mapping)")
            lines.append("")
            for o in externals:
                lines.append(f"- **{o.table_name}**")
            lines.append("")

    # Mapping details
    lines.append("## Mapping Details")
    lines.append("")
    for obj in sorted(scan.objects, key=lambda o: o.name):
        src = ", ".join(obj.source_tables) if obj.source_tables else "(none)"
        tgt = ", ".join(obj.target_tables) if obj.target_tables else "(none)"
        score = analysis.complexity_scores.get(obj.name, 0)
        lines.append(f"### {obj.name}")
        lines.append("")
        lines.append(f"**Complexity: {score}** | "
                     f"Sources: {src} | Targets: {tgt}")
        lines.append("")
        if obj.expressions:
            lines.append("| Expression |")
            lines.append("|---|")
            for expr in obj.expressions:
                safe = expr.replace("|", "\\|").replace("\n", " ")
                lines.append(f"| `{safe}` |")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("*Generated by [Crawl](https://github.com/digital-rain-tech/crawl) v0.1.0*")

    return "\n".join(lines)
