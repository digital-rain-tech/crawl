"""ODI XML parser — offline parsing of ODI Smart Export files.

Usage:
    crawl scan --source odi-export:./my_export.zip
    crawl scan --source odi-export:./directory_of_xmls

Parses the XML files produced by ODI Studio's Smart Export feature
(File → Export → Smart Export). This mode requires no database connection,
making it ideal for first customer engagements where DB access isn't available.

The Smart Export XML uses a <SunopsisExport> root element containing <Object>
elements with class attributes mapping to internal Java classes (SnpTrt, SnpPop,
SnpMapping, SnpLineTrt, etc.). Each Object has <Field> children with name/type/value.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from crawl.models import (
    DataObject,
    ObjectType,
    ScanResult,
    SourcePlatform,
)
from crawl.parsers import BaseParser

# Map ODI Java class names to our categories
_CLASS_PREFIX = "com.sunopsis.dwg.dbobj."

# TrtType field values for Knowledge Modules
_KM_TYPES = {
    "KI": "IKM",  # Integration KM
    "KL": "LKM",  # Loading KM
    "KC": "CKM",  # Check KM
    "KR": "RKM",  # Reverse-engineering KM
    "KJ": "JKM",  # Journalizing KM
    "KS": "SKM",  # Service KM
}


def _get_field(obj_elem: ET.Element, field_name: str) -> str | None:
    """Extract field value from an ODI Object element."""
    for field in obj_elem.findall("Field"):
        if field.get("name") == field_name:
            text = field.text
            if text is None or text == "null":
                return None
            return text.strip()
    return None


def _get_class_name(obj_elem: ET.Element) -> str:
    """Get the short class name (e.g., 'SnpTrt' from full Java class)."""
    cls = obj_elem.get("class", "")
    if cls.startswith(_CLASS_PREFIX):
        return cls[len(_CLASS_PREFIX) :]
    return cls


class OdiXmlParser(BaseParser):
    """Parser for ODI Smart Export XML/ZIP files.

    Accepts:
    - A single .xml file (one Smart Export object)
    - A .zip file (standard Smart Export output with multiple XMLs)
    - A directory of .xml files
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def test_connection(self) -> bool:
        """Verify the export file/directory exists and looks like ODI XML."""
        if not self.path.exists():
            return False
        if self.path.is_file():
            suffix = self.path.suffix.lower()
            if suffix == ".zip":
                return True
            if suffix == ".xml":
                return self._is_odi_xml(self.path)
        if self.path.is_dir():
            return any(self.path.glob("*.xml"))
        return False

    def scan(self) -> ScanResult:
        """Parse ODI Smart Export XML and produce a ScanResult."""
        xml_files = self._collect_xml_files()
        result = ScanResult(platform=SourcePlatform.ODI)

        # First pass: collect all objects indexed by class and ID
        all_objects: dict[str, list[ET.Element]] = {}
        for xml_path in xml_files:
            for obj_elem in self._parse_xml(xml_path):
                cls = _get_class_name(obj_elem)
                all_objects.setdefault(cls, []).append(obj_elem)

        # Extract Knowledge Modules (SnpTrt with KM TrtType)
        self._extract_knowledge_modules(all_objects, result)

        # Extract KM steps (SnpLineTrt) and link to their KM
        self._extract_km_steps(all_objects, result)

        # Extract Interfaces (SnpPop — 11g style)
        self._extract_interfaces(all_objects, result)

        # Extract Mappings (SnpMapping — 12c style)
        self._extract_mappings(all_objects, result)

        # Extract mapping components (SnpMapComp — 12c)
        self._extract_mapping_components(all_objects, result)

        # Extract technologies (SnpTechno)
        self._extract_technologies(all_objects, result)

        return result

    def _collect_xml_files(self) -> list[Path]:
        """Gather all XML files to parse."""
        if self.path.is_file():
            if self.path.suffix.lower() == ".zip":
                return self._extract_zip()
            return [self.path]
        if self.path.is_dir():
            return sorted(self.path.glob("*.xml"))
        return []

    def _extract_zip(self) -> list[Path]:
        """Extract ZIP and return paths to XML files inside."""
        import tempfile

        self._tmp_dir = tempfile.mkdtemp(prefix="crawl_odi_")
        tmp = Path(self._tmp_dir)
        with zipfile.ZipFile(self.path, "r") as zf:
            zf.extractall(tmp)
        return sorted(tmp.rglob("*.xml"))

    def _is_odi_xml(self, path: Path) -> bool:
        """Quick check if a file looks like ODI export XML."""
        try:
            with open(path, "r", encoding="iso-8859-1") as f:
                header = f.read(500)
            return "<SunopsisExport>" in header
        except Exception:
            return False

    def _parse_xml(self, path: Path) -> list[ET.Element]:
        """Parse an ODI XML file and return all Object elements."""
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            if root.tag != "SunopsisExport":
                return []
            return root.findall("Object")
        except ET.ParseError:
            return []

    def _extract_knowledge_modules(
        self, all_objects: dict[str, list[ET.Element]], result: ScanResult
    ) -> None:
        """Extract KMs from SnpTrt objects."""
        for obj in all_objects.get("SnpTrt", []):
            trt_type = _get_field(obj, "TrtType")
            trt_name = _get_field(obj, "TrtName")
            if not trt_name:
                continue

            km_label = _KM_TYPES.get(trt_type or "", "")
            if not km_label:
                # Not a KM — could be a procedure or other treatment
                continue

            data_obj = DataObject(
                name=trt_name,
                object_type=ObjectType.MAPPING,  # KMs define transformation logic
                platform=SourcePlatform.ODI,
                schema=km_label,  # Use schema field to store KM type
                last_modified=_get_field(obj, "LastDate"),
                owner=_get_field(obj, "LastUser"),
                knowledge_modules=[f"{km_label}: {trt_name}"],
            )

            # Collect description text from linked SnpTxt
            i_txt = _get_field(obj, "ITxtTrtTxt")
            if i_txt:
                for txt_obj in all_objects.get("SnpTxt", []):
                    if _get_field(txt_obj, "ITxt") == i_txt:
                        desc = _get_field(txt_obj, "Txt")
                        if desc:
                            data_obj.source_code = desc
                        break
                # Also check SnpTxtHeader
                for txt_obj in all_objects.get("SnpTxtHeader", []):
                    if _get_field(txt_obj, "ITxt") == i_txt:
                        desc = _get_field(txt_obj, "Txt")
                        if desc and not data_obj.source_code:
                            data_obj.source_code = desc
                        break

            result.objects.append(data_obj)

    def _extract_km_steps(
        self, all_objects: dict[str, list[ET.Element]], result: ScanResult
    ) -> None:
        """Extract KM step SQL from SnpLineTrt objects and attach to parent KMs."""
        # Build ITrt → DataObject index
        km_by_itrt: dict[str, DataObject] = {}
        for obj in result.objects:
            # Find the corresponding SnpTrt to get ITrt
            for trt in all_objects.get("SnpTrt", []):
                if _get_field(trt, "TrtName") == obj.name:
                    itrt = _get_field(trt, "ITrt")
                    if itrt:
                        km_by_itrt[itrt] = obj
                    break

        # Build ITxt → text content index
        txt_by_id: dict[str, str] = {}
        for cls_name in ("SnpTxtHeader", "SnpTxt"):
            for txt_obj in all_objects.get(cls_name, []):
                i_txt = _get_field(txt_obj, "ITxt")
                txt = _get_field(txt_obj, "Txt")
                if i_txt and txt:
                    txt_by_id.setdefault(i_txt, txt)

        # Link steps to their parent KM
        for step in all_objects.get("SnpLineTrt", []):
            itrt = _get_field(step, "ITrt")
            step_name = _get_field(step, "SqlName") or "unnamed_step"
            technology = _get_field(step, "DefTechno") or ""

            parent = km_by_itrt.get(itrt or "")
            if not parent:
                continue

            # Collect source SQL (ColITxt) and target SQL (DefITxt)
            col_txt_id = _get_field(step, "ColITxt")
            def_txt_id = _get_field(step, "DefITxt")
            col_sql = txt_by_id.get(col_txt_id or "")
            def_sql = txt_by_id.get(def_txt_id or "")

            step_desc = f"[{step_name}] ({technology})"
            if col_sql:
                step_desc += f"\n  Source: {col_sql[:200]}"
            if def_sql:
                step_desc += f"\n  Target: {def_sql[:200]}"

            parent.expressions.append(step_desc)

    def _extract_interfaces(
        self, all_objects: dict[str, list[ET.Element]], result: ScanResult
    ) -> None:
        """Extract 11g interfaces from SnpPop objects."""
        for obj in all_objects.get("SnpPop", []):
            pop_name = _get_field(obj, "PopName")
            if not pop_name:
                continue
            data_obj = DataObject(
                name=pop_name,
                object_type=ObjectType.INTERFACE,
                platform=SourcePlatform.ODI,
                last_modified=_get_field(obj, "LastDate"),
                owner=_get_field(obj, "LastUser"),
            )
            result.objects.append(data_obj)

    def _extract_mappings(
        self, all_objects: dict[str, list[ET.Element]], result: ScanResult
    ) -> None:
        """Extract 12c mappings from SnpMapping objects."""
        for obj in all_objects.get("SnpMapping", []):
            name = _get_field(obj, "Name") or _get_field(obj, "MappingName")
            if not name:
                continue
            data_obj = DataObject(
                name=name,
                object_type=ObjectType.MAPPING,
                platform=SourcePlatform.ODI,
                last_modified=_get_field(obj, "LastDate"),
                owner=_get_field(obj, "LastUser"),
            )
            result.objects.append(data_obj)

    def _extract_mapping_components(
        self, all_objects: dict[str, list[ET.Element]], result: ScanResult
    ) -> None:
        """Extract 12c mapping components (datastores, joins, filters, etc.)."""
        for obj in all_objects.get("SnpMapComp", []):
            comp_name = _get_field(obj, "Name")
            comp_type = _get_field(obj, "TypeName")
            if comp_type == "DATASTORE" and comp_name:
                # Could be a source or target — we'll need connection info to determine
                # For now just note the datastore reference
                pass

    def _extract_technologies(
        self, all_objects: dict[str, list[ET.Element]], result: ScanResult
    ) -> None:
        """Extract technology definitions (Oracle, SQL Server, etc.)."""
        for obj in all_objects.get("SnpTechno", []):
            tech_name = _get_field(obj, "TechnoName")
            if tech_name:
                # Store as metadata, not a scannable object
                pass
