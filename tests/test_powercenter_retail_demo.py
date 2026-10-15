"""Tests for the fictional retail demo export in examples/powercenter/."""

from pathlib import Path

import pytest

from crawl.models import ObjectType
from crawl.parsers.powercenter.xml import PctrXmlParser

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
    assert len(by_type[ObjectType.MAPPING]) == 12
    assert len(by_type[ObjectType.SESSION]) == 11
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
