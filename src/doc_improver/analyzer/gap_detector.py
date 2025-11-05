"""Documentation gap detection and analysis."""

import re
import uuid
from typing import List, Dict, Any, Optional
import logging

from doc_improver.models import (
    CodeEntity,
    WebPage,
    DocumentationGap,
    DocumentationType,
    Severity,
)
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class GapDetector:
    """Detects gaps and issues in documentation."""

    def __init__(self):
        """Initialize gap detector."""
        self.gaps: List[DocumentationGap] = []

    def analyze_code_entities(self, entities: List[CodeEntity]) -> List[DocumentationGap]:
        """Analyze code entities to find documentation gaps.

        Args:
            entities: List of code entities to analyze

        Returns:
            List of identified documentation gaps
        """
        logger.info(f"Analyzing {len(entities)} code entities for documentation gaps")
        self.gaps = []

        for entity in entities:
            if not entity.is_public:
                continue  # Skip private entities

            # Check for missing docstrings
            if not entity.docstring:
                self._add_missing_docstring_gap(entity)
            else:
                # Check for incomplete docstrings
                self._analyze_docstring_completeness(entity)

        logger.info(f"Found {len(self.gaps)} documentation gaps")
        return self.gaps

    def analyze_web_pages(self, pages: List[WebPage]) -> List[DocumentationGap]:
        """Analyze web pages to find documentation gaps.

        Args:
            pages: List of web pages to analyze

        Returns:
            List of identified documentation gaps
        """
        logger.info(f"Analyzing {len(pages)} web pages for documentation gaps")
        web_gaps = []

        for page in pages:
            if not page.has_docs:
                gap = DocumentationGap(
                    id=self._generate_gap_id(),
                    gap_type=DocumentationType.MISSING_API_DOCS,
                    severity=Severity.HIGH,
                    location=page.url,
                    description=f"Page '{page.title or page.url}' has no documentation content",
                    current_documentation=None,
                    context={
                        "url": page.url,
                        "title": page.title,
                        "completeness_score": page.doc_completeness_score,
                    }
                )
                web_gaps.append(gap)
            elif page.doc_completeness_score < 0.5:
                gap = DocumentationGap(
                    id=self._generate_gap_id(),
                    gap_type=DocumentationType.INCOMPLETE_DOCSTRING,
                    severity=Severity.MEDIUM,
                    location=page.url,
                    description=f"Page '{page.title or page.url}' has incomplete documentation (score: {page.doc_completeness_score:.2f})",
                    current_documentation=page.content[:500],
                    context={
                        "url": page.url,
                        "title": page.title,
                        "completeness_score": page.doc_completeness_score,
                    }
                )
                web_gaps.append(gap)

        logger.info(f"Found {len(web_gaps)} web documentation gaps")
        return web_gaps

    def _add_missing_docstring_gap(self, entity: CodeEntity) -> None:
        """Add a gap for missing docstring.

        Args:
            entity: Code entity missing documentation
        """
        severity = self._determine_severity(entity)

        gap = DocumentationGap(
            id=self._generate_gap_id(),
            gap_type=DocumentationType.MISSING_DOCSTRING,
            severity=severity,
            location=f"{entity.file_path}:{entity.line_number}",
            entity=entity,
            description=f"{entity.type.capitalize()} '{entity.name}' has no docstring",
            current_documentation=None,
            context={
                "entity_type": entity.type,
                "entity_name": entity.name,
                "signature": entity.signature,
            }
        )

        self.gaps.append(gap)

    def _analyze_docstring_completeness(self, entity: CodeEntity) -> None:
        """Analyze if existing docstring is complete.

        Args:
            entity: Code entity with docstring
        """
        if not entity.docstring:
            return

        issues = []
        docstring_lower = entity.docstring.lower()

        # Check for parameter documentation
        if entity.parameters:
            # Look for Args/Parameters/Arguments section
            has_param_docs = any(
                keyword in docstring_lower
                for keyword in ['args:', 'parameters:', 'arguments:', 'param ', ':param']
            )

            if not has_param_docs:
                issues.append("missing parameter documentation")
                self._add_incomplete_gap(
                    entity,
                    DocumentationType.MISSING_PARAMETERS,
                    "Parameters are not documented"
                )

            # Check if all parameters are documented
            elif entity.parameters:
                for param in entity.parameters:
                    if param['name'] not in entity.docstring and param['name'] != 'self':
                        issues.append(f"parameter '{param['name']}' not documented")

        # Check for return documentation
        if entity.return_type and entity.return_type != 'None':
            has_return_docs = any(
                keyword in docstring_lower
                for keyword in ['returns:', 'return:', ':returns:', ':return:']
            )

            if not has_return_docs:
                issues.append("missing return documentation")
                self._add_incomplete_gap(
                    entity,
                    DocumentationType.MISSING_RETURNS,
                    "Return value is not documented"
                )

        # Check for exception documentation (if raises keyword in code)
        if entity.signature and 'raise' in entity.signature.lower():
            has_exception_docs = any(
                keyword in docstring_lower
                for keyword in ['raises:', 'raise:', 'throws:', ':raises:']
            )

            if not has_exception_docs:
                issues.append("missing exception documentation")
                self._add_incomplete_gap(
                    entity,
                    DocumentationType.MISSING_EXCEPTIONS,
                    "Exceptions are not documented"
                )

        # Check for examples (for public functions/methods)
        if entity.type in ['function', 'method'] and entity.is_public:
            has_examples = any(
                keyword in docstring_lower
                for keyword in ['example:', 'examples:', '>>>', 'usage:']
            )

            if not has_examples and len(entity.parameters) > 0:
                issues.append("missing usage examples")

        # Check if description is too short
        if len(entity.docstring.strip()) < 20:
            issues.append("description too brief")
            self._add_incomplete_gap(
                entity,
                DocumentationType.UNCLEAR_DESCRIPTION,
                "Description is too brief to be helpful"
            )

    def _add_incomplete_gap(
        self,
        entity: CodeEntity,
        gap_type: DocumentationType,
        description: str
    ) -> None:
        """Add a gap for incomplete documentation.

        Args:
            entity: Code entity with incomplete docs
            gap_type: Type of documentation gap
            description: Description of the issue
        """
        severity = self._determine_severity(entity)

        gap = DocumentationGap(
            id=self._generate_gap_id(),
            gap_type=gap_type,
            severity=severity,
            location=f"{entity.file_path}:{entity.line_number}",
            entity=entity,
            description=f"{entity.type.capitalize()} '{entity.name}': {description}",
            current_documentation=entity.docstring,
            context={
                "entity_type": entity.type,
                "entity_name": entity.name,
                "signature": entity.signature,
            }
        )

        self.gaps.append(gap)

    def _determine_severity(self, entity: CodeEntity) -> Severity:
        """Determine the severity of a documentation gap.

        Args:
            entity: Code entity

        Returns:
            Severity level
        """
        # Critical: Public API classes and functions
        if entity.type in ['class', 'function'] and entity.is_public:
            # Check if it's likely part of public API
            if not entity.name.startswith('_'):
                return Severity.CRITICAL

        # High: Public methods with parameters
        if entity.type == 'method' and entity.is_public and entity.parameters:
            return Severity.HIGH

        # Medium: Other public functions/methods
        if entity.is_public:
            return Severity.MEDIUM

        # Low: Internal code
        return Severity.LOW

    def _generate_gap_id(self) -> str:
        """Generate a unique gap ID.

        Returns:
            Unique gap identifier
        """
        return str(uuid.uuid4())

    def get_gaps_by_severity(self, severity: Severity) -> List[DocumentationGap]:
        """Get gaps filtered by severity.

        Args:
            severity: Severity level to filter by

        Returns:
            List of gaps matching severity
        """
        return [gap for gap in self.gaps if gap.severity == severity]

    def get_gaps_by_type(self, gap_type: DocumentationType) -> List[DocumentationGap]:
        """Get gaps filtered by type.

        Args:
            gap_type: Gap type to filter by

        Returns:
            List of gaps matching type
        """
        return [gap for gap in self.gaps if gap.gap_type == gap_type]

    def get_critical_gaps(self) -> List[DocumentationGap]:
        """Get all critical documentation gaps.

        Returns:
            List of critical gaps
        """
        return self.get_gaps_by_severity(Severity.CRITICAL)

    def generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of identified gaps.

        Returns:
            Dictionary with gap statistics
        """
        return {
            "total_gaps": len(self.gaps),
            "by_severity": {
                "critical": len([g for g in self.gaps if g.severity == Severity.CRITICAL]),
                "high": len([g for g in self.gaps if g.severity == Severity.HIGH]),
                "medium": len([g for g in self.gaps if g.severity == Severity.MEDIUM]),
                "low": len([g for g in self.gaps if g.severity == Severity.LOW]),
            },
            "by_type": {
                gap_type.value: len([g for g in self.gaps if g.gap_type == gap_type])
                for gap_type in DocumentationType
            },
        }
