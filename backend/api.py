# FastAPI backend for XHS Multi-Account Scraper
# Version: 1.6 - Real-time browser status updates via SSE
# Changes: Added BrowserEventManager for broadcasting browser state changes to all clients
# Previous: PostgreSQL database integration for tracking and statistics

import os
import json
import uuid
import asyncio
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from account_manager import AccountManager, BASE_DIR
from browser_manager import BrowserManager
from xiaohongshu_scraper import run_scrape_task, OUTPUT_DIR
from data_models import ScrapeFilter
from scrape_manager import ScrapeManager
from browser_event_manager import BrowserEventManager

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


# Global managers
account_manager: AccountManager = None
browser_manager: BrowserManager = None
scrape_manager: ScrapeManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown"""
    global account_manager, browser_manager, scrape_manager

    # Startup
    print("Starting up XHS Scraper API...")

    # Initialize database
    try:
        await init_database()
        print("Database connection initialized")
    except Exception as e:
        print(f"WARNING: Failed to initialize database: {e}")
        print("Continuing without database (tracking disabled)")

    account_manager = AccountManager()
    browser_manager = BrowserManager(account_manager)
    scrape_manager = ScrapeManager()
    await browser_manager.start()

    yield

    # Shutdown
    print("Shutting down XHS Scraper API...")
    await browser_manager.stop()

    # Close database connection
    try:
        await close_database()
        print("Database connection closed")
    except Exception as e:
        print(f"Error closing database: {e}")


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

    success = account_manager.delete_account(account_id)
    if not success:
        raise HTTPException(status_code=404, detail="Account not found")

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

    return {"success": True}


@app.post("/api/browsers/login")
async def open_browser_for_login():
    """Open a new browser for manual login (creates new account)"""
    account_id = await browser_manager.open_browser_for_login()
    if account_id < 0:
        raise HTTPException(status_code=500, detail="Failed to create new account browser")

    return {"success": True, "account_id": account_id}


@app.post("/api/browsers/{account_id}/close")
async def close_browser(account_id: int):
    """Close browser for an account"""
    if not browser_manager.is_browser_open(account_id):
        return {"success": True, "message": "Browser not open"}

    success = await browser_manager.close_browser(account_id)
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

            # Stream logs until task completes
            while True:
                try:
                    # Wait for log message with timeout
                    message = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                    yield f"data: {json.dumps({'type': 'log', 'message': message})}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"

                # Check if task is done
                current_scrape = scrape_manager.get_scrape(task_id)
                if current_scrape and current_scrape.status != "running":
                    yield f"data: {json.dumps({'type': 'status', 'status': current_scrape.status})}\n\n"
                    break

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
