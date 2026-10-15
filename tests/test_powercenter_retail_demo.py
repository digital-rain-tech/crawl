"""Tests for the fictional retail demo export in examples/powercenter/."""

from pathlib import Path

import pytest

from crawl.analysis import analyze
from crawl.models import ObjectType
from crawl.parsers.powercenter.xml import PctrXmlParser
from crawl.report import generate_markdown

EXAMPLES = Path(__file__).parent.parent / "examples" / "powercenter"


@pytest.fixture(scope="module")
def result():
    return PctrXmlParser(str(EXAMPLES / "retail_nightly.xml")).scan()


def test_committed_xml_matches_generator():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "generate_retail_demo", EXAMPLES / "generate_retail_demo.py"
    )
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    committed = (EXAMPLES / "retail_nightly.xml").read_text(encoding="utf-8")
    assert committed == gen.build(), "Regenerate with generate_retail_demo.py"


def test_object_counts(result):
    by_type = {t: [o for o in result.objects if o.object_type == t] for t in ObjectType}
    assert len(by_type[ObjectType.MAPPING]) == 13
    assert len(by_type[ObjectType.SESSION]) == 12
    assert len(by_type[ObjectType.WORKFLOW]) == 1


def test_legacy_mapping_has_no_session(result):
    referenced = {d.target for d in result.dependencies if d.dependency_type == "references"}
    assert "m_LEGACY_PROMO_EXTRACT" not in referenced
    assert "m_DW_LOAD_FACT_SALES" in referenced


def test_fact_sales_business_rules(result):
    m = next(o for o in result.objects if o.name == "m_DW_LOAD_FACT_SALES")
    assert m.source_tables == ["ODS_ITEM", "ODS_SALES_LINE"]
    assert m.target_tables == ["FACT_SALES"]
    text = " ".join(m.expressions)
    assert "FISCAL_WEEK" in text
    assert "0.02" in text  # loyalty discount
    assert "User Defined Join" in text


def test_router_groups_extracted(result):
    m = next(o for o in result.objects if o.name == "m_DM_LOAD_MEMBER_SEGMENT")
    groups = [e for e in m.expressions if "Router] Group" in e]
    assert len(groups) == 3


def test_failure_branch_in_workflow(result):
    failed = [d for d in result.dependencies if "FAILED" in d.dependency_type]
    assert len(failed) == 1
    assert failed[0].target == "wf_RETAIL_NIGHTLY/em_NOTIFY_FAILURE"


def test_target_writes_traced_through_pass_through_ports(result):
    m = next(o for o in result.objects if o.name == "m_DW_LOAD_FACT_SALES")
    # NET_AMT is computed in EXP_SALES_AMOUNTS, the last transformation
    assert "0.02" in m.target_writes["FACT_SALES.NET_AMT"]
    # FISCAL_WEEK is computed one transformation earlier and passes through
    assert "FY_START" in m.target_writes["FACT_SALES.FISCAL_WEEK"]
    # Straight copies are not business logic
    assert "FACT_SALES.QTY" not in m.target_writes


def test_data_flow_dependencies_deduplicated(result):
    flow = [(d.source, d.target) for d in result.dependencies if d.dependency_type == "data_flow"]
    assert len(flow) == len(set(flow))


def test_analysis_finds_history_reload_contradictions(result):
    analysis = analyze(result)
    found = {(c.target_table, c.target_column) for c in analysis.contradictions}
    assert found == {("FACT_SALES", "NET_AMT"), ("FACT_SALES", "FISCAL_WEEK")}
    for c in analysis.contradictions:
        assert {c.mapping_a, c.mapping_b} == {
            "m_DW_LOAD_FACT_SALES", "m_DW_RELOAD_FACT_SALES_HIST"
        }


def test_analysis_counts_and_scores_only_logic_objects(result):
    analysis = analyze(result)
    assert analysis.summary["total_mappings"] == 13
    assert analysis.summary["total_objects"] == 26
    assert analysis.objects_by_type == {"mapping": 13, "session": 12, "workflow": 1}
    assert "wf_RETAIL_NIGHTLY" not in analysis.complexity_scores
    assert "s_DW_LOAD_FACT_SALES" not in analysis.complexity_scores


def test_no_execution_history_flags_without_run_stats(result):
    analysis = analyze(result)
    assert not [r for r in analysis.risks if r.risk_type == "no_execution_history"]


def test_execution_history_flags_when_source_has_run_stats(result):
    ran = next(o for o in result.objects if o.name == "m_DW_LOAD_FACT_SALES")
    ran.execution_count = 30
    try:
        flagged = {r.mapping_name for r in analyze(result).risks
                   if r.risk_type == "no_execution_history"}
    finally:
        ran.execution_count = None
    assert "m_LEGACY_PROMO_EXTRACT" in flagged
    assert "m_DW_LOAD_FACT_SALES" not in flagged


def test_report_header(result):
    md = generate_markdown(result, analyze(result))
    assert "13 mappings, 12 sessions, 1 workflow" in md
    assert "## Contradictions" in md


def test_different_constants_are_not_contradictions():
    from crawl.models import DataObject, ScanResult, SourcePlatform

    def mapping(name, logic):
        return DataObject(
            name=name, object_type=ObjectType.MAPPING, platform=SourcePlatform.POWERCENTER,
            target_tables=["REJECTS"], target_writes={"REJECTS.ERR_CODE": logic},
        )

    scan = ScanResult(platform=SourcePlatform.POWERCENTER, objects=[
        mapping("m_a", "74"), mapping("m_b", "'E77'"), mapping("m_c", "$$ERR_CODE"),
    ])
    assert analyze(scan).contradictions == []
    scan.objects.append(mapping("m_d", "IIF(QTY < 0, 1, 2)"))
    assert len(analyze(scan).contradictions) == 3
