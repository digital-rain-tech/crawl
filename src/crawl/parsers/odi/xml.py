"""ODI XML parser — offline parsing of ODI Smart Export files.

Usage:
    crawl scan --source odi-export:./my_export.zip

Parses the XML files produced by ODI Studio's Smart Export feature
(File → Export → Smart Export). This mode requires no database connection,
making it ideal for first customer engagements where DB access isn't available.

The Smart Export ZIP contains XML files with mapping definitions, interface
definitions, packages, knowledge module assignments, and dependency metadata.
"""

from __future__ import annotations

from pathlib import Path

from crawl.models import ScanResult, SourcePlatform
from crawl.parsers import BaseParser


class OdiXmlParser(BaseParser):
    """Parser for ODI Smart Export XML/ZIP files.

    Accepts either a .zip file (standard Smart Export output) or a directory
    of extracted XML files.
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def test_connection(self) -> bool:
        """Verify the export file/directory exists and looks like ODI XML."""
        if not self.path.exists():
            return False
        if self.path.is_file() and self.path.suffix.lower() == ".zip":
            return True
        if self.path.is_dir():
            # Look for ODI XML markers
            return any(self.path.glob("*.xml"))
        return False

    def scan(self) -> ScanResult:
        """Parse ODI Smart Export XML and produce a ScanResult."""
        # TODO: Implementation outline:
        # 1. If ZIP, extract to temp directory
        # 2. Find and parse XML files
        # 3. Extract mapping/interface definitions
        # 4. Extract source/target table references
        # 5. Extract transformation expressions
        # 6. Build DataObjects and Dependencies
        # 7. Return ScanResult
        raise NotImplementedError("ODI XML parsing not yet implemented")
