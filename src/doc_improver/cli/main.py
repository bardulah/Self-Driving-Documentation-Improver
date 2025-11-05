"""Main CLI entry point."""

import sys
import time
from pathlib import Path
from typing import Optional
import logging

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from doc_improver.models import (
    TargetType,
    ExplorationMode,
    ProjectReport,
    Severity,
)
from doc_improver.explorer.code_explorer import CodeExplorer
from doc_improver.explorer.web_explorer import explore_website_sync
from doc_improver.analyzer.gap_detector import GapDetector
from doc_improver.generator.doc_generator import DocumentationGenerator
from doc_improver.integrations.claude_client import ClaudeClient
from doc_improver.utils.config_manager import ConfigManager
from doc_improver.utils.logger import setup_logger, console, create_progress

logger = setup_logger(__name__)


@click.group()
@click.version_option(version="0.1.0")
def main():
    """
    Self-Driving Documentation Improver

    Automatically explores software/websites, identifies documentation gaps,
    and generates improvements using Claude AI.
    """
    pass


@main.command()
@click.argument('target', type=str)
@click.option(
    '--type', 'target_type',
    type=click.Choice(['code', 'website', 'api'], case_sensitive=False),
    required=True,
    help='Type of target to analyze'
)
@click.option(
    '--mode',
    type=click.Choice(['quick', 'standard', 'deep'], case_sensitive=False),
    default='standard',
    help='Exploration thoroughness level'
)
@click.option(
    '--output', '-o',
    type=click.Path(),
    help='Output file for report'
)
@click.option(
    '--apply',
    is_flag=True,
    help='Automatically apply improvements (use with caution!)'
)
@click.option(
    '--dry-run',
    is_flag=True,
    default=True,
    help='Preview changes without applying'
)
@click.option(
    '--config',
    type=click.Path(exists=True),
    help='Path to configuration file'
)
@click.option(
    '--api-key',
    envvar='ANTHROPIC_API_KEY',
    help='Anthropic API key (or set ANTHROPIC_API_KEY env var)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
def analyze(
    target: str,
    target_type: str,
    mode: str,
    output: Optional[str],
    apply: bool,
    dry_run: bool,
    config: Optional[str],
    api_key: Optional[str],
    verbose: bool
):
    """
    Analyze TARGET for documentation gaps and generate improvements.

    TARGET can be a file path, directory, or URL depending on the type.

    Examples:

        Analyze Python code:
        $ doc-improver analyze ./my_project --type code

        Analyze website:
        $ doc-improver analyze https://example.com/docs --type website

        Apply improvements:
        $ doc-improver analyze ./my_project --type code --apply
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    console.print(Panel.fit(
        "[bold cyan]Self-Driving Documentation Improver[/bold cyan]\n"
        "Analyzing and improving documentation...",
        border_style="cyan"
    ))

    try:
        # Load configuration
        config_manager = ConfigManager(Path(config) if config else None)

        # Get configurations
        exploration_config = config_manager.get_exploration_config(
            target_type=target_type,
            target=target,
            overrides={'mode': mode}
        )

        generation_config = config_manager.get_generation_config(
            overrides={'api_key': api_key, 'auto_apply': apply and not dry_run}
        )

        # Start analysis
        start_time = time.time()

        with create_progress() as progress:
            # Exploration phase
            task = progress.add_task("[cyan]Exploring target...", total=100)

            if target_type == 'code':
                explorer = CodeExplorer(exploration_config)
                entities = explorer.explore()
                progress.update(task, completed=33)

                # Gap detection
                progress.update(task, description="[yellow]Detecting gaps...")
                detector = GapDetector()
                gaps = detector.analyze_code_entities(entities)
                progress.update(task, completed=66)

            elif target_type == 'website':
                pages = explore_website_sync(exploration_config)
                progress.update(task, completed=33)

                # Gap detection
                progress.update(task, description="[yellow]Detecting gaps...")
                detector = GapDetector()
                gaps = detector.analyze_web_pages(pages)
                progress.update(task, completed=66)
            else:
                click.echo("API analysis not yet implemented", err=True)
                sys.exit(1)

            # Generate improvements
            progress.update(task, description="[green]Generating improvements...")
            generator = DocumentationGenerator(generation_config)
            improvements = generator.generate_improvements(gaps)
            progress.update(task, completed=100)

        elapsed_time = time.time() - start_time

        # Display results
        _display_results(
            target,
            TargetType(target_type),
            gaps,
            improvements,
            elapsed_time
        )

        # Apply improvements if requested
        if apply or not dry_run:
            console.print("\n[bold yellow]Applying improvements...[/bold yellow]")
            stats = generator.apply_improvements(dry_run=dry_run)
            console.print(f"Applied: {stats['applied']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}")

        # Export report if requested
        if output:
            output_path = Path(output)
            generator.export_improvements(output_path)
            console.print(f"\n[green]Report exported to: {output_path}[/green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if verbose:
            console.print_exception()
        sys.exit(1)


@main.command()
@click.option(
    '--output', '-o',
    type=click.Path(),
    default='.doc-improver.yaml',
    help='Output path for config file'
)
def init(output: str):
    """
    Initialize configuration file with defaults.
    """
    output_path = Path(output)

    if output_path.exists():
        if not click.confirm(f"{output_path} already exists. Overwrite?"):
            return

    ConfigManager.create_default_config(output_path)
    console.print(f"[green]Configuration file created at: {output_path}[/green]")


@main.command()
@click.option(
    '--api-key',
    envvar='ANTHROPIC_API_KEY',
    help='Anthropic API key to validate'
)
def validate(api_key: Optional[str]):
    """
    Validate Claude API configuration.
    """
    if not api_key:
        console.print("[red]No API key provided. Set ANTHROPIC_API_KEY environment variable.[/red]")
        sys.exit(1)

    try:
        config_manager = ConfigManager()
        gen_config = config_manager.get_generation_config(overrides={'api_key': api_key})

        console.print("[cyan]Validating API key...[/cyan]")
        client = ClaudeClient(gen_config)

        if client.validate_api_key():
            console.print("[green]✓ API key is valid![/green]")
        else:
            console.print("[red]✗ API key validation failed[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        sys.exit(1)


def _display_results(
    target: str,
    target_type: TargetType,
    gaps: list,
    improvements: list,
    elapsed_time: float
):
    """Display analysis results in a formatted table."""

    # Summary panel
    summary = f"""
[bold]Target:[/bold] {target}
[bold]Type:[/bold] {target_type.value}
[bold]Time:[/bold] {elapsed_time:.2f}s
[bold]Gaps Found:[/bold] {len(gaps)}
[bold]Improvements Generated:[/bold] {len(improvements)}
"""

    console.print(Panel(summary, title="Analysis Summary", border_style="green"))

    # Gaps by severity
    if gaps:
        table = Table(title="Documentation Gaps by Severity")
        table.add_column("Severity", style="cyan")
        table.add_column("Count", justify="right", style="magenta")

        severity_counts = {}
        for gap in gaps:
            severity_counts[gap.severity.value] = severity_counts.get(gap.severity.value, 0) + 1

        for severity in ['critical', 'high', 'medium', 'low']:
            count = severity_counts.get(severity, 0)
            if count > 0:
                color = {
                    'critical': 'red',
                    'high': 'yellow',
                    'medium': 'blue',
                    'low': 'green'
                }[severity]
                table.add_row(f"[{color}]{severity.upper()}[/{color}]", str(count))

        console.print(table)

    # Sample improvements
    if improvements:
        console.print("\n[bold cyan]Sample Improvements:[/bold cyan]")
        for i, imp in enumerate(improvements[:3], 1):
            console.print(f"\n[yellow]{i}. {imp.gap.location}[/yellow]")
            console.print(f"   Confidence: {imp.confidence_score:.2%}")
            console.print(f"   {imp.gap.description}")


if __name__ == '__main__':
    main()
