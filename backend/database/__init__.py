# Database package for XHSCOfSmartICE
# Version 1.0 - Initial database setup with PostgreSQL
# Provides SQLAlchemy models, connection management, and repository functions

from .connection import DatabaseConnection, get_database
from .models import (
    Base,
    Account,
    BrowserSession,
    ScrapeTask,
    Post,
    PostImage,
    AccountUsageStats,
)
from .repositories import (
    AccountRepository,
    BrowserSessionRepository,
    ScrapeTaskRepository,
    PostRepository,
    StatsRepository,
)

__all__ = [
    "DatabaseConnection",
    "get_database",
    "Base",
    "Account",
    "BrowserSession",
    "ScrapeTask",
    "Post",
    "PostImage",
    "AccountUsageStats",
    "AccountRepository",
    "BrowserSessionRepository",
    "ScrapeTaskRepository",
    "PostRepository",
    "StatsRepository",
]
