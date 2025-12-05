# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-account browser manager and scraper for Xiaohongshu (小红书/REDNote). Full-stack application with FastAPI backend managing Playwright browser instances and Next.js frontend dashboard.

## Commands

```bash
# Backend - Start API server
cd backend && uv run uvicorn api:app --reload --port 8000

# Frontend - Start dev server
cd frontend && npm run dev

# Install dependencies
uv venv && uv pip install playwright fastapi uvicorn
uv run playwright install chromium
cd frontend && npm install
```

## Architecture

```
├── backend/
│   ├── api.py              # FastAPI REST endpoints (accounts, browsers, scraping)
│   ├── account_manager.py  # CRUD operations for account_config.json
│   ├── browser_manager.py  # Playwright browser lifecycle (open/close/kill)
│   ├── xiaohongshu_scraper.py  # Search and scrape XHS posts
│   └── data_models.py      # Dataclasses: Account, XHSPost, ScrapeFilter
├── frontend/               # Next.js 16 + React 19 + Tailwind
│   └── src/
│       ├── app/            # App router pages
│       ├── components/     # React components
│       └── lib/            # API client utilities
├── account_config.json     # Persistent account registry
├── user_data/account_X/    # Chrome profile directories per account
└── output/                 # Scraped JSON results
```

**Backend Flow:**
1. `AccountManager` reads/writes `account_config.json` and manages `user_data/` directories
2. `BrowserManager` launches persistent Chrome contexts per account using Playwright
3. Browsers auto-positioned in grid layout via `--window-position` args
4. `XHSScraper` searches keywords, scrapes post details, applies filters (min likes/collects)
5. On shutdown: graceful close with 5s timeout, then force-kill orphaned Chrome processes

**API Endpoints:**
- `GET/POST/DELETE /api/accounts` - Account CRUD
- `POST /api/browsers/{id}/open|close` - Browser control
- `POST /api/browsers/login` - Create new account with login browser
- `POST /api/scrape/start` - Run scrape task with filters

**Session Detection:**
- Login expired = QR code page shown (`.qrcode-container`, `.qrcode-img`)
- Logged in = no QR code elements present
