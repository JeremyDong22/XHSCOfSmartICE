# Database connection management for PostgreSQL
# Version 1.0 - Async SQLAlchemy connection with connection pooling
#
# Provides DatabaseConnection class for managing PostgreSQL connections
# Uses async SQLAlchemy with asyncpg driver for FastAPI compatibility

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool

from .models import Base


# Default database configuration
# Can be overridden via environment variables
DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/xhs_scraper"


class DatabaseConnection:
    """
    Database connection manager for PostgreSQL
    Provides async session management and connection pooling
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection manager

        Args:
            database_url: PostgreSQL connection URL. If not provided, uses
                         DATABASE_URL env var or default local connection.
        """
        self.database_url = database_url or os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None

    @property
    def engine(self) -> AsyncEngine:
        """Get or create the async engine"""
        if self._engine is None:
            self._engine = create_async_engine(
                self.database_url,
                echo=False,  # Set to True for SQL query logging
                pool_pre_ping=True,  # Verify connections before use
                pool_size=5,
                max_overflow=10,
            )
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get or create the session factory"""
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._session_factory

    async def create_tables(self) -> None:
        """Create all database tables if they don't exist"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self) -> None:
        """Drop all database tables (use with caution!)"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Context manager for database sessions
        Automatically handles commit/rollback and session cleanup

        Usage:
            async with db.session() as session:
                result = await session.execute(query)
        """
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def close(self) -> None:
        """Close the database engine and all connections"""
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None


# Global database instance
# Initialize with custom URL if needed, otherwise uses default/env config
_database: Optional[DatabaseConnection] = None


def get_database() -> DatabaseConnection:
    """
    Get the global database connection instance
    Creates one if it doesn't exist
    """
    global _database
    if _database is None:
        _database = DatabaseConnection()
    return _database


async def init_database(database_url: Optional[str] = None) -> DatabaseConnection:
    """
    Initialize the database connection and create tables
    Call this during application startup

    Args:
        database_url: Optional custom database URL

    Returns:
        DatabaseConnection instance
    """
    global _database
    _database = DatabaseConnection(database_url)
    await _database.create_tables()
    return _database


async def close_database() -> None:
    """
    Close the database connection
    Call this during application shutdown
    """
    global _database
    if _database is not None:
        await _database.close()
        _database = None
