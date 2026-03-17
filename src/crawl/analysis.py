"""Post-scan analysis — the stuff ODI Studio can't tell you.

Takes a ScanResult and produces migration intelligence:
- Contradiction detection (same target column, different logic)
- Migration risk scoring (vendor-specific syntax, cross-platform hops)
- Dead code / orphan detection (unused datastores, never-executed mappings)
- Complexity scoring
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from crawl.models import ScanResult


@dataclass
class Contradiction:
    """Two mappings compute the same target column with different logic."""

    target_table: str
    target_column: str
    mapping_a: str
    expression_a: str
    mapping_b: str
    expression_b: str
    severity: str = "warning"  # warning or error


@dataclass
class MigrationRisk:
    """A migration risk flag on a specific mapping."""

    mapping_name: str
    risk_type: str  # vendor_specific, cross_platform, complexity, no_execution_history
    description: str
    severity: str = "medium"  # low, medium, high, critical


@dataclass
class OrphanDatastore:
    """A datastore that appears as source/target but has issues."""

    table_name: str
    issue: str  # "write_only" (never read), "read_only" (never written), "orphan" (neither)


@dataclass
class AnalysisResult:
    """Complete analysis output — the wow factor."""

    contradictions: list[Contradiction] = field(default_factory=list)
    risks: list[MigrationRisk] = field(default_factory=list)
    orphans: list[OrphanDatastore] = field(default_factory=list)
    complexity_scores: dict[str, int] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)


# Vendor-specific patterns that signal migration risk
_VENDOR_PATTERNS = [
    (r"\bSYSDATE\b", "Oracle SYSDATE — replace with target-specific date function"),
    (r"\bNVL\b", "Oracle NVL — replace with COALESCE"),
    (r"\bDECODE\b", "Oracle DECODE — replace with CASE WHEN"),
    (r"\bROWNUM\b", "Oracle ROWNUM — replace with ROW_NUMBER() or LIMIT"),
    (r"\bCONNECT\s+BY\b", "Oracle hierarchical query — rewrite for target platform"),
    (r"\bDBMS_\w+", "Oracle DBMS_ package — no equivalent in most targets"),
    (r"\bUTL_\w+", "Oracle UTL_ package — no equivalent in most targets"),
    (r"\bTO_DATE\b", "Oracle TO_DATE — replace with target date parsing"),
    (r"\bTO_CHAR\b", "Oracle TO_CHAR — replace with target string conversion"),
    (r"\bTO_NUMBER\b", "Oracle TO_NUMBER — replace with CAST"),
    (r"\(\+\)", "Oracle outer join syntax — replace with ANSI LEFT/RIGHT JOIN"),
    (r"\bDUAL\b", "Oracle DUAL table — not needed on most platforms"),
    (r"\bSQOOP\b", "Sqoop dependency — consider replacing with Spark/native connector"),
    (r"\bOLH\b", "Oracle Loader for Hadoop — platform-specific, needs alternative"),
    (r"Big Data SQL", "Big Data SQL — Oracle-specific cross-engine query, needs rewrite"),
]


def analyze(scan_result: ScanResult) -> AnalysisResult:
    """Run all analysis passes on a scan result."""
    result = AnalysisResult()

    _detect_contradictions(scan_result, result)
    _detect_migration_risks(scan_result, result)
    _detect_orphans(scan_result, result)
    _score_complexity(scan_result, result)
    _build_summary(scan_result, result)

    return result


def _detect_contradictions(scan: ScanResult, out: AnalysisResult) -> None:
    """Find cases where multiple mappings write to the same target column differently."""
    # Group expressions by target table + column
    target_writes: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for obj in scan.objects:
        for expr in obj.expressions:
            # Parse "TARGET.COLUMN = <logic>" pattern
            match = re.match(r"^(\w+)\.(\w+)\s*=\s*(.+)$", expr.strip())
            if not match:
                continue
            component, column, logic = match.groups()

            # Check if this component is a target datastore
            for tgt in obj.target_tables:
                tgt_short = tgt.split(".")[-1]  # "OracleMovie.MOVIE" → "MOVIE"
                if component.upper() == tgt_short.upper() or component.upper() in tgt.upper():
                    key = f"{tgt}.{column}".upper()
                    target_writes[key].append((obj.name, logic.strip()))
                    break

    # Find contradictions — same target column, different logic
    for key, writes in target_writes.items():
        if len(writes) < 2:
            continue
        # Compare each pair
        seen_logic: dict[str, str] = {}  # normalized_logic → first mapping
        for mapping_name, logic in writes:
            normalized = re.sub(r"\s+", " ", logic.upper().strip())
            if normalized in seen_logic:
                continue  # Same logic, no contradiction
            for prev_logic, prev_mapping in seen_logic.items():
                if prev_logic != normalized:
                    parts = key.split(".", 1)
                    target_table = parts[0] if len(parts) > 0 else key
                    target_column = parts[1] if len(parts) > 1 else ""
                    out.contradictions.append(Contradiction(
                        target_table=target_table,
                        target_column=target_column,
                        mapping_a=prev_mapping,
                        expression_a=prev_logic.lower(),
                        mapping_b=mapping_name,
                        expression_b=logic,
                        severity="warning",
                    ))
            seen_logic[normalized] = mapping_name


def _detect_migration_risks(scan: ScanResult, out: AnalysisResult) -> None:
    """Flag vendor-specific syntax and cross-platform concerns."""
    for obj in scan.objects:
        all_text = " ".join(obj.expressions)
        if obj.source_code:
            all_text += " " + obj.source_code

        # Check vendor-specific patterns
        for pattern, description in _VENDOR_PATTERNS:
            if re.search(pattern, all_text, re.IGNORECASE):
                out.risks.append(MigrationRisk(
                    mapping_name=obj.name,
                    risk_type="vendor_specific",
                    description=description,
                    severity="medium",
                ))

        # Cross-platform hops (source and target in different models/platforms)
        source_platforms = {s.split(".")[0] for s in obj.source_tables if "." in s}
        target_platforms = {t.split(".")[0] for t in obj.target_tables if "." in t}
        all_platforms = source_platforms | target_platforms
        if len(all_platforms) > 1:
            out.risks.append(MigrationRisk(
                mapping_name=obj.name,
                risk_type="cross_platform",
                description=f"Cross-platform data movement: {' → '.join(sorted(all_platforms))}",
                severity="high",
            ))

        # No execution history
        if obj.execution_count is None or obj.execution_count == 0:
            if obj.last_executed is None:
                out.risks.append(MigrationRisk(
                    mapping_name=obj.name,
                    risk_type="no_execution_history",
                    description="No execution history — may be dead code or untested",
                    severity="low",
                ))


def _detect_orphans(scan: ScanResult, out: AnalysisResult) -> None:
    """Find datastores that are written but never read, or vice versa."""
    all_sources: set[str] = set()
    all_targets: set[str] = set()

    for obj in scan.objects:
        for s in obj.source_tables:
            all_sources.add(s)
        for t in obj.target_tables:
            all_targets.add(t)

    # Written but never read downstream
    write_only = all_targets - all_sources
    for t in sorted(write_only):
        out.orphans.append(OrphanDatastore(
            table_name=t,
            issue="terminal_target — written but never read by another mapping (may be a final output)",
        ))

    # Read but never written by any mapping (external source)
    read_only = all_sources - all_targets
    for s in sorted(read_only):
        out.orphans.append(OrphanDatastore(
            table_name=s,
            issue="external_source — read but not produced by any mapping in this repository",
        ))


def _score_complexity(scan: ScanResult, out: AnalysisResult) -> None:
    """Score each mapping's migration complexity."""
    for obj in scan.objects:
        score = 0
        # Base: number of expressions
        score += len(obj.expressions) * 2
        # Sources: each additional source adds complexity
        score += max(0, len(obj.source_tables) - 1) * 5
        # Cross-platform adds complexity
        platforms = set()
        for s in obj.source_tables:
            if "." in s:
                platforms.add(s.split(".")[0])
        for t in obj.target_tables:
            if "." in t:
                platforms.add(t.split(".")[0])
        if len(platforms) > 1:
            score += 10
        # KM count adds complexity
        score += len(obj.knowledge_modules) * 2

        out.complexity_scores[obj.name] = score


def _build_summary(scan: ScanResult, out: AnalysisResult) -> None:
    """Build summary statistics."""
    out.summary = {
        "total_mappings": len(scan.objects),
        "total_dependencies": len(scan.dependencies),
        "total_expressions": sum(len(o.expressions) for o in scan.objects),
        "contradictions_found": len(out.contradictions),
        "migration_risks": len(out.risks),
        "high_severity_risks": sum(1 for r in out.risks if r.severity in ("high", "critical")),
        "orphan_datastores": len(out.orphans),
        "avg_complexity": (
            round(sum(out.complexity_scores.values()) / len(out.complexity_scores))
            if out.complexity_scores else 0
        ),
    }
