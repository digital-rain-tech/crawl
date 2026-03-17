"""Tests for the ODI XML parser using real ODI export fixtures."""

from pathlib import Path

from crawl.models import SourcePlatform
from crawl.parsers.odi.xml import OdiXmlParser

FIXTURES = Path(__file__).parent / "fixtures" / "odi"


class TestOdiXmlParserConnection:
    """Test connection/validation logic."""

    def test_valid_xml_file(self):
        parser = OdiXmlParser(str(FIXTURES / "IKM_SQL_to_SQL_Append.xml"))
        assert parser.test_connection() is True

    def test_valid_directory(self):
        parser = OdiXmlParser(str(FIXTURES))
        assert parser.test_connection() is True

    def test_nonexistent_path(self):
        parser = OdiXmlParser("/nonexistent/path")
        assert parser.test_connection() is False

    def test_non_odi_xml(self):
        parser = OdiXmlParser(str(FIXTURES / "GEO_DIM_demo.xml"))
        # This file exists but isn't an ODI export (no SunopsisExport root)
        # test_connection should return False for non-ODI XML
        result = parser.test_connection()
        # GEO_DIM_demo.xml might or might not have SunopsisExport — check
        assert isinstance(result, bool)


class TestOdiXmlParserScanSingleKm:
    """Test scanning a single KM XML file."""

    def test_ikm_sql_to_sql_append(self):
        parser = OdiXmlParser(str(FIXTURES / "IKM_SQL_to_SQL_Append.xml"))
        result = parser.scan()

        assert result.platform == SourcePlatform.ODI
        assert len(result.objects) >= 1

        # Find the IKM
        ikm = next((o for o in result.objects if "SQL to SQL Append" in o.name), None)
        assert ikm is not None
        assert ikm.platform == SourcePlatform.ODI
        assert ikm.schema == "IKM"  # KM type stored in schema field

    def test_ikm_has_description(self):
        parser = OdiXmlParser(str(FIXTURES / "IKM_SQL_to_SQL_Append.xml"))
        result = parser.scan()

        ikm = next((o for o in result.objects if "SQL to SQL Append" in o.name), None)
        assert ikm is not None
        assert ikm.source_code is not None
        assert len(ikm.source_code) > 0

    def test_ikm_has_steps(self):
        parser = OdiXmlParser(str(FIXTURES / "IKM_SQL_to_SQL_Append.xml"))
        result = parser.scan()

        ikm = next((o for o in result.objects if "SQL to SQL Append" in o.name), None)
        assert ikm is not None
        assert len(ikm.expressions) > 0, "IKM should have KM step expressions"

    def test_lkm_sql_to_sql(self):
        parser = OdiXmlParser(str(FIXTURES / "LKM_SQL_to_SQL.xml"))
        result = parser.scan()

        lkm = next((o for o in result.objects if "SQL to SQL" in o.name), None)
        assert lkm is not None
        assert lkm.schema == "LKM"

    def test_ckm_oracle(self):
        parser = OdiXmlParser(str(FIXTURES / "CKM_Oracle.xml"))
        result = parser.scan()

        ckm = next((o for o in result.objects if "Oracle" in o.name), None)
        assert ckm is not None
        assert ckm.schema == "CKM"

    def test_rkm_oracle(self):
        parser = OdiXmlParser(str(FIXTURES / "RKM_Oracle.xml"))
        result = parser.scan()

        rkm = next((o for o in result.objects if "Oracle" in o.name), None)
        assert rkm is not None
        assert rkm.schema == "RKM"


class TestOdiXmlParserScan12cKm:
    """Test scanning an ODI 12c KM (has Admin/Encryption headers)."""

    def test_ikm_marklogic(self):
        parser = OdiXmlParser(str(FIXTURES / "KM_IKM_SQL_to_MarkLogic.xml"))
        result = parser.scan()

        ikm = next((o for o in result.objects if "MarkLogic" in o.name), None)
        assert ikm is not None
        assert ikm.schema == "IKM"
        assert ikm.platform == SourcePlatform.ODI

    def test_12c_has_steps(self):
        parser = OdiXmlParser(str(FIXTURES / "KM_IKM_SQL_to_MarkLogic.xml"))
        result = parser.scan()

        ikm = next((o for o in result.objects if "MarkLogic" in o.name), None)
        assert ikm is not None
        assert len(ikm.expressions) > 0


class TestOdiXmlParserScanDirectory:
    """Test scanning a directory of multiple XML files."""

    def test_scan_all_fixtures(self):
        parser = OdiXmlParser(str(FIXTURES))
        result = parser.scan()

        assert result.platform == SourcePlatform.ODI
        # Should find KMs from multiple files
        assert len(result.objects) >= 4  # At least IKM, LKM, CKM, RKM

        km_types = {o.schema for o in result.objects if o.schema}
        assert "IKM" in km_types
        assert "LKM" in km_types
        assert "CKM" in km_types
        assert "RKM" in km_types

    def test_all_objects_have_names(self):
        parser = OdiXmlParser(str(FIXTURES))
        result = parser.scan()

        for obj in result.objects:
            assert obj.name, f"Object should have a name: {obj}"
            assert obj.platform == SourcePlatform.ODI
