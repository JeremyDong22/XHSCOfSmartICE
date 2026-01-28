# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-account browser manager and scraper for Xiaohongshu (小红书/REDNote). Full-stack application with FastAPI backend managing Playwright browser instances and Next.js frontend dashboard. Includes AI-powered data cleaning with Gemini Flash for image/text labeling.

## Commands

```bash
# Backend - Start API server (use --host 0.0.0.0 for LAN access)
cd backend && uv run uvicorn api:app --reload --host 0.0.0.0 --port 8000

# Frontend - Start dev server
cd frontend && npm run dev

# Install dependencies
uv venv && uv pip install playwright fastapi uvicorn google-generativeai python-dotenv pillow aiohttp
uv run playwright install chromium
cd frontend && npm install
```

## Architecture

```
├── backend/
│   ├── api.py                  # FastAPI REST endpoints (accounts, browsers, scraping, cleaning)
│   ├── account_manager.py      # CRUD operations for account_config.json
│   ├── browser_manager.py      # Playwright browser lifecycle (open/close/kill)
│   ├── browser_event_manager.py # SSE broadcasting for real-time browser state updates
│   ├── xiaohongshu_scraper.py  # Search and scrape XHS posts
│   ├── scrape_manager.py       # Async task tracking with database integration
│   ├── image_downloader.py     # Async image downloader for local caching
│   ├── data_cleaning_service.py # Post filtering + Gemini labeling orchestration
│   ├── gemini_labeler.py       # Gemini Flash API for image/text classification
│   ├── data_models.py          # Dataclasses: Account, XHSPost, ScrapeFilter
│   └── database/               # SQLAlchemy models + repositories (PostgreSQL)
│       ├── models.py           # Account, BrowserSession, ScrapeTask, Post tables
│       └── repositories.py     # Data access layer for stats aggregation
├── frontend/                   # Next.js 16 + React 19 + Tailwind 4
│   └── src/
│       ├── app/                # App router pages (/, /data-laundry)
│       ├── components/         # React components (AccountCard, ScrapeForm, CleanedResultsViewer)
│       └── lib/api.ts          # API client with SSE streaming support
├── account_config.json         # Persistent account registry
├── cleaning_tasks.json         # Persistent cleaning task state
├── user_data/account_X/        # Chrome profile directories per account
├── output/                     # Raw scraped JSON results
├── output_images/              # Locally cached cover images ({note_id}_cover.webp)
└── cleaned_output/             # AI-labeled and filtered results
```

**Backend Flow:**
1. `AccountManager` reads/writes `account_config.json` and manages `user_data/` directories
2. `BrowserManager` launches persistent Chrome contexts per account using Playwright
3. Browsers auto-positioned in grid layout via `--window-position` args
4. `XHSScraper` searches keywords, scrapes post details, applies filters (min likes/collects)
5. `ImageDownloader` caches cover images locally (XHS CDN URLs expire after 1-2 days)
6. `DataCleaningService` filters posts by metrics and uses `GeminiLabeler` to classify by image/text
7. `BrowserEventManager` broadcasts state changes to frontend via SSE
8. On shutdown: graceful close with 5s timeout, then force-kill orphaned Chrome processes

**Key API Endpoints:**
- `GET/POST/DELETE /api/accounts` - Account CRUD
- `POST /api/browsers/{id}/open|close` - Browser control
- `POST /api/browsers/login` - Create new account with login browser
- `POST /api/scrape/start` - Run scrape task with filters
- `DELETE /api/scrape/results/{filename}` - Delete result with cascade (JSON + log + images)
- `GET /api/images/{filename}` - Serve locally cached cover images
- `POST /api/cleaning/start` - Start Gemini-powered data cleaning task
- `GET /api/cleaning/tasks/{id}/logs` - SSE stream for real-time cleaning progress
- `GET /api/cleaning/results` - List cleaned output files

**Gemini Labeling Modes:**
- `cover_image`, `all_images` - Image-only classification
- `title`, `content` - Text-only classification
- `cover_image_title`, `cover_image_content`, `full` - Combined modes

**Session Detection:**
- Login expired = QR code page shown (`.qrcode-container`, `.qrcode-img`)
- Logged in = no QR code elements present

**Environment Variables (backend/.env):**
- `GEMINI_API_KEY` - Required for data cleaning features

**Development Notes:**
- After modifying backend Python files, manually restart the backend server. The `--reload` flag may hang on "Waiting for background tasks to complete" due to active SSE connections. Kill the process (`kill -9 <pid>`) and restart.
- On backend startup, orphaned Chrome processes from previous sessions are automatically cleaned up.
