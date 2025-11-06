"""Enhanced CLI with all new features."""

import sys
import time
import asyncio
from pathlib import Path
from typing import Optional
import logging

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn

from doc_improver.models import (
    TargetType,
    ExplorationMode,
    Severity,
)
from doc_improver.explorer.code_explorer_v2 import CodeExplorerV2
from doc_improver.explorer.web_explorer import explore_website_sync
from doc_improver.analyzer.gap_detector import GapDetector
from doc_improver.generator.doc_generator import DocumentationGenerator
from doc_improver.integrations.claude_client_v2 import ClaudeClientV2
from doc_improver.utils.config_manager import ConfigManager
from doc_improver.utils.logger import setup_logger, console
from doc_improver.utils.cache import SyncCacheManager
from doc_improver.utils.metrics import MetricsTracker, StateManager
from doc_improver.utils.ast_rewriter import ASTRewriter, can_apply_improvements
from doc_improver.utils.git_integration import GitIntegration, create_documentation_pr_workflow
from doc_improver.cli.interactive import run_interactive_review, quick_review_mode, QUESTIONARY_AVAILABLE

logger = setup_logger(__name__)


@click.group()
@click.version_option(version="0.2.0")
def main():
    """
    Self-Driving Documentation Improver v2.0

    Automatically explores software/websites, identifies documentation gaps,
    and generates improvements using Claude AI.
    """
    pass


@main.command()
@click.argument('target', type=str)
@click.option('--type', 'target_type', type=click.Choice(['code', 'website', 'api']), required=True)
@click.option('--mode', type=click.Choice(['quick', 'standard', 'deep']), default='standard')
@click.option('--output', '-o', type=click.Path(), help='Output file for report')
@click.option('--apply', is_flag=True, help='Apply improvements automatically')
@click.option('--interactive', '-i', is_flag=True, help='Interactive review mode')
@click.option('--dry-run', is_flag=True, default=True, help='Preview without applying')
@click.option('--config', type=click.Path(exists=True), help='Config file path')
@click.option('--api-key', envvar='ANTHROPIC_API_KEY', help='Anthropic API key')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging')
@click.option('--no-cache', is_flag=True, help='Disable caching')
@click.option('--create-pr', is_flag=True, help='Create GitHub PR with changes')
@click.option('--resume', is_flag=True, help='Resume from last checkpoint')
def analyze(
    target: str,
    target_type: str,
    mode: str,
    output: Optional[str],
    apply: bool,
    interactive: bool,
    dry_run: bool,
    config: Optional[str],
    api_key: Optional[str],
    verbose: bool,
    no_cache: bool,
    create_pr: bool,
    resume: bool
):
    """Analyze TARGET for documentation gaps and generate improvements."""
    if verbose:
        logger.setLevel(logging.DEBUG)

    console.print(Panel.fit(
        "[bold cyan]Self-Driving Documentation Improver v2.0[/bold cyan]\n"
        "Enhanced with caching, async processing, and git integration",
        border_style="cyan"
    ))

    try:
        # Load configuration
        config_manager = ConfigManager(Path(config) if config else None)
        exploration_config = config_manager.get_exploration_config(
            target_type=target_type,
            target=target,
            overrides={'mode': mode}
        )
        generation_config = config_manager.get_generation_config(
            overrides={'api_key': api_key}
        )

        # Initialize state manager
        state_manager = StateManager()

        # Check for resume
        if resume:
            checkpoint = state_manager.get_last_checkpoint()
            if checkpoint:
                console.print(f"[yellow]Resuming from checkpoint: {checkpoint['description']}[/yellow]")
            else:
                console.print("[yellow]No checkpoint found, starting fresh[/yellow]")

        # Initialize metrics
        metrics = MetricsTracker()

        start_time = time.time()
        use_cache = not no_cache

        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            # Exploration phase
            task = progress.add_task("[cyan]Exploring target...", total=100)

            if target_type == 'code':
                explorer = CodeExplorerV2(exploration_config, use_cache=use_cache)
                entities = explorer.explore()
                progress.update(task, completed=25)

                # Display stats
                stats = explorer.get_stats()
                console.print(f"\n[green]✓[/green] Found {stats['total_entities']} entities")
                console.print(f"  Public: {stats['public_entities']}, Undocumented: {stats['undocumented']}")

                # Gap detection
                progress.update(task, description="[yellow]Detecting gaps...")
                detector = GapDetector()
                gaps = detector.analyze_code_entities(entities)
                progress.update(task, completed=50)

            elif target_type == 'website':
                pages = explore_website_sync(exploration_config)
                progress.update(task, completed=25)

                progress.update(task, description="[yellow]Detecting gaps...")
                detector = GapDetector()
                gaps = detector.analyze_web_pages(pages)
                progress.update(task, completed=50)
            else:
                click.echo("API analysis not yet implemented", err=True)
                sys.exit(1)

            console.print(f"\n[yellow]⚠[/yellow] Found {len(gaps)} documentation gaps")

            # Show gap summary
            _display_gap_summary(gaps)

            # Generate improvements
            progress.update(task, description="[green]Generating improvements...")
            generator = DocumentationGenerator(generation_config)
            client = ClaudeClientV2(generation_config, use_cache=use_cache)

            # Use async batch processing
            async def generate_all():
                improvements = []
                gap_results = await client.batch_generate_async(
                    gaps,
                    max_concurrent=5,
                    progress_callback=lambda i, total: progress.update(
                        task,
                        completed=50 + (i / total * 40)
                    )
                )

                for gap, (doc, reasoning) in zip(gaps, gap_results):
                    from doc_improver.models import DocumentationImprovement
                    imp = DocumentationImprovement(
                        gap_id=gap.id,
                        gap=gap,
                        improved_documentation=doc,
                        confidence_score=0.8,  # Simplified
                        reasoning=reasoning
                    )
                    improvements.append(imp)
                return improvements

            loop = asyncio.get_event_loop()
            improvements = loop.run_until_complete(generate_all())
            progress.update(task, completed=100)

        elapsed_time = time.time() - start_time

        # Display results
        _display_results(target, TargetType(target_type), gaps, improvements, elapsed_time)

        # Interactive review
        if interactive:
            if not QUESTIONARY_AVAILABLE:
                console.print("[red]Interactive mode requires questionary[/red]")
            else:
                results = run_interactive_review(improvements)
                improvements = results['approved']
                console.print(f"\n[green]Proceeding with {len(improvements)} approved improvements[/green]")

        # Apply improvements
        if improvements and (apply or not dry_run):
            console.print("\n[bold yellow]Applying improvements...[/bold yellow]")

            if can_apply_improvements():
                rewriter = ASTRewriter()
                stats = rewriter.apply_improvements_batch(improvements, dry_run=dry_run)
                console.print(f"Applied: {stats['applied']}, Failed: {stats['failed']}, Skipped: {stats['skipped']}")
            else:
                console.print("[red]libcst not available, cannot apply improvements[/red]")

        # Create PR if requested
        if create_pr and improvements and not dry_run:
            console.print("\n[bold cyan]Creating GitHub PR...[/bold cyan]")
            pr_url = create_documentation_pr_workflow(improvements, auto_push=True)
            if pr_url:
                console.print(f"[green]✓ Created PR: {pr_url}[/green]")

        # Record metrics
        loop.run_until_complete(
            metrics.initialize()
        )
        loop.run_until_complete(
            metrics.record_run(
                target=target,
                target_type=target_type,
                mode=mode,
                duration=elapsed_time,
                stats={
                    'total_entities': len(entities) if target_type == 'code' else len(pages),
                    'gaps_found': len(gaps),
                    'improvements_generated': len(improvements),
                    'improvements_applied': stats.get('applied', 0) if not dry_run else 0
                }
            )
        )

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
def setup():
    """Interactive setup wizard."""
    console.print(Panel.fit(
        "[bold cyan]Setup Wizard[/bold cyan]\n"
        "Configure Self-Driving Documentation Improver",
        border_style="cyan"
    ))

    if not QUESTIONARY_AVAILABLE:
        console.print("[red]Setup wizard requires questionary[/red]")
        return

    import questionary

    # API Key
    api_key = questionary.password("Enter your Anthropic API key:").ask()

    if api_key:
        # Validate
        console.print("[cyan]Validating API key...[/cyan]")
        try:
            from doc_improver.models import GenerationConfig
            config = GenerationConfig(api_key=api_key)
            client = ClaudeClientV2(config)

            if client.validate_api_key():
                console.print("[green]✓ API key is valid![/green]")

                # Save to config
                import os
                os.environ['ANTHROPIC_API_KEY'] = api_key

                # Create config file
                config_path = Path.cwd() / ".doc-improver.yaml"
                ConfigManager.create_default_config(config_path)
                console.print(f"[green]✓ Created config file: {config_path}[/green]")
            else:
                console.print("[red]✗ API key validation failed[/red]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")


@main.command()
def metrics():
    """View analytics and metrics."""
    console.print(Panel.fit(
        "[bold cyan]Metrics & Analytics[/bold cyan]",
        border_style="cyan"
    ))

    tracker = MetricsTracker()
    loop = asyncio.get_event_loop()
    stats = loop.run_until_complete(tracker.get_stats_summary())

    # Display stats
    table = Table(title="Overall Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right", style="green")

    table.add_row("Total Runs", str(stats['total_runs']))
    table.add_row("Total Improvements Applied", str(stats['total_improvements_applied']))
    table.add_row("Average Confidence", f"{stats['average_confidence']:.1%}")

    console.print(table)

    # Gaps by severity
    if stats['gaps_by_severity']:
        console.print("\n[bold]Gaps by Severity:[/bold]")
        for severity, count in stats['gaps_by_severity'].items():
            console.print(f"  {severity}: {count}")

    # Recent runs
    if stats['recent_runs']:
        console.print("\n[bold]Recent Runs:[/bold]")
        for run in stats['recent_runs']:
            console.print(f"  {run['timestamp']}: {run['target']} ({run['gaps_found']} gaps)")


@main.command()
@click.option('--clear', is_flag=True, help='Clear all cache')
def cache(clear: bool):
    """Manage cache."""
    cache_mgr = SyncCacheManager()

    if clear:
        cache_mgr.clear_all()
        console.print("[green]✓ Cache cleared[/green]")
    else:
        stats = cache_mgr.get_stats()
        console.print(f"API responses cached: {stats['api_responses']}")
        console.print(f"File analyses cached: {stats['file_analyses']}")
        console.print(f"Expired entries: {stats['expired']}")


@main.command()
def check_config():
    """Validate configuration."""
    try:
        config_mgr = ConfigManager()
        console.print("[green]✓ Configuration is valid[/green]")
    except Exception as e:
        console.print(f"[red]Configuration error: {e}[/red]")
        sys.exit(1)


def _display_gap_summary(gaps: list) -> None:
    """Display gap summary table."""
    if not gaps:
        return

    table = Table(title="Gaps by Severity")
    table.add_column("Severity", style="cyan")
    table.add_column("Count", justify="right")

    severity_counts = {}
    for gap in gaps:
        severity_counts[gap.severity.value] = severity_counts.get(gap.severity.value, 0) + 1

    for severity in ['critical', 'high', 'medium', 'low']:
        count = severity_counts.get(severity, 0)
        if count > 0:
            color = {'critical': 'red', 'high': 'yellow', 'medium': 'blue', 'low': 'green'}[severity]
            table.add_row(f"[{color}]{severity.upper()}[/{color}]", str(count))

    console.print(table)


def _display_results(target: str, target_type: TargetType, gaps: list, improvements: list, elapsed_time: float):
    """Display analysis results."""
    summary = f"""
[bold]Target:[/bold] {target}
[bold]Type:[/bold] {target_type.value}
[bold]Time:[/bold] {elapsed_time:.2f}s
[bold]Gaps Found:[/bold] {len(gaps)}
[bold]Improvements Generated:[/bold] {len(improvements)}
"""
    console.print(Panel(summary, title="Analysis Summary", border_style="green"))


if __name__ == '__main__':
    main()
