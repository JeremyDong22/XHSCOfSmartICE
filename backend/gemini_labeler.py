# Gemini Flash Image and Content Labeling Module
# Version: 1.0 - Initial implementation for XHS post categorization
# Changes: Created Gemini API integration with flexible prompt engineering for multi-modal labeling
# - Supports multiple labeling modes (cover image, all images, title, content, combinations)
# - Uses gemini-flash-latest model with system instructions for structured JSON output
# - Handles safety settings, error handling, and image downloading
# - Provides batch labeling with user-defined categories
#
# Features:
# - Supports multiple labeling modes: cover image, all images, title, content, or combinations
# - Flexible categorization with user-defined prompts
# - Structured JSON output with labels, confidence, and reasoning
# - Error handling and retry logic for API calls

import os
import json
import logging
from typing import List, Dict, Any, Optional, Literal
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


@dataclass
class LabelingResult:
    """Structured result for a single post's labeling"""
    note_id: str
    labels: Dict[str, str]  # e.g., {"cover_image_label": "Single Dish"}
    confidence: float  # 0.0 to 1.0
    reasoning: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class GeminiLabeler:
    """
    Gemini 2.0 Flash client for image and content labeling.

    This module provides flexible prompt engineering for categorizing XHS posts
    based on images (cover or all), text (title or content), or combinations.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-flash-latest"):
        """
        Initialize Gemini labeler with API key.

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY env var)
            model_name: Gemini model to use (default: gemini-flash-latest)
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment or constructor")

        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model_name = model_name

        # Create model with system instruction for output format
        system_instruction = self._build_system_prompt()
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )

        logger.info(f"Initialized GeminiLabeler with model: {model_name}")

    def _build_system_prompt(self) -> str:
        """
        Build the system instruction for output format.

        Returns:
            System prompt string defining JSON output format
        """
        return """You are an expert content categorization assistant. Analyze the provided content and categorize it according to the user's instructions.

CRITICAL: You MUST respond with ONLY a valid JSON object. Do not include any text before or after the JSON.

Your response MUST follow this exact JSON structure:
{
  "labels": {
    "cover_image_label": "Category Name",
    "title_label": "Category Name",
    "content_label": "Category Name",
    "images_label": "Category Name"
  },
  "confidence": 0.95,
  "reasoning": "Brief explanation of why you chose these categories"
}

Rules:
- Only include label fields that are relevant to the analysis mode
- confidence should be between 0.0 and 1.0
- reasoning should be 1-2 sentences maximum
- All category names must exactly match one of the categories provided by the user
- If uncertain, choose the closest matching category and lower the confidence score"""

    def _build_categorization_prompt(self, categories: List[str], mode: LabelingMode) -> str:
        """
        Build the user-defined categorization prompt.

        Args:
            categories: List of category descriptions (e.g., ["Single Dish - One main item", "Multiple Dishes - Multiple items"])
            mode: Labeling mode to determine what to analyze

        Returns:
            Categorization prompt string
        """
        mode_instructions = {
            LabelingMode.COVER_IMAGE: "Analyze the cover image and categorize it.",
            LabelingMode.ALL_IMAGES: "Analyze all provided images and categorize them collectively.",
            LabelingMode.TITLE: "Analyze the title text and categorize it.",
            LabelingMode.CONTENT: "Analyze the content text and categorize it.",
            LabelingMode.TITLE_CONTENT: "Analyze both the title and content text and categorize them.",
            LabelingMode.COVER_IMAGE_TITLE: "Analyze the cover image and title together and categorize them.",
            LabelingMode.COVER_IMAGE_CONTENT: "Analyze the cover image and content text together and categorize them.",
            LabelingMode.ALL_IMAGES_TITLE: "Analyze all images and title together and categorize them.",
            LabelingMode.ALL_IMAGES_CONTENT: "Analyze all images and content text together and categorize them.",
            LabelingMode.FULL: "Analyze all images, title, and content together and categorize them."
        }

        instruction = mode_instructions.get(mode, "Analyze the provided content and categorize it.")

        # Format categories list
        categories_text = "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(categories)])

        return f"""{instruction}

Available categories:
{categories_text}

Choose the most appropriate category based on the content provided."""

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
        categorization_prompt: str
    ) -> List[Any]:
        """
        Prepare content parts for Gemini API based on labeling mode.

        Args:
            post: XHS post dictionary
            mode: Labeling mode
            categorization_prompt: User categorization instructions

        Returns:
            List of content parts (text and/or images) for Gemini
        """
        parts = [categorization_prompt]

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
            Parsed JSON dictionary
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
            return json.loads(text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response_text}")
            raise

    def label_post(
        self,
        post: Dict[str, Any],
        categories: List[str],
        mode: LabelingMode = LabelingMode.COVER_IMAGE
    ) -> LabelingResult:
        """
        Label a single XHS post using Gemini 2.0 Flash.

        Args:
            post: XHS post dictionary (must have note_id)
            categories: List of category descriptions
            mode: Labeling mode (what to analyze)

        Returns:
            LabelingResult with labels, confidence, and reasoning
        """
        note_id = post.get("note_id", "unknown")

        try:
            # Build prompts
            categorization_prompt = self._build_categorization_prompt(categories, mode)

            # Prepare content parts
            content_parts = self._prepare_content_parts(post, mode, categorization_prompt)

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

            # Validate structure
            if "labels" not in result_json or "confidence" not in result_json or "reasoning" not in result_json:
                raise ValueError(f"Response missing required fields: {result_json}")

            return LabelingResult(
                note_id=note_id,
                labels=result_json["labels"],
                confidence=float(result_json["confidence"]),
                reasoning=result_json["reasoning"]
            )

        except Exception as e:
            logger.error(f"Error labeling post {note_id}: {e}")
            return LabelingResult(
                note_id=note_id,
                labels={},
                confidence=0.0,
                reasoning="",
                error=str(e)
            )

    def label_posts_batch(
        self,
        posts: List[Dict[str, Any]],
        categories: List[str],
        mode: LabelingMode = LabelingMode.COVER_IMAGE,
        max_posts: Optional[int] = None
    ) -> List[LabelingResult]:
        """
        Label multiple XHS posts in batch.

        Args:
            posts: List of XHS post dictionaries
            categories: List of category descriptions
            mode: Labeling mode (what to analyze)
            max_posts: Maximum number of posts to process (None = all)

        Returns:
            List of LabelingResult objects
        """
        if max_posts:
            posts = posts[:max_posts]

        results = []
        for idx, post in enumerate(posts):
            logger.info(f"Processing post {idx + 1}/{len(posts)}: {post.get('note_id', 'unknown')}")
            result = self.label_post(post, categories, mode)
            results.append(result)

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
