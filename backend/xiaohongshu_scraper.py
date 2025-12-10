# Xiaohongshu scraper module
# Version: 2.6 - Added image downloading after scraping
# Changes: Integrated image_downloader to cache cover images locally after scraping
# Previous: Fixed parallel scraping support with proper timeouts

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

# Database imports
from database import get_database
from database.repositories import PostRepository, AccountRepository, StatsRepository

# Image downloader
from image_downloader import download_post_images, get_local_image_filename

# Paths relative to project root (parent of backend/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

# Verified CSS selectors for XHS search cards (from DevTools research)
SELECTORS = {
    'card': 'section.note-item',
    'permanent_link': 'a[href^="/explore/"]',
    'tokenized_link': 'a.cover',  # Has full href with xsec_token parameter
    'title': '.footer a.title span',
    'author_name': '.name-time-wrapper .name',
    'author_avatar': 'img.author-avatar',
    'author_link': 'a.author',
    'likes_count': '.like-wrapper .count',
    'cover_image': 'a.cover img',
    'publish_date': '.name-time-wrapper .time',
    # Video detection - play icon overlay on card
    'video_icon': 'svg.play-icon, .play-icon, span.play-icon, [class*="video-icon"]',
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
        # Use 'load' instead of 'networkidle' to avoid hanging on continuous XHS network requests
        # Add timeout to prevent blocking other parallel scrape tasks
        await self.page.goto(search_url, timeout=30000)
        await self.page.wait_for_load_state('load', timeout=15000)
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
                        // Get tokenized URL from a.cover (has xsec_token parameter)
                        // On search pages: /search_result/xxx?xsec_token=...
                        // On feed pages: /explore/xxx?xsec_token=...
                        const coverLink = card.querySelector('a.cover');
                        const tokenizedPath = coverLink ? coverLink.getAttribute('href') : '';

                        // Extract note ID from the tokenized path (handles both /search_result/ and /explore/)
                        let noteId = null;
                        if (tokenizedPath) {
                            const match = tokenizedPath.match(/\\/(search_result|explore)\\/([a-f0-9]+)/);
                            if (match) noteId = match[2];
                        }

                        // Fallback: get from hidden permanent link
                        if (!noteId) {
                            const permLink = card.querySelector('a[href^="/explore/"]');
                            if (permLink) {
                                const match = permLink.href.match(/\\/explore\\/([a-f0-9]+)/);
                                if (match) noteId = match[1];
                            }
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

                        // Build full tokenized URL
                        const tokenizedUrl = tokenizedPath
                            ? 'https://www.xiaohongshu.com' + tokenizedPath
                            : '';

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

                        // Video detection - check for play icon overlay
                        const hasVideoIcon = card.querySelector('svg.play-icon, .play-icon, span.play-icon, [class*="video-icon"]') !== null;

                        results.push({
                            noteId,
                            tokenizedUrl,
                            title,
                            authorName,
                            authorAvatar,
                            authorProfileUrl,
                            likes,
                            coverImage,
                            publishDate,
                            cardWidth,
                            cardHeight,
                            isVideo: hasVideoIcon
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
                        tokenized_url=item['tokenizedUrl'],  # Full URL with xsec_token
                        title=item['title'],
                        author=item['authorName'],
                        author_avatar=item['authorAvatar'],
                        author_profile_url=item['authorProfileUrl'],
                        likes=item['likes'],
                        cover_image=item['coverImage'],
                        publish_date=item['publishDate'],
                        card_width=item['cardWidth'],
                        card_height=item['cardHeight'],
                        is_video=item['isVideo']  # Video detection flag
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
        Search for keyword, extract from cards, and apply filters in real-time.
        v2: 边抓边过滤，不再预抓3倍数量，更高效
        """
        if not self.page:
            await self.init_page()

        if progress_callback:
            await progress_callback(f"Starting search for '{keyword}'...")
            filter_info = f"Filter: min_likes={filters.min_likes}, target={filters.max_posts} posts"
            if filters.skip_videos:
                filter_info += ", skip_videos=ON (only images)"
            await progress_callback(filter_info)
            if filters.min_collects > 0 or filters.min_comments > 0:
                await progress_callback("NOTE: min_collects and min_comments filters are IGNORED in search-only mode")

        # Navigate to search page
        if progress_callback:
            await progress_callback(f"Navigating to search for '{keyword}'...")

        search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&source=web_search_result_notes"
        # Use 'load' instead of 'networkidle' to avoid hanging on continuous XHS network requests
        # Add timeout to prevent blocking other parallel scrape tasks
        await self.page.goto(search_url, timeout=30000)
        await self.page.wait_for_load_state('load', timeout=15000)
        await self._random_delay(2, 4)

        # Check session status
        session = await self.check_session()
        if progress_callback:
            await progress_callback(f"Session check: {'OK' if session['logged_in'] else 'WARNING - may need re-login'}")

        # Real-time filtering variables
        filtered_posts = []       # Posts that passed filters
        seen_note_ids = set()     # Track duplicates
        total_scanned = 0         # Total posts scanned
        videos_skipped = 0
        likes_filtered = 0
        scroll_count = 0
        no_new_posts_count = 0    # Consecutive scrolls with no new posts (for end detection)
        max_no_new_posts = 3      # Stop after 3 consecutive scrolls with no new posts

        # Main loop: scroll and filter until we have enough posts or page ends
        while len(filtered_posts) < filters.max_posts:
            # Check for cancellation
            if cancel_check and cancel_check():
                if progress_callback:
                    await progress_callback("Cancellation requested, stopping...")
                break

            # Extract cards from current view
            card_data = await self.page.evaluate('''() => {
                const results = [];
                const cards = document.querySelectorAll('section.note-item');

                cards.forEach(card => {
                    try {
                        const coverLink = card.querySelector('a.cover');
                        const tokenizedPath = coverLink ? coverLink.getAttribute('href') : '';

                        let noteId = null;
                        if (tokenizedPath) {
                            const match = tokenizedPath.match(/\\/(search_result|explore)\\/([a-f0-9]+)/);
                            if (match) noteId = match[2];
                        }

                        if (!noteId) {
                            const permLink = card.querySelector('a[href^="/explore/"]');
                            if (permLink) {
                                const match = permLink.href.match(/\\/explore\\/([a-f0-9]+)/);
                                if (match) noteId = match[1];
                            }
                        }

                        if (!noteId) {
                            const searchLink = card.querySelector('a[href*="/search_result/"]');
                            if (searchLink) {
                                const match = searchLink.href.match(/\\/search_result\\/([a-f0-9]+)/);
                                if (match) noteId = match[1];
                            }
                        }

                        if (!noteId) return;

                        const tokenizedUrl = tokenizedPath
                            ? 'https://www.xiaohongshu.com' + tokenizedPath
                            : '';

                        const titleEl = card.querySelector('.footer a.title span');
                        const title = titleEl ? titleEl.textContent.trim() : '';

                        const authorNameEl = card.querySelector('.name-time-wrapper .name');
                        const authorName = authorNameEl ? authorNameEl.textContent.trim() : '';

                        const avatarEl = card.querySelector('img.author-avatar');
                        const authorAvatar = avatarEl ? avatarEl.src : '';

                        const authorLinkEl = card.querySelector('a.author');
                        let authorProfileUrl = '';
                        if (authorLinkEl) {
                            authorProfileUrl = authorLinkEl.href;
                        }

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

                        const coverEl = card.querySelector('a.cover img');
                        const coverImage = coverEl ? coverEl.src : '';

                        const dateEl = card.querySelector('.name-time-wrapper .time');
                        const publishDate = dateEl ? dateEl.textContent.trim() : '';

                        const cardWidth = parseInt(card.getAttribute('data-width')) || 0;
                        const cardHeight = parseInt(card.getAttribute('data-height')) || 0;

                        const hasVideoIcon = card.querySelector('svg.play-icon, .play-icon, span.play-icon, [class*="video-icon"]') !== null;

                        results.push({
                            noteId,
                            tokenizedUrl,
                            title,
                            authorName,
                            authorAvatar,
                            authorProfileUrl,
                            likes,
                            coverImage,
                            publishDate,
                            cardWidth,
                            cardHeight,
                            isVideo: hasVideoIcon
                        });
                    } catch (e) {
                        // Skip this card on error
                    }
                });

                return results;
            }''')

            # Process each new card with real-time filtering
            new_posts_this_scroll = 0
            for item in card_data:
                if item['noteId'] in seen_note_ids:
                    continue  # Already processed

                seen_note_ids.add(item['noteId'])
                total_scanned += 1
                new_posts_this_scroll += 1

                # Create post object
                post = XHSPost(
                    note_id=item['noteId'],
                    permanent_url=f"https://www.xiaohongshu.com/explore/{item['noteId']}",
                    tokenized_url=item['tokenizedUrl'],
                    title=item['title'],
                    author=item['authorName'],
                    author_avatar=item['authorAvatar'],
                    author_profile_url=item['authorProfileUrl'],
                    likes=item['likes'],
                    cover_image=item['coverImage'],
                    publish_date=item['publishDate'],
                    card_width=item['cardWidth'],
                    card_height=item['cardHeight'],
                    is_video=item['isVideo']
                )

                # Real-time filtering
                if filters.skip_videos and post.is_video:
                    videos_skipped += 1
                    if progress_callback:
                        await progress_callback(f"  - Skipped video: {post.title[:30]}...")
                elif post.likes < filters.min_likes:
                    likes_filtered += 1
                    if progress_callback:
                        await progress_callback(f"  - Low likes ({post.likes}<{filters.min_likes}): {post.title[:30]}...")
                else:
                    # Passed all filters!
                    filtered_posts.append(post)
                    if progress_callback:
                        post_type = "📹" if post.is_video else "📷"
                        await progress_callback(f"  ✓ [{len(filtered_posts)}/{filters.max_posts}] {post_type} {post.title[:25]}... (likes={post.likes})")

                    # Check if we have enough
                    if len(filtered_posts) >= filters.max_posts:
                        break

            # Check if we have enough posts
            if len(filtered_posts) >= filters.max_posts:
                break

            # Detect page end: no new posts for consecutive scrolls
            if new_posts_this_scroll == 0:
                no_new_posts_count += 1
                if progress_callback:
                    await progress_callback(f"No new posts this scroll ({no_new_posts_count}/{max_no_new_posts})")
                if no_new_posts_count >= max_no_new_posts:
                    if progress_callback:
                        await progress_callback("⚠️ Page has no more content, stopping...")
                    break
            else:
                no_new_posts_count = 0  # Reset counter

            # Scroll down to load more
            await self.page.evaluate('window.scrollBy(0, window.innerHeight)')
            await self._random_delay(1.5, 2.5)
            scroll_count += 1

            if progress_callback:
                await progress_callback(f"Scrolling... (scanned: {total_scanned}, kept: {len(filtered_posts)}/{filters.max_posts})")

        # Final summary
        if progress_callback:
            summary = f"✅ Complete: {len(filtered_posts)} posts kept (scanned {total_scanned})"
            if videos_skipped > 0 or likes_filtered > 0:
                summary += f" | Filtered out: {videos_skipped} videos, {likes_filtered} low-likes"
            await progress_callback(summary)

        return filtered_posts


async def save_posts_to_database(
    posts: List[XHSPost],
    account_id: int,
    keyword: str,
    scrape_task_id: Optional[int] = None,
    progress_callback=None
) -> Tuple[int, int]:
    """
    Save posts to database. Returns (new_count, duplicate_count).
    """
    new_count = 0
    duplicate_count = 0

    try:
        db = get_database()
        async with db.session() as session:
            # Ensure account exists in database
            account_repo = AccountRepository(session)
            await account_repo.get_or_create(account_id)

            post_repo = PostRepository(session)

            for post in posts:
                # Check if post already exists
                existing = await post_repo.get_by_note_id(post.note_id)

                # Upsert the post
                await post_repo.upsert(
                    note_id=post.note_id,
                    scrape_task_id=scrape_task_id,
                    account_id=account_id,
                    title=post.title,
                    permanent_url=post.permanent_url,
                    tokenized_url=post.tokenized_url,
                    author_name=post.author,
                    author_avatar_url=post.author_avatar,
                    author_profile_url=post.author_profile_url,
                    likes=post.likes,
                    cover_image_url=post.cover_image,
                    is_video=post.is_video,
                    card_width=post.card_width,
                    card_height=post.card_height,
                    publish_date=post.publish_date,
                    scraped_at=datetime.utcnow(),
                    keyword=keyword,
                )

                if existing:
                    duplicate_count += 1
                else:
                    new_count += 1

            # Update account stats
            await account_repo.increment_stats(
                account_id,
                posts_scraped=new_count  # Only count new posts
            )

            # Update hourly stats
            hour_start = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
            stats_repo = StatsRepository(session)
            await stats_repo.record_stats(
                account_id=account_id,
                period_type="hour",
                period_start=hour_start,
                posts_scraped=new_count,
                keywords_searched=1
            )

        if progress_callback:
            await progress_callback(f"Database: Saved {new_count} new posts, {duplicate_count} duplicates")

    except Exception as e:
        print(f"Error saving posts to database: {e}")
        if progress_callback:
            await progress_callback(f"Warning: Failed to save to database - {str(e)}")

    return new_count, duplicate_count


def save_results(posts: List[XHSPost], keyword: str, account_id: int, logs: List[str] = None) -> Tuple[str, str]:
    """
    Save scrape results to JSON file and logs to a companion .log file.
    Returns tuple of (json_filepath, log_filepath).
    """
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_keyword = re.sub(r'[^\w\u4e00-\u9fff]', '_', keyword)
    base_filename = f"{safe_keyword}_account{account_id}_{timestamp}"

    # Save JSON results
    json_filepath = os.path.join(OUTPUT_DIR, f"{base_filename}.json")
    results = {
        "keyword": keyword,
        "account_id": account_id,
        "scraped_at": datetime.now().isoformat(),
        "scrape_mode": "search_only",  # Indicate this is search-only data
        "total_posts": len(posts),
        "posts": [post.to_dict() for post in posts]
    }
    with open(json_filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Save log file alongside JSON
    log_filepath = os.path.join(OUTPUT_DIR, f"{base_filename}.log")
    log_content = [
        f"=== XHS Scrape Log ===",
        f"Keyword: {keyword}",
        f"Account ID: {account_id}",
        f"Timestamp: {datetime.now().isoformat()}",
        f"Total posts saved: {len(posts)}",
        f"",
        f"=== Progress Log ===",
    ]
    if logs:
        log_content.extend(logs)
    else:
        log_content.append("(No log messages recorded)")

    with open(log_filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_content))

    return json_filepath, log_filepath


async def run_scrape_task(
    context: BrowserContext,
    keyword: str,
    account_id: int,
    filters: ScrapeFilter,
    progress_callback=None,
    cancel_check=None,
    scrape_task_id: Optional[int] = None
) -> Tuple[List[XHSPost], str, str]:
    """
    Run a complete scrape task.
    Returns (posts, json_filepath, log_filepath).
    Supports cancellation via cancel_check callback.
    """
    scraper = XHSScraper(context)
    collected_logs: List[str] = []

    # Wrapper to collect logs while still calling the original callback
    async def log_collecting_callback(message: str):
        timestamp = datetime.now().strftime('%H:%M:%S')
        collected_logs.append(f"[{timestamp}] {message}")
        if progress_callback:
            await progress_callback(message)

    try:
        await scraper.init_page()
        posts = await scraper.search_and_scrape(keyword, filters, log_collecting_callback, cancel_check)

        # Download cover images after scraping (if not cancelled)
        if posts and not (cancel_check and cancel_check()):
            await log_collecting_callback(f"Downloading {len(posts)} cover images...")
            try:
                # Download images with progress reporting
                image_results = await download_post_images(
                    posts=posts,
                    progress_callback=log_collecting_callback,
                    max_concurrent=10
                )

                # Update posts with local image paths
                for post in posts:
                    local_path = image_results.get(post.note_id)
                    if local_path:
                        # Store just the filename (not full path) for portability
                        post.local_cover_image = get_local_image_filename(post.note_id)

            except Exception as e:
                await log_collecting_callback(f"Warning: Image download failed - {str(e)}")
                # Continue without images - not critical

        # Save posts to database
        if posts:
            await save_posts_to_database(
                posts=posts,
                account_id=account_id,
                keyword=keyword,
                scrape_task_id=scrape_task_id,
                progress_callback=log_collecting_callback
            )

        # Save results and logs even if cancelled (partial results)
        json_filepath, log_filepath = save_results(posts, keyword, account_id, collected_logs)

        return posts, json_filepath, log_filepath

    finally:
        await scraper.close()
