# Database package for XHSCOfSmartICE
# Version 1.1 - Added init_database and close_database convenience functions
# Provides SQLAlchemy models, connection management, and repository functions

from .connection import DatabaseConnection, get_database, init_database, close_database
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
    "init_database",
    "close_database",
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
