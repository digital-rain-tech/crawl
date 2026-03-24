"""Source string resolution — maps --source arguments to the right parser.

Examples:
    oracle://host:1521/sid     → Oracle stored procedure parser
    postgres://host:5432/db    → PostgreSQL parser
    odi://host:1521/repo       → ODI DB parser (live queries against SNP_ tables)
    odi-export:./export.zip    → ODI XML parser (offline Smart Export)
    pctr-export:./workflow.xml → PowerCenter XML parser (offline powrmart.dtd)
"""

from __future__ import annotations

from urllib.parse import urlparse

from crawl.parsers import BaseParser


def resolve_parser(source: str) -> BaseParser:
    """Parse a source string and return the appropriate parser instance.

    Raises:
        ValueError: If the source string scheme is not recognized.
    """
    # Handle offline export schemes (prefix:path)
    if ":" in source and "//" not in source:
        scheme, path = source.split(":", 1)
        return _resolve_export_parser(scheme.lower(), path)

    # Handle DB connection strings (scheme://...)
    parsed = urlparse(source)
    scheme = parsed.scheme.lower()

    if scheme in ("postgres", "postgresql"):
        raise NotImplementedError("PostgreSQL parser not yet implemented")
    elif scheme == "oracle":
        raise NotImplementedError("Oracle stored procedure parser not yet implemented")
    elif scheme == "odi":
        from crawl.parsers.odi.db import OdiDbParser

        return OdiDbParser(source)
    elif scheme in ("sqlserver", "mssql"):
        raise NotImplementedError("SQL Server parser not yet implemented")
    elif scheme == "snowflake":
        raise NotImplementedError("Snowflake parser not yet implemented")
    else:
        raise ValueError(
            f"Unknown source scheme: {scheme!r}. "
            f"Supported: postgres, oracle, odi, sqlserver, snowflake, "
            f"odi-export, pctr-export"
        )


def _resolve_export_parser(scheme: str, path: str) -> BaseParser:
    """Resolve offline export source strings."""
    if scheme == "odi-export":
        from crawl.parsers.odi.xml import OdiXmlParser

        return OdiXmlParser(path)
    elif scheme == "pctr-export":
        from crawl.parsers.powercenter.xml import PctrXmlParser

        return PctrXmlParser(path)
    else:
        raise ValueError(
            f"Unknown export scheme: {scheme!r}. "
            f"Supported: odi-export, pctr-export"
        )
