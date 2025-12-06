# Browser manager for XHS multi-account system
# Version: 1.5 - Reduced browser close timeout for faster hot-reload
# Changes: Browser stop() now uses 2s timeout instead of 5s for faster shutdown during hot-reload
# Previous: Fixed browser duration tracking bug where 0-second durations were skipped

import asyncio
import subprocess
import platform
from typing import Dict, Optional, Callable
from datetime import datetime
from playwright.async_api import async_playwright, BrowserContext, Page, Playwright
from account_manager import AccountManager

# Database imports
from database import get_database
from database.repositories import BrowserSessionRepository, AccountRepository, StatsRepository


class BrowserManager:
    """Manages Playwright browser instances for multiple accounts"""

    def __init__(self, account_manager: AccountManager):
        self.account_manager = account_manager
        self.playwright: Optional[Playwright] = None
        self.contexts: Dict[int, BrowserContext] = {}
        self.pages: Dict[int, Page] = {}
        self.session_ids: Dict[int, int] = {}  # Track database session IDs per account
        self._running = False

    async def start(self):
        """Initialize Playwright and clean up any orphaned processes from previous sessions"""
        if not self.playwright:
            # Clean up any orphaned Chrome processes and lock files from previous runs
            self._kill_orphaned_chrome_processes()
            self.playwright = await async_playwright().start()
            self._running = True

    async def stop(self):
        """Close all browsers and stop Playwright"""
        # Close all contexts with reduced timeout for hot-reload
        for account_id in list(self.contexts.keys()):
            await self.close_browser(account_id, timeout=2.0)

        # Stop Playwright
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
            self._running = False

    def is_running(self) -> bool:
        return self._running

    def is_browser_open(self, account_id: int) -> bool:
        """Check if a browser is open for the given account"""
        return account_id in self.contexts

    def get_open_browsers(self) -> list:
        """Get list of account IDs with open browsers"""
        return list(self.contexts.keys())

    async def open_browser(self, account_id: int, position_index: int = 0) -> bool:
        """
        Open a browser for the specified account.
        Returns True if successful, False otherwise.
        """
        if not self.playwright:
            await self.start()

        if account_id in self.contexts:
            print(f"Browser for account {account_id} is already open")
            return False

        account = self.account_manager.get_account(account_id)
        if not account:
            print(f"Account {account_id} not found")
            return False

        user_data_path = self.account_manager.get_user_data_path(account_id)

        try:
            context = await self.playwright.chromium.launch_persistent_context(
                user_data_path,
                headless=False,
                channel='chrome',
                viewport={'width': 1280, 'height': 800},
                args=[
                    '--disable-blink-features=AutomationControlled',
                    f'--window-position={(position_index % 4) * 350},{(position_index // 4) * 450}'
                ]
            )

            # Open XHS homepage
            page = await context.new_page()
            await page.goto('https://www.xiaohongshu.com')

            self.contexts[account_id] = context
            self.pages[account_id] = page

            # Update last used timestamp
            self.account_manager.mark_account_used(account_id)

            # Track browser session in database
            await self._track_browser_open(account_id)

            return True

        except Exception as e:
            print(f"Failed to open browser for account {account_id}: {e}")
            return False

    async def open_browser_for_login(self, on_login_complete: Optional[Callable] = None) -> int:
        """
        Open a new browser for manual login.
        Creates a new account and returns its ID.
        """
        if not self.playwright:
            await self.start()

        # Create new account
        account = self.account_manager.create_account()
        account_id = account.account_id
        user_data_path = self.account_manager.get_user_data_path(account_id)

        try:
            context = await self.playwright.chromium.launch_persistent_context(
                user_data_path,
                headless=False,
                channel='chrome',
                viewport={'width': 1280, 'height': 800},
                args=['--disable-blink-features=AutomationControlled']
            )

            # Create label page
            label_page = await context.new_page()
            await label_page.set_content(f'''
                <html>
                <head><title>New Account {account_id} - Please Login</title></head>
                <body style="display:flex;flex-direction:column;justify-content:center;align-items:center;height:100vh;margin:0;background:linear-gradient(135deg,#ff6b6b,#feca57);">
                    <h1 style="font-size:80px;color:#fff;font-family:Arial;margin:0;text-shadow:2px 2px 4px rgba(0,0,0,0.3);">Account {account_id}</h1>
                    <p style="font-size:24px;color:#fff;margin:20px 0;">Please login in the next tab</p>
                    <p style="font-size:18px;color:rgba(255,255,255,0.8);">Session will be saved automatically</p>
                </body>
                </html>
            ''')

            # Open XHS login page
            page = await context.new_page()
            await page.goto('https://www.xiaohongshu.com')

            self.contexts[account_id] = context
            self.pages[account_id] = page

            return account_id

        except Exception as e:
            print(f"Failed to create new account browser: {e}")
            # Clean up the account if browser failed
            self.account_manager.delete_account(account_id)
            return -1

    async def close_browser(self, account_id: int, timeout: float = 5.0) -> bool:
        """Close browser for the specified account with timeout"""
        if account_id not in self.contexts:
            return False

        context = self.contexts[account_id]
        close_reason = "manual"

        try:
            # Try graceful close with timeout
            await asyncio.wait_for(context.close(), timeout=timeout)
            close_reason = "graceful"
        except asyncio.TimeoutError:
            print(f"Browser {account_id} close timed out after {timeout}s, force killing...")
            # Force kill the browser process for this account
            self._force_kill_browser_for_account(account_id)
            close_reason = "force_killed"
        except Exception as e:
            print(f"Error closing browser for account {account_id}: {e}")
            self._force_kill_browser_for_account(account_id)
            close_reason = "crash"

        # Track browser close in database
        await self._track_browser_close(account_id, close_reason)

        # Clean up our tracking regardless of how it closed
        if account_id in self.contexts:
            del self.contexts[account_id]
        if account_id in self.pages:
            del self.pages[account_id]

        return True

    def _force_kill_browser_for_account(self, account_id: int):
        """Force kill Chrome process for a specific account"""
        user_data_path = self.account_manager.get_user_data_path(account_id)

        try:
            result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if ('Google Chrome' in line or 'chrome' in line.lower()) and user_data_path in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            pid = parts[1]
                            subprocess.run(['kill', '-9', pid], check=False)
                            print(f"Force killed Chrome process {pid} for account {account_id}")
        except Exception as e:
            print(f"Error force killing browser for account {account_id}: {e}")

    async def close_and_delete_account(self, account_id: int) -> bool:
        """Close browser and delete account completely"""
        # Close browser first
        await self.close_browser(account_id)

        # Wait for browser to fully close
        await asyncio.sleep(0.5)

        # Delete account data
        return self.account_manager.delete_account(account_id)

    def get_context(self, account_id: int) -> Optional[BrowserContext]:
        """Get the browser context for an account"""
        return self.contexts.get(account_id)

    def get_page(self, account_id: int) -> Optional[Page]:
        """Get the main page for an account"""
        return self.pages.get(account_id)

    async def navigate_to(self, account_id: int, url: str) -> bool:
        """Navigate an account's browser to a URL"""
        page = self.get_page(account_id)
        if not page:
            return False
        try:
            await page.goto(url)
            return True
        except Exception as e:
            print(f"Failed to navigate: {e}")
            return False

    async def open_all_active_accounts(self):
        """Open browsers for all active accounts"""
        active_accounts = self.account_manager.get_active_accounts()
        for idx, account in enumerate(active_accounts):
            if not self.is_browser_open(account.account_id):
                await self.open_browser(account.account_id, position_index=idx)
                await asyncio.sleep(0.5)

    async def close_all_browsers(self):
        """Close all open browsers (tracked contexts + orphaned OS processes)"""
        # First close tracked contexts
        for account_id in list(self.contexts.keys()):
            await self.close_browser(account_id)

        # Then kill any orphaned Chrome processes using our user_data directory
        await asyncio.sleep(0.5)
        self._kill_orphaned_chrome_processes()

    def _kill_orphaned_chrome_processes(self):
        """Kill Chrome processes that use our user_data directory and clean up lock files"""
        user_data_dir = self.account_manager.user_data_dir
        killed_count = 0

        if platform.system() == 'Darwin':  # macOS
            try:
                # Method 1: Use ps to find Chrome processes with our user_data path
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True
                )

                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        if 'Google Chrome' in line and user_data_dir in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                pid = parts[1]
                                try:
                                    subprocess.run(['kill', '-9', pid], check=False)
                                    killed_count += 1
                                    print(f"Killed Chrome process: {pid}")
                                except Exception as e:
                                    print(f"Failed to kill process {pid}: {e}")
            except Exception as e:
                print(f"Error finding Chrome processes: {e}")

            # Method 2: Also kill any chrome helper processes
            try:
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True
                )
                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        if ('Google Chrome Helper' in line or 'chrome' in line.lower()) and user_data_dir in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                pid = parts[1]
                                try:
                                    subprocess.run(['kill', '-9', pid], check=False)
                                    killed_count += 1
                                except Exception:
                                    pass
            except Exception:
                pass

        elif platform.system() == 'Linux':
            try:
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True
                )

                if result.stdout:
                    for line in result.stdout.strip().split('\n'):
                        if 'chrome' in line.lower() and user_data_dir in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                pid = parts[1]
                                try:
                                    subprocess.run(['kill', '-9', pid], check=False)
                                    killed_count += 1
                                except Exception:
                                    pass
            except Exception:
                pass

        # Clean up SingletonLock files that prevent browser from opening
        self._cleanup_singleton_locks()

        print(f"Killed {killed_count} orphaned Chrome processes")
        return killed_count

    def _cleanup_singleton_locks(self):
        """Remove SingletonLock files from all account user_data directories"""
        import os
        user_data_dir = self.account_manager.user_data_dir

        if not os.path.exists(user_data_dir):
            return

        for folder in os.listdir(user_data_dir):
            if folder.startswith('account_'):
                lock_file = os.path.join(user_data_dir, folder, 'SingletonLock')
                socket_file = os.path.join(user_data_dir, folder, 'SingletonSocket')
                cookie_file = os.path.join(user_data_dir, folder, 'SingletonCookie')

                for f in [lock_file, socket_file, cookie_file]:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                            print(f"Removed lock file: {f}")
                        except Exception as e:
                            print(f"Failed to remove {f}: {e}")

    def get_orphaned_process_count(self) -> int:
        """Count Chrome processes using our user_data that aren't tracked"""
        user_data_dir = self.account_manager.user_data_dir
        count = 0

        try:
            result = subprocess.run(
                ['ps', 'aux'],
                capture_output=True,
                text=True
            )
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if ('Google Chrome' in line or 'chrome' in line.lower()) and user_data_dir in line:
                        count += 1
        except Exception:
            pass

        return count

    # Database tracking methods
    async def _track_browser_open(self, account_id: int):
        """Track browser open in database"""
        try:
            db = get_database()
            async with db.session() as session:
                # Create or get account in DB
                account_repo = AccountRepository(session)
                await account_repo.get_or_create(account_id)

                # Start browser session
                browser_repo = BrowserSessionRepository(session)
                browser_session = await browser_repo.start_session(account_id)
                self.session_ids[account_id] = browser_session.id

                # Increment account's total browser opens
                await account_repo.increment_stats(
                    account_id,
                    browser_opens=1
                )

                # Update hourly stats
                hour_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
                stats_repo = StatsRepository(session)
                await stats_repo.record_stats(
                    account_id=account_id,
                    period_type="hour",
                    period_start=hour_start,
                    browser_opens=1
                )

        except Exception as e:
            print(f"Error tracking browser open in database: {e}")

    async def _track_browser_close(self, account_id: int, close_reason: str):
        """Track browser close in database"""
        try:
            db = get_database()
            async with db.session() as session:
                browser_repo = BrowserSessionRepository(session)
                session_id = self.session_ids.get(account_id)

                if session_id:
                    # End the browser session
                    browser_session = await browser_repo.end_session(session_id, close_reason)

                    if browser_session and browser_session.duration_seconds is not None:
                        # Update account's total browser duration
                        account_repo = AccountRepository(session)
                        await account_repo.increment_stats(
                            account_id,
                            browser_duration_seconds=browser_session.duration_seconds
                        )

                        # Update hourly stats
                        hour_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
                        stats_repo = StatsRepository(session)
                        await stats_repo.record_stats(
                            account_id=account_id,
                            period_type="hour",
                            period_start=hour_start,
                            browser_closes=1,
                            browser_duration_seconds=browser_session.duration_seconds
                        )

                    # Clean up session tracking
                    if account_id in self.session_ids:
                        del self.session_ids[account_id]
                else:
                    # No session ID tracked, try to end by account
                    await browser_repo.end_session_by_account(account_id, close_reason)

        except Exception as e:
            print(f"Error tracking browser close in database: {e}")
