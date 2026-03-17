"""ODI DB parser — live queries against the ODI work repository SNP_ tables.

Usage:
    crawl scan --source odi://localhost:1521/XEPDB1

Connects to the Oracle database hosting the ODI work repository and reads
metadata from SNP_ tables. Supports both ODI 11g (SNP_POP family) and
12c (SNP_MAP family) schemas — both coexist in 12c repositories.

Safety: All queries are SELECT-only against SNP_ metadata tables.
Never touches user data tables.

Requires: oracledb (pip install oracledb)
"""

from __future__ import annotations

from urllib.parse import urlparse

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

Q_DETECT_VERSION = "SELECT COUNT(*) AS cnt FROM snp_mapping"

Q_PROJECTS = "SELECT i_project, project_name FROM snp_project"

Q_FOLDERS = "SELECT i_folder, folder_name, i_project, par_i_folder FROM snp_folder"

# --- 12c Mappings ---

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
SELECT cn.i_start_map_cp, cn.i_end_map_cp
FROM snp_map_conn cn
WHERE cn.i_owner_mapping = :mapping_id
"""

Q_MAPPING_CONNECTION_POINTS = """
SELECT cp.i_map_cp, cp.direction, cp.i_owner_map_comp
FROM snp_map_cp cp
JOIN snp_map_comp mc ON cp.i_owner_map_comp = mc.i_map_comp
WHERE mc.i_owner_mapping = :mapping_id
"""

Q_MAPPING_DATASTORES = """
SELECT mc.i_map_comp, mc.name AS comp_name, mc.type_name,
       mr.qualified_name, t.table_name, mdl.mod_name AS model_name
FROM snp_map_comp mc
LEFT JOIN snp_map_ref mr ON mc.i_map_ref = mr.i_map_ref
LEFT JOIN snp_table t ON mr.i_ref_id = t.i_table
LEFT JOIN snp_model mdl ON t.i_mod = mdl.i_mod
WHERE mc.i_owner_mapping = :mapping_id
  AND mc.type_name IN ('DATASTORE', 'FILE')
"""

Q_MAPPING_EXPRESSIONS = """
SELECT ma.name AS attr_name, me.parsed_txt, mc.name AS comp_name
FROM snp_map_expr me
JOIN snp_map_attr ma ON me.i_owner_map_attr = ma.i_map_attr
JOIN snp_map_cp cp ON ma.i_owner_map_cp = cp.i_map_cp
JOIN snp_map_comp mc ON cp.i_owner_map_comp = mc.i_map_comp
WHERE mc.i_owner_mapping = :mapping_id
  AND me.parsed_txt IS NOT NULL
"""

# --- 11g Interfaces ---

Q_INTERFACES_11G = """
SELECT p.i_pop, p.pop_name, t.table_name AS target_table, p.last_date
FROM snp_pop p
LEFT JOIN snp_table t ON p.i_table = t.i_table
"""

Q_INTERFACE_SOURCES_11G = """
SELECT t.table_name AS source_table
FROM snp_source_tab st
JOIN snp_table t ON st.i_table = t.i_table
JOIN snp_src_set ss ON st.i_src_set = ss.i_src_set
JOIN snp_data_set ds ON ss.i_data_set = ds.i_data_set
WHERE ds.i_pop = :pop_id
"""

# --- Knowledge Modules ---

Q_KNOWLEDGE_MODULES = """
SELECT t.i_trt, t.trt_name, t.trt_type FROM snp_trt t
"""

# --- Packages ---

Q_PACKAGES = """
SELECT p.i_package, p.pack_name, p.i_folder FROM snp_package p
"""

# --- Execution history ---

Q_EXECUTION_HISTORY = """
SELECT s.scen_name, MAX(s.sess_beg) AS last_run,
       COUNT(*) AS exec_count,
       SUM(tl.nb_row) AS total_rows, SUM(tl.nb_err) AS total_errors
FROM snp_session s
JOIN snp_sess_task_log tl ON s.sess_no = tl.sess_no
GROUP BY s.scen_name
"""

# KM type codes
_KM_TYPES = {"KI": "IKM", "KL": "LKM", "KC": "CKM", "KR": "RKM", "KJ": "JKM", "KS": "SKM"}


def _parse_odi_connection(connection_string: str) -> dict:
    """Parse odi://user:pass@host:port/service into connection params.

    Supports:
        odi://host:port/service                  (uses env/default credentials)
        odi://user:pass@host:port/service         (explicit credentials)
    """
    parsed = urlparse(connection_string)
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 1521,
        "service": (parsed.path or "/XEPDB1").lstrip("/"),
        "user": parsed.username,
        "password": parsed.password,
    }


class OdiDbParser(BaseParser):
    """Parser for ODI work repositories via live DB connection.

    Connects to Oracle and queries SNP_ metadata tables. Supports both
    11g interfaces (SNP_POP) and 12c mappings (SNP_MAP) — auto-detects
    which are present.
    """

    def __init__(self, connection_string: str, user: str | None = None,
                 password: str | None = None) -> None:
        self.connection_string = connection_string
        self._params = _parse_odi_connection(connection_string)
        # Allow override from CLI or env
        if user:
            self._params["user"] = user
        if password:
            self._params["password"] = password
        self._conn = None

    def _connect(self):
        """Establish Oracle connection using oracledb thin mode."""
        import oracledb

        if self._conn is not None:
            return self._conn

        params = self._params
        self._conn = oracledb.connect(
            user=params["user"],
            password=params["password"],
            dsn=f'{params["host"]}:{params["port"]}/{params["service"]}',
        )
        return self._conn

    def _query(self, sql: str, **bind_params) -> list[dict]:
        """Execute a read-only query and return rows as dicts."""
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(sql, bind_params)
            cols = [c[0].lower() for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def test_connection(self) -> bool:
        """Verify we can connect and the repo has SNP_ tables."""
        try:
            rows = self._query("SELECT COUNT(*) AS cnt FROM user_tables WHERE table_name LIKE 'SNP_%'")
            return rows[0]["cnt"] > 0
        except Exception:
            return False

    def scan(self) -> ScanResult:
        """Discover all ODI mappings/interfaces and their dependencies."""
        result = ScanResult(platform=SourcePlatform.ODI)

        # Detect 12c vs 11g
        has_12c = self._query(Q_DETECT_VERSION)[0]["cnt"] > 0

        # Scan 12c mappings
        if has_12c:
            self._scan_12c_mappings(result)

        # Scan 11g interfaces
        self._scan_11g_interfaces(result)

        # Close connection
        if self._conn:
            self._conn.close()
            self._conn = None

        return result

    def _scan_12c_mappings(self, result: ScanResult) -> None:
        """Scan 12c mappings from SNP_MAP family."""
        mappings = self._query(Q_MAPPINGS_12C)

        for m in mappings:
            mapping_id = m["i_mapping"]
            mapping_name = m["mapping_name"]

            # Get datastores for this mapping
            datastores = self._query(Q_MAPPING_DATASTORES, mapping_id=mapping_id)

            # Get connection points and connections to determine source vs target
            cps = self._query(Q_MAPPING_CONNECTION_POINTS, mapping_id=mapping_id)
            conns = self._query(Q_MAPPING_CONNECTIONS, mapping_id=mapping_id)

            # Start CPs are outputs that feed into something
            start_cps = {c["i_start_map_cp"] for c in conns}
            # End CPs are inputs that receive from something
            end_cps = {c["i_end_map_cp"] for c in conns}

            source_tables = []
            target_tables = []
            for ds in datastores:
                comp_id = ds["i_map_comp"]
                table_name = ds["table_name"] or ds["comp_name"]
                model = ds["model_name"] or ""

                # Find this component's output CPs
                out_cps = [cp for cp in cps
                           if cp["i_owner_map_comp"] == comp_id and cp["direction"] == "O"]
                in_cps = [cp for cp in cps
                          if cp["i_owner_map_comp"] == comp_id and cp["direction"] == "I"]

                # Target: has input CP that's an end_cp, but output CP is NOT a start_cp
                # (nothing flows out of it further)
                is_target = (
                    any(cp["i_map_cp"] in end_cps for cp in in_cps)
                    and not any(cp["i_map_cp"] in start_cps for cp in out_cps)
                )
                # Source: has output CP that's a start_cp, but input CP is NOT an end_cp
                is_source = (
                    any(cp["i_map_cp"] in start_cps for cp in out_cps)
                    and not any(cp["i_map_cp"] in end_cps for cp in in_cps)
                )

                label = f"{model}.{table_name}" if model else table_name
                if is_target:
                    target_tables.append(label)
                elif is_source:
                    source_tables.append(label)

            # Get expressions
            expressions = []
            expr_rows = self._query(Q_MAPPING_EXPRESSIONS, mapping_id=mapping_id)
            for e in expr_rows:
                parsed = e["parsed_txt"]
                if parsed:
                    attr = e["attr_name"] or ""
                    comp = e["comp_name"] or ""
                    expressions.append(f"{comp}.{attr} = {parsed}")

            # Get components for KM types
            components = self._query(Q_MAPPING_COMPONENTS, mapping_id=mapping_id)

            obj = DataObject(
                name=mapping_name,
                object_type=ObjectType.MAPPING,
                platform=SourcePlatform.ODI,
                last_modified=str(m["last_date"]) if m["last_date"] else None,
                source_tables=source_tables,
                target_tables=target_tables,
                expressions=expressions,
                knowledge_modules=list({c["type_name"] for c in components}),
            )

            result.objects.append(obj)

            # Add dependencies
            for src in source_tables:
                for tgt in target_tables:
                    result.dependencies.append(Dependency(
                        source=src,
                        target=tgt,
                        dependency_type=f"mapping:{mapping_name}",
                    ))

    def _scan_11g_interfaces(self, result: ScanResult) -> None:
        """Scan 11g interfaces from SNP_POP family."""
        interfaces = self._query(Q_INTERFACES_11G)

        for iface in interfaces:
            pop_id = iface["i_pop"]
            pop_name = iface["pop_name"]
            target = iface.get("target_table")

            # Get sources
            source_rows = self._query(Q_INTERFACE_SOURCES_11G, pop_id=pop_id)
            source_tables = [r["source_table"] for r in source_rows]

            obj = DataObject(
                name=pop_name,
                object_type=ObjectType.INTERFACE,
                platform=SourcePlatform.ODI,
                last_modified=str(iface["last_date"]) if iface["last_date"] else None,
                source_tables=source_tables,
                target_tables=[target] if target else [],
            )
            result.objects.append(obj)
