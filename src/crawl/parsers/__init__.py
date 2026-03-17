"""Database and ETL parsers for extracting transformation logic.

All parsers implement the BaseParser protocol and produce ScanResult objects
containing the common intermediate representation (DataObject, Dependency, etc.).

Parsers are resolved from source strings by the registry:
    oracle://host/sid    → Oracle stored proc parser
    postgres://host/db   → PostgreSQL parser
    odi://host/repo      → ODI parser (live DB mode)
    odi-export:./file    → ODI parser (offline XML mode)
    pctr-export:./file   → PowerCenter parser (offline XML mode)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from crawl.models import ScanResult


class BaseParser(ABC):
    """Base class for all source parsers."""

    @abstractmethod
    def scan(self) -> ScanResult:
        """Discover all objects in the source and return a ScanResult."""
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        """Verify the source is accessible. Returns True if OK."""
        ...
