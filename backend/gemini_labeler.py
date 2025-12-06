# Gemini Flash Image and Content Labeling Module
# Version: 2.0 - Food industry refactor: binary classification with style labels
# Changes:
# - New output format: {label: "是/否", style_label: "特写图/环境图/拼接图/信息图", reasoning: "中文解释"}
# - Binary classification based on user-provided content description
# - Fixed style categories: 特写图, 环境图, 拼接图, 信息图
# - User description becomes binary match criteria (是 or 否)
# - Transparent prompt exposure for user visibility
#
# Previous: Rate limit detection and auto-pause on 429 errors
#
# Features:
# - Binary content matching (是/否) based on user description
# - Fixed image style classification (特写图/环境图/拼接图/信息图)
# - Transparent prompting - what you see in UI is what Gemini sees
# - Structured JSON output with label, style_label, and reasoning
# - Error handling and retry logic for API calls
# - Progress callback for real-time streaming logs
# - Auto-pause on rate limit (429) errors

import os
import json
import logging
from typing import List, Dict, Any, Optional, Literal, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import google.generativeai as genai
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
    """Custom exception for Gemini API rate limit (429) errors"""
    def __init__(self, message: str, processed_count: int = 0, retry_after: int = 60):
        super().__init__(message)
        self.processed_count = processed_count
        self.retry_after = retry_after  # Suggested wait time in seconds


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
    FULL = "full"  # All images + title + content


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
    label: str  # Binary: "是" or "不是"
    style_label: str  # One of: "特写图", "环境图", "拼接图", "信息图"
    reasoning: str  # Explanation in Chinese
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class GeminiLabeler:
    """
    Gemini 2.0 Flash client for image and content labeling.

    This module provides flexible prompt engineering for categorizing XHS posts
    based on images (cover or all), text (title or content), or combinations.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.0-flash"):
        """
        Initialize Gemini labeler with API key.

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
            model_name: Gemini model to use (default: gemini-2.0-flash)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or constructor")

        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model_name = model_name

        # Create model WITHOUT system instruction - everything is transparent
        self.model = genai.GenerativeModel(model_name=model_name)

        logger.info(f"Initialized GeminiLabeler with model: {model_name} (no hidden system prompt)")

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

Based on this criteria, determine if the post matches (是) or doesn't match (否).

Also classify the image style into one of these fixed categories:
- 特写图: Close-up shots focusing on the main subject (food, product details)
- 环境图: Environment/ambiance shots showing location, atmosphere, setting
- 拼接图: Collage or composite images combining multiple photos
- 信息图: Infographic style with text overlays, promotional content, lists

Output your analysis in this exact JSON format:
{{
  "label": "<是 or 否>",
  "style_label": "<特写图 or 环境图 or 拼接图 or 信息图>",
  "reasoning": "<brief explanation in Chinese>"
}}"""

    def _download_image(self, url: str) -> Optional[Image.Image]:
        """
        Download image from URL and return PIL Image object.

        Args:
            url: Image URL to download

        Returns:
            PIL Image object or None if download fails
        """
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            return img
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {e}")
            return None

    def _prepare_content_parts(
        self,
        post: Dict[str, Any],
        mode: LabelingMode,
        full_prompt: str
    ) -> List[Any]:
        """
        Prepare content parts for Gemini API based on labeling mode.

        Args:
            post: XHS post dictionary
            mode: Labeling mode
            full_prompt: Complete prompt with instructions

        Returns:
            List of content parts (text and/or images) for Gemini
        """
        parts = [full_prompt]

        # Add images based on mode
        if mode in [LabelingMode.COVER_IMAGE, LabelingMode.COVER_IMAGE_TITLE, LabelingMode.COVER_IMAGE_CONTENT, LabelingMode.FULL]:
            cover_url = post.get("cover_image")
            if cover_url:
                img = self._download_image(cover_url)
                if img:
                    parts.append(img)
                    parts.append(f"[Cover Image URL: {cover_url}]")

        if mode in [LabelingMode.ALL_IMAGES, LabelingMode.ALL_IMAGES_TITLE, LabelingMode.ALL_IMAGES_CONTENT, LabelingMode.FULL]:
            images = post.get("images", [])
            if not images and post.get("cover_image"):
                # Fallback to cover if no images array
                images = [post["cover_image"]]

            for idx, img_url in enumerate(images):
                img = self._download_image(img_url)
                if img:
                    parts.append(img)
                    parts.append(f"[Image {idx + 1} URL: {img_url}]")

        # Add text based on mode
        if mode in [LabelingMode.TITLE, LabelingMode.TITLE_CONTENT, LabelingMode.COVER_IMAGE_TITLE,
                    LabelingMode.ALL_IMAGES_TITLE, LabelingMode.FULL]:
            title = post.get("title", "")
            if title:
                parts.append(f"\nTitle: {title}")

        if mode in [LabelingMode.CONTENT, LabelingMode.TITLE_CONTENT, LabelingMode.COVER_IMAGE_CONTENT,
                    LabelingMode.ALL_IMAGES_CONTENT, LabelingMode.FULL]:
            content = post.get("content", "")
            if content:
                parts.append(f"\nContent: {content}")

        return parts

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse JSON response from Gemini, handling potential formatting issues.

        Args:
            response_text: Raw response text from Gemini

        Returns:
            Parsed JSON dictionary (extracts first item if array is returned)
        """
        # Try to extract JSON if wrapped in markdown code blocks
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
            # Handle array responses - extract first item
            if isinstance(result, list):
                if len(result) > 0:
                    return result[0]
                else:
                    return {}
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response_text}")
            raise


    def label_post(
        self,
        post: Dict[str, Any],
        user_description: str,
        mode: LabelingMode = LabelingMode.COVER_IMAGE
    ) -> LabelingResult:
        """
        Label a single XHS post using Gemini 2.0 Flash with binary classification.

        Args:
            post: XHS post dictionary (must have note_id)
            user_description: User's description of what posts they want to filter
            mode: Labeling mode (what to analyze)

        Returns:
            LabelingResult with label (是/不是), style_label, and reasoning
        """
        note_id = post.get("note_id", "unknown")

        try:
            # Build the prompt with binary classification and style labeling
            full_prompt = self._build_prompt(user_description)

            # Prepare content parts
            content_parts = self._prepare_content_parts(post, mode, full_prompt)

            # Generate content with system instruction
            generation_config = genai.types.GenerationConfig(
                temperature=0.1,  # Low temperature for consistent categorization
                top_p=0.95,
                top_k=40,
                max_output_tokens=1024,
            )

            from google.generativeai.types import HarmCategory, HarmBlockThreshold

            safety_settings = {
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }

            response = self.model.generate_content(
                content_parts,
                generation_config=generation_config,
                safety_settings=safety_settings
            )

            # Check if response was blocked
            if not response.candidates or not response.candidates[0].content.parts:
                # Response was blocked, check why
                if hasattr(response, 'prompt_feedback'):
                    block_reason = response.prompt_feedback
                    raise ValueError(f"Response blocked: {block_reason}")
                else:
                    raise ValueError("Response blocked by safety filters")

            # Parse response
            response_text = response.text
            logger.debug(f"Gemini response for {note_id}: {response_text}")

            result_json = self._parse_json_response(response_text)

            # Extract label (是/否)
            label = result_json.get("label", "否")
            if label not in ["是", "否"]:
                logger.warning(f"Invalid label '{label}' for {note_id}, defaulting to '否'")
                label = "否"

            # Extract style_label (特写图/环境图/拼接图/信息图)
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

        except Exception as e:
            error_str = str(e)
            logger.error(f"Error labeling post {note_id}: {error_str}")

            # Check for rate limit (429) errors - re-raise as RateLimitError
            if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                # Extract retry_after if available (Gemini often suggests wait time)
                retry_after = 60  # Default 60 seconds
                if "retry" in error_str.lower():
                    # Try to extract suggested wait time from error message
                    import re
                    match = re.search(r'(\d+(?:\.\d+)?)\s*s', error_str)
                    if match:
                        retry_after = int(float(match.group(1))) + 5  # Add buffer

                raise RateLimitError(
                    f"Rate limit exceeded. Please wait {retry_after}s before retrying.",
                    retry_after=retry_after
                )

            return LabelingResult(
                note_id=note_id,
                label="否",
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
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None
    ) -> List[LabelingResult]:
        """
        Label multiple XHS posts in batch with binary classification.

        Args:
            posts: List of XHS post dictionaries
            user_description: User's description of what posts they want to filter
            mode: Labeling mode (what to analyze)
            max_posts: Maximum number of posts to process (None = all)
            progress_callback: Optional callback(index, total, title, status) for progress updates

        Returns:
            List of LabelingResult objects
        """
        if max_posts:
            posts = posts[:max_posts]

        results = []
        total = len(posts)
        for idx, post in enumerate(posts):
            title = post.get('title', 'Untitled')[:50]  # Truncate long titles
            note_id = post.get('note_id', 'unknown')

            logger.info(f"Processing post {idx + 1}/{total}: {note_id}")

            # Report progress: starting this post
            if progress_callback:
                progress_callback(idx + 1, total, title, "processing")

            try:
                result = self.label_post(post, user_description, mode)
                results.append(result)

                # Report progress: completed this post
                if progress_callback:
                    status = "error" if result.error else "done"
                    label_info = f"{result.label} ({result.style_label})"
                    progress_callback(idx + 1, total, title, f"{status}: {label_info}")

            except RateLimitError as e:
                # Send rate limit warning through progress callback
                if progress_callback:
                    progress_callback(idx + 1, total, title, f"⚠️ RATE_LIMIT: {e}")

                logger.warning(f"Rate limit hit after processing {idx} posts. Stopping batch.")

                # Update the exception with the count of successfully processed posts
                e.processed_count = len(results)
                raise e

        return results


def test_gemini_labeler():
    """
    Test function using sample data from output directory.
    Tests categorization of "Single Dish" vs "Multiple Dishes" for cover images.
    """
    logger.info("Starting Gemini Labeler test")

    # Load sample data
    sample_file = "/Users/jeremydong/Desktop/Smartice/APPs/XHSCOfSmartICE/output/爆浆蛋糕_account5_20251206_175247.json"

    with open(sample_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    posts = data.get("posts", [])
    logger.info(f"Loaded {len(posts)} posts from sample file")

    # Initialize labeler
    labeler = GeminiLabeler()

    # Define categorization
    categories = [
        "Single Dish - Image shows one main food item (e.g., one cake, one pastry)",
        "Multiple Dishes - Image shows multiple food items or a spread of different dishes"
    ]

    # Test first 3 posts
    results = labeler.label_posts_batch(
        posts=posts,
        categories=categories,
        mode=LabelingMode.COVER_IMAGE,
        max_posts=3
    )

    # Print results
    print("\n" + "="*80)
    print("GEMINI LABELING RESULTS")
    print("="*80)

    for result in results:
        print(f"\nPost ID: {result.note_id}")
        print(f"Labels: {json.dumps(result.labels, ensure_ascii=False, indent=2)}")
        print(f"Confidence: {result.confidence}")
        print(f"Reasoning: {result.reasoning}")
        if result.error:
            print(f"Error: {result.error}")
        print("-" * 80)

    # Save results to file
    output_file = "/Users/jeremydong/Desktop/Smartice/APPs/XHSCOfSmartICE/output/gemini_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(
            {
                "test_mode": "cover_image",
                "categories": categories,
                "total_posts_tested": len(results),
                "results": [r.to_dict() for r in results]
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    logger.info(f"Test results saved to: {output_file}")
    print(f"\nTest results saved to: {output_file}")

    return results


def test_advanced_labeling_modes():
    """
    Advanced test showcasing different labeling modes:
    - Title-only labeling
    - Cover Image + Title combined labeling
    - Multiple category options
    """
    logger.info("Starting Advanced Labeling Modes Test")

    # Load sample data
    sample_file = "/Users/jeremydong/Desktop/Smartice/APPs/XHSCOfSmartICE/output/爆浆蛋糕_account5_20251206_175247.json"

    with open(sample_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    posts = data.get("posts", [])[:3]
    labeler = GeminiLabeler()

    print("\n" + "="*80)
    print("ADVANCED LABELING MODES DEMO")
    print("="*80)

    # Test 1: Title-only labeling - Recipe vs Product Review
    print("\n### Test 1: Title-Only Labeling (Recipe vs Product Review)")
    print("-" * 80)

    title_categories = [
        "Recipe/DIY - Content about making food at home (e.g., '教程', '制作', '做法')",
        "Product Review - Content reviewing restaurants, stores, or products (e.g., '店名', '推荐', '测评')"
    ]

    title_results = labeler.label_posts_batch(
        posts=posts,
        categories=title_categories,
        mode=LabelingMode.TITLE,
        max_posts=3
    )

    for result in title_results:
        post = next(p for p in posts if p['note_id'] == result.note_id)
        print(f"\nTitle: {post['title']}")
        print(f"Label: {result.labels.get('title_label', 'N/A')}")
        print(f"Confidence: {result.confidence}")
        print(f"Reasoning: {result.reasoning}")

    # Test 2: Cover Image + Title combined - Premium vs Budget
    print("\n\n### Test 2: Cover Image + Title Combined (Premium vs Budget)")
    print("-" * 80)

    combined_categories = [
        "Premium/Luxury - High-end presentation, elaborate plating, upscale environment",
        "Casual/Homestyle - Simple presentation, home-cooked feel, everyday dining"
    ]

    combined_results = labeler.label_posts_batch(
        posts=posts,
        categories=combined_categories,
        mode=LabelingMode.COVER_IMAGE_TITLE,
        max_posts=3
    )

    for result in combined_results:
        post = next(p for p in posts if p['note_id'] == result.note_id)
        print(f"\nTitle: {post['title']}")
        print(f"Label: {result.labels.get('cover_image_label', 'N/A')}")
        print(f"Confidence: {result.confidence}")
        print(f"Reasoning: {result.reasoning}")

    # Save all results
    output_file = "/Users/jeremydong/Desktop/Smartice/APPs/XHSCOfSmartICE/output/gemini_advanced_test_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(
            {
                "test_1_title_only": {
                    "mode": "title",
                    "categories": title_categories,
                    "results": [r.to_dict() for r in title_results]
                },
                "test_2_combined": {
                    "mode": "cover_image_title",
                    "categories": combined_categories,
                    "results": [r.to_dict() for r in combined_results]
                }
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    logger.info(f"Advanced test results saved to: {output_file}")
    print(f"\n\nAdvanced test results saved to: {output_file}")


if __name__ == "__main__":
    # Run basic test
    print("Running basic test...")
    test_gemini_labeler()

    # Run advanced test
    print("\n\nRunning advanced labeling modes test...")
    test_advanced_labeling_modes()
