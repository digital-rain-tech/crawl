"""Crawl CLI — pre-migration intelligence for enterprise data infrastructure."""

import click
from rich.console import Console

from crawl import __version__

console = Console()


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

    console.print(f"Scanning [bold]{source}[/]...")
    result = parser.scan()

    console.print(f"\nDiscovered [bold green]{len(result.objects)}[/] objects:")
    for obj in result.objects:
        sources = ", ".join(obj.source_tables) if obj.source_tables else "?"
        targets = ", ".join(obj.target_tables) if obj.target_tables else "?"
        console.print(f"  {obj.object_type.value}: [bold]{obj.name}[/]  {sources} → {targets}")

    console.print(f"\n[bold green]{len(result.dependencies)}[/] dependencies found.")


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
@click.option("--format", "fmt", type=click.Choice(["dbt-docs", "json", "markdown"]), default="json")
def export(fmt: str):
    """Export extracted logic to dbt-docs YAML, JSON, or Markdown."""
    click.echo(f"Export format: {fmt}")
    click.echo("Not yet implemented.")


if __name__ == "__main__":
    main()
