"""Crawl CLI — pre-migration intelligence for enterprise data infrastructure."""

import click

from crawl import __version__


@click.group()
@click.version_option(version=__version__)
def main():
    """Crawl: Extract business logic from your data infrastructure."""
    pass


@main.command()
@click.option("--source", required=True, help="Database connection string (e.g., postgres://...)")
def scan(source: str):
    """Connect to a database and discover stored procs, views, and functions."""
    click.echo(f"Scanning {source}...")
    click.echo("Not yet implemented. Follow progress at https://github.com/digital-rain-tech/crawl")


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
