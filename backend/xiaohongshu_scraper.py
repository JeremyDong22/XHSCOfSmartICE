# Xiaohongshu scraper module
# Version: 2.0 - Search-only mode, no post detail clicks (anti-bot bypass)
# Updated: Completely redesigned to extract all data from search result cards
# Changes: Removed scrape_post(), added verified CSS selectors, session detection

import asyncio
import json
import os
import random
import re
from urllib.parse import quote
from datetime import datetime
from typing import List, Optional, Tuple
from playwright.async_api import Page, BrowserContext
from data_models import XHSPost, ScrapeFilter, ScrapeTask

# Paths relative to project root (parent of backend/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Verified CSS selectors for XHS search cards (from DevTools research)
SELECTORS = {
    'card': 'section.note-item',
    'permanent_link': 'a[href^="/explore/"]',
    'title': '.footer a.title span',
    'author_name': '.name-time-wrapper .name',
    'author_avatar': 'img.author-avatar',
    'author_link': 'a.author',
    'likes_count': '.like-wrapper .count',
    'cover_image': 'a.cover img',
    'publish_date': '.name-time-wrapper .time',
    # Login detection selectors
    'qr_code': '.qrcode-container, .qrcode-img',
    'login_modal': '.login-container',
    'skeleton': '.skeleton-container'
}


class XHSScraper:
    """Scraper for Xiaohongshu posts - search-only mode (no clicking into posts)"""

    def __init__(self, context: BrowserContext):
        self.context = context
        self.page: Optional[Page] = None

    async def init_page(self) -> Page:
        """Initialize a new page for scraping"""
        self.page = await self.context.new_page()
        return self.page

    async def close(self):
        """Close the scraper page"""
        if self.page:
            await self.page.close()
            self.page = None

    async def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """Add random delay to avoid detection"""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def check_session(self) -> dict:
        """Check if user is logged in by looking for QR code / login modal"""
        if not self.page:
            return {'logged_in': False, 'reason': 'No page initialized'}

        session_info = await self.page.evaluate('''() => {
            const hasQR = document.querySelector('.qrcode-container, .qrcode-img') !== null;
            const hasLoginModal = document.querySelector('.login-container') !== null;
            const hasSkeleton = document.querySelector('.skeleton-container') !== null;
            const hasCards = document.querySelector('section.note-item') !== null;

            return {
                hasQRCode: hasQR,
                hasLoginModal: hasLoginModal,
                hasSkeleton: hasSkeleton,
                hasCards: hasCards,
                loggedIn: !hasQR && !hasLoginModal && hasCards
            };
        }''')

        return {
            'logged_in': session_info['loggedIn'],
            'has_qr': session_info['hasQRCode'],
            'has_login_modal': session_info['hasLoginModal'],
            'has_skeleton': session_info['hasSkeleton'],
            'has_cards': session_info['hasCards']
        }

    async def search_and_extract(
        self,
        keyword: str,
        max_results: int = 30,
        progress_callback=None,
        cancel_check=None
    ) -> List[XHSPost]:
        """
        Search for keyword and extract ALL available data from search cards.
        Does NOT click into individual posts - avoids bot detection.

        Returns list of XHSPost objects with data available from cards only.
        """
        if not self.page:
            await self.init_page()

        if progress_callback:
            await progress_callback(f"Navigating to search for '{keyword}'...")

        search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&source=web_search_result_notes"
        await self.page.goto(search_url)
        await self.page.wait_for_load_state('networkidle')
        await self._random_delay(2, 4)

        # Check session status
        session = await self.check_session()
        if not session['logged_in']:
            if progress_callback:
                reason = "QR code shown" if session['has_qr'] else "Login modal shown" if session['has_login_modal'] else "No cards loaded"
                await progress_callback(f"WARNING: Session may be expired - {reason}")
            # Continue anyway, might get partial results

        if progress_callback:
            await progress_callback(f"Session check: {'OK' if session['logged_in'] else 'WARNING - may need re-login'}")

        posts = []
        scroll_count = 0
        max_scrolls = max_results // 8 + 3  # Estimate scrolls needed
        seen_note_ids = set()

        while len(posts) < max_results and scroll_count < max_scrolls:
            # Check for cancellation
            if cancel_check and cancel_check():
                if progress_callback:
                    await progress_callback("Cancellation requested, stopping...")
                break

            # Extract ALL data from current visible cards using verified selectors
            card_data = await self.page.evaluate('''() => {
                const results = [];
                const cards = document.querySelectorAll('section.note-item');

                cards.forEach(card => {
                    try {
                        // Get note ID from hidden permanent link (most reliable)
                        let noteId = null;
                        const permLink = card.querySelector('a[href^="/explore/"]');
                        if (permLink) {
                            const match = permLink.href.match(/\\/explore\\/([a-f0-9]+)/);
                            if (match) noteId = match[1];
                        }

                        // Fallback: get from search_result link
                        if (!noteId) {
                            const searchLink = card.querySelector('a[href*="/search_result/"]');
                            if (searchLink) {
                                const match = searchLink.href.match(/\\/search_result\\/([a-f0-9]+)/);
                                if (match) noteId = match[1];
                            }
                        }

                        if (!noteId) return;

                        // Title
                        const titleEl = card.querySelector('.footer a.title span');
                        const title = titleEl ? titleEl.textContent.trim() : '';

                        // Author name
                        const authorNameEl = card.querySelector('.name-time-wrapper .name');
                        const authorName = authorNameEl ? authorNameEl.textContent.trim() : '';

                        // Author avatar
                        const avatarEl = card.querySelector('img.author-avatar');
                        const authorAvatar = avatarEl ? avatarEl.src : '';

                        // Author profile URL
                        const authorLinkEl = card.querySelector('a.author');
                        let authorProfileUrl = '';
                        if (authorLinkEl) {
                            authorProfileUrl = authorLinkEl.href;
                        }

                        // Likes count - parse "1.1万" format
                        const likesEl = card.querySelector('.like-wrapper .count');
                        let likes = 0;
                        if (likesEl) {
                            const likesText = likesEl.textContent.trim();
                            if (likesText.includes('万')) {
                                likes = Math.round(parseFloat(likesText.replace('万', '')) * 10000);
                            } else {
                                likes = parseInt(likesText.replace(/[^0-9]/g, '')) || 0;
                            }
                        }

                        // Cover image
                        const coverEl = card.querySelector('a.cover img');
                        const coverImage = coverEl ? coverEl.src : '';

                        // Publish date
                        const dateEl = card.querySelector('.name-time-wrapper .time');
                        const publishDate = dateEl ? dateEl.textContent.trim() : '';

                        // Card dimensions (data attributes)
                        const cardWidth = parseInt(card.getAttribute('data-width')) || 0;
                        const cardHeight = parseInt(card.getAttribute('data-height')) || 0;

                        results.push({
                            noteId,
                            title,
                            authorName,
                            authorAvatar,
                            authorProfileUrl,
                            likes,
                            coverImage,
                            publishDate,
                            cardWidth,
                            cardHeight
                        });
                    } catch (e) {
                        // Skip this card on error
                    }
                });

                return results;
            }''')

            # Add new cards, avoiding duplicates
            new_count = 0
            for item in card_data:
                if item['noteId'] not in seen_note_ids and len(posts) < max_results:
                    seen_note_ids.add(item['noteId'])

                    post = XHSPost(
                        note_id=item['noteId'],
                        permanent_url=f"https://www.xiaohongshu.com/explore/{item['noteId']}",
                        title=item['title'],
                        author=item['authorName'],
                        author_avatar=item['authorAvatar'],
                        author_profile_url=item['authorProfileUrl'],
                        likes=item['likes'],
                        cover_image=item['coverImage'],
                        publish_date=item['publishDate'],
                        card_width=item['cardWidth'],
                        card_height=item['cardHeight']
                    )
                    posts.append(post)
                    new_count += 1

            if progress_callback and new_count > 0:
                await progress_callback(f"Extracted {new_count} new posts (total: {len(posts)}/{max_results})")

            if len(posts) >= max_results:
                break

            # Scroll down to load more
            await self.page.evaluate('window.scrollBy(0, window.innerHeight)')
            await self._random_delay(1.5, 2.5)
            scroll_count += 1

            if progress_callback:
                await progress_callback(f"Scrolling... ({scroll_count}/{max_scrolls})")

        if progress_callback:
            await progress_callback(f"Extraction complete: {len(posts)} posts found")

        return posts

    async def search_and_scrape(
        self,
        keyword: str,
        filters: ScrapeFilter,
        progress_callback=None,
        cancel_check=None
    ) -> List[XHSPost]:
        """
        Search for keyword, extract from cards, and apply filters.
        This is the main entry point - wraps search_and_extract with filtering.
        """
        if progress_callback:
            await progress_callback(f"Starting search for '{keyword}'...")
            await progress_callback(f"Filter: min_likes={filters.min_likes}, max_posts={filters.max_posts}")
            if filters.min_collects > 0 or filters.min_comments > 0:
                await progress_callback("NOTE: min_collects and min_comments filters are IGNORED in search-only mode")

        # Get more results than needed to account for filtering
        fetch_count = filters.max_posts * 2 if filters.min_likes > 0 else filters.max_posts

        all_posts = await self.search_and_extract(
            keyword=keyword,
            max_results=fetch_count,
            progress_callback=progress_callback,
            cancel_check=cancel_check
        )

        if cancel_check and cancel_check():
            return all_posts[:filters.max_posts]

        # Apply filters
        filtered_posts = []
        for post in all_posts:
            if len(filtered_posts) >= filters.max_posts:
                break

            if filters.passes(post):
                filtered_posts.append(post)
                if progress_callback:
                    await progress_callback(f"  + Kept: {post.title[:30]}... (likes={post.likes})")
            else:
                if progress_callback:
                    await progress_callback(f"  - Filtered out: {post.title[:30]}... (likes={post.likes} < {filters.min_likes})")

        if progress_callback:
            await progress_callback(f"After filtering: {len(filtered_posts)} posts kept (from {len(all_posts)} found)")

        return filtered_posts


def save_results(posts: List[XHSPost], keyword: str, account_id: int) -> str:
    """Save scrape results to JSON file"""
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_keyword = re.sub(r'[^\w\u4e00-\u9fff]', '_', keyword)
    filename = f"{safe_keyword}_account{account_id}_{timestamp}.json"
    filepath = os.path.join(OUTPUT_DIR, filename)

    results = {
        "keyword": keyword,
        "account_id": account_id,
        "scraped_at": datetime.now().isoformat(),
        "scrape_mode": "search_only",  # Indicate this is search-only data
        "total_posts": len(posts),
        "posts": [post.to_dict() for post in posts]
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return filepath


async def run_scrape_task(
    context: BrowserContext,
    keyword: str,
    account_id: int,
    filters: ScrapeFilter,
    progress_callback=None,
    cancel_check=None
) -> Tuple[List[XHSPost], str]:
    """
    Run a complete scrape task.
    Returns (posts, output_filepath).
    Supports cancellation via cancel_check callback.
    """
    scraper = XHSScraper(context)

    try:
        await scraper.init_page()
        posts = await scraper.search_and_scrape(keyword, filters, progress_callback, cancel_check)

        # Save results even if cancelled (partial results)
        filepath = save_results(posts, keyword, account_id)

        return posts, filepath

    finally:
        await scraper.close()
