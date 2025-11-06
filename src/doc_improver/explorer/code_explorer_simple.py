"""Simplified code explorer without async complexity."""

from pathlib import Path
from typing import List, Optional
import logging

from doc_improver.models import CodeEntity, ExplorationConfig
from doc_improver.explorer.base_analyzer import AnalyzerRegistry
from doc_improver.explorer.python_analyzer import PythonAnalyzer
from doc_improver.explorer.javascript_analyzer import JavaScriptAnalyzer
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class SimpleCodeExplorer:
    """Simple, reliable code explorer."""

    def __init__(self, config: ExplorationConfig):
        """Initialize code explorer.

        Args:
            config: Exploration configuration
        """
        self.config = config
        self.root_path = Path(config.target_path_or_url)
        self.entities: List[CodeEntity] = []

        # Initialize analyzer registry
        self.registry = AnalyzerRegistry()
        self._register_default_analyzers()

    def _register_default_analyzers(self) -> None:
        """Register default language analyzers."""
        self.registry.register(PythonAnalyzer())
        self.registry.register(JavaScriptAnalyzer())
        logger.debug("Registered default analyzers")

    def explore(self) -> List[CodeEntity]:
        """Explore the code repository.

        Returns:
            List of discovered code entities
        """
        logger.info(f"Exploring code at: {self.root_path}")

        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")

        if self.root_path.is_file():
            entities = self._analyze_file(self.root_path)
            self.entities.extend(entities)
        else:
            self._explore_directory(self.root_path)

        logger.info(f"Found {len(self.entities)} code entities")
        return self.entities

    def _explore_directory(self, directory: Path, depth: int = 0) -> None:
        """Recursively explore directory for code files.

        Args:
            directory: Directory to explore
            depth: Current recursion depth
        """
        if depth > self.config.max_depth:
            return

        try:
            items = list(directory.iterdir())

            for item in items:
                # Skip excluded patterns
                if self._should_exclude(item):
                    continue

                if item.is_file():
                    analyzer = self.registry.get_analyzer(item)
                    if analyzer:
                        entities = self._analyze_file(item)
                        self.entities.extend(entities)
                elif item.is_dir():
                    # Recurse into subdirectories
                    self._explore_directory(item, depth + 1)

        except PermissionError:
            logger.warning(f"Permission denied: {directory}")
        except Exception as e:
            logger.error(f"Error exploring {directory}: {e}")

    def _analyze_file(self, file_path: Path) -> List[CodeEntity]:
        """Analyze a single code file.

        Args:
            file_path: Path to the file to analyze

        Returns:
            List of code entities
        """
        # Get appropriate analyzer
        analyzer = self.registry.get_analyzer(file_path)
        if not analyzer:
            logger.debug(f"No analyzer found for {file_path}")
            return []

        try:
            entities = analyzer.analyze_file(file_path, self.root_path)
            return entities

        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}", exc_info=True)
            return []

    def _should_exclude(self, path: Path) -> bool:
        """Check if path matches exclusion patterns.

        Args:
            path: Path to check

        Returns:
            True if should be excluded
        """
        path_str = str(path)
        for pattern in self.config.exclude_patterns:
            if path.match(pattern):
                return True
        return False

    def get_public_entities(self) -> List[CodeEntity]:
        """Get only public entities that should be documented.

        Returns:
            List of public code entities
        """
        return [e for e in self.entities if e.is_public]

    def get_undocumented_entities(self) -> List[CodeEntity]:
        """Get entities without documentation.

        Returns:
            List of undocumented code entities
        """
        return [e for e in self.entities if e.is_public and not e.docstring]

    def get_stats(self):
        """Get exploration statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "total_entities": len(self.entities),
            "public_entities": len(self.get_public_entities()),
            "undocumented": len(self.get_undocumented_entities()),
        }


# Alias for compatibility
CodeExplorer = SimpleCodeExplorer
