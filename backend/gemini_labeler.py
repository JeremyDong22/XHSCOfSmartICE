# OpenRouter Gemini Flash Image and Content Labeling Module
# Version: 3.1 - Updated label values from 是/否 to 满足/不满足
# Changes: Changed binary labels to clearer Chinese terms for UI display
# Previous: v3.0 - Switched from direct Gemini SDK to OpenRouter API
#
# Features:
# - Binary content matching (满足/不满足) based on user description
# - Fixed image style classification (特写图/环境图/拼接图/信息图)
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


# Fixed style categories for food industry
STYLE_CATEGORIES = [
    "特写图",  # Close-up shot
    "环境图",  # Environment/Scene shot
    "拼接图",  # Collage/Composite
    "信息图",  # Infographic
]


@dataclass
class LabelingResult:
    """Structured result for a single post's labeling"""
    note_id: str
    label: str  # Binary: "满足" or "不满足"
    style_label: str  # One of: "特写图", "环境图", "拼接图", "信息图"
    reasoning: str  # Explanation in Chinese
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


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

Also classify the image style into one of these fixed categories:
- 特写图: Close-up shots focusing on the main subject (food, product details)
- 环境图: Environment/ambiance shots showing location, atmosphere, setting
- 拼接图: Collage or composite images combining multiple photos
- 信息图: Infographic style with text overlays, promotional content, lists

Output your analysis in this exact JSON format:
{{
  "label": "<满足 or 不满足>",
  "style_label": "<特写图 or 环境图 or 拼接图 or 信息图>",
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

    def label_posts_batch(
        self,
        posts: List[Dict[str, Any]],
        user_description: str,
        mode: LabelingMode = LabelingMode.COVER_IMAGE,
        max_posts: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
        include_likes: bool = False
    ) -> List[LabelingResult]:
        """
        Label multiple XHS posts in batch with binary classification.

        Args:
            posts: List of XHS post dictionaries
            user_description: User's description of what posts they want to filter
            mode: Labeling mode (what to analyze)
            max_posts: Maximum number of posts to process (None = all)
            progress_callback: Optional callback(index, total, title, status)
            include_likes: Whether to include likes count in analysis

        Returns:
            List of LabelingResult objects
        """
        if max_posts:
            posts = posts[:max_posts]

        results = []
        total = len(posts)
        for idx, post in enumerate(posts):
            title = post.get('title', 'Untitled')[:50]
            note_id = post.get('note_id', 'unknown')

            logger.info(f"Processing post {idx + 1}/{total}: {note_id}")

            if progress_callback:
                progress_callback(idx + 1, total, title, "processing")

            try:
                result = self.label_post(post, user_description, mode, include_likes)
                results.append(result)

                if progress_callback:
                    status = "error" if result.error else "done"
                    label_info = f"{result.label} ({result.style_label})"
                    progress_callback(idx + 1, total, title, f"{status}: {label_info}")

            except RateLimitError as e:
                if progress_callback:
                    progress_callback(idx + 1, total, title, f"⚠️ RATE_LIMIT: {e}")

                logger.warning(f"Rate limit hit after processing {idx} posts. Stopping batch.")
                e.processed_count = len(results)
                raise e

        return results


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
