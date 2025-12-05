# Xiaohongshu scraper module
# Version: 1.1 - Search and scrape XHS posts with filtering
# Updated: Paths adjusted for backend/ directory structure

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


class XHSScraper:
    """Scraper for Xiaohongshu posts"""

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

    async def search(self, keyword: str, max_results: int = 30) -> List[Tuple[str, dict]]:
        """
        Search for keyword and return list of (note_id, preview_data) tuples.
        Preview data includes title, likes count from search results.
        """
        if not self.page:
            await self.init_page()

        search_url = f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&source=web_search_result_notes"
        await self.page.goto(search_url)
        await self.page.wait_for_load_state('networkidle')
        await self._random_delay(2, 4)

        results = []
        scroll_count = 0
        max_scrolls = max_results // 10 + 2  # Estimate scrolls needed

        while len(results) < max_results and scroll_count < max_scrolls:
            # Extract search results from current view
            new_results = await self.page.evaluate('''() => {
                const results = [];

                // Find all note cards in search results
                const cards = document.querySelectorAll('section.note-item, [class*="note-item"]');

                cards.forEach(card => {
                    try {
                        // Find the link to the note
                        const link = card.querySelector('a[href*="/search_result/"], a[href*="/explore/"]');
                        if (!link) return;

                        const href = link.href;
                        const match = href.match(/\\/(search_result|explore)\\/([a-f0-9]+)/);
                        if (!match || !match[2]) return;

                        const noteId = match[2];

                        // Try to get preview info
                        const titleEl = card.querySelector('.title, [class*="title"]');
                        const title = titleEl ? titleEl.textContent.trim() : '';

                        // Get likes count from card
                        const likesEl = card.querySelector('[class*="like"], [class*="count"]');
                        let likes = 0;
                        if (likesEl) {
                            const likesText = likesEl.textContent.trim();
                            if (likesText.includes('万')) {
                                likes = parseFloat(likesText) * 10000;
                            } else {
                                likes = parseInt(likesText.replace(/[^0-9]/g, '')) || 0;
                            }
                        }

                        results.push({
                            noteId,
                            title,
                            likes
                        });
                    } catch (e) {
                        // Skip this card
                    }
                });

                return results;
            }''')

            # Add new results, avoiding duplicates
            seen_ids = {r[0] for r in results}
            for item in new_results:
                if item['noteId'] not in seen_ids:
                    results.append((item['noteId'], item))
                    seen_ids.add(item['noteId'])

            if len(results) >= max_results:
                break

            # Scroll down to load more
            await self.page.evaluate('window.scrollBy(0, window.innerHeight)')
            await self._random_delay(1, 2)
            scroll_count += 1

        return results[:max_results]

    async def scrape_post(self, note_id: str) -> Optional[XHSPost]:
        """Scrape a single post by note ID"""
        if not self.page:
            await self.init_page()

        url = f"https://www.xiaohongshu.com/explore/{note_id}"

        try:
            await self.page.goto(url)
            await self.page.wait_for_load_state('networkidle')
            await self._random_delay(1, 2)

            # Extract post data
            data = await self.page.evaluate('''() => {
                const result = {
                    title: '',
                    content: '',
                    images: [],
                    hashtags: [],
                    likes: 0,
                    collects: 0,
                    comments: 0,
                    author: '',
                    publishDate: ''
                };

                // Title
                const titleEl = document.querySelector('.title');
                if (titleEl) result.title = titleEl.textContent?.trim() || '';

                // Content
                const descEl = document.querySelector('.desc');
                if (descEl) result.content = descEl.innerText?.trim() || '';

                // Author
                const authorEl = document.querySelector('.username, .author-name, [class*="username"]');
                if (authorEl) result.author = authorEl.textContent?.trim() || '';

                // Images - spectrum URLs are original images
                document.querySelectorAll('img').forEach(img => {
                    const src = img.src;
                    if (src && src.includes('spectrum') && !result.images.includes(src)) {
                        result.images.push(src);
                    }
                });

                // Hashtags
                document.querySelectorAll('a[href*="search_result"]').forEach(a => {
                    const text = a.textContent?.trim();
                    if (text && text.startsWith('#') && !result.hashtags.includes(text)) {
                        result.hashtags.push(text);
                    }
                });

                // Engagement metrics - look for interact bar
                const interactBar = document.querySelector('.interact-container, [class*="interact"]');
                if (interactBar) {
                    const spans = interactBar.querySelectorAll('span, [class*="count"]');
                    spans.forEach((span, idx) => {
                        const text = span.textContent?.trim() || '';
                        let value = 0;
                        if (text.includes('万')) {
                            value = parseFloat(text) * 10000;
                        } else {
                            value = parseInt(text.replace(/[^0-9]/g, '')) || 0;
                        }

                        // Usually order is: likes, collects, comments
                        if (idx === 0 || span.closest('[class*="like"]')) result.likes = value;
                        else if (idx === 1 || span.closest('[class*="collect"]')) result.collects = value;
                        else if (idx === 2 || span.closest('[class*="comment"]')) result.comments = value;
                    });
                }

                // Try alternative selectors for metrics
                const likeEl = document.querySelector('[class*="like-wrapper"] span, .like-count');
                const collectEl = document.querySelector('[class*="collect-wrapper"] span, .collect-count');
                const commentEl = document.querySelector('[class*="chat-wrapper"] span, .comment-count');

                const parseCount = (el) => {
                    if (!el) return 0;
                    const text = el.textContent?.trim() || '';
                    if (text.includes('万')) return parseFloat(text) * 10000;
                    return parseInt(text.replace(/[^0-9]/g, '')) || 0;
                };

                if (likeEl && result.likes === 0) result.likes = parseCount(likeEl);
                if (collectEl && result.collects === 0) result.collects = parseCount(collectEl);
                if (commentEl && result.comments === 0) result.comments = parseCount(commentEl);

                return result;
            }''')

            if not data['title'] and not data['content']:
                return None

            return XHSPost(
                note_id=note_id,
                permanent_url=f"https://www.xiaohongshu.com/explore/{note_id}",
                title=data['title'],
                content=data['content'],
                images=data['images'],
                hashtags=data['hashtags'],
                likes=data['likes'],
                collects=data['collects'],
                comments=data['comments'],
                author=data['author'],
                publish_date=data['publishDate']
            )

        except Exception as e:
            print(f"Error scraping {note_id}: {e}")
            return None

    async def search_and_scrape(
        self,
        keyword: str,
        filters: ScrapeFilter,
        progress_callback=None
    ) -> List[XHSPost]:
        """
        Search for keyword, scrape matching posts, and apply filters.
        """
        posts = []

        # Search for posts
        if progress_callback:
            progress_callback(f"Searching for '{keyword}'...")

        search_results = await self.search(keyword, max_results=filters.max_posts * 2)

        if progress_callback:
            progress_callback(f"Found {len(search_results)} results, scraping details...")

        # Scrape each post
        for idx, (note_id, preview) in enumerate(search_results):
            if len(posts) >= filters.max_posts:
                break

            if progress_callback:
                progress_callback(f"Scraping {idx + 1}/{len(search_results)}: {preview.get('title', note_id)[:30]}...")

            post = await self.scrape_post(note_id)

            if post:
                # Apply filters
                if filters.passes(post):
                    posts.append(post)
                    if progress_callback:
                        progress_callback(f"  -> Saved (likes={post.likes}, collects={post.collects})")
                else:
                    if progress_callback:
                        progress_callback(f"  -> Filtered out (likes={post.likes}, collects={post.collects})")

            await self._random_delay(1, 2)

        return posts


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
    progress_callback=None
) -> Tuple[List[XHSPost], str]:
    """
    Run a complete scrape task.
    Returns (posts, output_filepath).
    """
    scraper = XHSScraper(context)

    try:
        await scraper.init_page()
        posts = await scraper.search_and_scrape(keyword, filters, progress_callback)

        # Save results
        filepath = save_results(posts, keyword, account_id)

        return posts, filepath

    finally:
        await scraper.close()
