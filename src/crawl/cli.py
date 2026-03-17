"""Crawl CLI — pre-migration intelligence for enterprise data infrastructure."""

import click
from rich.console import Console
from rich.table import Table

from crawl import __version__

console = Console()

# Human-readable descriptions for ODI Knowledge Module types
_KM_DESCRIPTIONS = {
    "IKM": "Integration KM — loads staged data into target (insert/update/merge strategy)",
    "LKM": "Loading KM — moves data from source to staging area",
    "CKM": "Check KM — validates data quality, isolates rejected rows",
    "RKM": "Reverse-engineering KM — reads source metadata (tables, columns, keys)",
    "JKM": "Journalizing KM — tracks row-level changes for incremental loads (CDC)",
    "SKM": "Service KM — exposes data operations as web services",
}


def _format_object_type(obj) -> str:
    """Format object type with KM-aware labeling."""
    km_type = obj.schema if obj.schema in _KM_DESCRIPTIONS else None
    if km_type:
        return km_type
    return obj.object_type.value


def _format_object_description(obj) -> str:
    """One-line description based on object type."""
    km_type = obj.schema if obj.schema in _KM_DESCRIPTIONS else None
    if km_type:
        return _KM_DESCRIPTIONS[km_type]
    sources = ", ".join(obj.source_tables) if obj.source_tables else ""
    targets = ", ".join(obj.target_tables) if obj.target_tables else ""
    if sources and targets:
        return f"{sources} → {targets}"
    if targets:
        return f"→ {targets}"
    if sources:
        return f"{sources} →"
    return ""


@click.group()
@click.version_option(version=__version__)
def main():
    """Crawl: Extract business logic from your data infrastructure."""
    pass


@main.command()
@click.option(
    "--source",
    required=True,
    help=(
        "Source to scan. Examples:\n"
        "  postgres://host/db          PostgreSQL stored procedures\n"
        "  oracle://host:1521/sid      Oracle PL/SQL\n"
        "  odi://host:1521/repo        ODI work repository (live DB)\n"
        "  odi-export:./export.zip     ODI Smart Export XML (offline)\n"
        "  pctr-export:./workflow.xml  PowerCenter XML export (offline)"
    ),
)
@click.option(
    "--i-know-this-is-prod",
    is_flag=True,
    default=False,
    help="Override production connection warning.",
)
def scan(source: str, i_know_this_is_prod: bool):
    """Discover stored procs, views, mappings, and ETL objects from a source."""
    from crawl.parsers.registry import resolve_parser

    # Warn on production-looking connection strings
    prod_keywords = ("prod", "production", "prd", "live")
    if any(kw in source.lower() for kw in prod_keywords) and not i_know_this_is_prod:
        console.print(
            "[bold red]WARNING:[/] Source string looks like a production environment.\n"
            "Crawl recommends connecting to staging/QA — stored procedure source code "
            "is identical across environments.\n"
            "Pass --i-know-this-is-prod to override.",
        )
        raise SystemExit(1)

    try:
        parser = resolve_parser(source)
    except (ValueError, NotImplementedError) as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise SystemExit(1)

    console.print(f"Resolved parser: [bold]{type(parser).__name__}[/]")

    if not parser.test_connection():
        console.print("[bold red]Error:[/] Could not connect to source.")
        raise SystemExit(1)

    console.print(f"Scanning [bold]{source}[/]...\n")
    result = parser.scan()

    if not result.objects:
        console.print("[yellow]No objects discovered.[/]")
        return

    # Build results table
    table = Table(title=f"Discovered {len(result.objects)} objects", show_lines=False)
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Name", style="bold")
    table.add_column("Description", style="dim")
    table.add_column("Steps", justify="right")

    for obj in result.objects:
        step_count = str(len(obj.expressions)) if obj.expressions else ""
        table.add_row(
            _format_object_type(obj),
            obj.name,
            _format_object_description(obj),
            step_count,
        )

    console.print(table)

    # Summary
    if result.dependencies:
        console.print(f"\n{len(result.dependencies)} dependencies found.")

    # Show KM type legend if any KMs were found
    km_types_found = {
        obj.schema for obj in result.objects if obj.schema in _KM_DESCRIPTIONS
    }
    if km_types_found:
        console.print("\n[dim]Knowledge Module types:[/]")
        for km_type in sorted(km_types_found):
            console.print(f"  [cyan]{km_type}[/]  {_KM_DESCRIPTIONS[km_type]}")


@main.command()
def extract():
    """Extract human-readable business rules from discovered objects."""
    click.echo("Not yet implemented.")


@main.command()
def triage():
    """Score each object by criticality, complexity, and migration risk."""
    click.echo("Not yet implemented.")


@main.command()
@click.option("--env", multiple=True, help="Environments to compare")
def diff(env: tuple[str, ...]):
    """Compare extracted logic between environments."""
    click.echo("Not yet implemented.")


@main.command()
@click.option(
    "--format", "fmt", type=click.Choice(["dbt-docs", "json", "markdown"]), default="json"
)
def export(fmt: str):
    """Export extracted logic to dbt-docs YAML, JSON, or Markdown."""
    click.echo(f"Export format: {fmt}")
    click.echo("Not yet implemented.")


if __name__ == "__main__":
    main()
