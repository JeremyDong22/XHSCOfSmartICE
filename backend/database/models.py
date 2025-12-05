# SQLAlchemy models for XHSCOfSmartICE database
# Version 1.0 - Initial schema design
#
# Tables:
# - accounts: Core account info with aggregated stats
# - browser_sessions: Track each browser open/close event with duration
# - scrape_tasks: Each scraping operation with filters and results
# - posts: Full post data storage (replaces JSON files)
# - post_images: Image file references for future image storage
# - account_usage_stats: Pre-aggregated stats for fast dashboard queries

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    UniqueConstraint,
    Index,
    BigInteger,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
import uuid

Base = declarative_base()


class Account(Base):
    """
    Account table - extends current account_config.json with usage tracking
    Stores core account info and aggregated lifetime statistics
    """
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # The existing account_X number from user_data folder
    account_id = Column(Integer, unique=True, nullable=False, index=True)
    nickname = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    # Aggregated lifetime stats (updated periodically for quick access)
    total_scrapes = Column(Integer, default=0, nullable=False)
    total_posts_scraped = Column(Integer, default=0, nullable=False)
    total_browser_opens = Column(Integer, default=0, nullable=False)
    total_browser_duration_seconds = Column(BigInteger, default=0, nullable=False)

    # Relationships
    browser_sessions = relationship("BrowserSession", back_populates="account")
    scrape_tasks = relationship("ScrapeTask", back_populates="account")
    posts = relationship("Post", back_populates="account")
    usage_stats = relationship("AccountUsageStats", back_populates="account")

    def __repr__(self):
        return f"<Account(account_id={self.account_id}, nickname={self.nickname})>"


class BrowserSession(Base):
    """
    Browser session tracking - records each browser open/close event
    Used to monitor browser usage patterns for anti-crawling analysis
    """
    __tablename__ = "browser_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False, index=True)
    opened_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    # Duration in seconds, calculated when session closes
    duration_seconds = Column(Integer, nullable=True)
    # Reason for close: 'manual', 'graceful', 'force_killed', 'crash', 'system_shutdown'
    close_reason = Column(String(50), nullable=True)

    # Relationship
    account = relationship("Account", back_populates="browser_sessions")

    # Index for querying open sessions and recent sessions
    __table_args__ = (
        Index("idx_browser_sessions_account_opened", "account_id", "opened_at"),
    )

    def __repr__(self):
        return f"<BrowserSession(account_id={self.account_id}, opened_at={self.opened_at})>"


class ScrapeTask(Base):
    """
    Scrape task tracking - records each scraping operation
    Stores filter settings, results count, and status
    """
    __tablename__ = "scrape_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # UUID for external reference (used in API)
    task_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False, index=True)
    keyword = Column(String(255), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    # Status: 'pending', 'running', 'completed', 'failed', 'cancelled'
    status = Column(String(50), nullable=False, default="pending")

    # Filter settings used for this scrape
    max_posts = Column(Integer, nullable=True)
    min_likes = Column(Integer, default=0)
    min_collects = Column(Integer, default=0)
    min_comments = Column(Integer, default=0)
    skip_videos = Column(Boolean, default=False)

    # Results summary
    posts_found = Column(Integer, default=0)
    posts_saved = Column(Integer, default=0)
    posts_filtered = Column(Integer, default=0)

    # Legacy file references (for backward compatibility with existing JSON output)
    result_file_path = Column(String(500), nullable=True)
    log_file_path = Column(String(500), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Relationship
    account = relationship("Account", back_populates="scrape_tasks")
    posts = relationship("Post", back_populates="scrape_task")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_scrape_tasks_account_started", "account_id", "started_at"),
        Index("idx_scrape_tasks_status", "status"),
        Index("idx_scrape_tasks_keyword", "keyword"),
    )

    def __repr__(self):
        return f"<ScrapeTask(task_id={self.task_id}, keyword={self.keyword}, status={self.status})>"


class Post(Base):
    """
    Post data storage - full post data from Xiaohongshu
    Replaces JSON file storage with queryable database records
    Handles deduplication via note_id unique constraint
    """
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # XHS post ID (hex string) - unique identifier
    note_id = Column(String(50), unique=True, nullable=False, index=True)
    # Which scrape task found this post (first discovery)
    scrape_task_id = Column(Integer, ForeignKey("scrape_tasks.id"), nullable=True)
    # Which account scraped this post
    account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=True, index=True)

    # Post content
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)  # For future detail page scraping
    permanent_url = Column(Text, nullable=True)
    tokenized_url = Column(Text, nullable=True)

    # Author information
    author_name = Column(String(255), nullable=True, index=True)
    author_avatar_url = Column(Text, nullable=True)
    author_profile_url = Column(Text, nullable=True)

    # Engagement metrics (can be updated over time)
    likes = Column(Integer, default=0)
    collects = Column(Integer, default=0)  # For future detail page scraping
    comments = Column(Integer, default=0)  # For future detail page scraping

    # Media information
    cover_image_url = Column(Text, nullable=True)
    is_video = Column(Boolean, default=False)
    card_width = Column(Integer, nullable=True)
    card_height = Column(Integer, nullable=True)

    # Metadata
    publish_date = Column(String(100), nullable=True)  # Keep as text, XHS format varies
    scraped_at = Column(DateTime, nullable=False)
    keyword = Column(String(255), nullable=True, index=True)  # Search keyword that found this

    # Deduplication tracking - track how often we see this post
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    times_seen = Column(Integer, default=1)

    # Relationships
    scrape_task = relationship("ScrapeTask", back_populates="posts")
    account = relationship("Account", back_populates="posts")
    images = relationship("PostImage", back_populates="post")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_posts_keyword", "keyword"),
        Index("idx_posts_scraped_at", "scraped_at"),
        Index("idx_posts_likes", "likes"),
        Index("idx_posts_author", "author_name"),
    )

    def __repr__(self):
        return f"<Post(note_id={self.note_id}, title={self.title[:30] if self.title else 'N/A'}...)>"


class PostImage(Base):
    """
    Post image references - stores file paths for downloaded images
    Images are stored in data/images/{account_id}/{note_id}/
    """
    __tablename__ = "post_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    note_id = Column(String(50), nullable=False, index=True)
    # 0 for cover image, 1+ for additional images in post
    image_index = Column(Integer, nullable=False)
    original_url = Column(Text, nullable=False)
    # Path relative to data/images/ folder
    local_file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    downloaded_at = Column(DateTime, nullable=True)

    # Relationship
    post = relationship("Post", back_populates="images")

    # Ensure unique image per post by index
    __table_args__ = (
        UniqueConstraint("note_id", "image_index", name="uq_post_image_index"),
    )

    def __repr__(self):
        return f"<PostImage(note_id={self.note_id}, index={self.image_index})>"


class AccountUsageStats(Base):
    """
    Pre-aggregated usage statistics for fast dashboard queries
    Stores per-minute, per-hour, and per-day statistics for each account
    Updated by background tasks or triggers
    """
    __tablename__ = "account_usage_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.account_id"), nullable=False, index=True)
    # Period type: 'minute', 'hour', 'day'
    period_type = Column(String(10), nullable=False)
    # Start of the period (truncated to minute/hour/day)
    period_start = Column(DateTime, nullable=False)

    # Scraping statistics for this period
    scrape_count = Column(Integer, default=0)
    posts_scraped = Column(Integer, default=0)
    keywords_searched = Column(Integer, default=0)

    # Browser statistics for this period
    browser_opens = Column(Integer, default=0)
    browser_closes = Column(Integer, default=0)
    browser_duration_seconds = Column(Integer, default=0)

    # Relationship
    account = relationship("Account", back_populates="usage_stats")

    # Unique constraint and indexes for efficient queries
    __table_args__ = (
        UniqueConstraint("account_id", "period_type", "period_start", name="uq_account_period"),
        Index("idx_usage_stats_period", "period_type", "period_start"),
        Index("idx_usage_stats_account_period", "account_id", "period_type", "period_start"),
    )

    def __repr__(self):
        return f"<AccountUsageStats(account_id={self.account_id}, period={self.period_type}, start={self.period_start})>"
