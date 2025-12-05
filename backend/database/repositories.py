# Repository layer for database operations
# Version 1.0 - CRUD operations and statistics queries
#
# Repositories:
# - AccountRepository: Account CRUD and lifetime stats
# - BrowserSessionRepository: Browser open/close tracking
# - ScrapeTaskRepository: Scrape task management
# - PostRepository: Post data storage and deduplication
# - StatsRepository: Usage statistics aggregation and queries

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from .models import (
    Account,
    BrowserSession,
    ScrapeTask,
    Post,
    PostImage,
    AccountUsageStats,
)


class AccountRepository:
    """Repository for account operations"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        account_id: int,
        nickname: Optional[str] = None,
        is_active: bool = True,
    ) -> Account:
        """Create a new account record"""
        account = Account(
            account_id=account_id,
            nickname=nickname,
            is_active=is_active,
            created_at=datetime.utcnow(),
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def get_by_account_id(self, account_id: int) -> Optional[Account]:
        """Get account by its account_id"""
        result = await self.session.execute(
            select(Account).where(Account.account_id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, active_only: bool = False) -> List[Account]:
        """Get all accounts, optionally filtered by active status"""
        query = select(Account)
        if active_only:
            query = query.where(Account.is_active == True)
        query = query.order_by(Account.account_id)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        account_id: int,
        nickname: Optional[str] = None,
        is_active: Optional[bool] = None,
        last_used_at: Optional[datetime] = None,
    ) -> Optional[Account]:
        """Update account fields"""
        account = await self.get_by_account_id(account_id)
        if account is None:
            return None

        if nickname is not None:
            account.nickname = nickname
        if is_active is not None:
            account.is_active = is_active
        if last_used_at is not None:
            account.last_used_at = last_used_at

        await self.session.flush()
        return account

    async def delete(self, account_id: int) -> bool:
        """Delete an account by account_id"""
        result = await self.session.execute(
            delete(Account).where(Account.account_id == account_id)
        )
        return result.rowcount > 0

    async def increment_stats(
        self,
        account_id: int,
        scrapes: int = 0,
        posts_scraped: int = 0,
        browser_opens: int = 0,
        browser_duration_seconds: int = 0,
    ) -> None:
        """Increment account lifetime statistics"""
        await self.session.execute(
            update(Account)
            .where(Account.account_id == account_id)
            .values(
                total_scrapes=Account.total_scrapes + scrapes,
                total_posts_scraped=Account.total_posts_scraped + posts_scraped,
                total_browser_opens=Account.total_browser_opens + browser_opens,
                total_browser_duration_seconds=Account.total_browser_duration_seconds + browser_duration_seconds,
                last_used_at=datetime.utcnow(),
            )
        )

    async def get_or_create(
        self,
        account_id: int,
        nickname: Optional[str] = None,
    ) -> Account:
        """Get existing account or create new one"""
        account = await self.get_by_account_id(account_id)
        if account is None:
            account = await self.create(account_id, nickname)
        return account


class BrowserSessionRepository:
    """Repository for browser session tracking"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def start_session(self, account_id: int) -> BrowserSession:
        """Record a browser session start"""
        browser_session = BrowserSession(
            account_id=account_id,
            opened_at=datetime.utcnow(),
        )
        self.session.add(browser_session)
        await self.session.flush()
        return browser_session

    async def end_session(
        self,
        session_id: int,
        close_reason: str = "manual",
    ) -> Optional[BrowserSession]:
        """Record a browser session end"""
        result = await self.session.execute(
            select(BrowserSession).where(BrowserSession.id == session_id)
        )
        browser_session = result.scalar_one_or_none()

        if browser_session is None:
            return None

        browser_session.closed_at = datetime.utcnow()
        browser_session.close_reason = close_reason

        # Calculate duration
        if browser_session.opened_at:
            duration = browser_session.closed_at - browser_session.opened_at
            browser_session.duration_seconds = int(duration.total_seconds())

        await self.session.flush()
        return browser_session

    async def end_session_by_account(
        self,
        account_id: int,
        close_reason: str = "manual",
    ) -> Optional[BrowserSession]:
        """End the currently open session for an account"""
        # Find open session for this account
        result = await self.session.execute(
            select(BrowserSession)
            .where(
                and_(
                    BrowserSession.account_id == account_id,
                    BrowserSession.closed_at.is_(None),
                )
            )
            .order_by(BrowserSession.opened_at.desc())
            .limit(1)
        )
        browser_session = result.scalar_one_or_none()

        if browser_session is None:
            return None

        browser_session.closed_at = datetime.utcnow()
        browser_session.close_reason = close_reason

        # Calculate duration
        if browser_session.opened_at:
            duration = browser_session.closed_at - browser_session.opened_at
            browser_session.duration_seconds = int(duration.total_seconds())

        await self.session.flush()
        return browser_session

    async def get_open_session(self, account_id: int) -> Optional[BrowserSession]:
        """Get currently open session for an account"""
        result = await self.session.execute(
            select(BrowserSession)
            .where(
                and_(
                    BrowserSession.account_id == account_id,
                    BrowserSession.closed_at.is_(None),
                )
            )
            .order_by(BrowserSession.opened_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_sessions_for_account(
        self,
        account_id: int,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[BrowserSession]:
        """Get browser sessions for an account"""
        query = select(BrowserSession).where(BrowserSession.account_id == account_id)
        if since:
            query = query.where(BrowserSession.opened_at >= since)
        query = query.order_by(BrowserSession.opened_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_total_duration_today(self, account_id: int) -> int:
        """Get total browser duration for today in seconds"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.coalesce(func.sum(BrowserSession.duration_seconds), 0))
            .where(
                and_(
                    BrowserSession.account_id == account_id,
                    BrowserSession.opened_at >= today_start,
                    BrowserSession.duration_seconds.isnot(None),
                )
            )
        )
        return result.scalar() or 0

    async def get_opens_today(self, account_id: int) -> int:
        """Get number of browser opens today"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count(BrowserSession.id))
            .where(
                and_(
                    BrowserSession.account_id == account_id,
                    BrowserSession.opened_at >= today_start,
                )
            )
        )
        return result.scalar() or 0


class ScrapeTaskRepository:
    """Repository for scrape task management"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        task_id: UUID,
        account_id: int,
        keyword: str,
        max_posts: Optional[int] = None,
        min_likes: int = 0,
        min_collects: int = 0,
        min_comments: int = 0,
        skip_videos: bool = False,
    ) -> ScrapeTask:
        """Create a new scrape task"""
        task = ScrapeTask(
            task_id=task_id,
            account_id=account_id,
            keyword=keyword,
            started_at=datetime.utcnow(),
            status="running",
            max_posts=max_posts,
            min_likes=min_likes,
            min_collects=min_collects,
            min_comments=min_comments,
            skip_videos=skip_videos,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def get_by_task_id(self, task_id: UUID) -> Optional[ScrapeTask]:
        """Get scrape task by UUID"""
        result = await self.session.execute(
            select(ScrapeTask).where(ScrapeTask.task_id == task_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        task_id: UUID,
        status: str,
        posts_found: Optional[int] = None,
        posts_saved: Optional[int] = None,
        posts_filtered: Optional[int] = None,
        error_message: Optional[str] = None,
        result_file_path: Optional[str] = None,
        log_file_path: Optional[str] = None,
    ) -> Optional[ScrapeTask]:
        """Update scrape task status and results"""
        task = await self.get_by_task_id(task_id)
        if task is None:
            return None

        task.status = status
        if status in ("completed", "failed", "cancelled"):
            task.completed_at = datetime.utcnow()
        if posts_found is not None:
            task.posts_found = posts_found
        if posts_saved is not None:
            task.posts_saved = posts_saved
        if posts_filtered is not None:
            task.posts_filtered = posts_filtered
        if error_message is not None:
            task.error_message = error_message
        if result_file_path is not None:
            task.result_file_path = result_file_path
        if log_file_path is not None:
            task.log_file_path = log_file_path

        await self.session.flush()
        return task

    async def get_tasks_for_account(
        self,
        account_id: int,
        since: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[ScrapeTask]:
        """Get scrape tasks for an account"""
        query = select(ScrapeTask).where(ScrapeTask.account_id == account_id)
        if since:
            query = query.where(ScrapeTask.started_at >= since)
        if status:
            query = query.where(ScrapeTask.status == status)
        query = query.order_by(ScrapeTask.started_at.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_scrapes_this_hour(self, account_id: int) -> int:
        """Get number of scrapes in the current hour"""
        hour_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count(ScrapeTask.id))
            .where(
                and_(
                    ScrapeTask.account_id == account_id,
                    ScrapeTask.started_at >= hour_start,
                )
            )
        )
        return result.scalar() or 0

    async def get_scrapes_today(self, account_id: int) -> int:
        """Get number of scrapes today"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        result = await self.session.execute(
            select(func.count(ScrapeTask.id))
            .where(
                and_(
                    ScrapeTask.account_id == account_id,
                    ScrapeTask.started_at >= today_start,
                )
            )
        )
        return result.scalar() or 0


class PostRepository:
    """Repository for post data storage"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(
        self,
        note_id: str,
        scrape_task_id: Optional[int] = None,
        account_id: Optional[int] = None,
        title: Optional[str] = None,
        content: Optional[str] = None,
        permanent_url: Optional[str] = None,
        tokenized_url: Optional[str] = None,
        author_name: Optional[str] = None,
        author_avatar_url: Optional[str] = None,
        author_profile_url: Optional[str] = None,
        likes: int = 0,
        collects: int = 0,
        comments: int = 0,
        cover_image_url: Optional[str] = None,
        is_video: bool = False,
        card_width: Optional[int] = None,
        card_height: Optional[int] = None,
        publish_date: Optional[str] = None,
        scraped_at: Optional[datetime] = None,
        keyword: Optional[str] = None,
    ) -> Post:
        """
        Insert or update a post. If post exists (by note_id),
        update last_seen_at and increment times_seen.
        """
        scraped_at = scraped_at or datetime.utcnow()

        # Check if post exists
        existing = await self.get_by_note_id(note_id)

        if existing:
            # Update existing post
            existing.last_seen_at = datetime.utcnow()
            existing.times_seen += 1
            # Update engagement metrics if they increased
            if likes > existing.likes:
                existing.likes = likes
            if collects > existing.collects:
                existing.collects = collects
            if comments > existing.comments:
                existing.comments = comments
            await self.session.flush()
            return existing
        else:
            # Create new post
            post = Post(
                note_id=note_id,
                scrape_task_id=scrape_task_id,
                account_id=account_id,
                title=title,
                content=content,
                permanent_url=permanent_url,
                tokenized_url=tokenized_url,
                author_name=author_name,
                author_avatar_url=author_avatar_url,
                author_profile_url=author_profile_url,
                likes=likes,
                collects=collects,
                comments=comments,
                cover_image_url=cover_image_url,
                is_video=is_video,
                card_width=card_width,
                card_height=card_height,
                publish_date=publish_date,
                scraped_at=scraped_at,
                keyword=keyword,
                first_seen_at=datetime.utcnow(),
                last_seen_at=datetime.utcnow(),
                times_seen=1,
            )
            self.session.add(post)
            await self.session.flush()
            return post

    async def bulk_upsert(self, posts_data: List[Dict[str, Any]]) -> int:
        """
        Bulk insert/update posts. Returns count of new posts inserted.
        """
        new_count = 0
        for post_data in posts_data:
            note_id = post_data.get("note_id")
            if not note_id:
                continue

            existing = await self.get_by_note_id(note_id)
            if existing is None:
                new_count += 1

            await self.upsert(**post_data)

        return new_count

    async def get_by_note_id(self, note_id: str) -> Optional[Post]:
        """Get post by note_id"""
        result = await self.session.execute(
            select(Post).where(Post.note_id == note_id)
        )
        return result.scalar_one_or_none()

    async def get_by_keyword(
        self,
        keyword: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Post]:
        """Get posts by search keyword"""
        result = await self.session.execute(
            select(Post)
            .where(Post.keyword == keyword)
            .order_by(Post.scraped_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_scrape_task(self, scrape_task_id: int) -> List[Post]:
        """Get all posts from a specific scrape task"""
        result = await self.session.execute(
            select(Post)
            .where(Post.scrape_task_id == scrape_task_id)
            .order_by(Post.likes.desc())
        )
        return list(result.scalars().all())

    async def count_by_account(self, account_id: int) -> int:
        """Count total posts scraped by an account"""
        result = await self.session.execute(
            select(func.count(Post.id))
            .where(Post.account_id == account_id)
        )
        return result.scalar() or 0

    async def get_total_count(self) -> int:
        """Get total post count"""
        result = await self.session.execute(select(func.count(Post.id)))
        return result.scalar() or 0

    async def search(
        self,
        keyword: Optional[str] = None,
        author: Optional[str] = None,
        min_likes: Optional[int] = None,
        is_video: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Post]:
        """Search posts with filters"""
        query = select(Post)

        conditions = []
        if keyword:
            conditions.append(
                or_(
                    Post.keyword.ilike(f"%{keyword}%"),
                    Post.title.ilike(f"%{keyword}%"),
                )
            )
        if author:
            conditions.append(Post.author_name.ilike(f"%{author}%"))
        if min_likes is not None:
            conditions.append(Post.likes >= min_likes)
        if is_video is not None:
            conditions.append(Post.is_video == is_video)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.order_by(Post.scraped_at.desc()).offset(offset).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())


class StatsRepository:
    """Repository for usage statistics"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_stats(
        self,
        account_id: int,
        period_type: str,
        period_start: datetime,
        scrape_count: int = 0,
        posts_scraped: int = 0,
        keywords_searched: int = 0,
        browser_opens: int = 0,
        browser_closes: int = 0,
        browser_duration_seconds: int = 0,
    ) -> AccountUsageStats:
        """
        Record or update usage stats for a period.
        Uses upsert to increment existing values.
        """
        # Try to find existing record
        result = await self.session.execute(
            select(AccountUsageStats)
            .where(
                and_(
                    AccountUsageStats.account_id == account_id,
                    AccountUsageStats.period_type == period_type,
                    AccountUsageStats.period_start == period_start,
                )
            )
        )
        stats = result.scalar_one_or_none()

        if stats:
            # Update existing
            stats.scrape_count += scrape_count
            stats.posts_scraped += posts_scraped
            stats.keywords_searched += keywords_searched
            stats.browser_opens += browser_opens
            stats.browser_closes += browser_closes
            stats.browser_duration_seconds += browser_duration_seconds
        else:
            # Create new
            stats = AccountUsageStats(
                account_id=account_id,
                period_type=period_type,
                period_start=period_start,
                scrape_count=scrape_count,
                posts_scraped=posts_scraped,
                keywords_searched=keywords_searched,
                browser_opens=browser_opens,
                browser_closes=browser_closes,
                browser_duration_seconds=browser_duration_seconds,
            )
            self.session.add(stats)

        await self.session.flush()
        return stats

    async def get_stats_for_period(
        self,
        account_id: int,
        period_type: str,
        start: datetime,
        end: datetime,
    ) -> List[AccountUsageStats]:
        """Get stats for a date range"""
        result = await self.session.execute(
            select(AccountUsageStats)
            .where(
                and_(
                    AccountUsageStats.account_id == account_id,
                    AccountUsageStats.period_type == period_type,
                    AccountUsageStats.period_start >= start,
                    AccountUsageStats.period_start < end,
                )
            )
            .order_by(AccountUsageStats.period_start)
        )
        return list(result.scalars().all())

    async def get_hourly_stats_today(self, account_id: int) -> List[AccountUsageStats]:
        """Get hourly stats for today"""
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow_start = today_start + timedelta(days=1)
        return await self.get_stats_for_period(
            account_id, "hour", today_start, tomorrow_start
        )

    async def get_daily_stats(
        self,
        account_id: int,
        days: int = 30,
    ) -> List[AccountUsageStats]:
        """Get daily stats for the last N days"""
        end = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        start = end - timedelta(days=days)
        return await self.get_stats_for_period(account_id, "day", start, end)

    async def get_account_summary(self, account_id: int) -> Dict[str, Any]:
        """
        Get summary statistics for an account including:
        - Today's stats
        - This hour's stats
        - Total lifetime stats
        """
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_start = now.replace(minute=0, second=0, microsecond=0)

        # Get account for lifetime stats
        account_result = await self.session.execute(
            select(Account).where(Account.account_id == account_id)
        )
        account = account_result.scalar_one_or_none()

        # Get today's aggregated stats
        today_result = await self.session.execute(
            select(
                func.coalesce(func.sum(AccountUsageStats.scrape_count), 0),
                func.coalesce(func.sum(AccountUsageStats.posts_scraped), 0),
                func.coalesce(func.sum(AccountUsageStats.browser_opens), 0),
                func.coalesce(func.sum(AccountUsageStats.browser_duration_seconds), 0),
            )
            .where(
                and_(
                    AccountUsageStats.account_id == account_id,
                    AccountUsageStats.period_type == "hour",
                    AccountUsageStats.period_start >= today_start,
                )
            )
        )
        today_stats = today_result.one()

        # Get this hour's stats
        hour_result = await self.session.execute(
            select(AccountUsageStats)
            .where(
                and_(
                    AccountUsageStats.account_id == account_id,
                    AccountUsageStats.period_type == "hour",
                    AccountUsageStats.period_start == hour_start,
                )
            )
        )
        hour_stats = hour_result.scalar_one_or_none()

        return {
            "account_id": account_id,
            "lifetime": {
                "total_scrapes": account.total_scrapes if account else 0,
                "total_posts_scraped": account.total_posts_scraped if account else 0,
                "total_browser_opens": account.total_browser_opens if account else 0,
                "total_browser_duration_seconds": account.total_browser_duration_seconds if account else 0,
            },
            "today": {
                "scrape_count": today_stats[0],
                "posts_scraped": today_stats[1],
                "browser_opens": today_stats[2],
                "browser_duration_seconds": today_stats[3],
            },
            "this_hour": {
                "scrape_count": hour_stats.scrape_count if hour_stats else 0,
                "posts_scraped": hour_stats.posts_scraped if hour_stats else 0,
                "browser_opens": hour_stats.browser_opens if hour_stats else 0,
                "browser_duration_seconds": hour_stats.browser_duration_seconds if hour_stats else 0,
            },
        }

    async def get_all_accounts_summary(self) -> List[Dict[str, Any]]:
        """Get summary for all accounts"""
        result = await self.session.execute(
            select(Account).order_by(Account.account_id)
        )
        accounts = result.scalars().all()

        summaries = []
        for account in accounts:
            summary = await self.get_account_summary(account.account_id)
            summary["nickname"] = account.nickname
            summary["is_active"] = account.is_active
            summary["created_at"] = account.created_at.isoformat() if account.created_at else None
            summary["last_used_at"] = account.last_used_at.isoformat() if account.last_used_at else None
            summaries.append(summary)

        return summaries
