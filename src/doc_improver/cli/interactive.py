"""Interactive review mode for documentation improvements."""

from typing import List, Dict, Any, Optional
import difflib

try:
    import questionary
    from questionary import Style
    QUESTIONARY_AVAILABLE = True
except ImportError:
    QUESTIONARY_AVAILABLE = False
    questionary = None

from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel
from rich.table import Table

from doc_improver.models import DocumentationImprovement
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)
console = Console()


# Custom style for questionary
custom_style = Style([
    ('qmark', 'fg:#673ab7 bold'),
    ('question', 'bold'),
    ('answer', 'fg:#f44336 bold'),
    ('pointer', 'fg:#673ab7 bold'),
    ('highlighted', 'fg:#673ab7 bold'),
    ('selected', 'fg:#cc5454'),
    ('separator', 'fg:#cc5454'),
    ('instruction', ''),
    ('text', ''),
    ('disabled', 'fg:#858585 italic')
]) if QUESTIONARY_AVAILABLE else None


class InteractiveReviewer:
    """Interactive reviewer for documentation improvements."""

    def __init__(self):
        """Initialize interactive reviewer."""
        if not QUESTIONARY_AVAILABLE:
            raise ImportError(
                "questionary is required for interactive mode. Install with: pip install questionary"
            )

        self.approved: List[DocumentationImprovement] = []
        self.rejected: List[DocumentationImprovement] = []
        self.edited: List[DocumentationImprovement] = []
        self.skipped: List[DocumentationImprovement] = []

    def review_improvements(
        self,
        improvements: List[DocumentationImprovement],
        auto_approve_threshold: float = 0.9
    ) -> Dict[str, List[DocumentationImprovement]]:
        """Review improvements interactively.

        Args:
            improvements: List of improvements to review
            auto_approve_threshold: Auto-approve if confidence above this

        Returns:
            Dictionary with categorized improvements
        """
        console.print(Panel.fit(
            f"[bold cyan]Interactive Review Mode[/bold cyan]\n"
            f"Reviewing {len(improvements)} improvements",
            border_style="cyan"
        ))

        for i, improvement in enumerate(improvements, 1):
            # Auto-approve very high confidence improvements
            if improvement.confidence_score >= auto_approve_threshold:
                console.print(f"\n[green]✓ Auto-approved (confidence: {improvement.confidence_score:.1%})[/green]")
                self.approved.append(improvement)
                continue

            # Display improvement details
            self._display_improvement(improvement, i, len(improvements))

            # Get user decision
            decision = self._get_user_decision(improvement)

            if decision == "approve":
                self.approved.append(improvement)
                console.print("[green]✓ Approved[/green]")
            elif decision == "reject":
                self.rejected.append(improvement)
                console.print("[red]✗ Rejected[/red]")
            elif decision == "edit":
                edited = self._edit_improvement(improvement)
                if edited:
                    self.edited.append(edited)
                    self.approved.append(edited)
                    console.print("[yellow]✎ Edited and approved[/yellow]")
            elif decision == "skip":
                self.skipped.append(improvement)
                console.print("[blue]⊘ Skipped[/blue]")
            elif decision == "quit":
                console.print("[yellow]Quitting review...[/yellow]")
                break

        # Display summary
        self._display_summary()

        return {
            'approved': self.approved,
            'rejected': self.rejected,
            'edited': self.edited,
            'skipped': self.skipped,
        }

    def _display_improvement(
        self,
        improvement: DocumentationImprovement,
        current: int,
        total: int
    ) -> None:
        """Display improvement details.

        Args:
            improvement: Improvement to display
            current: Current index
            total: Total count
        """
        console.print(f"\n[bold]═══ {current}/{total} ═══[/bold]")

        # Location and metadata
        gap = improvement.gap
        console.print(f"[cyan]Location:[/cyan] {gap.location}")
        console.print(f"[cyan]Type:[/cyan] {gap.gap_type.value}")
        console.print(f"[cyan]Severity:[/cyan] {gap.severity.value}")
        console.print(f"[cyan]Confidence:[/cyan] {improvement.confidence_score:.1%}")

        if gap.entity:
            console.print(f"[cyan]Entity:[/cyan] {gap.entity.name} ({gap.entity.type})")

        console.print()

        # Show diff
        if improvement.diff:
            console.print("[bold]Diff:[/bold]")
            diff_syntax = Syntax(improvement.diff, "diff", theme="monokai", line_numbers=False)
            console.print(diff_syntax)
        else:
            # Show before/after
            if gap.current_documentation:
                console.print("[bold]Current Documentation:[/bold]")
                console.print(Panel(gap.current_documentation, border_style="red"))

            console.print("[bold]Improved Documentation:[/bold]")
            console.print(Panel(improvement.improved_documentation, border_style="green"))

        # Show reasoning
        console.print(f"\n[bold]Reasoning:[/bold] {improvement.reasoning}")

    def _get_user_decision(self, improvement: DocumentationImprovement) -> str:
        """Get user decision for an improvement.

        Args:
            improvement: Improvement to decide on

        Returns:
            Decision string
        """
        choices = [
            "approve - Apply this improvement",
            "reject - Reject this improvement",
            "edit - Edit before applying",
            "skip - Skip for now",
            "quit - Stop reviewing"
        ]

        answer = questionary.select(
            "What would you like to do?",
            choices=choices,
            style=custom_style
        ).ask()

        if answer:
            return answer.split(' - ')[0]
        else:
            return "quit"

    def _edit_improvement(
        self,
        improvement: DocumentationImprovement
    ) -> Optional[DocumentationImprovement]:
        """Allow user to edit improvement.

        Args:
            improvement: Improvement to edit

        Returns:
            Edited improvement or None if cancelled
        """
        console.print("\n[yellow]Edit Mode[/yellow]")
        console.print("Enter the improved documentation (Ctrl+D or Ctrl+Z when done):")
        console.print("[dim]Current version shown below:[/dim]")
        console.print(Panel(improvement.improved_documentation, border_style="yellow"))

        # Use questionary for multi-line input
        edited_text = questionary.text(
            "Edited documentation:",
            default=improvement.improved_documentation,
            multiline=True,
            style=custom_style
        ).ask()

        if edited_text and edited_text != improvement.improved_documentation:
            # Create new improvement with edited text
            improvement.improved_documentation = edited_text
            improvement.reasoning += " [User edited]"
            return improvement

        return None

    def _display_summary(self) -> None:
        """Display review summary."""
        console.print("\n")
        console.print(Panel.fit(
            "[bold]Review Summary[/bold]",
            border_style="cyan"
        ))

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="green")

        table.add_row("Approved", str(len(self.approved)))
        table.add_row("Rejected", str(len(self.rejected)))
        table.add_row("Edited", str(len(self.edited)))
        table.add_row("Skipped", str(len(self.skipped)))
        table.add_row("[bold]Total Reviewed", str(
            len(self.approved) + len(self.rejected) + len(self.skipped)
        ))

        console.print(table)


def run_interactive_review(
    improvements: List[DocumentationImprovement],
    auto_approve_threshold: float = 0.9
) -> Dict[str, List[DocumentationImprovement]]:
    """Run interactive review session.

    Args:
        improvements: Improvements to review
        auto_approve_threshold: Auto-approve threshold

    Returns:
        Dictionary with categorized improvements
    """
    if not QUESTIONARY_AVAILABLE:
        console.print("[red]Interactive mode requires questionary. Install with: pip install questionary[/red]")
        return {'approved': [], 'rejected': [], 'edited': [], 'skipped': []}

    reviewer = InteractiveReviewer()
    return reviewer.review_improvements(improvements, auto_approve_threshold)


def quick_review_mode(improvements: List[DocumentationImprovement]) -> List[DocumentationImprovement]:
    """Quick review mode - show all and ask for batch approval.

    Args:
        improvements: Improvements to review

    Returns:
        List of approved improvements
    """
    if not QUESTIONARY_AVAILABLE:
        return improvements

    console.print(Panel.fit(
        "[bold cyan]Quick Review Mode[/bold cyan]\n"
        f"Showing {len(improvements)} improvements",
        border_style="cyan"
    ))

    # Show summary table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Location", style="green")
    table.add_column("Type", style="yellow")
    table.add_column("Confidence", justify="right", style="blue")

    for i, imp in enumerate(improvements, 1):
        table.add_row(
            str(i),
            imp.gap.location[:50],
            imp.gap.gap_type.value[:20],
            f"{imp.confidence_score:.1%}"
        )

    console.print(table)

    # Ask for approval
    answer = questionary.confirm(
        f"Apply all {len(improvements)} improvements?",
        default=False,
        style=custom_style
    ).ask()

    if answer:
        return improvements
    else:
        # Allow filtering by confidence
        threshold = questionary.text(
            "Apply improvements above confidence threshold (0.0-1.0):",
            default="0.7",
            style=custom_style
        ).ask()

        try:
            threshold_val = float(threshold)
            filtered = [imp for imp in improvements if imp.confidence_score >= threshold_val]
            console.print(f"[green]Filtered to {len(filtered)} improvements[/green]")
            return filtered
        except ValueError:
            console.print("[red]Invalid threshold, applying none[/red]")
            return []
