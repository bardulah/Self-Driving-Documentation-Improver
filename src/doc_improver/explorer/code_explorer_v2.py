"""Enhanced code exploration with plugin system and caching."""

import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from doc_improver.models import CodeEntity, ExplorationConfig
from doc_improver.explorer.base_analyzer import AnalyzerRegistry
from doc_improver.explorer.python_analyzer import PythonAnalyzer
from doc_improver.explorer.javascript_analyzer import JavaScriptAnalyzer
from doc_improver.utils.cache import CacheManager
from doc_improver.utils.logger import setup_logger, create_progress

logger = setup_logger(__name__)


class CodeExplorerV2:
    """Enhanced code explorer with plugin system and caching."""

    def __init__(self, config: ExplorationConfig, use_cache: bool = True):
        """Initialize code explorer.

        Args:
            config: Exploration configuration
            use_cache: Whether to use caching
        """
        self.config = config
        self.root_path = Path(config.target_path_or_url)
        self.entities: List[CodeEntity] = []
        self.use_cache = use_cache

        # Initialize cache
        self.cache = CacheManager() if use_cache else None

        # Initialize analyzer registry
        self.registry = AnalyzerRegistry()
        self._register_default_analyzers()

    def _register_default_analyzers(self) -> None:
        """Register default language analyzers."""
        self.registry.register(PythonAnalyzer())
        self.registry.register(JavaScriptAnalyzer())
        logger.debug("Registered default analyzers")

    async def explore_async(self) -> List[CodeEntity]:
        """Explore the code repository asynchronously.

        Returns:
            List of discovered code entities
        """
        logger.info(f"Exploring code at: {self.root_path}")

        if not self.root_path.exists():
            raise ValueError(f"Path does not exist: {self.root_path}")

        if self.root_path.is_file():
            entities = await self._analyze_file_async(self.root_path)
            self.entities.extend(entities)
        else:
            await self._explore_directory_async(self.root_path)

        logger.info(f"Found {len(self.entities)} code entities")
        return self.entities

    def explore(self) -> List[CodeEntity]:
        """Synchronous wrapper for explore_async.

        Returns:
            List of discovered code entities
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.explore_async())

    async def _explore_directory_async(
        self,
        directory: Path,
        depth: int = 0,
        progress_callback: Optional[callable] = None
    ) -> None:
        """Recursively explore directory for code files.

        Args:
            directory: Directory to explore
            depth: Current recursion depth
            progress_callback: Optional callback for progress updates
        """
        if depth > self.config.max_depth:
            return

        try:
            items = list(directory.iterdir())
            files_to_analyze = []

            for item in items:
                # Skip excluded patterns
                if self._should_exclude(item):
                    continue

                if item.is_file():
                    analyzer = self.registry.get_analyzer(item)
                    if analyzer:
                        files_to_analyze.append(item)
                elif item.is_dir():
                    # Recurse into subdirectories
                    await self._explore_directory_async(item, depth + 1, progress_callback)

            # Analyze files in this directory
            for file_path in files_to_analyze:
                if progress_callback:
                    progress_callback(file_path)

                entities = await self._analyze_file_async(file_path)
                self.entities.extend(entities)

        except PermissionError:
            logger.warning(f"Permission denied: {directory}")
        except Exception as e:
            logger.error(f"Error exploring {directory}: {e}")

    async def _analyze_file_async(self, file_path: Path) -> List[CodeEntity]:
        """Analyze a single code file with caching.

        Args:
            file_path: Path to the file to analyze

        Returns:
            List of code entities
        """
        # Check cache first
        if self.cache:
            cached = await self.cache.async_manager.get_file_analysis(str(file_path))
            if cached:
                logger.debug(f"Using cached analysis for {file_path}")
                # Convert dict back to CodeEntity
                return [CodeEntity(**entity) for entity in cached]

        # Get appropriate analyzer
        analyzer = self.registry.get_analyzer(file_path)
        if not analyzer:
            logger.debug(f"No analyzer found for {file_path}")
            return []

        try:
            entities = analyzer.analyze_file(file_path, self.root_path)

            # Cache the results
            if self.cache and entities:
                await self.cache.async_manager.set_file_analysis(
                    str(file_path),
                    entities
                )

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

    def get_stats(self) -> Dict[str, Any]:
        """Get exploration statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "total_entities": len(self.entities),
            "public_entities": len(self.get_public_entities()),
            "undocumented": len(self.get_undocumented_entities()),
            "by_type": self._count_by_type(),
            "by_language": self._count_by_language(),
        }

    def _count_by_type(self) -> Dict[str, int]:
        """Count entities by type.

        Returns:
            Dictionary of counts
        """
        counts = {}
        for entity in self.entities:
            counts[entity.type] = counts.get(entity.type, 0) + 1
        return counts

    def _count_by_language(self) -> Dict[str, int]:
        """Count entities by programming language.

        Returns:
            Dictionary of counts
        """
        counts = {}
        for entity in self.entities:
            ext = Path(entity.file_path).suffix
            lang = {
                '.py': 'Python',
                '.js': 'JavaScript',
                '.ts': 'TypeScript',
                '.jsx': 'JavaScript React',
                '.tsx': 'TypeScript React',
            }.get(ext, ext)
            counts[lang] = counts.get(lang, 0) + 1
        return counts


# For backward compatibility
class CodeExplorer(CodeExplorerV2):
    """Alias for CodeExplorerV2 for backward compatibility."""
    pass
