# Data models for XHS Scraper
# Version: 1.1 - Updated for search-only scraping (no detail page clicks)
# Changed: Removed fields not available from search cards (content, hashtags, collects, comments)
# Added: author_avatar, author_profile_url, cover_image, card_dimensions

from dataclasses import dataclass, field, asdict
from typing import List, Optional
from datetime import datetime
import json


@dataclass
class XHSPost:
    """Xiaohongshu post data structure - from search card extraction only"""
    note_id: str
    permanent_url: str
    title: str
    author: str
    author_avatar: str = ""
    author_profile_url: str = ""
    likes: int = 0
    cover_image: str = ""
    publish_date: str = ""
    card_width: int = 0
    card_height: int = 0
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    # Fields NOT available from search cards (kept for compatibility, always empty)
    content: str = ""
    images: List[str] = field(default_factory=list)
    hashtags: List[str] = field(default_factory=list)
    collects: int = 0
    comments: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class ScrapeFilter:
    """Filter conditions for scraping posts
    Note: Only min_likes works with search-only mode (collects/comments not available)
    """
    min_likes: int = 0
    min_collects: int = 0  # IGNORED in search-only mode
    min_comments: int = 0  # IGNORED in search-only mode
    max_posts: int = 20

    def passes(self, post: XHSPost) -> bool:
        """Check if a post passes the filter conditions
        Note: Only likes filter works in search-only mode
        """
        return post.likes >= self.min_likes


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
