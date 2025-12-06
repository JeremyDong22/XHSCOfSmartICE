# Data Cleaning Service with Gemini Integration
# Version: 1.5 - Re-export RateLimitError for API layer to catch
# Changes: Import and propagate RateLimitError from gemini_labeler
# Previous: Added progress callback support for real-time log streaming

import os
import json
import logging
from typing import List, Dict, Any, Optional, Literal, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

from gemini_labeler import GeminiLabeler, LabelingMode, LabelingResult, RateLimitError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Output directory for cleaned results
CLEANED_OUTPUT_DIR = Path(__file__).parent.parent / "cleaned_output"
CLEANED_OUTPUT_DIR.mkdir(exist_ok=True)


@dataclass
class FilterByCondition:
    """Filter condition for pre-filtering posts before labeling"""
    metric: Literal["likes", "collects", "comments"]
    operator: Literal["gte", "lte", "gt", "lt", "eq"]
    value: int

    def passes(self, post: Dict[str, Any]) -> bool:
        """Check if a post passes the filter condition"""
        metric_value = post.get(self.metric, 0)

        if self.operator == "gte":
            return metric_value >= self.value
        elif self.operator == "lte":
            return metric_value <= self.value
        elif self.operator == "gt":
            return metric_value > self.value
        elif self.operator == "lt":
            return metric_value < self.value
        elif self.operator == "eq":
            return metric_value == self.value

        return False


@dataclass
class LabelCategory:
    """Label category with name and description"""
    name: str         # Short label name for output (e.g., "single_food")
    description: str  # Detailed description for AI inference criteria


@dataclass
class LabelByCondition:
    """Label condition for Gemini categorization"""
    image_target: Optional[Literal["cover_image", "images"]]
    text_target: Optional[Literal["title", "content"]]
    categories: List[LabelCategory]  # User-defined categories with name and description
    prompt: str  # User's categorization prompt/instruction

    def to_labeling_mode(self) -> LabelingMode:
        """Convert UI selections to GeminiLabeler LabelingMode"""
        # Map combinations to appropriate mode
        if self.image_target == "cover_image" and self.text_target is None:
            return LabelingMode.COVER_IMAGE
        elif self.image_target == "images" and self.text_target is None:
            return LabelingMode.ALL_IMAGES
        elif self.image_target is None and self.text_target == "title":
            return LabelingMode.TITLE
        elif self.image_target is None and self.text_target == "content":
            return LabelingMode.CONTENT
        elif self.image_target == "cover_image" and self.text_target == "title":
            return LabelingMode.COVER_IMAGE_TITLE
        elif self.image_target == "cover_image" and self.text_target == "content":
            return LabelingMode.COVER_IMAGE_CONTENT
        elif self.image_target == "images" and self.text_target == "title":
            return LabelingMode.ALL_IMAGES_TITLE
        elif self.image_target == "images" and self.text_target == "content":
            return LabelingMode.ALL_IMAGES_CONTENT
        else:
            # Default to cover image if unclear
            logger.warning(f"Unknown combination: image={self.image_target}, text={self.text_target}. Defaulting to COVER_IMAGE")
            return LabelingMode.COVER_IMAGE


@dataclass
class CleaningConfig:
    """Configuration for data cleaning task"""
    source_files: List[str]  # Paths to input JSON files
    filter_by: Optional[FilterByCondition] = None
    label_by: Optional[LabelByCondition] = None
    output_filename: Optional[str] = None  # If None, auto-generated


class DataCleaningService:
    """
    Service for cleaning and labeling XHS scrape results.

    Features:
    - Filter posts by metrics (likes, collects, comments) before labeling
    - Label posts using Gemini with flexible image/text combinations
    - Combine multiple result files into one cleaned output
    - Track metadata (processing time, filter/label conditions, etc.)
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        """
        Initialize data cleaning service.

        Args:
            gemini_api_key: Optional Gemini API key (defaults to env var)
        """
        self.gemini_api_key = gemini_api_key
        self.labeler: Optional[GeminiLabeler] = None

    def _load_posts_from_files(self, filepaths: List[str]) -> tuple[List[Dict[str, Any]], List[str]]:
        """
        Load posts from multiple JSON files.

        Args:
            filepaths: List of absolute file paths to load

        Returns:
            Tuple of (combined posts list, successfully loaded filenames)
        """
        all_posts = []
        loaded_files = []

        for filepath in filepaths:
            if not os.path.exists(filepath):
                logger.warning(f"File not found: {filepath}")
                continue

            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    posts = data.get("posts", [])
                    all_posts.extend(posts)
                    loaded_files.append(os.path.basename(filepath))
                    logger.info(f"Loaded {len(posts)} posts from {os.path.basename(filepath)}")
            except Exception as e:
                logger.error(f"Failed to load {filepath}: {e}")

        return all_posts, loaded_files

    def _apply_filter(
        self,
        posts: List[Dict[str, Any]],
        filter_condition: FilterByCondition
    ) -> List[Dict[str, Any]]:
        """
        Apply filter condition to posts.

        Args:
            posts: List of post dictionaries
            filter_condition: Filter condition to apply

        Returns:
            Filtered list of posts
        """
        filtered = [p for p in posts if filter_condition.passes(p)]
        logger.info(f"Filter applied: {len(posts)} posts -> {len(filtered)} posts (removed {len(posts) - len(filtered)})")
        return filtered

    def _apply_labels(
        self,
        posts: List[Dict[str, Any]],
        label_condition: LabelByCondition,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Apply Gemini labeling to posts.

        Args:
            posts: List of post dictionaries
            label_condition: Label condition with categories and targets
            progress_callback: Optional callback(message) for progress updates

        Returns:
            Posts with added label fields
        """
        # Initialize labeler if not already done
        if self.labeler is None:
            self.labeler = GeminiLabeler(api_key=self.gemini_api_key)

        # Get labeling mode
        mode = label_condition.to_labeling_mode()
        logger.info(f"Starting labeling with mode: {mode.value}")

        # Create a wrapper callback that converts labeler's callback format to string messages
        def labeler_progress(idx: int, total: int, title: str, status: str):
            if progress_callback:
                progress_callback(f"[{idx}/{total}] {title} - {status}")

        # Run batch labeling - pass user's prompt directly to Gemini (transparent prompting)
        results: List[LabelingResult] = self.labeler.label_posts_batch(
            posts=posts,
            categories=label_condition.categories,
            mode=mode,
            user_prompt=label_condition.prompt,
            progress_callback=labeler_progress
        )

        # Merge labels back into posts
        labeled_posts = []
        for post, result in zip(posts, results):
            # Create a copy of the post
            labeled_post = post.copy()

            # Add label fields
            labeled_post["labels"] = result.labels
            labeled_post["label_confidence"] = result.confidence
            labeled_post["label_reasoning"] = result.reasoning

            if result.error:
                labeled_post["label_error"] = result.error

            labeled_posts.append(labeled_post)

        logger.info(f"Labeled {len(labeled_posts)} posts")
        return labeled_posts

    def clean_and_label(
        self,
        config: CleaningConfig,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute full cleaning and labeling pipeline.

        Args:
            config: Cleaning configuration
            progress_callback: Optional callback(message) for progress updates

        Returns:
            Dictionary with metadata and processed posts
        """
        start_time = datetime.now()

        def log(msg: str):
            logger.info(msg)
            if progress_callback:
                progress_callback(msg)

        # Step 1: Load posts from files
        log(f"Loading posts from {len(config.source_files)} file(s)...")
        all_posts, loaded_files = self._load_posts_from_files(config.source_files)
        total_input = len(all_posts)
        log(f"Total posts loaded: {total_input}")

        # Step 2: Apply filter (if enabled)
        if config.filter_by:
            log(f"Applying filter: {config.filter_by.metric} {config.filter_by.operator} {config.filter_by.value}")
            all_posts = self._apply_filter(all_posts, config.filter_by)
            log(f"After filter: {len(all_posts)} posts remaining")

        # Step 3: Apply labels (if enabled)
        if config.label_by:
            log(f"Starting labeling with {len(config.label_by.categories)} categories...")
            all_posts = self._apply_labels(all_posts, config.label_by, progress_callback)

        # Step 4: Calculate processing time
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        # Step 5: Build output structure
        result = {
            "metadata": {
                "cleaned_at": end_time.isoformat(),
                "processed_by": self.labeler.model_name if self.labeler else "no_labeling",
                "processing_time_seconds": round(processing_time, 2),
                "original_files": loaded_files,
                "total_posts_input": total_input,
                "total_posts_output": len(all_posts)
            },
            "posts": all_posts
        }

        # Add filter condition metadata
        if config.filter_by:
            result["metadata"]["filter_by_condition"] = {
                "metric": config.filter_by.metric,
                "operator": config.filter_by.operator,
                "value": config.filter_by.value
            }

        # Add label condition metadata
        if config.label_by:
            # Convert LabelCategory dataclass objects to dicts for JSON serialization
            categories_as_dicts = [
                {"name": cat.name, "description": cat.description}
                for cat in config.label_by.categories
            ]
            result["metadata"]["label_by_condition"] = {
                "image_target": config.label_by.image_target,
                "text_target": config.label_by.text_target,
                "label_count": len(config.label_by.categories),
                "prompt": config.label_by.prompt,
                "categories": categories_as_dicts
            }

        logger.info(f"Cleaning complete in {processing_time:.2f}s: {total_input} -> {len(all_posts)} posts")
        return result

    def save_cleaned_result(self, result: Dict[str, Any], output_filename: Optional[str] = None) -> str:
        """
        Save cleaned result to JSON file.

        Args:
            result: Cleaned result dictionary
            output_filename: Optional filename (auto-generated if None)

        Returns:
            Absolute path to saved file
        """
        if output_filename is None:
            # Auto-generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"cleaned_{timestamp}.json"

        output_path = CLEANED_OUTPUT_DIR / output_filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved cleaned result to: {output_path}")
        return str(output_path)


def test_data_cleaning_service():
    """
    Test function using sample data from output directory.
    Tests filtering by likes >= 70 and labeling with cover_image + title.
    """
    logger.info("Starting Data Cleaning Service test")

    # Initialize service
    service = DataCleaningService()

    # Sample file
    sample_file = "/Users/jeremydong/Desktop/Smartice/APPs/XHSCOfSmartICE/output/爆浆蛋糕_account5_20251206_175247.json"

    # Create config
    config = CleaningConfig(
        source_files=[sample_file],
        filter_by=FilterByCondition(
            metric="likes",
            operator="gte",
            value=70
        ),
        label_by=LabelByCondition(
            image_target="cover_image",
            text_target="title",
            categories=[
                "Single Dish - Image shows one main food item (e.g., one cake, one pastry)",
                "Multiple Dishes - Image shows multiple food items or a spread of different dishes"
            ],
            prompt="Categorize based on whether the cover image and title represent a single dish or multiple dishes"
        )
    )

    # Run cleaning
    result = service.clean_and_label(config)

    # Save result
    output_path = service.save_cleaned_result(result, output_filename="test_cleaned_result.json")

    # Print summary
    print("\n" + "="*80)
    print("DATA CLEANING TEST RESULTS")
    print("="*80)
    print(f"\nOutput file: {output_path}")
    print(f"\nMetadata:")
    print(json.dumps(result["metadata"], ensure_ascii=False, indent=2))
    print(f"\nSample labeled post (first result):")
    if result["posts"]:
        sample_post = result["posts"][0]
        print(f"  Title: {sample_post['title']}")
        print(f"  Likes: {sample_post['likes']}")
        print(f"  Labels: {json.dumps(sample_post.get('labels', {}), ensure_ascii=False, indent=4)}")
        print(f"  Confidence: {sample_post.get('label_confidence', 'N/A')}")
        print(f"  Reasoning: {sample_post.get('label_reasoning', 'N/A')}")
    print("="*80)

    return result


if __name__ == "__main__":
    test_data_cleaning_service()
