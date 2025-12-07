# OpenRouter Gemini Flash Image and Content Labeling Module
# Version: 4.3 - Real-time result tracking for cancellation support
# Changes: Track results in real-time during batch processing, add get_current_results() method
# Previous: v4.2 - Graceful error handling with partial results
#
# Features:
# - Concurrent batch processing with configurable parallelism (default: 5)
# - Binary content matching (满足/不满足) based on user description
# - 5 mutually exclusive style categories (人物图/特写图/环境图/拼接图/信息图)
# - Optional likes count inclusion in analysis
# - Transparent prompting - what you see in UI is what Gemini sees
# - Structured JSON output with label, style_label, and reasoning
# - Error handling and retry logic for API calls
# - Progress callback for real-time streaming logs
# - Auto-pause on rate limit (429) errors
# - Uses OpenRouter API for access to Gemini 2.0 Flash

import os
import json
import logging
import base64
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Literal, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from dotenv import load_dotenv
import requests
from io import BytesIO
from PIL import Image

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Custom exception for API rate limit (429) errors"""
    def __init__(self, message: str, processed_count: int = 0, retry_after: int = 60):
        super().__init__(message)
        self.processed_count = processed_count
        self.retry_after = retry_after


class LabelingMode(str, Enum):
    """Enumeration of supported labeling modes"""
    COVER_IMAGE = "cover_image"
    ALL_IMAGES = "all_images"
    TITLE = "title"
    CONTENT = "content"
    TITLE_CONTENT = "title_content"
    COVER_IMAGE_TITLE = "cover_image_title"
    COVER_IMAGE_CONTENT = "cover_image_content"
    ALL_IMAGES_TITLE = "all_images_title"
    ALL_IMAGES_CONTENT = "all_images_content"
    FULL = "full"


# Fixed style categories for food industry (5 mutually exclusive types)
STYLE_CATEGORIES = [
    "人物图",  # Person-focused shot (visual focus on people)
    "特写图",  # Close-up shot of objects/food (subject fills 80%+ of frame)
    "环境图",  # Environment/Scene shot (ambiance, location)
    "拼接图",  # Collage/Composite (multiple images combined)
    "信息图",  # Infographic (text overlays, lists, menus)
]


@dataclass
class LabelingResult:
    """Structured result for a single post's labeling"""
    note_id: str
    label: str  # Binary: "满足" or "不满足"
    style_label: str  # One of: "人物图", "特写图", "环境图", "拼接图", "信息图"
    reasoning: str  # Explanation in Chinese
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BatchResult:
    """
    Wrapper for batch labeling results that supports partial completion.
    Always returns results even if interrupted by errors.
    """
    results: List[LabelingResult]  # All results (successful + errors)
    total_posts: int  # Total posts attempted
    successful_count: int  # Successfully labeled posts
    error_count: int  # Posts with errors
    is_partial: bool  # True if interrupted by 429/other fatal error
    interrupted_reason: Optional[str] = None  # Reason for interruption if partial
    interrupted_at_index: Optional[int] = None  # Index where processing stopped

    def to_dict(self) -> dict:
        return {
            "total_posts": self.total_posts,
            "successful_count": self.successful_count,
            "error_count": self.error_count,
            "is_partial": self.is_partial,
            "interrupted_reason": self.interrupted_reason,
            "interrupted_at_index": self.interrupted_at_index
        }


class GeminiLabeler:
    """
    Gemini 2.0 Flash client via OpenRouter for image and content labeling.

    This module provides flexible prompt engineering for categorizing XHS posts
    based on images (cover or all), text (title or content), or combinations.
    Uses OpenRouter API to access Google's Gemini 2.0 Flash model.
    """

    # OpenRouter API configuration
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL = "google/gemini-2.0-flash-001"

    def __init__(self, api_key: Optional[str] = None, model_name: str = None):
        """
        Initialize Gemini labeler with OpenRouter API key.

        Args:
            api_key: OpenRouter API key (defaults to OPEN_ROUTER_API_KEY env var)
            model_name: Model to use (default: google/gemini-2.0-flash-001)
        """
        self.api_key = api_key or os.getenv("OPEN_ROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPEN_ROUTER_API_KEY not found in environment or constructor")

        self.model_name = model_name or self.DEFAULT_MODEL

        # Set up request headers
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://smartice.app",
            "X-Title": "SmartICE XHS Labeler"
        }

        # Real-time tracking for cancellation support
        self._current_results: List[Optional[LabelingResult]] = []
        self._current_posts: List[Dict[str, Any]] = []
        self._results_lock = threading.Lock()

        logger.info(f"Initialized GeminiLabeler via OpenRouter with model: {self.model_name}")

    def _build_prompt(self, user_description: str) -> str:
        """
        Build the full prompt for binary classification with style labeling.

        Args:
            user_description: User's description of what posts they want to filter

        Returns:
            Complete prompt string with output format and classification criteria
        """
        return f"""You are a content labeler for Xiaohongshu (小红书) posts. Analyze the provided content and categorize it.

User's filter criteria: {user_description}

Based on this criteria, determine if the post matches (满足) or doesn't match (不满足).

Also classify the image style into ONE of these 5 mutually exclusive categories (判断依据是视觉焦点):
- 人物图: Person-focused shots where people are the visual focus - facing camera, check-in poses, or people as the main subject even in distant/scenic backgrounds
- 特写图: Close-up shots of objects/food where the subject fills most of the frame (80%+), surroundings are minimal (not about people)
- 环境图: Scene/ambiance shots showing location, atmosphere; people may appear but are NOT the visual focus (small in frame, not facing camera)
- 拼接图: Collage or composite images combining multiple photos into one
- 信息图: Infographic style with text overlays, promotional content, menus, price lists

Output your analysis in this exact JSON format:
{{
  "label": "<满足 or 不满足>",
  "style_label": "<人物图 or 特写图 or 环境图 or 拼接图 or 信息图>",
  "reasoning": "<brief explanation in Chinese>"
}}"""

    def _download_image_as_base64(self, url: str) -> Optional[str]:
        """
        Download image from URL and return as base64 encoded string.

        Args:
            url: Image URL to download

        Returns:
            Base64 encoded image string or None if download fails
        """
        try:
            # Use browser-like headers to bypass CDN restrictions
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
                "Referer": "https://www.xiaohongshu.com/"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Detect image type from content-type header or URL
            content_type = response.headers.get('content-type', 'image/jpeg')
            if 'png' in content_type or url.lower().endswith('.png'):
                mime_type = 'image/png'
            elif 'gif' in content_type or url.lower().endswith('.gif'):
                mime_type = 'image/gif'
            elif 'webp' in content_type or url.lower().endswith('.webp'):
                mime_type = 'image/webp'
            else:
                mime_type = 'image/jpeg'

            # Encode to base64
            base64_image = base64.b64encode(response.content).decode('utf-8')
            return f"data:{mime_type};base64,{base64_image}"

        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            return None

    def _prepare_content_parts(
        self,
        post: Dict[str, Any],
        mode: LabelingMode,
        full_prompt: str,
        include_likes: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Prepare content parts for OpenRouter API based on labeling mode.
        Returns OpenAI-compatible message content format.

        Args:
            post: XHS post dictionary
            mode: Labeling mode
            full_prompt: Complete prompt with instructions
            include_likes: Whether to include likes count in analysis

        Returns:
            List of content parts in OpenAI format
        """
        parts = []

        # Build text content
        text_content = full_prompt

        # Add text based on mode
        if mode in [LabelingMode.TITLE, LabelingMode.TITLE_CONTENT, LabelingMode.COVER_IMAGE_TITLE,
                    LabelingMode.ALL_IMAGES_TITLE, LabelingMode.FULL]:
            title = post.get("title", "")
            if title:
                text_content += f"\n\nTitle: {title}"

        if mode in [LabelingMode.CONTENT, LabelingMode.TITLE_CONTENT, LabelingMode.COVER_IMAGE_CONTENT,
                    LabelingMode.ALL_IMAGES_CONTENT, LabelingMode.FULL]:
            content = post.get("content", "")
            if content:
                text_content += f"\n\nContent: {content}"

        # Add likes count if requested
        if include_likes:
            likes = post.get("likes", 0)
            text_content += f"\n\nLikes: {likes}"

        # Add the text part first
        parts.append({"type": "text", "text": text_content})

        # Add images based on mode - download and encode as base64
        # (XHS CDN URLs block direct access from external servers)
        if mode in [LabelingMode.COVER_IMAGE, LabelingMode.COVER_IMAGE_TITLE,
                    LabelingMode.COVER_IMAGE_CONTENT]:
            cover_url = post.get("cover_image")
            if cover_url:
                base64_url = self._download_image_as_base64(cover_url)
                if base64_url:
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": base64_url}
                    })

        if mode in [LabelingMode.ALL_IMAGES, LabelingMode.ALL_IMAGES_TITLE,
                    LabelingMode.ALL_IMAGES_CONTENT, LabelingMode.FULL]:
            images = post.get("images", [])
            if not images and post.get("cover_image"):
                images = [post["cover_image"]]

            for img_url in images:
                base64_url = self._download_image_as_base64(img_url)
                if base64_url:
                    parts.append({
                        "type": "image_url",
                        "image_url": {"url": base64_url}
                    })

        return parts

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON response, handling potential formatting issues.

        Args:
            response_text: Raw response text from API

        Returns:
            Parsed JSON dictionary
        """
        text = response_text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            result = json.loads(text)
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response_text}")
            raise

    def label_post(
        self,
        post: Dict[str, Any],
        user_description: str,
        mode: LabelingMode = LabelingMode.COVER_IMAGE,
        include_likes: bool = False
    ) -> LabelingResult:
        """
        Label a single XHS post using Gemini 2.0 Flash via OpenRouter.

        Args:
            post: XHS post dictionary (must have note_id)
            user_description: User's description of what posts they want to filter
            mode: Labeling mode (what to analyze)
            include_likes: Whether to include likes count in analysis

        Returns:
            LabelingResult with label (满足/不满足), style_label, and reasoning
        """
        note_id = post.get("note_id", "unknown")

        try:
            # Build the prompt
            full_prompt = self._build_prompt(user_description)

            # Prepare content parts in OpenAI format
            content_parts = self._prepare_content_parts(post, mode, full_prompt, include_likes)

            # Build the request payload
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": content_parts
                    }
                ],
                "temperature": 0.1,
                "top_p": 0.95,
                "max_tokens": 1024
            }

            # Make the API request
            response = requests.post(
                self.OPENROUTER_BASE_URL,
                headers=self.headers,
                json=payload,
                timeout=60
            )

            # Log error details for debugging
            if response.status_code >= 400:
                logger.error(f"API error {response.status_code}: {response.text}")

            # Check for rate limit errors
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise RateLimitError(
                    f"Rate limit exceeded. Please wait {retry_after}s before retrying.",
                    retry_after=retry_after
                )

            response.raise_for_status()

            # Parse the response
            response_data = response.json()

            # Extract the message content
            if 'choices' not in response_data or len(response_data['choices']) == 0:
                raise ValueError("No response choices returned from API")

            response_text = response_data['choices'][0]['message']['content']
            logger.debug(f"API response for {note_id}: {response_text}")

            result_json = self._parse_json_response(response_text)

            # Extract label (满足/不满足)
            label = result_json.get("label", "不满足")
            if label not in ["满足", "不满足"]:
                logger.warning(f"Invalid label '{label}' for {note_id}, defaulting to '不满足'")
                label = "不满足"

            # Extract style_label
            style_label = result_json.get("style_label", "特写图")
            if style_label not in STYLE_CATEGORIES:
                logger.warning(f"Invalid style_label '{style_label}' for {note_id}, defaulting to '特写图'")
                style_label = "特写图"

            # Extract reasoning
            reasoning = result_json.get("reasoning", "")

            return LabelingResult(
                note_id=note_id,
                label=label,
                style_label=style_label,
                reasoning=reasoning
            )

        except RateLimitError:
            raise
        except Exception as e:
            error_str = str(e)
            logger.error(f"Error labeling post {note_id}: {error_str}")

            # Check for rate limit errors in exception message
            if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                import re
                retry_after = 60
                match = re.search(r'(\d+(?:\.\d+)?)\s*s', error_str)
                if match:
                    retry_after = int(float(match.group(1))) + 5

                raise RateLimitError(
                    f"Rate limit exceeded. Please wait {retry_after}s before retrying.",
                    retry_after=retry_after
                )

            return LabelingResult(
                note_id=note_id,
                label="不满足",
                style_label="特写图",
                reasoning="",
                error=error_str
            )

    def get_current_results(self) -> Optional[tuple[List[Dict[str, Any]], List[LabelingResult]]]:
        """
        Get the current partial results during batch processing.
        Used for saving progress when task is manually cancelled.

        Returns:
            Tuple of (posts, results) or None if no batch is in progress
        """
        with self._results_lock:
            if not self._current_posts or not self._current_results:
                return None

            # Filter to only successfully labeled results
            valid_results = []
            for r in self._current_results:
                if r is not None and r.label:  # Has actual label (not empty)
                    valid_results.append(r)

            if not valid_results:
                return None

            return (list(self._current_posts), list(self._current_results))

    def label_posts_batch(
        self,
        posts: List[Dict[str, Any]],
        user_description: str,
        mode: LabelingMode = LabelingMode.COVER_IMAGE,
        max_posts: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
        include_likes: bool = False,
        max_concurrency: int = 5
    ) -> BatchResult:
        """
        Label multiple XHS posts in batch with concurrent processing.
        Returns BatchResult wrapper that always contains results even on errors.
        Results are tracked in real-time for cancellation support via get_current_results().

        Args:
            posts: List of XHS post dictionaries
            user_description: User's description of what posts they want to filter
            mode: Labeling mode (what to analyze)
            max_posts: Maximum number of posts to process (None = all)
            progress_callback: Optional callback(index, total, title, status)
            include_likes: Whether to include likes count in analysis
            max_concurrency: Maximum parallel API calls (default: 5)

        Returns:
            BatchResult containing all results with partial completion info
        """
        if max_posts:
            posts = posts[:max_posts]

        total = len(posts)
        # Pre-allocate results list to maintain order
        results: List[Optional[LabelingResult]] = [None] * total
        completed_count = 0
        rate_limit_hit = False
        rate_limit_error = None
        interrupted_index = None
        lock = threading.Lock()

        # Initialize real-time tracking (thread-safe)
        with self._results_lock:
            self._current_posts = list(posts)
            self._current_results = [None] * total

        logger.info(f"Starting concurrent batch labeling: {total} posts, concurrency={max_concurrency}")

        def process_single(idx: int, post: Dict[str, Any]) -> tuple[int, LabelingResult]:
            """Process a single post and return (index, result)"""
            nonlocal rate_limit_hit, rate_limit_error, interrupted_index

            # Skip if rate limit already hit - mark as skipped (not processed)
            if rate_limit_hit:
                return idx, LabelingResult(
                    note_id=post.get('note_id', 'unknown'),
                    label="",  # Empty = not processed
                    style_label="",
                    reasoning="",
                    error="Skipped due to rate limit"
                )

            title = post.get('title', 'Untitled')[:50]
            note_id = post.get('note_id', 'unknown')

            try:
                result = self.label_post(post, user_description, mode, include_likes)
                return idx, result
            except RateLimitError as e:
                with lock:
                    if not rate_limit_hit:
                        rate_limit_hit = True
                        rate_limit_error = e
                        interrupted_index = idx
                return idx, LabelingResult(
                    note_id=note_id,
                    label="",  # Empty = not processed
                    style_label="",
                    reasoning="",
                    error=f"Rate limit: {e}"
                )

        def update_progress(idx: int, result: LabelingResult):
            """Thread-safe progress update and real-time result tracking"""
            nonlocal completed_count
            with lock:
                completed_count += 1
                # Update real-time tracking
                with self._results_lock:
                    self._current_results[idx] = result
                title = posts[idx].get('title', 'Untitled')[:50]
                if progress_callback:
                    if result.error:
                        status = f"error: {result.error[:30]}"
                    else:
                        status = f"done: {result.label} ({result.style_label})"
                    progress_callback(completed_count, total, title, status)

        # Execute with ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            # Submit all tasks
            futures = {
                executor.submit(process_single, idx, post): idx
                for idx, post in enumerate(posts)
            }

            # Process results as they complete
            for future in as_completed(futures):
                try:
                    idx, result = future.result()
                    results[idx] = result
                    update_progress(idx, result)
                except Exception as e:
                    idx = futures[future]
                    note_id = posts[idx].get('note_id', 'unknown')
                    error_result = LabelingResult(
                        note_id=note_id,
                        label="",  # Empty = not processed
                        style_label="",
                        reasoning="",
                        error=str(e)
                    )
                    results[idx] = error_result
                    update_progress(idx, error_result)

        # Count results: successful = has label, error = has error, skipped = neither
        final_results = [r for r in results if r is not None]
        success_count = sum(1 for r in final_results if r.label and not r.error)
        error_count = sum(1 for r in final_results if r.error)

        logger.info(f"Batch complete: {success_count}/{total} successful, {error_count} errors, partial={rate_limit_hit}")

        # Clear real-time tracking on completion
        with self._results_lock:
            self._current_posts = []
            self._current_results = []

        # Build interrupted reason if applicable
        interrupted_reason = None
        if rate_limit_hit and rate_limit_error:
            interrupted_reason = f"API Rate Limit (429): {rate_limit_error}"

        # Return BatchResult - never throw exception, always return partial results
        return BatchResult(
            results=final_results,
            total_posts=total,
            successful_count=success_count,
            error_count=error_count,
            is_partial=rate_limit_hit,
            interrupted_reason=interrupted_reason,
            interrupted_at_index=interrupted_index
        )


# Test function
def test_openrouter_labeler():
    """Quick test of the OpenRouter Gemini labeler with one image"""
    import glob

    logger.info("Testing OpenRouter Gemini Labeler")

    # Find a sample file - use the most recently modified one
    output_dir = "/Users/jeremydong/Desktop/Smartice/APPs/XHSCOfSmartICE/output"
    json_files = glob.glob(f"{output_dir}/*.json")

    if not json_files:
        logger.error("No JSON files found in output directory")
        return False

    # Sort by modification time (newest first)
    json_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    sample_file = json_files[0]
    logger.info(f"Using sample file: {sample_file}")

    with open(sample_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    posts = data.get("posts", [])
    if not posts:
        logger.error("No posts found in sample file")
        return False

    # Test with first post only
    test_post = posts[0]
    logger.info(f"Testing with post: {test_post.get('note_id')} - {test_post.get('title', 'No title')[:50]}")

    try:
        labeler = GeminiLabeler()

        result = labeler.label_post(
            post=test_post,
            user_description="美食相关的内容",
            mode=LabelingMode.COVER_IMAGE
        )

        print("\n" + "=" * 60)
        print("OPENROUTER GEMINI LABELER TEST RESULT")
        print("=" * 60)
        print(f"Note ID: {result.note_id}")
        print(f"Label: {result.label}")
        print(f"Style: {result.style_label}")
        print(f"Reasoning: {result.reasoning}")
        if result.error:
            print(f"Error: {result.error}")
            return False
        print("=" * 60)
        print("✅ Test PASSED!")
        return True

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        print(f"\n❌ Test FAILED: {e}")
        return False


if __name__ == "__main__":
    test_openrouter_labeler()
