"""ODI DB parser — live queries against the ODI work repository SNP_ tables.

Usage:
    crawl scan --source odi://host:1521/repo_schema

Connects to the Oracle database hosting the ODI work repository and reads
metadata from SNP_ tables. Supports both ODI 11g (SNP_POP family) and
12c (SNP_MAP family) schemas — both coexist in 12c repositories.

Safety: All queries are SELECT-only against SNP_ metadata tables.
Never touches user data tables.
"""

from __future__ import annotations

from crawl.models import (
    DataObject,
    Dependency,
    ObjectType,
    ScanResult,
    SourcePlatform,
)
from crawl.parsers import BaseParser

# ---------------------------------------------------------------------------
# Allowlisted queries — every SQL Crawl will execute against the ODI repo.
# These are the ONLY queries that will run. No dynamic SQL.
# ---------------------------------------------------------------------------

# Detect whether this is a 12c repo (has populated SNP_MAPPING table)
Q_DETECT_VERSION = """
SELECT COUNT(*) AS cnt FROM snp_mapping
"""

# Project / folder hierarchy
Q_PROJECTS = """
SELECT i_project, project_name FROM snp_project
"""

Q_FOLDERS = """
SELECT i_folder, folder_name, i_project, par_i_folder FROM snp_folder
"""

# --- 12c Mappings (SNP_MAP family) ---

Q_MAPPINGS_12C = """
SELECT m.i_mapping, m.name AS mapping_name, m.i_folder, m.last_date
FROM snp_mapping m
"""

Q_MAPPING_COMPONENTS = """
SELECT mc.i_map_comp, mc.name, mc.type_name, mc.i_owner_mapping, mc.i_map_ref
FROM snp_map_comp mc
WHERE mc.i_owner_mapping = :mapping_id
"""

Q_MAPPING_CONNECTIONS = """
SELECT conn.i_start_map_cp, conn.i_end_map_cp
FROM snp_map_conn conn
JOIN snp_map_cp cp ON conn.i_start_map_cp = cp.i_map_cp
JOIN snp_map_comp mc ON cp.i_owner_map_comp = mc.i_map_comp
WHERE mc.i_owner_mapping = :mapping_id
"""

Q_MAPPING_TARGETS_12C = """
SELECT m.name AS mapping_name, mr.qualified_name, t.table_name AS target_table,
       mdl.cod_mod AS model_code
FROM snp_mapping m
JOIN snp_map_comp mc ON m.i_mapping = mc.i_owner_mapping
JOIN snp_map_cp cp ON mc.i_map_comp = cp.i_owner_map_comp
JOIN snp_map_ref mr ON mc.i_map_ref = mr.i_map_ref
JOIN snp_table t ON mr.i_ref_id = t.i_table
JOIN snp_model mdl ON t.i_mod = mdl.i_mod
WHERE cp.direction = 'O'
  AND cp.i_map_cp NOT IN (SELECT i_start_map_cp FROM snp_map_conn)
"""

Q_MAPPING_SOURCES_12C = """
SELECT m.name AS mapping_name, mr.qualified_name, t.table_name AS source_table,
       mdl.cod_mod AS model_code
FROM snp_mapping m
JOIN snp_map_comp mc ON m.i_mapping = mc.i_owner_mapping
JOIN snp_map_cp cp ON mc.i_map_comp = cp.i_owner_map_comp
JOIN snp_map_ref mr ON mc.i_map_ref = mr.i_map_ref
JOIN snp_table t ON mr.i_ref_id = t.i_table
JOIN snp_model mdl ON t.i_mod = mdl.i_mod
WHERE cp.direction = 'I'
  AND cp.i_map_cp NOT IN (SELECT i_end_map_cp FROM snp_map_conn)
"""

Q_MAPPING_EXPRESSIONS_12C = """
SELECT mc.name AS component_name, ma.i_map_attr, me.parsed_txt
FROM snp_map_expr me
JOIN snp_map_attr ma ON me.i_owner_map_attr = ma.i_map_attr
JOIN snp_map_comp mc ON ma.i_owner_map_comp = mc.i_map_comp
WHERE mc.i_owner_mapping = :mapping_id
"""

# --- 11g Interfaces (SNP_POP family) ---

Q_INTERFACES_11G = """
SELECT p.i_pop, p.pop_name, t.table_name AS target_table, p.last_date
FROM snp_pop p
JOIN snp_table t ON p.i_table = t.i_table
"""

Q_INTERFACE_SOURCES_11G = """
SELECT st.i_source_tab, t.table_name AS source_table
FROM snp_source_tab st
JOIN snp_table t ON st.i_table = t.i_table
JOIN snp_src_set ss ON st.i_src_set = ss.i_src_set
JOIN snp_data_set ds ON ss.i_data_set = ds.i_data_set
WHERE ds.i_pop = :pop_id
"""

Q_INTERFACE_EXPRESSIONS_11G = """
SELECT pc.col_name AS target_column, tc.string_elt AS expression_text
FROM snp_pop_col pc
JOIN snp_pop_mapping pm ON pc.i_pop_col = pm.i_pop_col
JOIN snp_txt_crossr tc ON pm.i_txt_map = tc.i_txt
WHERE pc.i_pop = :pop_id
ORDER BY pc.col_name, tc.string_pos
"""

# --- Knowledge Modules ---

Q_KNOWLEDGE_MODULES = """
SELECT t.i_trt, t.trt_name FROM snp_trt t
"""

# --- Execution history (for dead code detection) ---

Q_EXECUTION_HISTORY = """
SELECT s.scen_name, MAX(s.sess_beg) AS last_run,
       COUNT(*) AS exec_count,
       SUM(tl.nb_row) AS total_rows, SUM(tl.nb_err) AS total_errors
FROM snp_session s
JOIN snp_sess_task_log tl ON s.sess_no = tl.sess_no
GROUP BY s.scen_name
"""

# --- Compiled SQL (from scenarios) ---

Q_SCENARIO_SQL = """
SELECT s.scen_name, st.task_name1, st.col_txt AS source_sql, st.def_txt AS target_sql
FROM snp_scen s
JOIN snp_scen_task st ON s.scen_no = st.scen_no
WHERE st.col_txt IS NOT NULL OR st.def_txt IS NOT NULL
"""


class OdiDbParser(BaseParser):
    """Parser for ODI work repositories via live DB connection.

    Connects to Oracle and queries SNP_ metadata tables. Supports both
    11g interfaces (SNP_POP) and 12c mappings (SNP_MAP) — auto-detects
    which are present.
    """

    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string
        self._conn = None

    def test_connection(self) -> bool:
        """Verify we can connect and the repo has SNP_ tables."""
        # TODO: Implement Oracle connection via oracledb/cx_Oracle
        raise NotImplementedError("ODI DB connection not yet implemented")

    def scan(self) -> ScanResult:
        """Discover all ODI mappings/interfaces and their dependencies."""
        # TODO: Implementation outline:
        # 1. Connect to Oracle DB
        # 2. Detect version (Q_DETECT_VERSION)
        # 3. Read project hierarchy (Q_PROJECTS, Q_FOLDERS)
        # 4. If 12c: read mappings, components, connections, expressions
        # 5. If 11g: read interfaces, sources, expressions
        # 6. Read execution history for dead code detection
        # 7. Build DataObjects with source/target tables, expressions
        # 8. Build Dependencies from the component graph
        # 9. Return ScanResult
        raise NotImplementedError("ODI DB scan not yet implemented")

    def _detect_version(self) -> str:
        """Detect whether repo is 11g-only or 12c."""
        # If SNP_MAPPING has rows → 12c (may also have 11g interfaces)
        # If SNP_MAPPING empty/missing → 11g only
        raise NotImplementedError

    def _scan_12c_mappings(self) -> list[DataObject]:
        """Scan 12c mappings from SNP_MAP family."""
        raise NotImplementedError

    def _scan_11g_interfaces(self) -> list[DataObject]:
        """Scan 11g interfaces from SNP_POP family."""
        raise NotImplementedError

    def _scan_execution_history(self) -> dict[str, dict]:
        """Read execution stats keyed by scenario name."""
        raise NotImplementedError
