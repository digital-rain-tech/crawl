#!/usr/bin/env python3
"""Generate a fictional PowerCenter export for demos: retail_nightly.xml.

The company, tables and rules are invented. Nothing here comes from a customer export.
The pipeline is a standard three-layer warehouse load (ODS → DW → DM) for a retail chain,
with the kind of undocumented business rules Crawl is built to surface: a 4-4-5 fiscal
calendar, loyalty-tier thresholds, a restocking-fee rule, Oracle-specific SQL, and a
legacy mapping that no session runs.

Run from the repo root:
    python examples/powercenter/generate_retail_demo.py
"""

from __future__ import annotations

from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

OUT = Path(__file__).parent / "retail_nightly.xml"
FOLDER = "RETAIL_EDW"

# ------------------------------------------------------------------
# Sources and targets: name → (database type, [(column, datatype)])
# ------------------------------------------------------------------

SOURCES = {
    "POS_SALES_LINE": ("Oracle", [
        ("TXN_ID", "number"), ("LINE_NO", "number"), ("STORE_CODE", "varchar2"),
        ("SKU", "varchar2"), ("QTY", "number"), ("UNIT_PRICE", "number"),
        ("DISC_AMT", "number"), ("CURRENCY_CD", "varchar2"), ("TXN_TS", "date"),
        ("MEMBER_NO", "varchar2"),
    ]),
    "POS_STORE": ("Oracle", [
        ("STORE_CODE", "varchar2"), ("STORE_NAME", "varchar2"), ("REGION_CD", "varchar2"),
        ("OPEN_DATE", "date"), ("CLOSE_DATE", "date"), ("SQFT", "number"),
    ]),
    "MERCH_ITEM": ("Oracle", [
        ("SKU", "varchar2"), ("ITEM_DESC", "varchar2"), ("DEPT_CD", "varchar2"),
        ("UNIT_COST", "number"), ("LIST_PRICE", "number"), ("STATUS", "varchar2"),
    ]),
    "RETURNS_FEED": ("Flat File", [
        ("RMA_NO", "string"), ("TXN_ID", "string"), ("SKU", "string"), ("QTY", "string"),
        ("REASON_CD", "string"), ("RETURN_DT", "string"), ("CONDITION_CD", "string"),
    ]),
    "FX_DAILY_RATE": ("Oracle", [
        ("CURRENCY_CD", "varchar2"), ("RATE_DATE", "date"), ("RATE_TO_USD", "number"),
    ]),
    "LOYALTY_MEMBER": ("Oracle", [
        ("MEMBER_NO", "varchar2"), ("JOIN_DATE", "date"), ("EMAIL_OPT_IN", "varchar2"),
    ]),
    "PROMO_CALENDAR": ("Oracle", [
        ("PROMO_ID", "varchar2"), ("START_DT", "date"), ("END_DT", "date"),
    ]),
}

TARGETS = {
    "ODS_SALES_LINE": ["TXN_ID", "LINE_NO", "STORE_CODE", "SKU", "QTY", "GROSS_AMT_USD",
                       "DISC_AMT_USD", "TXN_DATE", "MEMBER_NO", "LOAD_TS"],
    "ODS_STORE": ["STORE_CODE", "STORE_NAME", "REGION_CD", "OPEN_DATE", "CLOSE_DATE",
                  "SQFT", "IS_ACTIVE"],
    "ODS_ITEM": ["SKU", "ITEM_DESC", "DEPT_CD", "UNIT_COST", "LIST_PRICE", "IS_SELLABLE"],
    "ODS_RETURN": ["RMA_NO", "TXN_ID", "SKU", "QTY", "REASON_CD", "RETURN_DATE",
                   "CONDITION_CD"],
    "DIM_STORE": ["STORE_KEY", "STORE_CODE", "STORE_NAME", "REGION_CD", "STORE_CLASS",
                  "EFF_START_DATE", "EFF_END_DATE", "CURRENT_FLAG"],
    "DIM_PRODUCT": ["PRODUCT_KEY", "SKU", "ITEM_DESC", "DEPT_CD", "MARGIN_TIER",
                    "EFF_START_DATE", "EFF_END_DATE", "CURRENT_FLAG"],
    "FACT_SALES": ["DATE_KEY", "STORE_KEY", "PRODUCT_KEY", "MEMBER_NO", "FISCAL_WEEK",
                   "QTY", "GROSS_AMT", "NET_AMT", "COST_AMT", "MARGIN_AMT"],
    "FACT_RETURNS": ["DATE_KEY", "STORE_KEY", "PRODUCT_KEY", "QTY", "REFUND_AMT",
                     "RESTOCK_FEE", "RESALEABLE_FLAG"],
    "AGG_STORE_DAY": ["DATE_KEY", "STORE_KEY", "TXN_COUNT", "NET_SALES", "NET_RETURNS",
                      "NET_REVENUE", "SALES_PER_SQFT"],
    "AGG_PRODUCT_MARGIN": ["FISCAL_WEEK", "PRODUCT_KEY", "UNITS", "REVENUE", "MARGIN_PCT"],
    "DM_MEMBER_SEGMENT": ["MEMBER_NO", "SPEND_12M", "VISITS_12M", "TIER", "CHURN_RISK"],
    "PROMO_EXTRACT_OUT": ["PROMO_ID", "SKU", "UNITS", "PROMO_REVENUE"],
}

# ------------------------------------------------------------------
# Mappings. Each transformation is (name, type, fields, attributes, router groups).
# fields: [(port, expression or None)]; expression None means a pass-through port.
# ------------------------------------------------------------------


def tx(name, tx_type, fields=(), attrs=(), groups=()):
    return {"name": name, "type": tx_type, "fields": list(fields), "attrs": list(attrs),
            "groups": list(groups)}


MAPPINGS = [
    # ---------------- ODS layer ----------------
    {
        "name": "m_ODS_LOAD_SALES_LINE",
        "sources": ["POS_SALES_LINE"], "targets": ["ODS_SALES_LINE"],
        "chain": [
            tx("SQ_POS_SALES_LINE", "Source Qualifier", attrs=[
                ("Source Filter",
                 ("POS_SALES_LINE.TXN_TS >= TRUNC(SYSDATE) - 1 "
                 "AND POS_SALES_LINE.TXN_TS < TRUNC(SYSDATE)")),
            ]),
            tx("LKP_FX_DAILY_RATE", "Lookup Procedure", attrs=[
                ("Lookup Sql Override",
                 ("SELECT CURRENCY_CD, RATE_DATE, NVL(RATE_TO_USD, 1) AS RATE_TO_USD "
                 "FROM FX_DAILY_RATE WHERE RATE_DATE >= TRUNC(SYSDATE) - 7")),
                ("Lookup condition", "CURRENCY_CD = IN_CURRENCY_CD AND RATE_DATE = IN_TXN_DATE"),
            ]),
            tx("EXP_CONVERT_USD", "Expression", fields=[
                ("TXN_DATE", "TRUNC(TXN_TS)"),
                ("GROSS_AMT_USD", ("ROUND(QTY * UNIT_PRICE * IIF(ISNULL(RATE_TO_USD), 1, "
                                  "RATE_TO_USD), 2)")),
                ("DISC_AMT_USD", ("ROUND(NVL(DISC_AMT, 0) * IIF(ISNULL(RATE_TO_USD), 1, "
                                 "RATE_TO_USD), 2)")),
                ("MEMBER_NO", ("IIF(LTRIM(RTRIM(MEMBER_NO)) = '' OR MEMBER_NO = '0000000', "
                              "NULL, MEMBER_NO)")),
                ("LOAD_TS", "SYSDATE"),
            ]),
        ],
    },
    {
        "name": "m_ODS_LOAD_STORE",
        "sources": ["POS_STORE"], "targets": ["ODS_STORE"],
        "chain": [
            tx("SQ_POS_STORE", "Source Qualifier"),
            tx("EXP_STORE_STATUS", "Expression", fields=[
                ("IS_ACTIVE", "IIF(ISNULL(CLOSE_DATE) OR CLOSE_DATE > SYSDATE, 'Y', 'N')"),
                ("REGION_CD", ("DECODE(REGION_CD, 'NE', 'EAST', 'SE', 'EAST', 'MW', 'CENTRAL', "
                              "'NW', 'WEST', 'SW', 'WEST', 'UNKNOWN')")),
            ]),
        ],
    },
    {
        "name": "m_ODS_LOAD_ITEM",
        "sources": ["MERCH_ITEM"], "targets": ["ODS_ITEM"],
        "chain": [
            tx("SQ_MERCH_ITEM", "Source Qualifier", attrs=[
                ("Sql Query",
                 ("SELECT SKU, ITEM_DESC, DEPT_CD, UNIT_COST, LIST_PRICE, STATUS "
                 "FROM MERCH_ITEM WHERE DEPT_CD NOT IN ('99', 'GC') AND ROWNUM <= 500000")),
            ]),
            tx("EXP_SELLABLE", "Expression", fields=[
                ("IS_SELLABLE", "DECODE(STATUS, 'A', 'Y', 'S', 'Y', 'N')"),
            ]),
        ],
    },
    {
        "name": "m_ODS_LOAD_RETURNS",
        "sources": ["RETURNS_FEED"], "targets": ["ODS_RETURN"],
        "chain": [
            tx("SQ_RETURNS_FEED", "Source Qualifier"),
            tx("EXP_PARSE_RETURN", "Expression", fields=[
                ("RETURN_DATE", "TO_DATE(RETURN_DT, 'YYYYMMDD')"),
                ("QTY", "TO_INTEGER(QTY)"),
                ("REASON_CD", "IIF(ISNULL(REASON_CD), 'UNK', UPPER(REASON_CD))"),
            ]),
            tx("FIL_VALID_RMA", "Filter", attrs=[
                ("Filter Condition", "NOT ISNULL(RMA_NO) AND TO_INTEGER(QTY) > 0"),
            ]),
        ],
    },
    # ---------------- DW layer ----------------
    {
        "name": "m_DW_LOAD_DIM_STORE",
        "sources": ["ODS_STORE"], "targets": ["DIM_STORE"],
        "chain": [
            tx("SQ_ODS_STORE", "Source Qualifier"),
            tx("LKP_DIM_STORE", "Lookup Procedure", attrs=[
                ("Lookup condition", "STORE_CODE = IN_STORE_CODE AND CURRENT_FLAG = 'Y'"),
            ]),
            tx("EXP_STORE_CLASS", "Expression", fields=[
                ("STORE_CLASS", ("IIF(SQFT >= 40000, 'FLAGSHIP', IIF(SQFT >= 15000, 'STANDARD', "
                                "'EXPRESS'))")),
                ("CHG_FLAG", ("IIF(STORE_NAME != LKP_STORE_NAME OR REGION_CD != LKP_REGION_CD, "
                             "1, 0)")),
            ]),
            tx("RTR_NEW_CHANGED", "Router", groups=[
                ("NEW", "ISNULL(LKP_STORE_KEY)"),
                ("CHANGED", "NOT ISNULL(LKP_STORE_KEY) AND CHG_FLAG = 1"),
            ]),
            tx("UPD_EXPIRE_OLD", "Update Strategy", fields=[
                ("EFF_END_DATE", "ADD_TO_DATE(SESSSTARTTIME, 'DD', -1)"),
            ], attrs=[("Update Strategy Expression", "DD_UPDATE")]),
            tx("SEQ_STORE_KEY", "Sequence"),
        ],
    },
    {
        "name": "m_DW_LOAD_DIM_PRODUCT",
        "sources": ["ODS_ITEM"], "targets": ["DIM_PRODUCT"],
        "chain": [
            tx("SQ_ODS_ITEM", "Source Qualifier", attrs=[
                ("Source Filter", "ODS_ITEM.IS_SELLABLE = 'Y'"),
            ]),
            tx("LKP_DIM_PRODUCT", "Lookup Procedure", attrs=[
                ("Lookup condition", "SKU = IN_SKU AND CURRENT_FLAG = 'Y'"),
            ]),
            tx("EXP_MARGIN_TIER", "Expression", fields=[
                ("LIST_MARGIN", "(LIST_PRICE - UNIT_COST) / IIF(LIST_PRICE = 0, NULL, LIST_PRICE)"),
                ("MARGIN_TIER", ("DECODE(TRUE, LIST_MARGIN >= 0.55, 'A', LIST_MARGIN >= 0.35, 'B', "
                                "LIST_MARGIN >= 0.15, 'C', 'D')")),
            ]),
            tx("RTR_NEW_CHANGED", "Router", groups=[
                ("NEW", "ISNULL(LKP_PRODUCT_KEY)"),
                ("CHANGED", ("NOT ISNULL(LKP_PRODUCT_KEY) AND (ITEM_DESC != LKP_ITEM_DESC "
                            "OR MARGIN_TIER != LKP_MARGIN_TIER)")),
            ]),
            tx("SEQ_PRODUCT_KEY", "Sequence"),
        ],
    },
    {
        "name": "m_DW_LOAD_FACT_SALES",
        "sources": ["ODS_SALES_LINE", "ODS_ITEM"], "targets": ["FACT_SALES"],
        "chain": [
            tx("SQ_ODS_SALES_LINE", "Source Qualifier", attrs=[
                ("User Defined Join", "ODS_SALES_LINE.SKU = ODS_ITEM.SKU (+)"),
                ("Source Filter", "ODS_SALES_LINE.TXN_DATE = TO_DATE('$$LOAD_DATE', 'YYYY-MM-DD')"),
            ]),
            tx("LKP_DIM_STORE", "Lookup Procedure", attrs=[
                ("Lookup condition", "STORE_CODE = IN_STORE_CODE AND CURRENT_FLAG = 'Y'"),
            ]),
            tx("LKP_DIM_PRODUCT", "Lookup Procedure", attrs=[
                ("Lookup condition", "SKU = IN_SKU AND CURRENT_FLAG = 'Y'"),
            ]),
            tx("EXP_FISCAL_CALENDAR", "Expression", fields=[
                ("DATE_KEY", "TO_INTEGER(TO_CHAR(TXN_DATE, 'YYYYMMDD'))"),
                ("FY_START", ("IIF(TO_CHAR(TXN_DATE, 'MMDD') >= '0201', "
                             "TO_DATE(TO_CHAR(TXN_DATE, 'YYYY') || '0201', 'YYYYMMDD'), "
                             "ADD_TO_DATE(TO_DATE(TO_CHAR(TXN_DATE, 'YYYY') || '0201', "
                             "'YYYYMMDD'), 'YYYY', -1))")),
                ("FISCAL_WEEK", "TRUNC(DATE_DIFF(TXN_DATE, FY_START, 'DD') / 7) + 1"),
                ("FISCAL_PERIOD", ("DECODE(TRUE, FISCAL_WEEK <= 4, 1, FISCAL_WEEK <= 8, 2, "
                                  "FISCAL_WEEK <= 13, 3, FISCAL_WEEK <= 17, 4, FISCAL_WEEK <= 21, "
                                  "5, FISCAL_WEEK <= 26, 6, FISCAL_WEEK <= 30, 7, FISCAL_WEEK <= "
                                  "34, 8, FISCAL_WEEK <= 39, 9, FISCAL_WEEK <= 43, 10, "
                                  "FISCAL_WEEK <= 47, 11, 12)")),
            ]),
            tx("EXP_SALES_AMOUNTS", "Expression", fields=[
                ("GROSS_AMT", "GROSS_AMT_USD"),
                ("NET_AMT", ("GROSS_AMT_USD - DISC_AMT_USD - IIF(NOT ISNULL(MEMBER_NO) AND "
                            "GROSS_AMT_USD > 100, ROUND(GROSS_AMT_USD * 0.02, 2), 0)")),
                ("COST_AMT", "QTY * NVL(UNIT_COST, 0)"),
                ("MARGIN_AMT", "NET_AMT - COST_AMT"),
                ("STORE_KEY", "IIF(ISNULL(LKP_STORE_KEY), -1, LKP_STORE_KEY)"),
                ("PRODUCT_KEY", "IIF(ISNULL(LKP_PRODUCT_KEY), -1, LKP_PRODUCT_KEY)"),
            ]),
        ],
    },
    {
        "name": "m_DW_LOAD_FACT_RETURNS",
        "sources": ["ODS_RETURN", "ODS_SALES_LINE"], "targets": ["FACT_RETURNS"],
        "chain": [
            tx("SQ_ODS_RETURN", "Source Qualifier", attrs=[
                ("User Defined Join", ("ODS_RETURN.TXN_ID = ODS_SALES_LINE.TXN_ID AND "
                                      "ODS_RETURN.SKU = ODS_SALES_LINE.SKU")),
            ]),
            tx("LKP_DIM_STORE", "Lookup Procedure", attrs=[
                ("Lookup condition", "STORE_CODE = IN_STORE_CODE AND CURRENT_FLAG = 'Y'"),
            ]),
            tx("LKP_DIM_PRODUCT", "Lookup Procedure", attrs=[
                ("Lookup condition", "SKU = IN_SKU AND CURRENT_FLAG = 'Y'"),
            ]),
            tx("EXP_REFUND", "Expression", fields=[
                ("DAYS_SINCE_SALE", "DATE_DIFF(RETURN_DATE, TXN_DATE, 'DD')"),
                ("UNIT_NET", "(GROSS_AMT_USD - DISC_AMT_USD) / QTY_SOLD"),
                ("RESTOCK_FEE", ("IIF(CONDITION_CD = 'OPENED' AND DAYS_SINCE_SALE > 14 AND "
                                "REASON_CD != 'DEF', ROUND(UNIT_NET * QTY * 0.15, 2), 0)")),
                ("REFUND_AMT", ("IIF(DAYS_SINCE_SALE > 90, 0, ROUND(UNIT_NET * QTY, 2) - "
                               "RESTOCK_FEE)")),
                ("RESALEABLE_FLAG", "DECODE(CONDITION_CD, 'NEW', 'Y', 'OPENED', 'Y', 'N')"),
            ]),
        ],
    },
    # ---------------- DM layer ----------------
    {
        "name": "m_DM_AGG_STORE_DAY",
        "sources": ["FACT_SALES", "FACT_RETURNS", "DIM_STORE"], "targets": ["AGG_STORE_DAY"],
        "chain": [
            tx("SQ_FACT_SALES", "Source Qualifier"),
            tx("AGG_BY_STORE_DAY", "Aggregator", fields=[
                ("TXN_COUNT", "COUNT(DISTINCT TXN_ID)"),
                ("NET_SALES", "SUM(NET_AMT)"),
            ]),
            tx("JNR_RETURNS", "Joiner", attrs=[
                ("Join Condition", "DATE_KEY = DATE_KEY1 AND STORE_KEY = STORE_KEY1"),
            ]),
            tx("EXP_REVENUE", "Expression", fields=[
                ("NET_RETURNS", "NVL(SUM_REFUND_AMT, 0) - NVL(SUM_RESTOCK_FEE, 0)"),
                ("NET_REVENUE", "NET_SALES - NET_RETURNS"),
                ("SALES_PER_SQFT", "IIF(SQFT > 0, ROUND(NET_REVENUE / SQFT, 4), NULL)"),
            ]),
        ],
    },
    {
        "name": "m_DM_AGG_PRODUCT_MARGIN",
        "sources": ["FACT_SALES"], "targets": ["AGG_PRODUCT_MARGIN"],
        "chain": [
            tx("SQ_FACT_SALES", "Source Qualifier"),
            tx("AGG_BY_WEEK_PRODUCT", "Aggregator", fields=[
                ("UNITS", "SUM(QTY)"),
                ("REVENUE", "SUM(GROSS_AMT)"),
                ("COST", "SUM(COST_AMT)"),
            ]),
            tx("EXP_MARGIN_PCT", "Expression", fields=[
                ("MARGIN_PCT", ("IIF(REVENUE = 0, NULL, ROUND((REVENUE - COST) / REVENUE * 100, "
                               "1))")),
            ]),
        ],
    },
    {
        "name": "m_DM_LOAD_MEMBER_SEGMENT",
        "sources": ["FACT_SALES", "LOYALTY_MEMBER"], "targets": ["DM_MEMBER_SEGMENT"],
        "chain": [
            tx("SQ_FACT_SALES", "Source Qualifier", attrs=[
                ("Sql Query",
                 ("SELECT F.MEMBER_NO, SUM(F.NET_AMT) SPEND_12M, COUNT(DISTINCT F.DATE_KEY) "
                 "VISITS_12M, MAX(F.DATE_KEY) LAST_VISIT FROM FACT_SALES F, LOYALTY_MEMBER M "
                 "WHERE F.MEMBER_NO = M.MEMBER_NO(+) AND F.DATE_KEY >= "
                 "TO_NUMBER(TO_CHAR(ADD_MONTHS(SYSDATE, -12), 'YYYYMMDD')) "
                 "GROUP BY F.MEMBER_NO")),
            ]),
            tx("EXP_DAYS_IDLE", "Expression", fields=[
                ("DAYS_IDLE", ("DATE_DIFF(SESSSTARTTIME, TO_DATE(TO_CHAR(LAST_VISIT), "
                              "'YYYYMMDD'), 'DD')")),
                ("CHURN_RISK", ("IIF(DAYS_IDLE > 120 AND VISITS_12M < 4, 'HIGH', "
                               "IIF(DAYS_IDLE > 60, 'MEDIUM', 'LOW'))")),
            ]),
            tx("RTR_TIER", "Router", groups=[
                ("PLATINUM", "SPEND_12M >= 5000 AND VISITS_12M >= 24"),
                ("GOLD", "SPEND_12M >= 2000 OR VISITS_12M >= 24"),
                ("SILVER", "SPEND_12M >= 500"),
            ]),
        ],
    },
    {
        # Backfill job, run by hand from its own session. Its rules drifted from the nightly
        # load: ISO weeks in place of the fiscal calendar, and no loyalty discount.
        "name": "m_DW_RELOAD_FACT_SALES_HIST",
        "sources": ["ODS_SALES_LINE", "ODS_ITEM"], "targets": ["FACT_SALES"],
        "chain": [
            tx("SQ_ODS_SALES_LINE", "Source Qualifier", attrs=[
                ("User Defined Join", "ODS_SALES_LINE.SKU = ODS_ITEM.SKU (+)"),
                ("Source Filter", ("ODS_SALES_LINE.TXN_DATE BETWEEN TO_DATE('$$FROM_DATE', "
                                   "'YYYY-MM-DD') AND TO_DATE('$$TO_DATE', 'YYYY-MM-DD')")),
            ]),
            tx("LKP_DIM_STORE", "Lookup Procedure", attrs=[
                ("Lookup condition", "STORE_CODE = IN_STORE_CODE AND CURRENT_FLAG = 'Y'"),
            ]),
            tx("LKP_DIM_PRODUCT", "Lookup Procedure", attrs=[
                ("Lookup condition", "SKU = IN_SKU AND CURRENT_FLAG = 'Y'"),
            ]),
            tx("EXP_HIST_AMOUNTS", "Expression", fields=[
                ("DATE_KEY", "TO_INTEGER(TO_CHAR(TXN_DATE, 'YYYYMMDD'))"),
                ("FISCAL_WEEK", "TO_INTEGER(TO_CHAR(TXN_DATE, 'IW'))"),
                ("GROSS_AMT", "GROSS_AMT_USD"),
                ("NET_AMT", "GROSS_AMT_USD - DISC_AMT_USD"),
                ("COST_AMT", "QTY * NVL(UNIT_COST, 0)"),
                ("MARGIN_AMT", "NET_AMT - COST_AMT"),
                ("STORE_KEY", "IIF(ISNULL(LKP_STORE_KEY), -1, LKP_STORE_KEY)"),
                ("PRODUCT_KEY", "IIF(ISNULL(LKP_PRODUCT_KEY), -1, LKP_PRODUCT_KEY)"),
            ]),
        ],
    },
    {
        # Legacy job: no session runs it. Crawl should list it so someone can retire it.
        "name": "m_LEGACY_PROMO_EXTRACT",
        "sources": ["PROMO_CALENDAR", "FACT_SALES"], "targets": ["PROMO_EXTRACT_OUT"],
        "chain": [
            tx("SQ_PROMO", "Source Qualifier", attrs=[
                ("Sql Query",
                 ("SELECT P.PROMO_ID, F.PRODUCT_KEY SKU, SUM(F.QTY) UNITS, SUM(F.NET_AMT) "
                 "PROMO_REVENUE FROM PROMO_CALENDAR P, FACT_SALES F WHERE F.DATE_KEY BETWEEN "
                 "TO_NUMBER(TO_CHAR(P.START_DT, 'YYYYMMDD')) AND "
                 "TO_NUMBER(TO_CHAR(P.END_DT, 'YYYYMMDD')) GROUP BY P.PROMO_ID, F.PRODUCT_KEY")),
                ("Post SQL", ("BEGIN DBMS_STATS.GATHER_TABLE_STATS('EDW', 'PROMO_EXTRACT_OUT'); "
                             "END;")),
            ]),
        ],
    },
]

# Sessions: one per mapping, except the legacy mapping.
SESSIONS = [m["name"] for m in MAPPINGS if not m["name"].startswith("m_LEGACY")]

# Workflow: ODS loads run in parallel, then dimensions, then facts, then marts.
WF_NAME = "wf_RETAIL_NIGHTLY"
WF_VARIABLES = [("$$LOAD_DATE", "string"), ("$$FX_FALLBACK_USED", "integer")]
WF_LINKS = [
    ("Start", "s_ODS_LOAD_SALES_LINE", ""),
    ("Start", "s_ODS_LOAD_STORE", ""),
    ("Start", "s_ODS_LOAD_ITEM", ""),
    ("Start", "s_ODS_LOAD_RETURNS", ""),
    ("s_ODS_LOAD_STORE", "s_DW_LOAD_DIM_STORE", "$s_ODS_LOAD_STORE.Status = SUCCEEDED"),
    ("s_ODS_LOAD_ITEM", "s_DW_LOAD_DIM_PRODUCT", "$s_ODS_LOAD_ITEM.Status = SUCCEEDED"),
    ("s_DW_LOAD_DIM_STORE", "s_DW_LOAD_FACT_SALES", "$s_DW_LOAD_DIM_STORE.Status = SUCCEEDED"),
    ("s_DW_LOAD_DIM_PRODUCT", "s_DW_LOAD_FACT_SALES",
     "$s_DW_LOAD_DIM_PRODUCT.Status = SUCCEEDED"),
    ("s_ODS_LOAD_SALES_LINE", "s_DW_LOAD_FACT_SALES",
     "$s_ODS_LOAD_SALES_LINE.Status = SUCCEEDED"),
    ("s_ODS_LOAD_RETURNS", "s_DW_LOAD_FACT_RETURNS", "$s_ODS_LOAD_RETURNS.Status = SUCCEEDED"),
    ("s_DW_LOAD_FACT_SALES", "s_DW_LOAD_FACT_RETURNS",
     "$s_DW_LOAD_FACT_SALES.Status = SUCCEEDED"),
    ("s_DW_LOAD_FACT_RETURNS", "s_DM_AGG_STORE_DAY", "$s_DW_LOAD_FACT_RETURNS.Status = SUCCEEDED"),
    ("s_DW_LOAD_FACT_SALES", "s_DM_AGG_PRODUCT_MARGIN",
     "$s_DW_LOAD_FACT_SALES.Status = SUCCEEDED"),
    ("s_DW_LOAD_FACT_SALES", "s_DM_LOAD_MEMBER_SEGMENT",
     "$s_DW_LOAD_FACT_SALES.Status = SUCCEEDED"),
    ("s_DW_LOAD_FACT_SALES", "em_NOTIFY_FAILURE", "$s_DW_LOAD_FACT_SALES.Status = FAILED"),
]


# ------------------------------------------------------------------
# XML builders
# ------------------------------------------------------------------


def _source(parent, name, db_type, cols):
    src = ET.SubElement(parent, "SOURCE", BUSINESSNAME="", DATABASETYPE=db_type,
                        DBDNAME="POS" if db_type == "Oracle" else "FlatFile", DESCRIPTION="",
                        NAME=name, OWNERNAME="POS" if db_type == "Oracle" else "",
                        VERSIONNUMBER="1")
    for i, (col, dtype) in enumerate(cols, 1):
        ET.SubElement(src, "SOURCEFIELD", DATATYPE=dtype, FIELDNUMBER=str(i), NAME=col,
                      KEYTYPE="PRIMARY KEY" if i == 1 else "NOT A KEY", NULLABLE="NULL")


def _target(parent, name, cols):
    tgt = ET.SubElement(parent, "TARGET", BUSINESSNAME="", DATABASETYPE="Oracle",
                        DESCRIPTION="", NAME=name, VERSIONNUMBER="1")
    for i, col in enumerate(cols, 1):
        ET.SubElement(tgt, "TARGETFIELD", DATATYPE="varchar2", FIELDNUMBER=str(i), NAME=col,
                      KEYTYPE="PRIMARY KEY" if i == 1 else "NOT A KEY", NULLABLE="NULL")


def _columns(table):
    if table in SOURCES:
        return [c for c, _ in SOURCES[table][1]]
    return TARGETS[table]


def _wire_ports(spec):
    """Work out each transformation's ports and the port-level connectors.

    Source columns enter the source qualifier. Each target column starts at the last
    transformation that computes it (or at the source qualifier if none does), passes
    through every later transformation, and connects to the target.
    """
    chain = spec["chain"]
    ports = [{port: expr for port, expr in t["fields"]} for t in chain]
    links = []  # (from_instance, from_type, field, to_instance, to_type)

    for src in spec["sources"]:
        for col in _columns(src):
            ports[0].setdefault(col, None)
            links.append((src, "Source Definition", col, chain[0]["name"], chain[0]["type"]))

    for tgt in spec["targets"]:
        for col in TARGETS[tgt]:
            start = max((i for i, p in enumerate(ports) if p.get(col)), default=0)
            ports[start].setdefault(col, None)
            for i in range(start + 1, len(chain)):
                ports[i].setdefault(col, col)  # pass-through port
                links.append((chain[i - 1]["name"], chain[i - 1]["type"], col,
                              chain[i]["name"], chain[i]["type"]))
            links.append((chain[-1]["name"], chain[-1]["type"], col, tgt, "Target Definition"))

    return ports, list(dict.fromkeys(links))


def _mapping(parent, spec):
    m = ET.SubElement(parent, "MAPPING", DESCRIPTION="", ISVALID="YES", NAME=spec["name"],
                      VERSIONNUMBER="1")
    ports, links = _wire_ports(spec)
    for t, tx_ports in zip(spec["chain"], ports):
        el = ET.SubElement(m, "TRANSFORMATION", DESCRIPTION="", NAME=t["name"], REUSABLE="NO",
                           TYPE=t["type"], VERSIONNUMBER="1")
        for grp_name, grp_expr in t["groups"]:
            ET.SubElement(el, "GROUP", DESCRIPTION="", NAME=grp_name, TYPE="OUTPUT",
                          EXPRESSION=grp_expr)
        for port, expr in tx_ports.items():
            attrs = {"DATATYPE": "string", "NAME": port}
            if expr:
                attrs["EXPRESSION"] = expr
                attrs["EXPRESSIONTYPE"] = "GENERAL"
            attrs["PORTTYPE"] = "INPUT/OUTPUT" if expr in (None, port) else "OUTPUT"
            ET.SubElement(el, "TRANSFORMFIELD", **attrs)
        for attr_name, value in t["attrs"]:
            ET.SubElement(el, "TABLEATTRIBUTE", NAME=attr_name, VALUE=value)

    for s in spec["sources"]:
        ET.SubElement(m, "INSTANCE", NAME=s, TRANSFORMATION_NAME=s,
                      TRANSFORMATION_TYPE="Source Definition", TYPE="SOURCE")
    for t in spec["chain"]:
        ET.SubElement(m, "INSTANCE", NAME=t["name"], TRANSFORMATION_NAME=t["name"],
                      TRANSFORMATION_TYPE=t["type"], TYPE="TRANSFORMATION")
    for t in spec["targets"]:
        ET.SubElement(m, "INSTANCE", NAME=t, TRANSFORMATION_NAME=t,
                      TRANSFORMATION_TYPE="Target Definition", TYPE="TARGET")

    for frm, frm_type, col, to, to_type in links:
        ET.SubElement(m, "CONNECTOR", FROMFIELD=col, FROMINSTANCE=frm,
                      FROMINSTANCETYPE=frm_type, TOFIELD=col, TOINSTANCE=to,
                      TOINSTANCETYPE=to_type)


def _session(parent, mapping_name):
    name = "s_" + mapping_name[2:]
    ET.SubElement(parent, "SESSION", DESCRIPTION="", ISVALID="YES", MAPPINGNAME=mapping_name,
                  NAME=name, REUSABLE="YES", VERSIONNUMBER="1")


def _workflow(parent):
    wf = ET.SubElement(parent, "WORKFLOW", DESCRIPTION="Nightly retail EDW load", ISVALID="YES",
                       NAME=WF_NAME, SERVERNAME="IS_RETAIL", VERSIONNUMBER="1")
    ET.SubElement(wf, "TASK", NAME="Start", TYPE="Start")
    ET.SubElement(wf, "TASK", NAME="em_NOTIFY_FAILURE", TYPE="Email")
    ET.SubElement(wf, "TASKINSTANCE", NAME="Start", TASKNAME="Start", TASKTYPE="Start")
    for m in SESSIONS:
        s = "s_" + m[2:]
        ET.SubElement(wf, "TASKINSTANCE", NAME=s, TASKNAME=s, TASKTYPE="Session")
    ET.SubElement(wf, "TASKINSTANCE", NAME="em_NOTIFY_FAILURE", TASKNAME="em_NOTIFY_FAILURE",
                  TASKTYPE="Email")
    for frm, to, cond in WF_LINKS:
        ET.SubElement(wf, "WORKFLOWLINK", CONDITION=cond, FROMTASK=frm, TOTASK=to)
    for var, dtype in WF_VARIABLES:
        ET.SubElement(wf, "WORKFLOWVARIABLE", DATATYPE=dtype, NAME=var, USERDEFINED="YES")


def build() -> str:
    root = ET.Element("POWERMART", CREATION_DATE="03/02/2026 09:00:00",
                      REPOSITORY_VERSION="189.98")
    repo = ET.SubElement(root, "REPOSITORY", NAME="REPO_RETAIL", VERSION="189",
                         CODEPAGE="UTF-8", DATABASETYPE="Oracle")
    folder = ET.SubElement(repo, "FOLDER", NAME=FOLDER, OWNER="Administrator", SHARED="SHARED",
                           DESCRIPTION="Fictional retail warehouse for Crawl demos")
    for name, (db_type, cols) in SOURCES.items():
        _source(folder, name, db_type, cols)
    for name, cols in TARGETS.items():
        _target(folder, name, cols)
    for spec in MAPPINGS:
        _mapping(folder, spec)
    for m in SESSIONS:
        _session(folder, m)
    _workflow(folder)

    body = minidom.parseString(ET.tostring(root, encoding="unicode")).toprettyxml(indent="  ")
    body = body.split("\n", 1)[1]  # drop minidom's XML declaration, add our own with DOCTYPE
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- Fictional demo export for Crawl. Generated by generate_retail_demo.py. -->\n"
        '<!DOCTYPE POWERMART SYSTEM "powrmart.dtd">\n' + body
    )


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUT}")
