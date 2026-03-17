"""Common intermediate representation for all parsers.

Every parser — regardless of source (database, ODI, PowerCenter, etc.) — produces
these data structures. The extraction, triage, and export layers consume only these
types, making them source-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ObjectType(Enum):
    """Type of data object discovered by a parser."""

    STORED_PROC = "stored_procedure"
    VIEW = "view"
    FUNCTION = "function"
    TRIGGER = "trigger"
    # ETL-specific
    MAPPING = "mapping"  # ODI 12c mapping, PowerCenter mapping
    INTERFACE = "interface"  # ODI 11g interface
    PACKAGE = "package"  # ODI package (orchestration)
    WORKFLOW = "workflow"  # PowerCenter workflow
    SESSION = "session"  # PowerCenter session
    LOAD_PLAN = "load_plan"  # ODI load plan


class SourcePlatform(Enum):
    """Source platform identifier."""

    POSTGRESQL = "postgresql"
    ORACLE = "oracle"
    SQLSERVER = "sqlserver"
    SNOWFLAKE = "snowflake"
    ODI = "odi"
    POWERCENTER = "powercenter"
    DATASTAGE = "datastage"


@dataclass
class DataObject:
    """A discovered object: stored proc, view, mapping, interface, etc."""

    name: str
    object_type: ObjectType
    platform: SourcePlatform
    source_code: str | None = None
    # Location in the source system
    schema: str | None = None  # DB schema or ETL project/folder path
    catalog: str | None = None  # DB catalog or ETL repository name
    # Metadata
    last_modified: str | None = None
    last_executed: str | None = None
    owner: str | None = None
    # ETL-specific
    source_tables: list[str] = field(default_factory=list)
    target_tables: list[str] = field(default_factory=list)
    expressions: list[str] = field(default_factory=list)
    knowledge_modules: list[str] = field(default_factory=list)
    # Execution stats (for dead code detection / triage)
    execution_count: int | None = None
    total_rows_processed: int | None = None
    total_errors: int | None = None


@dataclass
class Dependency:
    """A directed dependency between two objects."""

    source: str  # object name
    target: str  # object name
    dependency_type: str = "references"  # references, calls, reads, writes


@dataclass
class BusinessRule:
    """An extracted business rule with confidence score."""

    object_name: str
    rule_text: str
    confidence: float  # 0.0 to 1.0
    line_number: int | None = None
    # What tables/columns are involved
    tables_referenced: list[str] = field(default_factory=list)
    columns_referenced: list[str] = field(default_factory=list)


@dataclass
class Contradiction:
    """A conflict between business rules in different objects."""

    rule_a: BusinessRule
    rule_b: BusinessRule
    description: str
    severity: str = "warning"  # warning, error


@dataclass
class ScanResult:
    """Complete output of a scan operation."""

    platform: SourcePlatform
    objects: list[DataObject] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    # Populated by extraction phase
    rules: list[BusinessRule] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
