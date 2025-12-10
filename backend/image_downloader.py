# Image downloader module for XHS Scraper
# Version: 1.0 - Initial implementation with async download, deduplication, and CDN bypass
# Changes: Created async image downloader with concurrent download support, deduplication, and proper headers
# Purpose: Download cover images from Xiaohongshu CDN to local storage to avoid URL expiration

import os
import asyncio
import aiohttp
from typing import List, Optional, Callable
from pathlib import Path

# Paths relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_IMAGES_DIR = os.path.join(BASE_DIR, 'output_images')

# Ensure output_images directory exists
os.makedirs(OUTPUT_IMAGES_DIR, exist_ok=True)


class ImageDownloader:
    """
    Async image downloader for Xiaohongshu cover images.
    Features:
    - Concurrent downloads with semaphore limiting
    - Automatic deduplication (skip if file exists)
    - CDN-friendly headers to avoid blocking
    - Progress callback support
    """

    def __init__(self, max_concurrent: int = 10):
        """
        Initialize image downloader.

        Args:
            max_concurrent: Maximum number of concurrent downloads (default: 10)
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Headers to bypass CDN restrictions
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.xiaohongshu.com/',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

    def get_local_image_path(self, note_id: str) -> str:
        """
        Get the local file path for a note's cover image.

        Args:
            note_id: The note ID

        Returns:
            Absolute path to the local image file
        """
        filename = f"{note_id}_cover.webp"
        return os.path.join(OUTPUT_IMAGES_DIR, filename)

    def image_exists(self, note_id: str) -> bool:
        """
        Check if image already exists locally.

        Args:
            note_id: The note ID

        Returns:
            True if image exists, False otherwise
        """
        return os.path.exists(self.get_local_image_path(note_id))

    async def download_image(
        self,
        note_id: str,
        image_url: str,
        session: aiohttp.ClientSession,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[str]:
        """
        Download a single image with semaphore limiting.

        Args:
            note_id: The note ID
            image_url: URL of the image to download
            session: aiohttp ClientSession for connection pooling
            progress_callback: Optional callback for progress updates

        Returns:
            Local file path if successful, None if failed or skipped
        """
        # Skip if no URL provided
        if not image_url:
            return None

        # Check if already exists (deduplication)
        local_path = self.get_local_image_path(note_id)
        if os.path.exists(local_path):
            if progress_callback:
                progress_callback(f"  ⏭️  Skipped (exists): {note_id}")
            return local_path

        # Use semaphore to limit concurrent downloads
        async with self.semaphore:
            try:
                # Download image with timeout
                async with session.get(image_url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        # Save to file
                        content = await response.read()
                        with open(local_path, 'wb') as f:
                            f.write(content)

                        if progress_callback:
                            size_kb = len(content) / 1024
                            progress_callback(f"  ✓ Downloaded: {note_id} ({size_kb:.1f}KB)")

                        return local_path
                    else:
                        if progress_callback:
                            progress_callback(f"  ✗ Failed ({response.status}): {note_id}")
                        return None

            except asyncio.TimeoutError:
                if progress_callback:
                    progress_callback(f"  ✗ Timeout: {note_id}")
                return None
            except Exception as e:
                if progress_callback:
                    progress_callback(f"  ✗ Error downloading {note_id}: {str(e)}")
                return None

    async def download_images_batch(
        self,
        posts_data: List[tuple],
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> dict:
        """
        Download multiple images concurrently.

        Args:
            posts_data: List of (note_id, cover_image_url) tuples
            progress_callback: Optional callback for progress updates

        Returns:
            Dictionary mapping note_id -> local_path (or None if failed)
        """
        if not posts_data:
            return {}

        if progress_callback:
            progress_callback(f"Starting image download: {len(posts_data)} images (max {self.max_concurrent} concurrent)")

        results = {}

        # Create aiohttp session for connection pooling
        async with aiohttp.ClientSession() as session:
            # Create download tasks
            tasks = []
            for note_id, image_url in posts_data:
                task = self.download_image(note_id, image_url, session, progress_callback)
                tasks.append((note_id, task))

            # Wait for all downloads to complete
            for note_id, task in tasks:
                local_path = await task
                results[note_id] = local_path

        # Summary
        successful = sum(1 for path in results.values() if path is not None)
        skipped = sum(1 for note_id, _ in posts_data if os.path.exists(self.get_local_image_path(note_id)))
        failed = len(posts_data) - successful

        if progress_callback:
            progress_callback(f"Image download complete: {successful} successful, {failed} failed, {skipped} skipped")

        return results


async def download_post_images(
    posts: List,
    progress_callback: Optional[Callable[[str], None]] = None,
    max_concurrent: int = 10
) -> dict:
    """
    Helper function to download images for a list of XHSPost objects.

    Args:
        posts: List of XHSPost objects
        progress_callback: Optional callback for progress updates
        max_concurrent: Maximum concurrent downloads

    Returns:
        Dictionary mapping note_id -> local_path
    """
    # Extract (note_id, cover_image) tuples
    posts_data = [(post.note_id, post.cover_image) for post in posts if post.cover_image]

    if not posts_data:
        if progress_callback:
            progress_callback("No images to download")
        return {}

    # Create downloader and download
    downloader = ImageDownloader(max_concurrent=max_concurrent)
    return await downloader.download_images_batch(posts_data, progress_callback)


def get_local_image_filename(note_id: str) -> str:
    """
    Get the local filename (not full path) for a note's cover image.

    Args:
        note_id: The note ID

    Returns:
        Filename only (e.g., "abc123_cover.webp")
    """
    return f"{note_id}_cover.webp"


def delete_images_by_note_ids(note_ids: List[str]) -> int:
    """
    Delete local images for a list of note IDs.

    Args:
        note_ids: List of note IDs

    Returns:
        Number of images deleted
    """
    deleted_count = 0
    for note_id in note_ids:
        filepath = os.path.join(OUTPUT_IMAGES_DIR, f"{note_id}_cover.webp")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                deleted_count += 1
            except Exception as e:
                print(f"Failed to delete image for {note_id}: {e}")

    return deleted_count
