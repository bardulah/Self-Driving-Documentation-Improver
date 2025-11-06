"""Documentation improvement generator and applicator."""

import difflib
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from doc_improver.models import (
    DocumentationGap,
    DocumentationImprovement,
    GenerationConfig,
)
from doc_improver.integrations.claude_client import ClaudeClient
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class DocumentationGenerator:
    """Generates and applies documentation improvements."""

    def __init__(self, config: GenerationConfig):
        """Initialize documentation generator.

        Args:
            config: Generation configuration
        """
        self.config = config
        self.client = ClaudeClient(config)
        self.improvements: List[DocumentationImprovement] = []

    def generate_improvements(
        self,
        gaps: List[DocumentationGap],
        additional_context: Optional[str] = None
    ) -> List[DocumentationImprovement]:
        """Generate improvements for all gaps.

        Args:
            gaps: List of documentation gaps
            additional_context: Optional additional context

        Returns:
            List of generated improvements
        """
        logger.info(f"Generating improvements for {len(gaps)} gaps")
        self.improvements = []

        for gap in gaps:
            try:
                improved_doc, reasoning = self.client.generate_documentation(
                    gap, additional_context
                )

                # Calculate confidence score (simple heuristic)
                confidence = self._calculate_confidence(improved_doc, gap)

                # Generate diff if there's existing documentation
                diff = None
                if gap.current_documentation:
                    diff = self._generate_diff(
                        gap.current_documentation,
                        improved_doc
                    )

                improvement = DocumentationImprovement(
                    gap_id=gap.id,
                    gap=gap,
                    improved_documentation=improved_doc,
                    diff=diff,
                    confidence_score=confidence,
                    reasoning=reasoning,
                )

                self.improvements.append(improvement)
                logger.debug(f"Generated improvement for {gap.location}")

            except Exception as e:
                logger.error(f"Failed to generate improvement for gap {gap.id}: {e}")

        logger.info(f"Successfully generated {len(self.improvements)} improvements")
        return self.improvements

    def apply_improvements(
        self,
        improvements: Optional[List[DocumentationImprovement]] = None,
        dry_run: bool = True
    ) -> Dict[str, int]:
        """Apply improvements to source files.

        Args:
            improvements: List of improvements to apply (uses all if None)
            dry_run: If True, don't actually modify files

        Returns:
            Dictionary with application statistics
        """
        if improvements is None:
            improvements = self.improvements

        logger.info(f"Applying {len(improvements)} improvements (dry_run={dry_run})")

        stats = {
            "total": len(improvements),
            "applied": 0,
            "skipped": 0,
            "failed": 0,
        }

        for improvement in improvements:
            if improvement.confidence_score < 0.5:
                logger.warning(
                    f"Skipping low-confidence improvement for {improvement.gap.location}"
                )
                stats["skipped"] += 1
                continue

            try:
                if not dry_run:
                    self._apply_improvement(improvement)
                stats["applied"] += 1
                logger.debug(f"Applied improvement to {improvement.gap.location}")
            except Exception as e:
                logger.error(f"Failed to apply improvement: {e}")
                stats["failed"] += 1

        logger.info(
            f"Application complete: {stats['applied']} applied, "
            f"{stats['skipped']} skipped, {stats['failed']} failed"
        )
        return stats

    def _apply_improvement(self, improvement: DocumentationImprovement) -> None:
        """Apply a single improvement to source file.

        Args:
            improvement: Improvement to apply
        """
        gap = improvement.gap
        if not gap.entity:
            # Can't apply to non-code entities
            return

        file_path = Path(gap.entity.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find where to insert documentation
        insert_line = gap.entity.line_number - 1  # 0-indexed

        # Determine indentation
        if insert_line < len(lines):
            current_line = lines[insert_line]
            indent = len(current_line) - len(current_line.lstrip())
            indent_str = ' ' * indent
        else:
            indent_str = ''

        # Format documentation
        doc_lines = self._format_docstring(
            improvement.improved_documentation,
            indent_str
        )

        # Insert documentation
        if gap.entity.docstring:
            # Replace existing docstring
            # This is simplified - proper implementation would need to find
            # the exact location and extent of the existing docstring
            lines[insert_line] = doc_lines
        else:
            # Insert new docstring
            lines.insert(insert_line + 1, doc_lines + '\n')

        # Write file back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

    def _format_docstring(self, documentation: str, indent: str) -> str:
        """Format documentation as a proper docstring.

        Args:
            documentation: Documentation text
            indent: Indentation string

        Returns:
            Formatted docstring
        """
        # Simple formatting - proper implementation would handle multi-line better
        lines = documentation.strip().split('\n')

        if len(lines) == 1:
            return f'{indent}"""{lines[0]}"""'

        formatted = [f'{indent}"""']
        formatted.extend([f'{indent}{line}' for line in lines])
        formatted.append(f'{indent}"""')

        return '\n'.join(formatted)

    def _calculate_confidence(self, documentation: str, gap: DocumentationGap) -> float:
        """Calculate confidence score for generated documentation.

        Args:
            documentation: Generated documentation
            gap: Original gap

        Returns:
            Confidence score between 0 and 1
        """
        score = 0.5  # Base score

        # Length check
        if len(documentation) > 50:
            score += 0.1
        if len(documentation) > 200:
            score += 0.1

        # Check for required sections based on gap type
        doc_lower = documentation.lower()

        if gap.entity and gap.entity.parameters:
            if any(keyword in doc_lower for keyword in ['args:', 'parameters:', ':param']):
                score += 0.15

        if gap.entity and gap.entity.return_type:
            if any(keyword in doc_lower for keyword in ['returns:', 'return:', ':return']):
                score += 0.15

        # Check for examples if configured
        if self.config.include_examples:
            if any(keyword in doc_lower for keyword in ['example:', '>>>', 'usage:']):
                score += 0.1

        return min(score, 1.0)

    def _generate_diff(self, old: str, new: str) -> str:
        """Generate a diff between old and new documentation.

        Args:
            old: Old documentation
            new: New documentation

        Returns:
            Diff string
        """
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile='current',
            tofile='improved',
            lineterm=''
        )

        return ''.join(diff)

    def export_improvements(self, output_path: Path) -> None:
        """Export improvements to a file for review.

        Args:
            output_path: Path to export file
        """
        logger.info(f"Exporting improvements to {output_path}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Documentation Improvements Report\n\n")
            f.write(f"Total improvements: {len(self.improvements)}\n\n")

            for i, improvement in enumerate(self.improvements, 1):
                f.write(f"## {i}. {improvement.gap.location}\n\n")
                f.write(f"**Type:** {improvement.gap.gap_type.value}\n")
                f.write(f"**Severity:** {improvement.gap.severity.value}\n")
                f.write(f"**Confidence:** {improvement.confidence_score:.2f}\n\n")
                f.write(f"**Description:** {improvement.gap.description}\n\n")

                if improvement.gap.current_documentation:
                    f.write("**Current Documentation:**\n```\n")
                    f.write(improvement.gap.current_documentation)
                    f.write("\n```\n\n")

                f.write("**Improved Documentation:**\n```\n")
                f.write(improvement.improved_documentation)
                f.write("\n```\n\n")

                if improvement.diff:
                    f.write("**Diff:**\n```diff\n")
                    f.write(improvement.diff)
                    f.write("\n```\n\n")

                f.write(f"**Reasoning:** {improvement.reasoning}\n\n")
                f.write("---\n\n")

        logger.info("Export complete")

    def get_high_confidence_improvements(
        self,
        threshold: float = 0.7
    ) -> List[DocumentationImprovement]:
        """Get improvements with high confidence scores.

        Args:
            threshold: Minimum confidence threshold

        Returns:
            List of high-confidence improvements
        """
        return [
            imp for imp in self.improvements
            if imp.confidence_score >= threshold
        ]
