"""Tests for the PowerCenter XML parser using synthetic POWERMART fixtures."""

from pathlib import Path

import pytest

from crawl.models import ObjectType, SourcePlatform
from crawl.parsers.powercenter.xml import PctrXmlParser
from crawl.parsers.registry import resolve_parser

FIXTURES = Path(__file__).parent / "fixtures" / "powercenter"


# ------------------------------------------------------------------
# Connection / validation
# ------------------------------------------------------------------


class TestPctrXmlParserConnection:
    def test_valid_xml_file(self):
        parser = PctrXmlParser(str(FIXTURES / "demo_workflow.xml"))
        assert parser.test_connection() is True

    def test_valid_directory(self):
        parser = PctrXmlParser(str(FIXTURES))
        assert parser.test_connection() is True

    def test_nonexistent_path(self):
        parser = PctrXmlParser("/nonexistent/path")
        assert parser.test_connection() is False

    def test_non_powermart_xml(self):
        # ODI fixtures are not POWERMART XML
        odi_fixture = Path(__file__).parent / "fixtures" / "odi" / "IKM_SQL_to_SQL_Append.xml"
        if odi_fixture.exists():
            parser = PctrXmlParser(str(odi_fixture))
            assert parser.test_connection() is False


# ------------------------------------------------------------------
# Registry integration
# ------------------------------------------------------------------


class TestPctrRegistry:
    def test_resolve_pctr_export(self):
        parser = resolve_parser(f"pctr-export:{FIXTURES / 'demo_workflow.xml'}")
        assert isinstance(parser, PctrXmlParser)


# ------------------------------------------------------------------
# Mapping extraction
# ------------------------------------------------------------------


class TestPctrMappingExtraction:
    @pytest.fixture()
    def result(self):
        parser = PctrXmlParser(str(FIXTURES / "demo_workflow.xml"))
        return parser.scan()

    def test_platform(self, result):
        assert result.platform == SourcePlatform.POWERCENTER

    def test_mappings_found(self, result):
        mappings = [o for o in result.objects if o.object_type == ObjectType.MAPPING]
        assert len(mappings) == 2
        names = {m.name for m in mappings}
        assert "m_VAL_PRODUCT_RATE_MAP" in names
        assert "m_LOAD_DIM_PRODUCT" in names

    def test_mapping_has_sources_and_targets(self, result):
        m = next(o for o in result.objects if o.name == "m_VAL_PRODUCT_RATE_MAP")
        assert "PRODUCT_RATE_MAP" in m.source_tables
        assert "ETL_ERR_LOG" in m.target_tables
        assert "PRODUCT_RATE_MAP_BAD" in m.target_tables

    def test_mapping_has_folder(self, result):
        m = next(o for o in result.objects if o.name == "m_VAL_PRODUCT_RATE_MAP")
        assert m.schema == "DEMO_FOLDER"

    def test_mapping_expressions_include_filter(self, result):
        m = next(o for o in result.objects if o.name == "m_VAL_PRODUCT_RATE_MAP")
        filter_exprs = [e for e in m.expressions if "Filter Condition" in e]
        assert len(filter_exprs) >= 1
        assert "BASE_RATE" in filter_exprs[0]

    def test_mapping_expressions_include_lookup_condition(self, result):
        m = next(o for o in result.objects if o.name == "m_VAL_PRODUCT_RATE_MAP")
        lkp_exprs = [e for e in m.expressions if "Lookup condition" in e]
        assert len(lkp_exprs) >= 1
        assert "PRODUCT_ID" in lkp_exprs[0]

    def test_dim_mapping_has_router_groups(self, result):
        m = next(o for o in result.objects if o.name == "m_LOAD_DIM_PRODUCT")
        router_exprs = [e for e in m.expressions if "Router" in e]
        assert len(router_exprs) >= 2  # NEW and CHANGED groups
        group_text = " ".join(router_exprs)
        assert "ISNULL" in group_text

    def test_data_flow_dependencies(self, result):
        flow_deps = [d for d in result.dependencies if d.dependency_type == "data_flow"]
        assert len(flow_deps) > 0
        # Check a specific connector: SQ → LKP in validation mapping
        sq_to_lkp = [
            d
            for d in flow_deps
            if "SQ_PRODUCT_RATE_MAP" in d.source and "LKP_PRODUCT_RATE_MAP" in d.target
        ]
        assert len(sq_to_lkp) >= 1


# ------------------------------------------------------------------
# Session extraction
# ------------------------------------------------------------------


class TestPctrSessionExtraction:
    @pytest.fixture()
    def result(self):
        parser = PctrXmlParser(str(FIXTURES / "demo_workflow.xml"))
        return parser.scan()

    def test_sessions_found(self, result):
        sessions = [o for o in result.objects if o.object_type == ObjectType.SESSION]
        assert len(sessions) == 2
        names = {s.name for s in sessions}
        assert "s_VAL_PRODUCT_RATE_MAP" in names
        assert "s_LOAD_DIM_PRODUCT" in names

    def test_session_references_mapping(self, result):
        ref_deps = [
            d
            for d in result.dependencies
            if d.dependency_type == "references" and d.source == "s_VAL_PRODUCT_RATE_MAP"
        ]
        assert len(ref_deps) == 1
        assert ref_deps[0].target == "m_VAL_PRODUCT_RATE_MAP"


# ------------------------------------------------------------------
# Workflow extraction
# ------------------------------------------------------------------


class TestPctrWorkflowExtraction:
    @pytest.fixture()
    def result(self):
        parser = PctrXmlParser(str(FIXTURES / "demo_workflow.xml"))
        return parser.scan()

    def test_workflow_found(self, result):
        workflows = [o for o in result.objects if o.object_type == ObjectType.WORKFLOW]
        assert len(workflows) == 1
        assert workflows[0].name == "wf_DEMO_LOAD"

    def test_workflow_has_variables(self, result):
        wf = next(o for o in result.objects if o.name == "wf_DEMO_LOAD")
        assert any("$$LOAD_DATE" in e for e in wf.expressions)

    def test_workflow_contains_sessions(self, result):
        contains_deps = [
            d
            for d in result.dependencies
            if d.dependency_type == "contains" and d.source == "wf_DEMO_LOAD"
        ]
        targets = {d.target for d in contains_deps}
        assert "s_VAL_PRODUCT_RATE_MAP" in targets
        assert "s_LOAD_DIM_PRODUCT" in targets

    def test_workflow_execution_links(self, result):
        exec_deps = [
            d
            for d in result.dependencies
            if d.dependency_type.startswith("executes_after") and "wf_DEMO_LOAD" in d.source
        ]
        assert len(exec_deps) >= 3  # Start→EW, EW→s_VAL, s_VAL→s_LOAD, + conditionals

    def test_workflow_conditional_links(self, result):
        cond_deps = [d for d in result.dependencies if "FAILED" in d.dependency_type]
        assert len(cond_deps) >= 1  # s_VAL failure → email / abort


# ------------------------------------------------------------------
# All objects have required fields
# ------------------------------------------------------------------


class TestPctrObjectIntegrity:
    def test_all_objects_have_names(self):
        parser = PctrXmlParser(str(FIXTURES / "demo_workflow.xml"))
        result = parser.scan()
        for obj in result.objects:
            assert obj.name, f"Object should have a name: {obj}"
            assert obj.platform == SourcePlatform.POWERCENTER

    def test_total_object_count(self):
        parser = PctrXmlParser(str(FIXTURES / "demo_workflow.xml"))
        result = parser.scan()
        # 2 mappings + 2 sessions + 1 workflow = 5
        assert len(result.objects) == 5
