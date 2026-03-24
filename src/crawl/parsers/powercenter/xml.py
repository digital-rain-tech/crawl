"""PowerCenter XML parser — offline parsing of POWERMART export files.

Usage:
    crawl scan --source pctr-export:./workflow.xml
    crawl scan --source pctr-export:./directory_of_xmls

Parses the XML files produced by Informatica PowerCenter's Repository Manager
export (File → Export Objects). These use the powrmart.dtd schema with a
<POWERMART> root element.

Object hierarchy:
    POWERMART → REPOSITORY → FOLDER → {SOURCE, TARGET, MAPPLET, MAPPING, SESSION, WORKFLOW}

Within a MAPPING:
    TRANSFORMATION  — the logic (Expression, Filter, Lookup, Aggregator, Router, etc.)
    INSTANCE        — placed copy of a TRANSFORMATION, SOURCE, TARGET, or MAPPLET
    CONNECTOR       — data flow link between two INSTANCE ports

Within a WORKFLOW:
    TASK            — non-session tasks (Event Wait, Control, Email, etc.)
    TASKINSTANCE    — placed copy of a SESSION or TASK in the workflow DAG
    WORKFLOWLINK    — execution dependency between TASKINSTANCEs
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from crawl.models import (
    DataObject,
    Dependency,
    ObjectType,
    ScanResult,
    SourcePlatform,
)
from crawl.parsers import BaseParser


def _attr(elem: ET.Element, name: str) -> str:
    """Get a stripped attribute value, or empty string."""
    return (elem.get(name) or "").strip()


class PctrXmlParser(BaseParser):
    """Parser for Informatica PowerCenter POWERMART XML exports.

    Accepts:
    - A single .xml file (one workflow/folder export)
    - A directory of .xml files
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def test_connection(self) -> bool:
        """Verify the export file/directory exists and looks like POWERMART XML."""
        if not self.path.exists():
            return False
        if self.path.is_file():
            return self._is_powermart_xml(self.path)
        if self.path.is_dir():
            return any(
                self._is_powermart_xml(p)
                for p in self.path.iterdir()
                if p.suffix.lower() == ".xml" and p.is_file()
            )
        return False

    def scan(self) -> ScanResult:
        """Parse PowerCenter XML export and produce a ScanResult."""
        xml_files = self._collect_xml_files()
        result = ScanResult(platform=SourcePlatform.POWERCENTER)

        for xml_path in xml_files:
            tree = self._parse_xml(xml_path)
            if tree is None:
                continue
            root = tree.getroot()
            for folder in root.iter("FOLDER"):
                self._extract_folder(folder, result)

        return result

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    def _collect_xml_files(self) -> list[Path]:
        """Gather all XML files to parse (case-insensitive extension)."""
        if self.path.is_file():
            return [self.path]
        if self.path.is_dir():
            # PowerCenter exports often use .XML (uppercase)
            return sorted(
                p for p in self.path.iterdir() if p.suffix.lower() == ".xml" and p.is_file()
            )
        return []

    def _is_powermart_xml(self, path: Path) -> bool:
        """Quick check if a file is a POWERMART export."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                header = f.read(500)
            return "<POWERMART" in header or "powrmart.dtd" in header
        except Exception:
            return False

    def _parse_xml(self, path: Path) -> ET.ElementTree | None:
        """Parse an XML file, returning the tree or None on failure."""
        try:
            return ET.parse(path)
        except ET.ParseError:
            return None

    # ------------------------------------------------------------------
    # Folder-level extraction
    # ------------------------------------------------------------------

    def _extract_folder(self, folder: ET.Element, result: ScanResult) -> None:
        """Extract all objects from a FOLDER element."""
        folder_name = _attr(folder, "NAME")

        # Collect source/target names for linking to mappings
        source_names: set[str] = set()
        target_names: set[str] = set()
        for src in folder.findall("SOURCE"):
            name = _attr(src, "NAME")
            if name:
                source_names.add(name)
        for tgt in folder.findall("TARGET"):
            name = _attr(tgt, "NAME")
            if name:
                target_names.add(name)

        # Extract mappings
        for mapping_elem in folder.findall("MAPPING"):
            self._extract_mapping(mapping_elem, folder_name, source_names, target_names, result)

        # Extract sessions
        for session_elem in folder.findall("SESSION"):
            self._extract_session(session_elem, folder_name, result)

        # Extract workflows
        for wf_elem in folder.findall("WORKFLOW"):
            self._extract_workflow(wf_elem, folder_name, result)

    # ------------------------------------------------------------------
    # Mapping extraction
    # ------------------------------------------------------------------

    def _extract_mapping(
        self,
        mapping: ET.Element,
        folder: str,
        source_names: set[str],
        target_names: set[str],
        result: ScanResult,
    ) -> None:
        """Extract a MAPPING into a DataObject with transformations and data flow."""
        name = _attr(mapping, "NAME")
        if not name:
            return

        # Collect source/target references from INSTANCEs within this mapping
        sources: list[str] = []
        targets: list[str] = []
        for inst in mapping.findall("INSTANCE"):
            inst_type = _attr(inst, "TYPE")
            tname = _attr(inst, "TRANSFORMATION_NAME")
            if inst_type == "SOURCE" and tname:
                sources.append(tname)
            elif inst_type == "TARGET" and tname:
                targets.append(tname)

        # Collect transformation expressions and filter conditions
        expressions: list[str] = []
        for tx in mapping.findall("TRANSFORMATION"):
            tx_name = _attr(tx, "NAME")
            tx_type = _attr(tx, "TYPE")

            # Collect expression fields
            for tf in tx.findall("TRANSFORMFIELD"):
                expr = _attr(tf, "EXPRESSION")
                field_name = _attr(tf, "NAME")
                if expr and expr != field_name:  # Skip pass-through
                    expressions.append(f"[{tx_name}:{tx_type}] {field_name} = {expr}")

            # Collect table attributes with business logic
            for ta in tx.findall("TABLEATTRIBUTE"):
                ta_name = _attr(ta, "NAME")
                ta_value = _attr(ta, "VALUE")
                if ta_value and ta_name in (
                    "Filter Condition",
                    "Lookup condition",
                    "Lookup Sql Override",
                    "Sql Query",
                    "User Defined Join",
                    "Source Filter",
                    "Pre SQL",
                    "Post SQL",
                ):
                    expressions.append(f"[{tx_name}:{tx_type}] {ta_name}: {ta_value}")

            # Collect Router GROUP conditions
            for grp in tx.findall("GROUP"):
                grp_name = _attr(grp, "NAME")
                grp_expr = _attr(grp, "EXPRESSION")
                if grp_expr:
                    expressions.append(f"[{tx_name}:Router] Group {grp_name}: {grp_expr}")

        data_obj = DataObject(
            name=name,
            object_type=ObjectType.MAPPING,
            platform=SourcePlatform.POWERCENTER,
            schema=folder,
            source_tables=sorted(set(sources)),
            target_tables=sorted(set(targets)),
            expressions=expressions,
        )
        result.objects.append(data_obj)

        # Add data flow dependencies from CONNECTORs
        for conn in mapping.findall("CONNECTOR"):
            from_inst = _attr(conn, "FROMINSTANCE")
            to_inst = _attr(conn, "TOINSTANCE")
            if from_inst and to_inst:
                result.dependencies.append(
                    Dependency(
                        source=f"{name}/{from_inst}",
                        target=f"{name}/{to_inst}",
                        dependency_type="data_flow",
                    )
                )

    # ------------------------------------------------------------------
    # Session extraction
    # ------------------------------------------------------------------

    def _extract_session(self, session: ET.Element, folder: str, result: ScanResult) -> None:
        """Extract a SESSION — runtime config that binds a mapping to connections."""
        name = _attr(session, "NAME")
        mapping_name = _attr(session, "MAPPINGNAME")
        if not name:
            return

        data_obj = DataObject(
            name=name,
            object_type=ObjectType.SESSION,
            platform=SourcePlatform.POWERCENTER,
            schema=folder,
        )

        # Link session → mapping dependency
        if mapping_name:
            result.dependencies.append(
                Dependency(source=name, target=mapping_name, dependency_type="references")
            )

        result.objects.append(data_obj)

    # ------------------------------------------------------------------
    # Workflow extraction
    # ------------------------------------------------------------------

    def _extract_workflow(self, workflow: ET.Element, folder: str, result: ScanResult) -> None:
        """Extract a WORKFLOW — orchestration DAG of sessions and tasks."""
        name = _attr(workflow, "NAME")
        if not name:
            return

        data_obj = DataObject(
            name=name,
            object_type=ObjectType.WORKFLOW,
            platform=SourcePlatform.POWERCENTER,
            schema=folder,
        )

        # Collect workflow variable names as expressions
        for wf_var in workflow.findall("WORKFLOWVARIABLE"):
            var_name = _attr(wf_var, "NAME")
            var_type = _attr(wf_var, "DATATYPE")
            if var_name:
                data_obj.expressions.append(f"[Variable] {var_name} ({var_type})")

        result.objects.append(data_obj)

        # Extract task execution dependencies from WORKFLOWLINKs
        for link in workflow.findall("WORKFLOWLINK"):
            from_task = _attr(link, "FROMTASK")
            to_task = _attr(link, "TOTASK")
            condition = _attr(link, "CONDITION")
            if from_task and to_task:
                dep_type = "executes_after"
                if condition:
                    dep_type = f"executes_after({condition})"
                result.dependencies.append(
                    Dependency(
                        source=f"{name}/{from_task}",
                        target=f"{name}/{to_task}",
                        dependency_type=dep_type,
                    )
                )

        # Link workflow → session dependencies from TASKINSTANCEs
        for ti in workflow.findall("TASKINSTANCE"):
            task_type = _attr(ti, "TASKTYPE")
            task_name = _attr(ti, "TASKNAME")
            if task_type == "Session" and task_name:
                result.dependencies.append(
                    Dependency(
                        source=name,
                        target=task_name,
                        dependency_type="contains",
                    )
                )
