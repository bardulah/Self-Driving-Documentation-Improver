"""Metrics and analytics tracking."""

import json
import aiosqlite
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class MetricsTracker:
    """Tracks metrics and analytics for documentation improvements."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize metrics tracker.

        Args:
            db_path: Path to metrics database
        """
        if db_path is None:
            db_path = Path.cwd() / ".doc-improver-cache" / "metrics.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database schema."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    target TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    mode TEXT,
                    duration_seconds REAL,
                    total_entities INTEGER,
                    gaps_found INTEGER,
                    improvements_generated INTEGER,
                    improvements_applied INTEGER,
                    metadata TEXT
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS gaps (
                    id TEXT PRIMARY KEY,
                    run_id INTEGER,
                    gap_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    location TEXT NOT NULL,
                    resolved BOOLEAN DEFAULT FALSE,
                    resolved_at TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS improvements (
                    id TEXT PRIMARY KEY,
                    gap_id TEXT,
                    confidence_score REAL,
                    applied BOOLEAN DEFAULT FALSE,
                    applied_at TIMESTAMP,
                    FOREIGN KEY (gap_id) REFERENCES gaps(id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS coverage (
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    target TEXT NOT NULL,
                    total_entities INTEGER,
                    documented_entities INTEGER,
                    coverage_percentage REAL
                )
            """)

            await db.commit()

        self._initialized = True
        logger.debug(f"Metrics initialized at {self.db_path}")

    async def record_run(
        self,
        target: str,
        target_type: str,
        mode: str,
        duration: float,
        stats: Dict[str, Any]
    ) -> int:
        """Record a documentation improvement run.

        Args:
            target: Target path/URL
            target_type: Type of target
            mode: Exploration mode
            duration: Duration in seconds
            stats: Run statistics

        Returns:
            Run ID
        """
        await self.initialize()

        metadata = json.dumps({
            k: v for k, v in stats.items()
            if k not in ['total_entities', 'gaps_found', 'improvements_generated', 'improvements_applied']
        })

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                INSERT INTO runs (
                    target, target_type, mode, duration_seconds,
                    total_entities, gaps_found, improvements_generated,
                    improvements_applied, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target,
                    target_type,
                    mode,
                    duration,
                    stats.get('total_entities', 0),
                    stats.get('gaps_found', 0),
                    stats.get('improvements_generated', 0),
                    stats.get('improvements_applied', 0),
                    metadata
                )
            )
            await db.commit()
            return cursor.lastrowid

    async def record_coverage(
        self,
        target: str,
        total_entities: int,
        documented_entities: int
    ) -> None:
        """Record documentation coverage.

        Args:
            target: Target path/URL
            total_entities: Total entities
            documented_entities: Documented entities
        """
        await self.initialize()

        coverage_pct = (documented_entities / total_entities * 100) if total_entities > 0 else 0

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO coverage (target, total_entities, documented_entities, coverage_percentage)
                VALUES (?, ?, ?, ?)
                """,
                (target, total_entities, documented_entities, coverage_pct)
            )
            await db.commit()

        logger.info(f"Coverage for {target}: {coverage_pct:.1f}%")

    async def get_coverage_trend(self, target: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get coverage trend over time.

        Args:
            target: Target path/URL
            limit: Number of records to return

        Returns:
            List of coverage records
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT timestamp, total_entities, documented_entities, coverage_percentage
                FROM coverage
                WHERE target = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (target, limit)
            )
            rows = await cursor.fetchall()

            return [
                {
                    'timestamp': row[0],
                    'total_entities': row[1],
                    'documented_entities': row[2],
                    'coverage_percentage': row[3]
                }
                for row in rows
            ]

    async def get_stats_summary(self) -> Dict[str, Any]:
        """Get overall statistics summary.

        Returns:
            Statistics dictionary
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            # Total runs
            cursor = await db.execute("SELECT COUNT(*) FROM runs")
            total_runs = (await cursor.fetchone())[0]

            # Total improvements
            cursor = await db.execute("SELECT COUNT(*) FROM improvements WHERE applied = TRUE")
            total_improvements = (await cursor.fetchone())[0]

            # Average confidence
            cursor = await db.execute("SELECT AVG(confidence_score) FROM improvements WHERE applied = TRUE")
            avg_confidence = (await cursor.fetchone())[0] or 0

            # Gaps by severity
            cursor = await db.execute(
                """
                SELECT severity, COUNT(*) as count
                FROM gaps
                GROUP BY severity
                """
            )
            gaps_by_severity = {row[0]: row[1] for row in await cursor.fetchall()}

            # Recent runs
            cursor = await db.execute(
                """
                SELECT target, timestamp, gaps_found, improvements_applied
                FROM runs
                ORDER BY timestamp DESC
                LIMIT 5
                """
            )
            recent_runs = [
                {
                    'target': row[0],
                    'timestamp': row[1],
                    'gaps_found': row[2],
                    'improvements_applied': row[3]
                }
                for row in await cursor.fetchall()
            ]

        return {
            'total_runs': total_runs,
            'total_improvements_applied': total_improvements,
            'average_confidence': avg_confidence,
            'gaps_by_severity': gaps_by_severity,
            'recent_runs': recent_runs
        }


class StateManager:
    """Manages processing state for incremental runs."""

    def __init__(self, state_file: Optional[Path] = None):
        """Initialize state manager.

        Args:
            state_file: Path to state file
        """
        if state_file is None:
            state_file = Path.cwd() / ".doc-improver-state.json"

        self.state_file = state_file
        self.state: Dict[str, Any] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.debug(f"Loaded state from {self.state_file}")
            except Exception as e:
                logger.warning(f"Error loading state: {e}")
                self.state = {}
        else:
            self.state = {
                'processed_files': {},
                'last_run': None,
                'checkpoints': []
            }

    def _save_state(self) -> None:
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dumps(self.state, f, indent=2, default=str)
            logger.debug(f"Saved state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def mark_file_processed(self, file_path: str, file_hash: str, entity_count: int) -> None:
        """Mark a file as processed.

        Args:
            file_path: Path to file
            file_hash: Hash of file content
            entity_count: Number of entities found
        """
        self.state['processed_files'][file_path] = {
            'hash': file_hash,
            'entity_count': entity_count,
            'processed_at': datetime.now().isoformat()
        }
        self._save_state()

    def is_file_processed(self, file_path: str, current_hash: str) -> bool:
        """Check if file has been processed and unchanged.

        Args:
            file_path: Path to file
            current_hash: Current file hash

        Returns:
            True if already processed and unchanged
        """
        if file_path not in self.state['processed_files']:
            return False

        stored_hash = self.state['processed_files'][file_path]['hash']
        return stored_hash == current_hash

    def create_checkpoint(self, description: str, data: Dict[str, Any]) -> None:
        """Create a checkpoint for resuming.

        Args:
            description: Checkpoint description
            data: Checkpoint data
        """
        checkpoint = {
            'description': description,
            'timestamp': datetime.now().isoformat(),
            'data': data
        }

        if 'checkpoints' not in self.state:
            self.state['checkpoints'] = []

        self.state['checkpoints'].append(checkpoint)
        self._save_state()

        logger.info(f"Created checkpoint: {description}")

    def get_last_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Get the most recent checkpoint.

        Returns:
            Checkpoint data or None
        """
        if not self.state.get('checkpoints'):
            return None

        return self.state['checkpoints'][-1]

    def clear_checkpoints(self) -> None:
        """Clear all checkpoints."""
        self.state['checkpoints'] = []
        self._save_state()

    def reset(self) -> None:
        """Reset all state."""
        self.state = {
            'processed_files': {},
            'last_run': None,
            'checkpoints': []
        }
        self._save_state()
        logger.info("State reset")
