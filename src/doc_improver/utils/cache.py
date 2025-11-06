"""Caching layer for API calls and analysis results."""

import hashlib
import json
import logging
import aiosqlite
import asyncio
from pathlib import Path
from typing import Optional, Any, Dict
from datetime import datetime, timedelta

from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class CacheManager:
    """Manages caching of API responses and analysis results."""

    def __init__(self, cache_dir: Path = None):
        """Initialize cache manager.

        Args:
            cache_dir: Directory for cache database (default: .doc-improver-cache)
        """
        if cache_dir is None:
            cache_dir = Path.cwd() / ".doc-improver-cache"

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / "cache.db"
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database schema."""
        if self._initialized:
            return

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    metadata TEXT
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    file_path TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    entities TEXT NOT NULL,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_api_expires
                ON api_cache(expires_at)
            """)

            await db.commit()

        self._initialized = True
        logger.debug(f"Cache initialized at {self.db_path}")

    def _hash_content(self, content: str) -> str:
        """Generate hash of content for cache key.

        Args:
            content: Content to hash

        Returns:
            SHA256 hash string
        """
        return hashlib.sha256(content.encode()).hexdigest()

    def _hash_dict(self, data: Dict[str, Any]) -> str:
        """Generate hash of dictionary for cache key.

        Args:
            data: Dictionary to hash

        Returns:
            SHA256 hash string
        """
        json_str = json.dumps(data, sort_keys=True)
        return self._hash_content(json_str)

    async def get_api_response(self, cache_key: str) -> Optional[str]:
        """Get cached API response.

        Args:
            cache_key: Cache key

        Returns:
            Cached response or None if not found/expired
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT value, expires_at
                FROM api_cache
                WHERE key = ?
                """,
                (cache_key,)
            )
            row = await cursor.fetchone()

            if row is None:
                return None

            value, expires_at = row

            # Check expiration
            if expires_at:
                expires = datetime.fromisoformat(expires_at)
                if datetime.now() > expires:
                    # Expired, delete it
                    await db.execute("DELETE FROM api_cache WHERE key = ?", (cache_key,))
                    await db.commit()
                    return None

            logger.debug(f"Cache hit for key: {cache_key[:16]}...")
            return value

    async def set_api_response(
        self,
        cache_key: str,
        value: str,
        ttl_hours: int = 24,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store API response in cache.

        Args:
            cache_key: Cache key
            value: Response to cache
            ttl_hours: Time to live in hours
            metadata: Optional metadata
        """
        await self.initialize()

        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        metadata_json = json.dumps(metadata) if metadata else None

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO api_cache (key, value, expires_at, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (cache_key, value, expires_at.isoformat(), metadata_json)
            )
            await db.commit()

        logger.debug(f"Cached response for key: {cache_key[:16]}...")

    async def get_file_analysis(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get cached file analysis.

        Args:
            file_path: Path to analyzed file

        Returns:
            Cached analysis or None if not found/outdated
        """
        await self.initialize()

        # Check if file still exists and get current hash
        path = Path(file_path)
        if not path.exists():
            return None

        try:
            with open(path, 'rb') as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Error reading file {file_path}: {e}")
            return None

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT file_hash, entities
                FROM analysis_cache
                WHERE file_path = ?
                """,
                (file_path,)
            )
            row = await cursor.fetchone()

            if row is None:
                return None

            cached_hash, entities_json = row

            # Check if file has changed
            if cached_hash != current_hash:
                # File changed, invalidate cache
                await db.execute("DELETE FROM analysis_cache WHERE file_path = ?", (file_path,))
                await db.commit()
                return None

            logger.debug(f"Cache hit for file: {file_path}")
            return json.loads(entities_json)

    async def set_file_analysis(
        self,
        file_path: str,
        entities: list
    ) -> None:
        """Store file analysis in cache.

        Args:
            file_path: Path to analyzed file
            entities: List of entities found
        """
        await self.initialize()

        # Calculate file hash
        path = Path(file_path)
        try:
            with open(path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Error reading file {file_path}: {e}")
            return

        # Handle both Pydantic v1 and v2
        serialized_entities = []
        for e in entities:
            if hasattr(e, 'model_dump'):  # Pydantic v2
                serialized_entities.append(e.model_dump())
            elif hasattr(e, 'dict'):  # Pydantic v1
                serialized_entities.append(e.dict())
            else:  # Already a dict
                serialized_entities.append(e)

        entities_json = json.dumps(serialized_entities)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO analysis_cache (file_path, file_hash, entities)
                VALUES (?, ?, ?)
                """,
                (file_path, file_hash, entities_json)
            )
            await db.commit()

        logger.debug(f"Cached analysis for file: {file_path}")

    async def clear_expired(self) -> int:
        """Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                DELETE FROM api_cache
                WHERE expires_at IS NOT NULL AND expires_at < ?
                """,
                (datetime.now().isoformat(),)
            )
            await db.commit()
            deleted = cursor.rowcount

        logger.info(f"Cleared {deleted} expired cache entries")
        return deleted

    async def clear_all(self) -> None:
        """Clear all cache entries."""
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM api_cache")
            await db.execute("DELETE FROM analysis_cache")
            await db.commit()

        logger.info("Cleared all cache entries")

    async def get_stats(self) -> Dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        await self.initialize()

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM api_cache")
            api_count = (await cursor.fetchone())[0]

            cursor = await db.execute("SELECT COUNT(*) FROM analysis_cache")
            analysis_count = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """
                SELECT COUNT(*) FROM api_cache
                WHERE expires_at IS NOT NULL AND expires_at < ?
                """,
                (datetime.now().isoformat(),)
            )
            expired_count = (await cursor.fetchone())[0]

        return {
            "api_responses": api_count,
            "file_analyses": analysis_count,
            "expired": expired_count,
        }


# Synchronous wrapper for backward compatibility
class SyncCacheManager:
    """Synchronous wrapper for CacheManager."""

    def __init__(self, cache_dir: Path = None):
        self.async_manager = CacheManager(cache_dir)

    def _run_async(self, coro):
        """Run async coroutine synchronously.

        Uses asyncio.run() which is safer for mixed environments.
        """
        import sys
        if sys.version_info >= (3, 7):
            return asyncio.run(coro)
        else:
            # Fallback for Python 3.6
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

    def get_api_response(self, cache_key: str) -> Optional[str]:
        return self._run_async(self.async_manager.get_api_response(cache_key))

    def set_api_response(
        self,
        cache_key: str,
        value: str,
        ttl_hours: int = 24,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        self._run_async(self.async_manager.set_api_response(cache_key, value, ttl_hours, metadata))

    def clear_expired(self) -> int:
        return self._run_async(self.async_manager.clear_expired())

    def clear_all(self) -> None:
        self._run_async(self.async_manager.clear_all())

    def get_stats(self) -> Dict[str, int]:
        return self._run_async(self.async_manager.get_stats())
