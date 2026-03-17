"""Tests for the ODI DB parser against a live Oracle container.

These tests require the ODI test database to be running:
    ./scripts/setup-odi-testdb.sh

Tests are skipped if the container is not available.
"""

import subprocess

import pytest

from crawl.models import ObjectType, SourcePlatform

# Check if the test DB container is running
_CONTAINER_RUNNING = False
try:
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", "crawl-odi-testdb"],
        capture_output=True, text=True, timeout=5,
    )
    _CONTAINER_RUNNING = result.stdout.strip() == "true"
except Exception:
    pass

requires_odi_db = pytest.mark.skipif(
    not _CONTAINER_RUNNING,
    reason="ODI test database not running (./scripts/setup-odi-testdb.sh)",
)

CONNECTION = "odi://odi_repo:odi123@localhost:1521/XEPDB1"


@requires_odi_db
class TestOdiDbParserConnection:

    def test_connection(self):
        from crawl.parsers.odi.db import OdiDbParser
        parser = OdiDbParser(CONNECTION)
        assert parser.test_connection() is True

    def test_bad_connection(self):
        from crawl.parsers.odi.db import OdiDbParser
        parser = OdiDbParser("odi://bad:bad@localhost:9999/NOPE")
        assert parser.test_connection() is False


@requires_odi_db
class TestOdiDbParserScan:

    def _scan(self):
        from crawl.parsers.odi.db import OdiDbParser
        parser = OdiDbParser(CONNECTION)
        return parser.scan()

    def test_finds_all_mappings(self):
        result = self._scan()
        assert result.platform == SourcePlatform.ODI
        assert len(result.objects) == 8

    def test_mapping_has_source_and_target(self):
        result = self._scan()
        # "E - Load Oracle (OLH)" maps movie_rating → ODI_MOVIE_RATING
        olh = next(o for o in result.objects if "Load Oracle" in o.name)
        assert olh.object_type == ObjectType.MAPPING
        assert any("movie_rating" in s for s in olh.source_tables)
        assert any("ODI_MOVIE_RATING" in t for t in olh.target_tables)

    def test_mapping_has_expressions(self):
        result = self._scan()
        olh = next(o for o in result.objects if "Load Oracle" in o.name)
        assert len(olh.expressions) > 0

    def test_multi_source_mapping(self):
        result = self._scan()
        # "F - Calc Sales" has CUSTOMER + movieapp_log_odistage → ODI_COUNTRY_SALES
        sales = next(o for o in result.objects if "Calc Sales" in o.name)
        assert len(sales.source_tables) >= 2
        assert len(sales.target_tables) >= 1

    def test_dependencies_created(self):
        result = self._scan()
        assert len(result.dependencies) > 0
        # Should have source→target deps
        dep_targets = {d.target for d in result.dependencies}
        assert any("ODI_MOVIE_RATING" in t for t in dep_targets)

    def test_all_objects_have_names(self):
        result = self._scan()
        for obj in result.objects:
            assert obj.name
            assert obj.platform == SourcePlatform.ODI

    def test_sessionize_mapping(self):
        result = self._scan()
        sess = next(o for o in result.objects if "Sessionize" in o.name)
        assert any("cust" in s for s in sess.source_tables)
        assert any("session_stats" in t for t in sess.target_tables)
        assert len(sess.expressions) > 10  # Complex mapping
