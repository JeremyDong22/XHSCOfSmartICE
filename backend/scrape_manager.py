# Scrape manager for tracking active scraping tasks
# Version: 1.2 - Fixed background task handling for graceful shutdown
# Changes: Added task tracking, shorter cleanup delay, cancellation handling
# Previous: Added database integration for scrape task tracking

import asyncio
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# Database imports
from database import get_database
from database.repositories import ScrapeTaskRepository, AccountRepository, StatsRepository


@dataclass
class ActiveScrape:
    """Active scraping task"""
    task_id: str
    account_id: int
    keyword: str
    started_at: str
    status: str  # running, completed, cancelled, failed
    asyncio_task: Optional[asyncio.Task] = None
    cancel_requested: bool = False
    db_task_id: Optional[int] = None  # Database ScrapeTask.id


class ScrapeManager:
    """Manages active scraping tasks"""

    def __init__(self):
        self.active_scrapes: Dict[str, ActiveScrape] = {}
        self.log_callbacks: Dict[str, list] = {}  # task_id -> list of callback functions
        self._background_tasks: set = set()  # Track background tasks for cleanup

    def _track_task(self, task: asyncio.Task):
        """Track a background task"""
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def create_scrape(self, task_id: str, account_id: int, keyword: str) -> ActiveScrape:
        """Create a new active scrape task"""
        scrape = ActiveScrape(
            task_id=task_id,
            account_id=account_id,
            keyword=keyword,
            started_at=datetime.now().isoformat(),
            status="running"
        )
        self.active_scrapes[task_id] = scrape
        self.log_callbacks[task_id] = []

        # Create task in database (fire-and-forget but tracked)
        task = asyncio.create_task(self._create_db_task(task_id, account_id, keyword))
        self._track_task(task)

        return scrape

    def get_scrape(self, task_id: str) -> Optional[ActiveScrape]:
        """Get active scrape by task ID"""
        return self.active_scrapes.get(task_id)

    def set_task(self, task_id: str, asyncio_task: asyncio.Task):
        """Set the asyncio task for a scrape"""
        if task_id in self.active_scrapes:
            self.active_scrapes[task_id].asyncio_task = asyncio_task

    def cancel_scrape(self, task_id: str) -> bool:
        """Request cancellation of a scrape task"""
        scrape = self.active_scrapes.get(task_id)
        if not scrape:
            return False

        scrape.cancel_requested = True
        if scrape.asyncio_task and not scrape.asyncio_task.done():
            scrape.asyncio_task.cancel()

        return True

    def is_cancelled(self, task_id: str) -> bool:
        """Check if scrape has been cancelled"""
        scrape = self.active_scrapes.get(task_id)
        return scrape.cancel_requested if scrape else False

    def complete_scrape(self, task_id: str, status: str = "completed"):
        """Mark scrape as completed/failed"""
        if task_id in self.active_scrapes:
            self.active_scrapes[task_id].status = status

            # Update database task status (tracked)
            task1 = asyncio.create_task(self._update_db_task_status(task_id, status))
            self._track_task(task1)

            # Update account scrape count (tracked)
            scrape = self.active_scrapes[task_id]
            task2 = asyncio.create_task(self._update_scrape_stats(scrape.account_id))
            self._track_task(task2)

            # Clean up after a delay (tracked, shorter delay for faster shutdown)
            task3 = asyncio.create_task(self._cleanup_scrape(task_id))
            self._track_task(task3)

    async def _cleanup_scrape(self, task_id: str):
        """Clean up scrape task after delay"""
        try:
            await asyncio.sleep(30)  # Keep for 30 seconds for final log retrieval
        except asyncio.CancelledError:
            pass  # Allow cancellation during shutdown
        finally:
            if task_id in self.active_scrapes:
                del self.active_scrapes[task_id]
            if task_id in self.log_callbacks:
                del self.log_callbacks[task_id]

    def add_log_callback(self, task_id: str, callback: Callable):
        """Add a callback for log messages"""
        if task_id in self.log_callbacks:
            self.log_callbacks[task_id].append(callback)

    def remove_log_callback(self, task_id: str, callback: Callable):
        """Remove a callback"""
        if task_id in self.log_callbacks:
            try:
                self.log_callbacks[task_id].remove(callback)
            except ValueError:
                pass

    async def send_log(self, task_id: str, message: str):
        """Send log message to all callbacks"""
        if task_id in self.log_callbacks:
            for callback in self.log_callbacks[task_id]:
                try:
                    await callback(message)
                except Exception as e:
                    print(f"Error sending log: {e}")

    def get_all_active(self) -> Dict[str, ActiveScrape]:
        """Get all active scrapes"""
        return {k: v for k, v in self.active_scrapes.items() if v.status == "running"}

    # Database helper methods
    async def _create_db_task(self, task_id: str, account_id: int, keyword: str):
        """Create scrape task in database"""
        try:
            db = get_database()
            async with db.session() as session:
                # Ensure account exists
                account_repo = AccountRepository(session)
                await account_repo.get_or_create(account_id)

                # Create scrape task
                task_repo = ScrapeTaskRepository(session)
                db_task = await task_repo.create(
                    task_id=UUID(task_id),
                    account_id=account_id,
                    keyword=keyword
                )

                # Store DB task ID
                if task_id in self.active_scrapes:
                    self.active_scrapes[task_id].db_task_id = db_task.id

        except Exception as e:
            print(f"Error creating scrape task in database: {e}")

    async def _update_db_task_status(self, task_id: str, status: str):
        """Update scrape task status in database"""
        try:
            db = get_database()
            async with db.session() as session:
                task_repo = ScrapeTaskRepository(session)
                await task_repo.update_status(
                    task_id=UUID(task_id),
                    status=status
                )
        except Exception as e:
            print(f"Error updating scrape task status in database: {e}")

    async def _update_scrape_stats(self, account_id: int):
        """Update account scrape statistics"""
        try:
            db = get_database()
            async with db.session() as session:
                # Increment account's total scrapes
                account_repo = AccountRepository(session)
                await account_repo.increment_stats(
                    account_id,
                    scrapes=1
                )

                # Update hourly stats
                hour_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
                stats_repo = StatsRepository(session)
                await stats_repo.record_stats(
                    account_id=account_id,
                    period_type="hour",
                    period_start=hour_start,
                    scrape_count=1
                )
        except Exception as e:
            print(f"Error updating scrape stats in database: {e}")
