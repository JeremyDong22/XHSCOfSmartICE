# FastAPI backend for XHS Multi-Account Scraper
# Version: 3.6 - Fixed parallel scraping with proper timeouts
# Changes: Fixed parallel scraping, added graceful shutdown timeout support
# Previous: Added include_likes field to LabelByRequest and LabelByConfigStored

import os
import json
import uuid
import asyncio
import logging
import time
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

# Load environment variables from .env file
load_dotenv()
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from account_manager import AccountManager, BASE_DIR
from browser_manager import BrowserManager
from xiaohongshu_scraper import run_scrape_task, OUTPUT_DIR
from data_models import ScrapeFilter
from scrape_manager import ScrapeManager
from browser_event_manager import BrowserEventManager
from data_cleaning_service import (
    DataCleaningService,
    CleaningConfig,
    FilterByCondition,
    LabelByCondition,
    RateLimitError,
    CLEANED_OUTPUT_DIR
)

# Database imports
from database import init_database, close_database, get_database
from database.repositories import StatsRepository

# Pydantic models for API requests/responses
class AccountResponse(BaseModel):
    account_id: int
    active: bool
    nickname: str
    created_at: str
    last_used: Optional[str]
    has_session: bool = False
    browser_open: bool = False

class AccountCreate(BaseModel):
    nickname: str = ""

class AccountUpdate(BaseModel):
    nickname: Optional[str] = None
    active: Optional[bool] = None

class StatsResponse(BaseModel):
    total: int
    active: int
    inactive: int
    with_session: int
    browsers_open: int

class BrowserStatusResponse(BaseModel):
    account_id: int
    is_open: bool

class ScrapeRequest(BaseModel):
    account_id: int
    keyword: str
    max_posts: int = 20
    min_likes: int = 0
    min_collects: int = 0
    min_comments: int = 0
    skip_videos: bool = False  # Skip video posts, keep only image posts

class ScrapeResponse(BaseModel):
    success: bool
    posts_count: int
    filepath: str

class ScrapeStartResponse(BaseModel):
    success: bool
    task_id: str
    message: str

class ResultFile(BaseModel):
    filename: str
    size: int


# Cleaning API models
class FilterByRequest(BaseModel):
    metric: Literal["likes", "collects", "comments"]
    operator: Literal["gte", "lte", "gt", "lt", "eq"]
    value: int


class LabelByRequest(BaseModel):
    """Request model for labeling: binary classification (是/否) + style labeling (4 fixed categories)"""
    image_target: Optional[Literal["cover_image", "images"]] = None
    text_target: Optional[Literal["title", "content"]] = None
    include_likes: bool = False  # Whether to include likes count in AI analysis
    user_description: str  # User's description of what posts they want to filter (for binary classification)
    full_prompt: str  # Complete prompt that will be sent to Gemini (for transparency)


# Persistent task storage models - defined before CleaningRequest which references them
class FilterByConfigStored(BaseModel):
    """Stored filter config for persistent task data"""
    enabled: bool = False
    metric: str = "likes"
    operator: str = "gte"
    value: int = 0


class LabelByConfigStored(BaseModel):
    """Stored label config for persistent task data"""
    enabled: bool = False
    imageTarget: Optional[str] = None
    textTarget: Optional[str] = None
    includeLikes: bool = False  # Whether to include likes count in AI analysis
    userDescription: str = ""  # User's description of desired posts (for binary classification)
    fullPrompt: str = ""  # Complete prompt sent to Gemini


class CleaningConfigStored(BaseModel):
    """Stored cleaning config for persistent task data"""
    filterBy: FilterByConfigStored
    labelBy: LabelByConfigStored


class CleaningRequest(BaseModel):
    source_files: List[str]  # Filenames in output/ directory
    filter_by: Optional[FilterByRequest] = None
    label_by: Optional[LabelByRequest] = None
    output_filename: Optional[str] = None
    # Frontend task tracking fields for persistent storage
    frontend_task_id: Optional[str] = None  # e.g., "task_1733556789"
    frontend_config: Optional[CleaningConfigStored] = None  # Full frontend config for restore


class CleaningStartResponse(BaseModel):
    success: bool
    task_id: str
    message: str


class CleanedResultFile(BaseModel):
    filename: str
    size: int
    cleaned_at: str
    total_posts: int


class CleaningTaskStatus(BaseModel):
    """Status of a cleaning task for frontend polling"""
    task_id: str
    status: Literal["pending", "processing", "completed", "failed", "rate_limited"]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    output_filename: Optional[str] = None  # Set when completed
    error: Optional[str] = None  # Set when failed


class CleaningTaskFull(BaseModel):
    """Full cleaning task data for persistent storage and frontend restore"""
    id: str  # Frontend task ID (e.g., task_1733556789)
    backend_task_id: str  # Backend task ID (UUID)
    files: List[str]  # Source filenames
    config: CleaningConfigStored
    status: Literal["queued", "processing", "completed", "failed", "rate_limited"]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: int = 0
    error: Optional[str] = None
    created_at: str  # When task was created


# Persistent task storage path
CLEANING_TASKS_FILE = os.path.join(BASE_DIR, "cleaning_tasks.json")


def load_cleaning_tasks() -> Dict[str, CleaningTaskFull]:
    """Load cleaning tasks from persistent storage"""
    start_time = time.time()
    logger.debug(f"Loading cleaning tasks from {CLEANING_TASKS_FILE}")
    if not os.path.exists(CLEANING_TASKS_FILE):
        logger.debug("Cleaning tasks file does not exist, returning empty dict")
        return {}
    try:
        with open(CLEANING_TASKS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Convert dict entries to CleaningTaskFull objects
            result = {k: CleaningTaskFull(**v) for k, v in data.items()}
            elapsed = time.time() - start_time
            logger.debug(f"Loaded {len(result)} cleaning tasks in {elapsed:.3f}s")
            return result
    except Exception as e:
        logger.error(f"Failed to load cleaning tasks: {e}")
        return {}


def save_cleaning_tasks(tasks: Dict[str, CleaningTaskFull]):
    """Save cleaning tasks to persistent storage"""
    start_time = time.time()
    logger.debug(f"Saving {len(tasks)} cleaning tasks to {CLEANING_TASKS_FILE}")
    try:
        with open(CLEANING_TASKS_FILE, 'w', encoding='utf-8') as f:
            # Convert Pydantic models to dicts
            json.dump({k: v.model_dump() for k, v in tasks.items()}, f, indent=2, ensure_ascii=False)
        elapsed = time.time() - start_time
        logger.debug(f"Saved cleaning tasks in {elapsed:.3f}s")
    except Exception as e:
        logger.error(f"Failed to save cleaning tasks: {e}")


# In-memory store (synced with file)
cleaning_task_statuses: Dict[str, CleaningTaskStatus] = {}
cleaning_tasks_full: Dict[str, CleaningTaskFull] = {}
# Track running cleaning tasks for cancellation - maps backend_task_id -> asyncio.Task
cleaning_running_tasks: Dict[str, asyncio.Task] = {}

# Cleaning task log queues - maps task_id -> list of subscriber queues
cleaning_log_queues: Dict[str, List[asyncio.Queue]] = {}
cleaning_log_history: Dict[str, List[str]] = {}  # Stores recent logs for late subscribers


def send_cleaning_log(task_id: str, message: str):
    """Send a log message to all subscribers of a cleaning task (thread-safe)"""
    # Store in history (keep last 100 messages)
    if task_id not in cleaning_log_history:
        cleaning_log_history[task_id] = []
    cleaning_log_history[task_id].append(message)
    if len(cleaning_log_history[task_id]) > 100:
        cleaning_log_history[task_id] = cleaning_log_history[task_id][-100:]

    # Broadcast to all subscribers
    if task_id in cleaning_log_queues:
        for queue in cleaning_log_queues[task_id]:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                pass  # Skip if queue is full


def add_cleaning_log_subscriber(task_id: str) -> asyncio.Queue:
    """Add a subscriber queue for a cleaning task's logs"""
    queue = asyncio.Queue(maxsize=100)
    if task_id not in cleaning_log_queues:
        cleaning_log_queues[task_id] = []
    cleaning_log_queues[task_id].append(queue)
    return queue


def remove_cleaning_log_subscriber(task_id: str, queue: asyncio.Queue):
    """Remove a subscriber queue for a cleaning task's logs"""
    if task_id in cleaning_log_queues:
        try:
            cleaning_log_queues[task_id].remove(queue)
            if not cleaning_log_queues[task_id]:
                del cleaning_log_queues[task_id]
        except ValueError:
            pass


def get_cleaning_log_history(task_id: str) -> List[str]:
    """Get the log history for a cleaning task"""
    return cleaning_log_history.get(task_id, [])


# Global managers
account_manager: AccountManager = None
browser_manager: BrowserManager = None
scrape_manager: ScrapeManager = None
browser_event_manager: BrowserEventManager = None
cleaning_service: DataCleaningService = None

# Shutdown coordination - used to signal SSE connections and background tasks to stop
shutdown_event: asyncio.Event = None
background_tasks: set = set()  # Track background tasks for cleanup


def track_background_task(task: asyncio.Task):
    """Register a background task for cleanup on shutdown"""
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown"""
    global account_manager, browser_manager, scrape_manager, browser_event_manager, cleaning_service, shutdown_event, cleaning_tasks_full

    # Startup
    print("Starting up XHS Scraper API...")

    # Initialize shutdown event
    shutdown_event = asyncio.Event()

    # Initialize database
    try:
        await init_database()
        print("Database connection initialized")
    except Exception as e:
        print(f"WARNING: Failed to initialize database: {e}")
        print("Continuing without database (tracking disabled)")

    # Load persistent cleaning tasks
    cleaning_tasks_full = load_cleaning_tasks()
    print(f"Loaded {len(cleaning_tasks_full)} cleaning tasks from storage")

    # Mark any "processing" tasks as failed (server was restarted during processing)
    for task_id, task in cleaning_tasks_full.items():
        if task.status == "processing":
            task.status = "failed"
            task.error = "Server restarted during processing"
            task.completed_at = datetime.now().isoformat()
    save_cleaning_tasks(cleaning_tasks_full)

    account_manager = AccountManager()
    browser_manager = BrowserManager(account_manager)
    scrape_manager = ScrapeManager()
    browser_event_manager = BrowserEventManager()
    cleaning_service = DataCleaningService()
    await browser_manager.start()

    yield

    # Shutdown - optimized for fast hot-reload
    print("Shutting down XHS Scraper API...")

    # Signal all SSE connections and background tasks to stop immediately
    shutdown_event.set()

    # Give SSE connections a moment to detect shutdown and close gracefully
    await asyncio.sleep(0.1)

    # Cancel all tracked background tasks with short timeout
    if background_tasks:
        print(f"Cancelling {len(background_tasks)} background tasks...")
        for task in background_tasks:
            if not task.done():
                task.cancel()
        # Wait briefly for tasks to cancel (max 0.5s)
        try:
            await asyncio.wait_for(
                asyncio.gather(*background_tasks, return_exceptions=True),
                timeout=0.5
            )
        except asyncio.TimeoutError:
            print("Background tasks cancellation timed out, forcing shutdown...")
        background_tasks.clear()

    # Cancel any active scrapes quickly
    if scrape_manager:
        active_scrapes = scrape_manager.get_all_active()
        for task_id in active_scrapes:
            scrape_manager.cancel_scrape(task_id)

    # Fast browser shutdown with reduced timeout for hot-reload
    await browser_manager.stop()

    # Close database connection
    try:
        await close_database()
        print("Database connection closed")
    except Exception as e:
        print(f"Error closing database: {e}")

    print("Shutdown complete")


app = FastAPI(
    title="XHS Multi-Account Scraper API",
    description="REST API for managing XHS accounts, browsers, and scraping tasks",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for LAN access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware for debugging slow requests
@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    """Log slow requests (> 1s) to help debug hangs"""
    start_time = time.time()
    path = request.url.path
    method = request.method

    # Skip noisy endpoints for timing logs
    skip_timing_log = path in ["/api/browsers/events", "/api/accounts/stats"]

    try:
        response = await call_next(request)
        elapsed = time.time() - start_time

        # Log slow requests (> 1 second)
        if elapsed > 1.0 and not skip_timing_log:
            logger.warning(f"SLOW REQUEST: {method} {path} took {elapsed:.2f}s")

        return response
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"REQUEST FAILED: {method} {path} after {elapsed:.2f}s - {e}")
        raise


# Account endpoints
@app.get("/api/accounts", response_model=List[AccountResponse])
async def get_accounts(active_only: bool = False):
    """Get all accounts or only active accounts"""
    if active_only:
        accounts = account_manager.get_active_accounts()
    else:
        accounts = account_manager.get_all_accounts()

    return [
        AccountResponse(
            account_id=acc.account_id,
            active=acc.active,
            nickname=acc.nickname,
            created_at=acc.created_at,
            last_used=acc.last_used,
            has_session=account_manager.account_has_session(acc.account_id),
            browser_open=browser_manager.is_browser_open(acc.account_id)
        )
        for acc in accounts
    ]


@app.get("/api/accounts/stats", response_model=StatsResponse)
async def get_account_stats():
    """Get account statistics"""
    stats = account_manager.get_stats()
    stats["browsers_open"] = len(browser_manager.get_open_browsers())
    return StatsResponse(**stats)


@app.get("/api/accounts/{account_id}", response_model=AccountResponse)
async def get_account(account_id: int):
    """Get a specific account by ID"""
    account = account_manager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    return AccountResponse(
        account_id=account.account_id,
        active=account.active,
        nickname=account.nickname,
        created_at=account.created_at,
        last_used=account.last_used,
        has_session=account_manager.account_has_session(account.account_id),
        browser_open=browser_manager.is_browser_open(account.account_id)
    )


@app.post("/api/accounts", response_model=AccountResponse)
async def create_account(data: AccountCreate):
    """Create a new account"""
    account = account_manager.create_account(nickname=data.nickname)
    return AccountResponse(
        account_id=account.account_id,
        active=account.active,
        nickname=account.nickname,
        created_at=account.created_at,
        last_used=account.last_used,
        has_session=False,
        browser_open=False
    )


@app.patch("/api/accounts/{account_id}")
async def update_account(account_id: int, data: AccountUpdate):
    """Update account properties"""
    updates = {}
    if data.nickname is not None:
        updates["nickname"] = data.nickname
    if data.active is not None:
        updates["active"] = data.active

    success = account_manager.update_account(account_id, **updates)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")

    return {"success": True}


@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: int):
    """Delete an account and its browser data"""
    # Close browser first if open
    if browser_manager.is_browser_open(account_id):
        await browser_manager.close_browser(account_id)
        await browser_event_manager.notify_browser_closed(account_id)

    success = account_manager.delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")

    # Broadcast account deleted event
    await browser_event_manager.notify_account_deleted(account_id)

    return {"success": True}


@app.post("/api/accounts/{account_id}/activate")
async def activate_account(account_id: int):
    """Activate an account"""
    success = account_manager.activate_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True}


@app.post("/api/accounts/{account_id}/deactivate")
async def deactivate_account(account_id: int):
    """Deactivate an account"""
    success = account_manager.deactivate_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"success": True}


# Sync endpoints
@app.get("/api/accounts/sync/status")
async def get_sync_status():
    """Get sync status between config and user_data folders"""
    return account_manager.sync_status()


@app.post("/api/accounts/sync/cleanup")
async def cleanup_orphaned():
    """Remove orphaned user_data folders (no config entry)"""
    removed = account_manager.cleanup_orphaned_folders()
    return {"success": True, "removed": removed}


@app.post("/api/accounts/sync/import")
async def import_orphaned():
    """Import orphaned user_data folders as new accounts"""
    imported = account_manager.import_orphaned_folders()
    return {"success": True, "imported": imported}


# Browser endpoints
@app.get("/api/browsers")
async def get_open_browsers():
    """Get list of account IDs with open browsers"""
    return {"browsers": browser_manager.get_open_browsers()}


@app.get("/api/browsers/{account_id}/status", response_model=BrowserStatusResponse)
async def get_browser_status(account_id: int):
    """Check if browser is open for an account"""
    return BrowserStatusResponse(
        account_id=account_id,
        is_open=browser_manager.is_browser_open(account_id)
    )


@app.post("/api/browsers/{account_id}/open")
async def open_browser(account_id: int):
    """Open browser for an existing account"""
    account = account_manager.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    if browser_manager.is_browser_open(account_id):
        return {"success": True, "message": "Browser already open"}

    success = await browser_manager.open_browser(account_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to open browser")

    # Broadcast browser opened event to all SSE clients
    await browser_event_manager.notify_browser_opened(account_id)

    return {"success": True}


@app.post("/api/browsers/login")
async def open_browser_for_login():
    """Open a new browser for manual login (creates new account)"""
    account_id = await browser_manager.open_browser_for_login()
    if account_id < 0:
        raise HTTPException(status_code=500, detail="Failed to create new account browser")

    # Broadcast new login browser created event to all SSE clients
    await browser_event_manager.notify_login_browser_created(account_id)

    return {"success": True, "account_id": account_id}


@app.post("/api/browsers/{account_id}/close")
async def close_browser(account_id: int):
    """Close browser for an account"""
    if not browser_manager.is_browser_open(account_id):
        return {"success": True, "message": "Browser not open"}

    success = await browser_manager.close_browser(account_id)

    # Broadcast browser closed event to all SSE clients
    if success:
        await browser_event_manager.notify_browser_closed(account_id)

    return {"success": success}


@app.post("/api/browsers/close-all")
async def close_all_browsers():
    """Close all open browsers"""
    await browser_manager.close_all_browsers()
    return {"success": True}


@app.post("/api/browsers/open-all")
async def open_all_browsers():
    """Open browsers for all active accounts"""
    await browser_manager.open_all_active_accounts()
    return {"success": True, "browsers": browser_manager.get_open_browsers()}


@app.get("/api/browsers/events")
async def browser_events():
    """
    SSE endpoint for real-time browser status updates.
    Clients subscribe to this endpoint to receive browser state changes instantly.
    Events: browser_opened, browser_closed, browser_login_created, account_deleted
    """
    async def event_generator():
        # Register this client
        client_queue = await browser_event_manager.add_client()

        try:
            # Send initial connection confirmation
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Subscribed to browser events'})}\n\n"

            while not (shutdown_event and shutdown_event.is_set()):
                try:
                    # Shorter timeout for faster shutdown detection during hot-reload
                    event = await asyncio.wait_for(client_queue.get(), timeout=2.0)
                    # Check shutdown immediately after getting event
                    if shutdown_event and shutdown_event.is_set():
                        break
                    yield f"data: {json.dumps({'type': event.event_type, 'account_id': event.account_id, 'timestamp': event.timestamp})}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive to prevent connection timeout
                    yield f": keepalive\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            # Unregister client on disconnect
            await browser_event_manager.remove_client(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# Scraping endpoints
@app.post("/api/scrape/start", response_model=ScrapeStartResponse)
async def start_scrape(request: ScrapeRequest):
    """Start a scraping task (returns task_id for SSE streaming)"""
    # Validate account and browser
    if not browser_manager.is_browser_open(request.account_id):
        raise HTTPException(status_code=400, detail="Browser not open for this account")

    context = browser_manager.get_context(request.account_id)
    if not context:
        raise HTTPException(status_code=500, detail="Failed to get browser context")

    # Create task ID
    task_id = str(uuid.uuid4())

    # Create active scrape
    scrape_manager.create_scrape(task_id, request.account_id, request.keyword)

    # Create filters
    filters = ScrapeFilter(
        min_likes=request.min_likes,
        min_collects=request.min_collects,
        min_comments=request.min_comments,
        max_posts=request.max_posts,
        skip_videos=request.skip_videos
    )

    # Define progress callback
    async def progress_callback(message: str):
        await scrape_manager.send_log(task_id, message)

    # Start scrape task in background
    async def run_task():
        try:
            await scrape_manager.send_log(task_id, f"Starting scrape for '{request.keyword}'...")

            # Wait a moment for database task to be created
            await asyncio.sleep(0.1)

            # Get database task ID if available
            scrape = scrape_manager.get_scrape(task_id)
            db_task_id = scrape.db_task_id if scrape else None

            posts, json_filepath, log_filepath = await run_scrape_task(
                context=context,
                keyword=request.keyword,
                account_id=request.account_id,
                filters=filters,
                progress_callback=progress_callback,
                cancel_check=lambda: scrape_manager.is_cancelled(task_id),
                scrape_task_id=db_task_id
            )

            if scrape_manager.is_cancelled(task_id):
                await scrape_manager.send_log(task_id, f"Scrape cancelled. Saved {len(posts)} posts.")
                scrape_manager.complete_scrape(task_id, "cancelled")
            else:
                await scrape_manager.send_log(task_id, f"Scrape complete! Found {len(posts)} posts.")
                await scrape_manager.send_log(task_id, f"Results saved to: {json_filepath}")
                await scrape_manager.send_log(task_id, f"Log saved to: {log_filepath}")
                scrape_manager.complete_scrape(task_id, "completed")
        except asyncio.CancelledError:
            await scrape_manager.send_log(task_id, "Scrape cancelled by user")
            scrape_manager.complete_scrape(task_id, "cancelled")
        except Exception as e:
            await scrape_manager.send_log(task_id, f"Error: {str(e)}")
            scrape_manager.complete_scrape(task_id, "failed")

    task = asyncio.create_task(run_task())
    scrape_manager.set_task(task_id, task)
    track_background_task(task)  # Track for cleanup on shutdown

    return ScrapeStartResponse(
        success=True,
        task_id=task_id,
        message="Scraping started. Connect to /api/scrape/logs/{task_id} for real-time updates."
    )


@app.get("/api/scrape/logs/{task_id}")
async def scrape_logs(task_id: str):
    """Stream scraping logs via SSE"""
    scrape = scrape_manager.get_scrape(task_id)
    if not scrape:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        # Create a queue for this SSE connection
        log_queue = asyncio.Queue()

        # Callback to add logs to queue
        async def queue_callback(message: str):
            await log_queue.put(message)

        # Register callback
        scrape_manager.add_log_callback(task_id, queue_callback)

        try:
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'status': scrape.status})}\n\n"

            # Stream logs until task completes or shutdown
            while not (shutdown_event and shutdown_event.is_set()):
                try:
                    # Shorter timeout for faster shutdown detection
                    message = await asyncio.wait_for(log_queue.get(), timeout=0.5)
                    # Check shutdown immediately after getting message
                    if shutdown_event and shutdown_event.is_set():
                        break
                    yield f"data: {json.dumps({'type': 'log', 'message': message})}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"

                # Check if task is done
                current_scrape = scrape_manager.get_scrape(task_id)
                if current_scrape and current_scrape.status != "running":
                    yield f"data: {json.dumps({'type': 'status', 'status': current_scrape.status})}\n\n"
                    break

        except asyncio.CancelledError:
            pass
        finally:
            # Cleanup
            scrape_manager.remove_log_callback(task_id, queue_callback)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/scrape/cancel/{task_id}")
async def cancel_scrape(task_id: str):
    """Cancel an ongoing scrape task"""
    success = scrape_manager.cancel_scrape(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or already completed")

    return {"success": True, "message": "Cancellation requested"}


@app.get("/api/scrape/status/{task_id}")
async def get_scrape_status(task_id: str):
    """Get status of a scrape task"""
    scrape = scrape_manager.get_scrape(task_id)
    if not scrape:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": task_id,
        "status": scrape.status,
        "keyword": scrape.keyword,
        "account_id": scrape.account_id,
        "started_at": scrape.started_at
    }


@app.get("/api/scrape/results", response_model=List[ResultFile])
async def get_scrape_results():
    """List all scrape result files"""
    if not os.path.exists(OUTPUT_DIR):
        return []

    files = []
    for f in os.listdir(OUTPUT_DIR):
        if f.endswith('.json'):
            filepath = os.path.join(OUTPUT_DIR, f)
            files.append(ResultFile(
                filename=f,
                size=os.path.getsize(filepath)
            ))

    return sorted(files, key=lambda x: x.filename, reverse=True)


@app.get("/api/scrape/results/{filename}")
async def get_scrape_result(filename: str):
    """Get contents of a specific result file"""
    filepath = os.path.join(OUTPUT_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.delete("/api/scrape/results/{filename}")
async def delete_scrape_result(filename: str):
    """Delete a scrape result file"""
    filepath = os.path.join(OUTPUT_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    # Security check - only allow deleting .json files in OUTPUT_DIR
    if not filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Can only delete .json files")

    try:
        os.remove(filepath)
        return {"success": True, "message": f"Deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


# Data Cleaning endpoints
@app.post("/api/cleaning/start")
async def start_cleaning(request: CleaningRequest):
    """
    Start a data cleaning and labeling task.

    This endpoint processes scraped JSON files by:
    1. Loading posts from specified source files
    2. Optionally filtering by metrics (likes, collects, comments)
    3. Optionally labeling using Gemini with image/text combinations
    4. Saving cleaned results with metadata
    """
    # Convert filenames to full paths
    source_paths = []
    for filename in request.source_files:
        filepath = os.path.join(OUTPUT_DIR, filename)
        if not os.path.exists(filepath):
            raise HTTPException(status_code=404, detail=f"Source file not found: {filename}")
        source_paths.append(filepath)

    # Build config
    config = CleaningConfig(
        source_files=source_paths,
        output_filename=request.output_filename
    )

    # Add filter if provided
    if request.filter_by:
        config.filter_by = FilterByCondition(
            metric=request.filter_by.metric,
            operator=request.filter_by.operator,
            value=request.filter_by.value
        )

    # Add label if provided
    if request.label_by:
        config.label_by = LabelByCondition(
            image_target=request.label_by.image_target,
            text_target=request.label_by.text_target,
            include_likes=request.label_by.include_likes,
            user_description=request.label_by.user_description,
            full_prompt=request.label_by.full_prompt
        )

    # Run cleaning in background task
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    # Get frontend task ID or generate one
    frontend_task_id = request.frontend_task_id or f"task_{int(datetime.now().timestamp() * 1000)}"

    # Initialize task status as processing
    cleaning_task_statuses[task_id] = CleaningTaskStatus(
        task_id=task_id,
        status="processing",
        started_at=now
    )

    # Save full task data for persistent storage (if frontend config provided)
    if request.frontend_config:
        cleaning_tasks_full[frontend_task_id] = CleaningTaskFull(
            id=frontend_task_id,
            backend_task_id=task_id,
            files=request.source_files,
            config=request.frontend_config,
            status="processing",
            started_at=now,
            progress=10,
            created_at=now
        )
        save_cleaning_tasks(cleaning_tasks_full)

    async def run_cleaning_task():
        try:
            logger.info(f"Starting cleaning task {task_id}")
            send_cleaning_log(task_id, "Starting cleaning task...")

            # Progress callback that sends logs to SSE subscribers
            def progress_callback(message: str):
                send_cleaning_log(task_id, message)

            # Run synchronous blocking operations in thread pool to avoid blocking event loop
            # This allows other API requests and SSE connections to continue working
            result = await asyncio.to_thread(
                cleaning_service.clean_and_label,
                config,
                progress_callback
            )
            send_cleaning_log(task_id, "Saving results...")
            output_path = await asyncio.to_thread(cleaning_service.save_cleaned_result, result, config.output_filename)
            output_filename = os.path.basename(output_path)
            completed_at = datetime.now().isoformat()
            logger.info(f"Cleaning task {task_id} completed: {output_path}")
            send_cleaning_log(task_id, f"✓ Task completed! Output: {output_filename}")

            # Update status to completed
            cleaning_task_statuses[task_id] = CleaningTaskStatus(
                task_id=task_id,
                status="completed",
                started_at=cleaning_task_statuses[task_id].started_at,
                completed_at=completed_at,
                output_filename=output_filename
            )

            # Update full task data
            if frontend_task_id in cleaning_tasks_full:
                cleaning_tasks_full[frontend_task_id].status = "completed"
                cleaning_tasks_full[frontend_task_id].completed_at = completed_at
                cleaning_tasks_full[frontend_task_id].progress = 100
                save_cleaning_tasks(cleaning_tasks_full)

        except asyncio.CancelledError:
            completed_at = datetime.now().isoformat()
            logger.info(f"Cleaning task {task_id} cancelled")
            send_cleaning_log(task_id, "✗ Task was cancelled")
            cleaning_task_statuses[task_id] = CleaningTaskStatus(
                task_id=task_id,
                status="failed",
                started_at=cleaning_task_statuses[task_id].started_at,
                completed_at=completed_at,
                error="Task was cancelled"
            )
            # Update full task data
            if frontend_task_id in cleaning_tasks_full:
                cleaning_tasks_full[frontend_task_id].status = "failed"
                cleaning_tasks_full[frontend_task_id].completed_at = completed_at
                cleaning_tasks_full[frontend_task_id].error = "Task was cancelled"
                save_cleaning_tasks(cleaning_tasks_full)

        except RateLimitError as e:
            # Handle Gemini API rate limit (429) - pause task instead of fail
            completed_at = datetime.now().isoformat()
            logger.warning(f"Cleaning task {task_id} hit rate limit: {e}")
            rate_limit_msg = f"⚠️ API Rate Limit (429): {e}. Processed {e.processed_count} posts before pausing."
            send_cleaning_log(task_id, rate_limit_msg)

            # Mark as rate_limited (special status for frontend to handle)
            cleaning_task_statuses[task_id] = CleaningTaskStatus(
                task_id=task_id,
                status="rate_limited",
                started_at=cleaning_task_statuses[task_id].started_at,
                completed_at=completed_at,
                error=rate_limit_msg
            )
            # Update full task data with rate_limited status
            if frontend_task_id in cleaning_tasks_full:
                cleaning_tasks_full[frontend_task_id].status = "rate_limited"
                cleaning_tasks_full[frontend_task_id].completed_at = completed_at
                cleaning_tasks_full[frontend_task_id].error = rate_limit_msg
                save_cleaning_tasks(cleaning_tasks_full)

        except Exception as e:
            completed_at = datetime.now().isoformat()
            logger.error(f"Cleaning task {task_id} failed: {e}")
            send_cleaning_log(task_id, f"✗ Task failed: {str(e)}")
            cleaning_task_statuses[task_id] = CleaningTaskStatus(
                task_id=task_id,
                status="failed",
                started_at=cleaning_task_statuses[task_id].started_at,
                completed_at=completed_at,
                error=str(e)
            )
            # Update full task data
            if frontend_task_id in cleaning_tasks_full:
                cleaning_tasks_full[frontend_task_id].status = "failed"
                cleaning_tasks_full[frontend_task_id].completed_at = completed_at
                cleaning_tasks_full[frontend_task_id].error = str(e)
                save_cleaning_tasks(cleaning_tasks_full)

    # Start task in background and track for cleanup
    cleaning_task = asyncio.create_task(run_cleaning_task())
    track_background_task(cleaning_task)
    # Track for cancellation
    cleaning_running_tasks[task_id] = cleaning_task

    # Remove from running tasks when done
    def on_task_done(t):
        cleaning_running_tasks.pop(task_id, None)
    cleaning_task.add_done_callback(on_task_done)

    return {
        "success": True,
        "task_id": task_id,
        "frontend_task_id": frontend_task_id,
        "message": "Cleaning task started. Results will be saved to cleaned_output/"
    }


@app.get("/api/cleaning/tasks/{task_id}/status", response_model=CleaningTaskStatus)
async def get_cleaning_task_status(task_id: str):
    """
    Get the status of a cleaning task.
    Frontend should poll this endpoint to track task progress.
    """
    if task_id not in cleaning_task_statuses:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    return cleaning_task_statuses[task_id]


@app.post("/api/cleaning/tasks/{task_id}/cancel")
async def cancel_cleaning_task(task_id: str):
    """
    Cancel a running cleaning task.
    This will cancel the asyncio task and mark it as failed.
    """
    # Check if task exists
    if task_id not in cleaning_task_statuses:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Check if task is running
    status = cleaning_task_statuses[task_id]
    if status.status != "processing":
        raise HTTPException(status_code=400, detail=f"Task is not running (status: {status.status})")

    # Cancel the running task
    if task_id in cleaning_running_tasks:
        running_task = cleaning_running_tasks[task_id]
        if not running_task.done():
            running_task.cancel()
            logger.info(f"Cancelled cleaning task {task_id}")
            send_cleaning_log(task_id, "✗ Task cancelled by user")

            # Update status immediately (the task's CancelledError handler will also update)
            completed_at = datetime.now().isoformat()
            cleaning_task_statuses[task_id] = CleaningTaskStatus(
                task_id=task_id,
                status="failed",
                started_at=status.started_at,
                completed_at=completed_at,
                error="Cancelled by user"
            )

            # Update full task data - find by backend_task_id
            for frontend_id, task_full in cleaning_tasks_full.items():
                if task_full.backend_task_id == task_id:
                    task_full.status = "failed"
                    task_full.completed_at = completed_at
                    task_full.error = "Cancelled by user"
                    save_cleaning_tasks(cleaning_tasks_full)
                    break

            return {"success": True, "message": "Task cancelled"}
        else:
            return {"success": False, "message": "Task already completed"}
    else:
        raise HTTPException(status_code=400, detail="Task not found in running tasks")


@app.get("/api/cleaning/logs/{task_id}")
async def cleaning_logs(task_id: str):
    """
    Stream cleaning task logs via SSE.
    Frontend subscribes to this endpoint to receive real-time progress updates.
    """
    async def event_generator():
        # Subscribe to log queue
        log_queue = add_cleaning_log_subscriber(task_id)

        try:
            # Send connection confirmation
            yield f"data: {json.dumps({'type': 'connected', 'task_id': task_id})}\n\n"

            # Send log history (for late subscribers)
            history = get_cleaning_log_history(task_id)
            for msg in history:
                # Check shutdown before sending each history message
                if shutdown_event and shutdown_event.is_set():
                    break
                yield f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"

            # Stream new logs until task completes or shutdown
            while not (shutdown_event and shutdown_event.is_set()):
                try:
                    # Shorter timeout for faster shutdown detection
                    message = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                    # Check shutdown immediately after getting message
                    if shutdown_event and shutdown_event.is_set():
                        break
                    yield f"data: {json.dumps({'type': 'log', 'message': message})}\n\n"

                    # Check if task completed
                    if message.startswith("✓") or message.startswith("✗"):
                        # Task is done, send status and close
                        status = cleaning_task_statuses.get(task_id)
                        if status:
                            yield f"data: {json.dumps({'type': 'status', 'status': status.status})}\n\n"
                        break

                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"

                    # Check if task is done (completed, failed, or rate_limited)
                    status = cleaning_task_statuses.get(task_id)
                    if status and status.status in ["completed", "failed", "rate_limited"]:
                        yield f"data: {json.dumps({'type': 'status', 'status': status.status})}\n\n"
                        break

        except asyncio.CancelledError:
            pass
        finally:
            # Unsubscribe from log queue
            remove_cleaning_log_subscriber(task_id, log_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/cleaning/tasks", response_model=List[CleaningTaskFull])
async def get_all_cleaning_tasks():
    """
    Get all cleaning tasks (for frontend restore on page refresh).
    Returns tasks sorted by created_at descending (newest first).
    """
    tasks = list(cleaning_tasks_full.values())
    # Sort by created_at descending
    tasks.sort(key=lambda t: t.created_at, reverse=True)
    return tasks


@app.delete("/api/cleaning/tasks/{task_id}")
async def delete_cleaning_task(task_id: str):
    """
    Delete a cleaning task from persistent storage.
    Only allows deleting completed or failed tasks.
    """
    if task_id not in cleaning_tasks_full:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    task = cleaning_tasks_full[task_id]
    if task.status == "processing":
        raise HTTPException(status_code=400, detail="Cannot delete a processing task")

    del cleaning_tasks_full[task_id]
    save_cleaning_tasks(cleaning_tasks_full)

    return {"success": True, "message": f"Task {task_id} deleted"}


@app.get("/api/cleaning/results", response_model=List[CleanedResultFile])
async def get_cleaned_results():
    """List all cleaned result files with metadata"""
    if not os.path.exists(CLEANED_OUTPUT_DIR):
        return []

    files = []
    for filename in os.listdir(CLEANED_OUTPUT_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(CLEANED_OUTPUT_DIR, filename)

            # Read metadata from file
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    metadata = data.get("metadata", {})

                    files.append(CleanedResultFile(
                        filename=filename,
                        size=os.path.getsize(filepath),
                        cleaned_at=metadata.get("cleaned_at", ""),
                        total_posts=metadata.get("total_posts_output", 0)
                    ))
            except Exception as e:
                logger.error(f"Failed to read metadata from {filename}: {e}")
                # Still include file even if metadata reading fails
                files.append(CleanedResultFile(
                    filename=filename,
                    size=os.path.getsize(filepath),
                    cleaned_at="",
                    total_posts=0
                ))

    return sorted(files, key=lambda x: x.filename, reverse=True)


@app.get("/api/cleaning/results/{filename}")
async def get_cleaned_result(filename: str):
    """Get contents of a specific cleaned result file"""
    filepath = os.path.join(CLEANED_OUTPUT_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Malformed JSON file: {str(e)}")


@app.delete("/api/cleaning/results/{filename}")
async def delete_cleaned_result(filename: str):
    """Delete a cleaned result file"""
    filepath = os.path.join(CLEANED_OUTPUT_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    # Security check - only allow deleting .json files in CLEANED_OUTPUT_DIR
    if not filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Can only delete .json files")

    try:
        os.remove(filepath)
        return {"success": True, "message": f"Deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")


# Database statistics endpoints
@app.get("/api/accounts/{account_id}/stats")
async def get_account_stats(account_id: int) -> Dict[str, Any]:
    """Get detailed statistics for a specific account"""
    try:
        db = get_database()
        async with db.session() as session:
            stats_repo = StatsRepository(session)
            summary = await stats_repo.get_account_summary(account_id)
            return summary
    except Exception as e:
        print(f"Error fetching account stats: {e}")
        # Return empty stats if database unavailable
        return {
            "account_id": account_id,
            "lifetime": {
                "total_scrapes": 0,
                "total_posts_scraped": 0,
                "total_browser_opens": 0,
                "total_browser_duration_seconds": 0,
            },
            "today": {
                "scrape_count": 0,
                "posts_scraped": 0,
                "browser_opens": 0,
                "browser_duration_seconds": 0,
            },
            "this_hour": {
                "scrape_count": 0,
                "posts_scraped": 0,
                "browser_opens": 0,
                "browser_duration_seconds": 0,
            },
        }


@app.get("/api/stats/all")
async def get_all_stats() -> List[Dict[str, Any]]:
    """Get statistics for all accounts"""
    try:
        db = get_database()
        async with db.session() as session:
            stats_repo = StatsRepository(session)
            summaries = await stats_repo.get_all_accounts_summary()
            return summaries
    except Exception as e:
        print(f"Error fetching all account stats: {e}")
        # Return empty list if database unavailable
        return []


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
