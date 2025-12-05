# Data models for XHS Scraper
# Version: 1.0 - Initial data structures for posts and scrape tasks

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
import json


@dataclass
class XHSPost:
    """Xiaohongshu post data structure"""
    note_id: str
    permanent_url: str
    title: str
    content: str
    images: List[str]
    hashtags: List[str]
    likes: int = 0
    collects: int = 0
    comments: int = 0
    author: str = ""
    publish_date: str = ""
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class ScrapeFilter:
    """Filter conditions for scraping posts"""
    min_likes: int = 0
    min_collects: int = 0
    min_comments: int = 0
    max_posts: int = 20

    def passes(self, post: XHSPost) -> bool:
        """Check if a post passes the filter conditions"""
        return (post.likes >= self.min_likes and
                post.collects >= self.min_collects and
                post.comments >= self.min_comments)


@dataclass
class ScrapeTask:
    """A scraping task configuration"""
    keyword: str
    account_id: int
    filters: ScrapeFilter
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"  # pending, running, completed, failed
    results_file: Optional[str] = None
    posts_found: int = 0
    posts_saved: int = 0


@dataclass
class Account:
    """Account information"""
    account_id: int
    active: bool = True
    nickname: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
