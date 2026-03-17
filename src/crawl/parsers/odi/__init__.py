"""Oracle Data Integrator (ODI) parsers.

Two ingestion modes:
- db.OdiDbParser:  Live queries against the ODI work repository (SNP_ tables)
- xml.OdiXmlParser: Offline parsing of ODI Smart Export XML/ZIP files

Both produce the same ScanResult with DataObjects representing ODI mappings (12c)
and interfaces (11g), plus source-to-target dependencies and transformation expressions.
"""
