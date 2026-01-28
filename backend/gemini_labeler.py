# OpenRouter Gemini Flash Image and Content Labeling Module
# Version: 5.8 - Switch VisionStruct to Gemini 2.5 Flash for cost savings
# Changes:
#   - Switch VISION_STRUCT_MODEL from Gemini 3 Flash to Gemini 2.5 Flash (~25% cost savings)
#   - Add cost tracking fields to LabelingResult, VisionStructResult, BatchResult
#   - Capture usage.cost from OpenRouter API responses
#   - VisionStruct uses Gemini 2.5 Flash (balance), labeling uses 2.0 Flash (cheapest)
# Previous: v5.6 - Optimized VisionStruct prompt with 6-phase analysis framework
#
# Features:
# - Concurrent batch processing with configurable parallelism (default: 5)
# - Binary content matching (满足/不满足) based on user description
# - 5 mutually exclusive style categories (人物图/特写图/环境图/拼接图/信息图)
# - VisionStruct detailed image analysis for comprehensive visual element extraction
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
import time
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

# VisionStruct prompt for detailed image analysis (vision-to-JSON)
# Extended with food_analysis section for ingredient/presentation analysis
VISION_STRUCT_PROMPT = """You are VisionStruct, an advanced Computer Vision & Data Serialization Engine. Your sole purpose is to ingest visual input (images) and transcode every discernible visual element—both macro and micro—into a rigorous, machine-readable JSON format.

CORE DIRECTIVE

Do not summarize. Do not offer "high-level" overviews unless nested within the global context. You must capture 100% of the visual data available in the image. If a detail exists in pixels, it must exist in your JSON output. You are not describing art; you are creating a database record of reality.

ANALYSIS PROTOCOL (6-PHASE FRAMEWORK)

Before generating the final JSON, perform a silent analysis (do not output this):

PHASE 1 - MACRO IDENTIFICATION:
- Identify the dish, cuisine type, and meal category
- List all visible ingredients and their cooking states
- Determine cooking methods used

PHASE 2 - MICRO-TEXTURE ANALYSIS:
For each major element, analyze:
- Surface texture (glossy, matte, crispy, smooth, rough, grainy)
- Moisture indicators (dry, moist, glistening, dripping)
- Temperature cues (steam, condensation, melting, frosting)
- Light interaction (specular highlights, subsurface scattering, translucency)

PHASE 3 - COLOR FORENSICS:
- Extract dominant colors as hex codes
- Note color gradients (caramelization, browning, char marks)
- Assess color temperature and saturation

PHASE 4 - DYNAMIC STATE INDICATORS:
Look for evidence of:
- Steam/vapor (location, intensity, direction)
- Flowing/dripping elements (sauces, cheese, oils)
- Melting states (ice cream, butter, cheese)
- Bubbling/sizzling indicators

PHASE 5 - COMPOSITION ANALYSIS:
- Plating style and arrangement
- Focal point and visual hierarchy
- Use of negative space
- Height and depth variation

PHASE 6 - LIGHTING TECHNICAL DETAILS:
- Light direction (use clock face: "2 o'clock position")
- Light quality (hard, soft, diffused)
- Shadow characteristics
- Highlight placement

OUTPUT FORMAT (STRICT)

You must return ONLY a single valid JSON object. Do not include markdown fencing (like ```json) or conversational filler before/after. Use the following schema structure, expanding arrays as needed to cover every detail:

{
  "meta": {
    "image_quality": "Low/Medium/High",
    "image_type": "Photo/Illustration/Diagram/Screenshot/etc",
    "resolution_estimation": "Approximate resolution if discernable"
  },

  "global_context": {
    "scene_description": "A comprehensive, objective paragraph describing the entire scene.",
    "time_of_day": "Specific time or lighting condition",
    "weather_atmosphere": "Foggy/Clear/Rainy/Chaotic/Serene",
    "lighting": {
      "source": "Sunlight/Artificial/Mixed",
      "direction": "Use clock face position: 10 o'clock, 2 o'clock, directly above, etc.",
      "quality": "Hard (sharp shadows)/Soft (diffused)/Dramatic (high contrast)",
      "color_temp": "Warm (2700-3500K)/Neutral (4000-5000K)/Cool (5500K+)",
      "color_temp_kelvin": "Estimated Kelvin value if discernible",
      "shadow_characteristics": "Harsh/Soft/Minimal/None - describe shadow edges and density",
      "highlight_locations": ["List where light catches and creates bright spots"]
    }
  },

  "color_palette": {
    "dominant_hex_estimates": ["#RRGGBB", "#RRGGBB"],
    "accent_colors": ["Color name 1", "Color name 2"],
    "contrast_level": "High/Low/Medium"
  },

  "composition": {
    "camera_angle": "Eye-level/High-angle/Low-angle/Macro",
    "depth_of_field": "Shallow (blurry background) / Deep (everything in focus)",
    "focal_point": "The primary element drawing the eye"
  },

  "objects": [
    {
      "id": "obj_001",
      "label": "Primary Object Name",
      "category": "Person/Vehicle/Furniture/Food/Dishware/Decoration/etc",
      "location": "Center/Top-Left/etc",
      "prominence": "Foreground/Background",
      "visual_attributes": {
        "color": "Detailed color description",
        "texture": "Rough/Smooth/Metallic/Fabric-type",
        "material": "Wood/Plastic/Skin/Ceramic/Glass/etc",
        "state": "Damaged/New/Wet/Dirty/Hot/Cold/Fresh",
        "dimensions_relative": "Large relative to frame"
      },
      "micro_details": [
        "Scuff mark on left corner",
        "stitching pattern visible on hem",
        "reflection of window in surface",
        "dust particles visible"
      ],
      "pose_or_orientation": "Standing/Tilted/Facing away",
      "text_content": null
    }
  ],

  "food_analysis": {
    "dish_category": "Describe the type of dish (e.g., soup, stir-fry, dessert, beverage, hot pot, BBQ, noodles)",
    "cuisine_style": "Describe the cuisine style or origin if identifiable",
    "cooking_methods": ["List all cooking methods visible or inferred: grilled, fried, steamed, baked, raw, braised, stir-fried, deep-fried, poached, smoked, etc."],

    "ingredients": [
      {
        "id": "ing_001",
        "name": "Ingredient name in both Chinese and English if possible",
        "role": "Describe the role: main ingredient, side ingredient, garnish, sauce, topping, etc.",
        "state": "Describe the state: raw, cooked, melted, crispy, flowing, steaming, caramelized, charred, etc.",
        "visual_cues": ["List visual details that indicate freshness, doneness, or appeal"],
        "quantity": "Specific count or amount if discernible (e.g., 3 shrimp, 5 slices, a handful)",
        "size": "Describe the size: large/medium/small, or estimated dimensions",
        "shape": "Describe the shape: round, rectangular, irregular, curled, flat, etc.",
        "cut_style": "Describe how it's cut or prepared: sliced, diced, whole, shredded, minced, julienned, etc.",
        "surface_texture": {
          "glossiness": "Describe shine level: glossy/matte/wet/oily",
          "roughness": "Describe surface: smooth/rough/bumpy/crispy-textured",
          "moisture": "Describe wetness: dry/moist/wet/dripping",
          "light_interaction": "How light interacts with surface: specular highlights (bright reflections), subsurface scattering (light penetrating translucent materials like meat/fruit), translucency, diffuse reflection"
        },
        "edge_condition": "Describe edges: crispy edges, charred edges, clean cut, torn, frayed, caramelized rim, etc.",
        "temperature_cues": "Visual indicators of temperature: steam rising, condensation, melting, frozen crystals, etc.",
        "color_gradient": "Describe color variations within the ingredient: browning on edges, pink center, gradient from cooked to raw, etc.",
        "visual_prominence": "0-1 score indicating how visually prominent this ingredient is in the frame (1.0 = dominant focal point, 0.1 = barely visible)",
        "position": {
          "absolute": "Where in the dish: center, left, right, top, bottom, scattered",
          "layer": "Which layer: bottom layer, middle layer, top layer, floating, submerged",
          "relative_to_others": ["Describe position relative to other ingredients: on top of X, next to Y, underneath Z, surrounded by W"]
        }
      }
    ],

    "sauce_analysis": {
      "present": true,
      "type": "Describe the sauce type: curry, gravy, broth, dressing, glaze, etc.",
      "color": "Describe sauce color with detail",
      "consistency": "Describe thickness: watery, thin, medium, thick, paste-like, gelatinous",
      "coverage": "Describe how sauce covers the dish: pooled at bottom, drizzled on top, coating everything, partial coverage",
      "surface_details": "Describe sauce surface: oil droplets floating, bubbles, skin forming, herbs visible, etc.",
      "flow_state": "Describe if sauce appears to be flowing, dripping, or static"
    },

    "presentation": {
      "plating_style": "Describe how the food is arranged: stacked, scattered, layered, circular, radial, linear, etc.",
      "portion_impression": "Describe the overall portion size impression",
      "height_dimension": "Describe the vertical dimension: tall/flat/layered, estimated height",
      "density": "Describe how packed or sparse the arrangement is",
      "symmetry": "Describe symmetry: symmetrical, asymmetrical, random, deliberate chaos",
      "focal_point": "What element draws the eye first",
      "color_harmony": "Describe how colors work together in the dish",
      "negative_space": "Describe use of empty space on the plate/bowl",
      "overflow_state": "Describe if food overflows the vessel or is contained within",
      "layering_description": "Describe the layer structure from bottom to top"
    },

    "dishware": {
      "type": "Describe the vessel: bowl, plate, cup, pot, wooden board, stone slab, banana leaf, etc.",
      "material": "Describe the material: ceramic, porcelain, metal, wood, glass, stone, bamboo, etc.",
      "style": "Describe the aesthetic style: traditional, modern, rustic, minimalist, industrial, vintage, etc.",
      "color": "Describe the dishware color and any patterns",
      "shape": "Describe the shape: round, square, oval, irregular, deep, shallow",
      "rim_style": "Describe the rim: wide rim, no rim, curved lip, straight edge",
      "condition": "New/Worn/Vintage/Chipped/etc.",
      "size_relative_to_food": "How the dishware size relates to the food portion: oversized plate, snug fit, overflowing",
      "fill_level": "How full is the vessel: 1/4, 1/2, 3/4, full, overflowing"
    },

    "decoration_elements": [
      {
        "element": "Name of decorative element (herbs, citrus, seeds, sauce drizzle, edible flowers, etc.)",
        "quantity": "How many or how much",
        "placement": "Describe where and how it's placed: scattered on top, single piece on side, ring around edge",
        "state": "Fresh/wilted/fried/dried/frozen",
        "purpose": "Describe its visual or flavor purpose: color contrast, freshness indicator, texture addition"
      }
    ],

    "appetite_triggers": [
      "List ALL visual elements that trigger appetite - be exhaustive:",
      "- Steam/vapor: describe density, direction, visibility",
      "- Glossy surfaces: where exactly, what's causing the shine",
      "- Melting: what's melting, how far along",
      "- Dripping/flowing: what liquid, from where to where",
      "- Bubbling/sizzling: location, intensity",
      "- Char marks/grill lines: pattern, color",
      "- Crispy textures: visible crunch indicators",
      "- Cheese pull/stretch: if applicable",
      "- Juice release: from cut meat, fruit, etc.",
      "- Caramelization: where, what color",
      "- Fresh condensation/water droplets: on what surfaces"
    ],

    "texture_contrast": "Describe ALL contrasting textures visible: crispy vs soft, smooth vs chunky, liquid vs solid, etc.",

    "aroma_indicators": "Describe visual cues that suggest aroma: steam carrying spices, visible herb oils, toasted elements, etc.",

    "dynamic_elements": {
      "steam_vapor": {
        "present": true,
        "location": "Where steam is rising from",
        "density": "Wispy/Light/Medium/Dense/Billowing",
        "direction": "Rising straight up/Drifting left/Swirling",
        "visibility": "Barely visible/Clearly visible/Prominent"
      },
      "flowing_dripping": {
        "present": true,
        "substance": "What is flowing: sauce, cheese, yolk, juice, etc.",
        "source": "Where it's flowing from",
        "destination": "Where it's flowing to",
        "viscosity": "Thin and fast/Slow and thick/Stretchy"
      },
      "melting": {
        "present": true,
        "element": "What is melting: cheese, butter, ice cream, etc.",
        "stage": "Just starting/Halfway/Almost fully melted",
        "pooling": "Is it pooling? Where?"
      },
      "bubbling_sizzling": {
        "present": true,
        "location": "Where bubbles/sizzle is visible",
        "intensity": "Gentle/Active/Vigorous",
        "bubble_size": "Tiny/Small/Large"
      }
    },

    "quality_metrics": {
      "visual_appeal_score": "1-10 score for overall visual appeal and appetite-triggering power",
      "professional_quality": "true/false - Does this look professionally photographed?",
      "style_tags": ["List style descriptors: rustic, modern, elegant, comfort food, gourmet, homestyle, street food, fine dining, etc."],
      "instagram_worthiness": "1-10 score for social media appeal"
    }
  },

  "text_ocr": {
    "present": true,
    "content": [
      {
        "text": "The exact text written",
        "location": "Sign post/T-shirt/Screen",
        "font_style": "Serif/Handwritten/Bold",
        "legibility": "Clear/Partially obscured"
      }
    ]
  },

  "semantic_relationships": [
    "Object A is supporting Object B",
    "Object C is casting a shadow on Object A",
    "Object D is visually similar to Object E",
    "Ingredient X is layered on top of Ingredient Y",
    "Sauce is pooling around the main dish"
  ]
}

CRITICAL CONSTRAINTS

Granularity: Never say "a crowd of people." Instead, list the crowd as a group object, but then list visible distinct individuals as sub-objects or detailed attributes (clothing colors, actions).

Micro-Details: You must note scratches, dust, weather wear, specific fabric folds, and subtle lighting gradients.

Food-Specific Details: For food images, you MUST populate the food_analysis section with exhaustive detail:
- Every visible ingredient must be listed with visual_prominence score
- Every appetite-triggering detail (steam, gloss, drip, char, melt) must be captured in dynamic_elements
- Light interaction (specular highlights, subsurface scattering) must be described for glossy/translucent foods
- Provide quality_metrics with visual_appeal_score (1-10)

Null Values: If a field is not applicable (e.g., food_analysis for non-food images), set it to null rather than omitting it, to maintain schema consistency.

Objectivity: Be measurable and specific with visual data points. Avoid subjective language - describe what you see, not how it makes you feel."""


@dataclass
class LabelingResult:
    """Structured result for a single post's labeling"""
    note_id: str
    label: str  # Binary: "满足" or "不满足"
    style_label: str  # One of: "人物图", "特写图", "环境图", "拼接图", "信息图"
    reasoning: str  # Explanation in Chinese
    error: Optional[str] = None
    cost: float = 0.0  # API cost in USD from OpenRouter

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VisionStructResult:
    """Structured result for VisionStruct image analysis"""
    note_id: str
    vision_struct: Optional[Dict[str, Any]] = None  # Full VisionStruct JSON
    error: Optional[str] = None
    cost: float = 0.0  # API cost in USD from OpenRouter

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
    total_cost: float = 0.0  # Total API cost in USD from OpenRouter

    def to_dict(self) -> dict:
        return {
            "total_posts": self.total_posts,
            "successful_count": self.successful_count,
            "error_count": self.error_count,
            "is_partial": self.is_partial,
            "interrupted_reason": self.interrupted_reason,
            "interrupted_at_index": self.interrupted_at_index,
            "total_cost": self.total_cost
        }


class GeminiLabeler:
    """
    Gemini 2.0 Flash client via OpenRouter for image and content labeling.

    This module provides flexible prompt engineering for categorizing XHS posts
    based on images (cover or all), text (title or content), or combinations.
    Uses OpenRouter API to access Google's Gemini 2.0 Flash model.

    Model selection:
    - Labeling (text/image classification): Gemini 2.0 Flash (cheaper, $0.0005/image)
    - VisionStruct (detailed vision-to-JSON): Gemini 3 Flash (better reasoning, $0.0026/image)
    """

    # OpenRouter API configuration
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL = "google/gemini-2.0-flash-001"  # For labeling (cheaper)
    VISION_STRUCT_MODEL = "google/gemini-2.5-flash-preview"  # For VisionStruct (balance of cost/quality)

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

        # Create session - keep system proxy (Cloudflare blocks direct connections)
        # Retry logic handles intermittent proxy failures
        self.session = requests.Session()
        # trust_env=True (default) to use HTTP_PROXY/HTTPS_PROXY env vars
        self.session.headers.update(self.headers)

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
            response = self.session.get(url, headers=headers, timeout=10)
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

            # Make the API request with retry logic for connection errors
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.session.post(
                        self.OPENROUTER_BASE_URL,
                        json=payload,
                        timeout=60
                    )
                    break  # Success, exit retry loop
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # 2s, 4s backoff
                        logger.warning(f"Connection error for {note_id}, retry {attempt + 1}/{max_retries} in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        raise  # Re-raise on final attempt

            if response is None:
                raise ValueError("No response received after retries")

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

            # Extract cost from OpenRouter response (in USD)
            api_cost = 0.0
            if 'usage' in response_data:
                api_cost = response_data['usage'].get('cost', 0.0) or 0.0

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
                reasoning=reasoning,
                cost=api_cost
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

    def analyze_vision_struct(
        self,
        post: Dict[str, Any],
    ) -> VisionStructResult:
        """
        Generate detailed VisionStruct JSON analysis for a single post's cover image.
        Uses VISION_STRUCT_PROMPT for comprehensive image-to-JSON conversion.

        Args:
            post: XHS post dictionary (must have note_id and cover_image)

        Returns:
            VisionStructResult with vision_struct JSON or error
        """
        note_id = post.get("note_id", "unknown")

        try:
            # Get cover image URL
            cover_url = post.get("cover_image")
            if not cover_url:
                return VisionStructResult(
                    note_id=note_id,
                    vision_struct=None,
                    error="No cover image available"
                )

            # Download and encode image
            base64_url = self._download_image_as_base64(cover_url)
            if not base64_url:
                return VisionStructResult(
                    note_id=note_id,
                    vision_struct=None,
                    error="Failed to download cover image"
                )

            # Prepare content parts with VisionStruct prompt
            content_parts = [
                {"type": "text", "text": VISION_STRUCT_PROMPT},
                {"type": "image_url", "image_url": {"url": base64_url}}
            ]

            # Build the request payload - use VISION_STRUCT_MODEL (Gemini 2.5 Flash) for balance of cost/quality
            payload = {
                "model": self.VISION_STRUCT_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": content_parts
                    }
                ],
                "temperature": 0.1,
                "top_p": 0.95,
                "max_tokens": 4096  # Larger for detailed VisionStruct output
            }

            # Make the API request with retry logic for connection errors
            max_retries = 3
            response = None
            for attempt in range(max_retries):
                try:
                    response = self.session.post(
                        self.OPENROUTER_BASE_URL,
                        json=payload,
                        timeout=120  # Longer timeout for detailed analysis
                    )
                    break  # Success, exit retry loop
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        logger.warning(f"VisionStruct connection error for {note_id}, retry {attempt + 1}/{max_retries} in {wait_time}s: {e}")
                        time.sleep(wait_time)
                    else:
                        raise

            if response is None:
                raise ValueError("No response received after retries")

            # Log error details for debugging
            if response.status_code >= 400:
                logger.error(f"VisionStruct API error {response.status_code}: {response.text}")

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

            # Extract cost from OpenRouter response (in USD)
            api_cost = 0.0
            if 'usage' in response_data:
                api_cost = response_data['usage'].get('cost', 0.0) or 0.0

            # Extract the message content
            if 'choices' not in response_data or len(response_data['choices']) == 0:
                raise ValueError("No response choices returned from API")

            response_text = response_data['choices'][0]['message']['content']
            logger.debug(f"VisionStruct API response for {note_id}: {response_text[:200]}...")

            # Parse JSON response
            vision_struct_json = self._parse_json_response(response_text)

            return VisionStructResult(
                note_id=note_id,
                vision_struct=vision_struct_json,
                error=None,
                cost=api_cost
            )

        except RateLimitError:
            raise
        except Exception as e:
            error_str = str(e)
            logger.error(f"Error analyzing VisionStruct for {note_id}: {error_str}")

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

            return VisionStructResult(
                note_id=note_id,
                vision_struct=None,
                error=error_str
            )

    def analyze_vision_struct_batch(
        self,
        posts: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
        max_concurrency: int = 3  # Lower default for detailed analysis
    ) -> List[VisionStructResult]:
        """
        Run VisionStruct analysis on multiple posts with concurrent processing.

        Args:
            posts: List of XHS post dictionaries
            progress_callback: Optional callback(index, total, title, status)
            max_concurrency: Maximum parallel API calls (default: 3)

        Returns:
            List of VisionStructResult in same order as input posts
        """
        total = len(posts)
        results: List[Optional[VisionStructResult]] = [None] * total
        completed_count = 0
        rate_limit_hit = False
        lock = threading.Lock()

        logger.info(f"Starting VisionStruct batch analysis: {total} posts, concurrency={max_concurrency}")

        def process_single(idx: int, post: Dict[str, Any]) -> tuple[int, VisionStructResult]:
            """Process a single post and return (index, result)"""
            nonlocal rate_limit_hit

            # Skip if rate limit already hit
            if rate_limit_hit:
                return idx, VisionStructResult(
                    note_id=post.get('note_id', 'unknown'),
                    vision_struct=None,
                    error="Skipped due to rate limit"
                )

            try:
                result = self.analyze_vision_struct(post)
                return idx, result
            except RateLimitError as e:
                with lock:
                    rate_limit_hit = True
                return idx, VisionStructResult(
                    note_id=post.get('note_id', 'unknown'),
                    vision_struct=None,
                    error=f"Rate limit: {e}"
                )

        def update_progress(idx: int, result: VisionStructResult):
            """Thread-safe progress update"""
            nonlocal completed_count
            with lock:
                completed_count += 1
                title = posts[idx].get('title', 'Untitled')[:50]
                if progress_callback:
                    if result.error:
                        status = f"vision_struct error: {result.error[:30]}"
                    else:
                        status = "vision_struct done"
                    progress_callback(completed_count, total, title, status)

        # Execute with ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            futures = {
                executor.submit(process_single, idx, post): idx
                for idx, post in enumerate(posts)
            }

            for future in as_completed(futures):
                try:
                    idx, result = future.result()
                    results[idx] = result
                    update_progress(idx, result)
                except Exception as e:
                    idx = futures[future]
                    note_id = posts[idx].get('note_id', 'unknown')
                    error_result = VisionStructResult(
                        note_id=note_id,
                        vision_struct=None,
                        error=str(e)
                    )
                    results[idx] = error_result
                    update_progress(idx, error_result)

        final_results = [r for r in results if r is not None]
        success_count = sum(1 for r in final_results if r.vision_struct is not None)
        logger.info(f"VisionStruct batch complete: {success_count}/{total} successful")

        return final_results

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
        # Calculate total cost from all results
        total_cost = sum(r.cost for r in final_results if r is not None)

        logger.info(f"Batch complete: {success_count}/{total} successful, {error_count} errors, partial={rate_limit_hit}, cost=${total_cost:.4f}")

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
            interrupted_at_index=interrupted_index,
            total_cost=total_cost
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
