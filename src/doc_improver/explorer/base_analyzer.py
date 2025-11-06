"""Base analyzer interface for language plugins."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Set
import logging

from doc_improver.models import CodeEntity
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class BaseLanguageAnalyzer(ABC):
    """Base class for language-specific code analyzers."""

    def __init__(self):
        """Initialize the analyzer."""
        self.supported_extensions: Set[str] = set()

    @abstractmethod
    def can_analyze(self, file_path: Path) -> bool:
        """Check if this analyzer can handle the given file.

        Args:
            file_path: Path to the file

        Returns:
            True if this analyzer supports the file type
        """
        pass

    @abstractmethod
    def analyze_file(self, file_path: Path, root_path: Path) -> List[CodeEntity]:
        """Analyze a file and extract code entities.

        Args:
            file_path: Path to the file to analyze
            root_path: Root path of the project (for relative paths)

        Returns:
            List of discovered code entities
        """
        pass

    def extract_file_context(
        self,
        file_path: Path,
        line_number: int,
        context_lines: int = 10
    ) -> Optional[str]:
        """Extract code context around a specific line.

        Args:
            file_path: Path to the file
            line_number: Line number of interest
            context_lines: Number of lines before/after to include

        Returns:
            Code context string or None if error
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            start = max(0, line_number - context_lines - 1)
            end = min(len(lines), line_number + context_lines)

            context = ''.join(lines[start:end])
            return context
        except Exception as e:
            logger.warning(f"Error extracting context from {file_path}: {e}")
            return None

    def get_function_body(
        self,
        file_path: Path,
        start_line: int,
        max_lines: int = 50
    ) -> Optional[str]:
        """Extract function/method body.

        Args:
            file_path: Path to the file
            start_line: Starting line number
            max_lines: Maximum lines to read

        Returns:
            Function body or None if error
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Simple heuristic: read until dedent or max_lines
            body_lines = []
            start_idx = start_line - 1

            if start_idx >= len(lines):
                return None

            # Get initial indentation
            first_line = lines[start_idx]
            initial_indent = len(first_line) - len(first_line.lstrip())

            for i in range(start_idx, min(len(lines), start_idx + max_lines)):
                line = lines[i]

                # Skip empty lines
                if not line.strip():
                    body_lines.append(line)
                    continue

                # Check indentation
                current_indent = len(line) - len(line.lstrip())

                # If we've dedented back to or past initial level, stop
                if current_indent <= initial_indent and i > start_idx:
                    break

                body_lines.append(line)

            return ''.join(body_lines)
        except Exception as e:
            logger.warning(f"Error extracting function body from {file_path}: {e}")
            return None


class AnalyzerRegistry:
    """Registry for language analyzers."""

    def __init__(self):
        """Initialize the registry."""
        self._analyzers: List[BaseLanguageAnalyzer] = []

    def register(self, analyzer: BaseLanguageAnalyzer) -> None:
        """Register a language analyzer.

        Args:
            analyzer: Analyzer instance to register
        """
        self._analyzers.append(analyzer)
        logger.debug(f"Registered analyzer: {analyzer.__class__.__name__}")

    def get_analyzer(self, file_path: Path) -> Optional[BaseLanguageAnalyzer]:
        """Get appropriate analyzer for a file.

        Args:
            file_path: Path to the file

        Returns:
            Analyzer instance or None if no analyzer found
        """
        for analyzer in self._analyzers:
            if analyzer.can_analyze(file_path):
                return analyzer

        return None

    def get_all_analyzers(self) -> List[BaseLanguageAnalyzer]:
        """Get all registered analyzers.

        Returns:
            List of all analyzers
        """
        return self._analyzers.copy()


# Global registry instance
registry = AnalyzerRegistry()
