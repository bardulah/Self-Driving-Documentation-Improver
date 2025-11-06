#!/usr/bin/env python3
"""
Simple, working CLI for documentation improvement.

This CLI focuses on reliability and clarity over features.
"""

import sys
import os
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

from doc_improver.models import ExplorationConfig, GenerationConfig, TargetType
from doc_improver.explorer.code_explorer_simple import SimpleCodeExplorer
from doc_improver.analyzer.gap_detector import GapDetector
from doc_improver.integrations.claude_client_v2 import ClaudeClientV2
from doc_improver.utils.ast_rewriter import ASTRewriter, can_apply_improvements


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """
    Documentation Improver - Find and fix documentation gaps.

    Start with: doc-improver analyze ./your_project
    """
    pass


@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--apply', is_flag=True, help='Apply improvements (requires API key)')
@click.option('--backup/--no-backup', default=True, help='Backup files before changes')
@click.option('--max-improvements', type=int, default=10, help='Maximum improvements to apply')
@click.option('--verbose', '-v', is_flag=True, help='Show detailed output')
def analyze(path: str, apply: bool, backup: bool, max_improvements: int, verbose: bool):
    """
    Analyze code for documentation gaps.

    Examples:
        doc-improver analyze ./my_project
        doc-improver analyze ./my_project --apply
    """
    console.print(Panel.fit(
        "[bold cyan]Documentation Improver[/bold cyan]\n"
        "Finding documentation gaps...",
        border_style="cyan"
    ))

    target_path = Path(path).resolve()

    # Step 1: Explore
    console.print(f"\n[cyan]Step 1:[/cyan] Exploring code in [bold]{target_path}[/bold]")

    config = ExplorationConfig(
        target_type=TargetType.CODE,
        target_path_or_url=str(target_path)
    )

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        task = progress.add_task("Scanning files...", total=None)

        explorer = SimpleCodeExplorer(config)
        entities = explorer.explore()

        progress.update(task, description=f"Found {len(entities)} entities")

    stats = explorer.get_stats()
    console.print(f"  Found: {stats['total_entities']} total, {stats['undocumented']} undocumented")

    if stats['total_entities'] == 0:
        console.print("[yellow]No code entities found. Check the path?[/yellow]")
        return

    # Step 2: Detect gaps
    console.print(f"\n[cyan]Step 2:[/cyan] Detecting documentation gaps")

    detector = GapDetector()
    gaps = detector.analyze_code_entities(entities)

    if not gaps:
        console.print("[green]✓ No documentation gaps found! Code is well documented.[/green]")
        return

    console.print(f"  Found {len(gaps)} gaps")

    # Show summary table
    _show_gap_summary(gaps)

    # Step 3: Generate improvements (if API key available)
    if apply:
        api_key = os.getenv('ANTHROPIC_API_KEY')

        if not api_key:
            console.print("\n[red]✗ ANTHROPIC_API_KEY not set[/red]")
            console.print("Set it with: export ANTHROPIC_API_KEY='your-key'")
            console.print("Or run without --apply to just see gaps")
            return

        console.print(f"\n[cyan]Step 3:[/cyan] Generating improvements (max {max_improvements})")

        # Limit gaps
        gaps_to_fix = gaps[:max_improvements]

        try:
            gen_config = GenerationConfig(api_key=api_key)
            client = ClaudeClientV2(gen_config, use_cache=True)

            improvements = []

            with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
                task = progress.add_task("Generating documentation...", total=len(gaps_to_fix))

                for i, gap in enumerate(gaps_to_fix):
                    try:
                        doc, reasoning = client.generate_documentation(gap)

                        from doc_improver.models import DocumentationImprovement
                        improvement = DocumentationImprovement(
                            gap_id=gap.id,
                            gap=gap,
                            improved_documentation=doc,
                            confidence_score=0.8,  # Simplified
                            reasoning=reasoning
                        )
                        improvements.append(improvement)

                        progress.update(task, advance=1, description=f"Generated {i+1}/{len(gaps_to_fix)}")

                    except Exception as e:
                        console.print(f"[red]Error generating for {gap.location}: {e}[/red]")
                        if verbose:
                            import traceback
                            traceback.print_exc()

            console.print(f"[green]✓ Generated {len(improvements)} improvements[/green]")

            # Step 4: Apply improvements
            if improvements and can_apply_improvements():
                console.print(f"\n[cyan]Step 4:[/cyan] Applying improvements")

                if backup:
                    _backup_files(improvements)

                rewriter = ASTRewriter()
                stats = rewriter.apply_improvements_batch(improvements, dry_run=False)

                console.print(f"[green]✓ Applied {stats['applied']} improvements[/green]")
                if stats['failed'] > 0:
                    console.print(f"[yellow]⚠ Failed {stats['failed']} improvements[/yellow]")

                # Show what was applied
                _show_applied_improvements(improvements)

            elif improvements:
                console.print("\n[yellow]libcst not available - cannot apply automatically[/yellow]")
                console.print("Install with: pip install libcst")

        except Exception as e:
            console.print(f"\n[red]✗ Error: {e}[/red]")
            if verbose:
                import traceback
                traceback.print_exc()
    else:
        console.print(f"\n[yellow]Run with --apply to generate and apply improvements[/yellow]")
        console.print("(Requires ANTHROPIC_API_KEY environment variable)")


@cli.command()
def example():
    """Run example analysis on test project."""
    console.print("[cyan]Running example...[/cyan]\n")

    example_path = Path(__file__).parent.parent.parent.parent / "examples" / "test_project"

    if not example_path.exists():
        console.print(f"[red]Example not found at {example_path}[/red]")
        return

    # Run analyze on example
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(analyze, [str(example_path)])
    console.print(result.output)


@cli.command()
def check():
    """Check if everything is set up correctly."""
    console.print("[cyan]Checking setup...[/cyan]\n")

    checks = []

    # Check Python version
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python version", py_version, sys.version_info >= (3, 9)))

    # Check API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    checks.append(("API key", "Set" if api_key else "Not set", bool(api_key)))

    # Check libcst
    checks.append(("libcst (for applying changes)", "Available" if can_apply_improvements() else "Not available", can_apply_improvements()))

    # Check imports
    try:
        from doc_improver.explorer.code_explorer_simple import SimpleCodeExplorer
        checks.append(("Core imports", "OK", True))
    except Exception as e:
        checks.append(("Core imports", f"Failed: {e}", False))

    # Display results
    table = Table(title="Setup Check")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("OK", style="green")

    all_ok = True
    for name, status, ok in checks:
        status_icon = "✓" if ok else "✗"
        status_color = "green" if ok else "red"
        table.add_row(name, status, f"[{status_color}]{status_icon}[/{status_color}]")
        if not ok:
            all_ok = False

    console.print(table)
    console.print()

    if all_ok:
        console.print("[green]✓ Everything is set up correctly![/green]")
    else:
        console.print("[yellow]⚠ Some issues detected. See above.[/yellow]")

        if not api_key:
            console.print("\nTo set API key:")
            console.print("  export ANTHROPIC_API_KEY='your-key-here'")

        if not can_apply_improvements():
            console.print("\nTo install libcst:")
            console.print("  pip install libcst")


def _show_gap_summary(gaps):
    """Display gap summary table."""
    from doc_improver.models import Severity

    table = Table(title="Documentation Gaps by Severity")
    table.add_column("Severity", style="cyan")
    table.add_column("Count", justify="right", style="white")
    table.add_column("Examples", style="dim")

    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW]:
        severity_gaps = [g for g in gaps if g.severity == severity]
        if severity_gaps:
            color = {"critical": "red", "high": "yellow", "medium": "blue", "low": "green"}[severity.value]
            examples = ", ".join([g.entity.name for g in severity_gaps[:3] if g.entity])
            if len(severity_gaps) > 3:
                examples += "..."

            table.add_row(
                f"[{color}]{severity.value.upper()}[/{color}]",
                str(len(severity_gaps)),
                examples
            )

    console.print("\n", table)


def _backup_files(improvements):
    """Backup files before modification."""
    backup_dir = Path('.doc-improver-backup')
    backup_dir.mkdir(exist_ok=True)

    import shutil
    from datetime import datetime

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    files_backed_up = set()

    for imp in improvements:
        if imp.gap.entity:
            file_path = Path(imp.gap.entity.file_path)
            if file_path.exists() and str(file_path) not in files_backed_up:
                backup_path = backup_dir / f"{file_path.name}.{timestamp}.bak"
                shutil.copy2(file_path, backup_path)
                files_backed_up.add(str(file_path))

    if files_backed_up:
        console.print(f"  [dim]Backed up {len(files_backed_up)} files to {backup_dir}[/dim]")


def _show_applied_improvements(improvements):
    """Show what improvements were applied."""
    console.print("\n[bold]Applied improvements:[/bold]")

    for imp in improvements[:5]:  # Show first 5
        if imp.gap.entity:
            console.print(f"  • {imp.gap.entity.name} ({imp.gap.entity.file_path}:{imp.gap.entity.line_number})")

    if len(improvements) > 5:
        console.print(f"  ... and {len(improvements) - 5} more")


def main():
    """Entry point."""
    try:
        cli()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    main()
