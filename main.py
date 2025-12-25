from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
import os
import requests
import base64
import time
import uvicorn
import json
import re
from io import BytesIO
from fastapi.responses import StreamingResponse, FileResponse
from fastapi import Header
import logging
import uuid
from datetime import datetime, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image as PILImage
from google import genai
from google.genai import types
from google.genai.types import Image as GeminiImage
from story_lib import generate_story
from typing import List, Optional, Dict, Any
from queue_manager import QueueManager
from batch_processor import BatchProcessor
from validation_utils import ConsistencyValidationResult
from audio_generator import AudioGenerator
import asyncio
from contextlib import asynccontextmanager

# Import security utilities
from rate_limiter import limiter, rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from security_utils import sanitize_input, sanitize_filename, validate_email, validate_phone, encrypt_data, decrypt_data
from virus_scanner import get_virus_scanner
import jwt
import stripe
from email_service import EmailService

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === CONFIG ===
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# MODEL = "gemini-2.5-flash"
MODEL = "gemini-3-pro-image-preview"
GEMINI_TEXT_MODEL = "gemini-2.5-flash"  # Model for text generation (scenes)

# Supabase Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Service role key for storage operations
STORAGE_BUCKET = "images"

# Security Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", os.getenv("JWT_SECRET", "change-this-in-production"))
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

# CORS Configuration - use environment variables for production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "*").split(",")

# Production mode check
IS_PRODUCTION = os.getenv("ENVIRONMENT", "development") == "production"

# Stripe Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID_MONTHLY = os.getenv("STRIPE_PRICE_ID_MONTHLY", "")
STRIPE_PRICE_ID_YEARLY = os.getenv("STRIPE_PRICE_ID_YEARLY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

# Initialize Stripe
if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
    logger.info("✅ Stripe initialized successfully")
else:
    logger.warning("⚠️ STRIPE_SECRET_KEY not found. Stripe payments will be disabled.")

# Initialize Gemini client
gemini_client = None
if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        logger.info("✅ Gemini client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini client: {e}")
else:
    logger.warning("⚠️ GEMINI_API_KEY not found. Image generation will be disabled.")

supabase: Client = None
if SUPABASE_URL:
    # Try service key first (bypasses RLS), then anon key
    key_to_use = SUPABASE_SERVICE_KEY if SUPABASE_SERVICE_KEY else SUPABASE_ANON_KEY
    key_type = "service" if SUPABASE_SERVICE_KEY else "anon"
    
    if key_to_use:
        try:
            supabase = create_client(SUPABASE_URL, key_to_use)
            logger.info(f"✅ Supabase client initialized successfully using {key_type} key")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase client: {e}")
    else:
        logger.warning("⚠️ No Supabase key found (SUPABASE_ANON_KEY or SUPABASE_SERVICE_KEY)")
else:
    logger.warning("⚠️ Supabase URL not found. Storage upload will be disabled.")

# Initialize queue manager and batch processor
queue_manager = None
batch_processor = None
worker_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for background tasks"""
    global queue_manager, batch_processor, worker_task
    
    # Initialize queue manager
    if supabase:
        queue_manager = QueueManager(supabase)
        batch_processor = BatchProcessor(
            queue_manager=queue_manager,
            gemini_client=gemini_client,
            openai_api_key=OPENAI_API_KEY,
            supabase_client=supabase,
            gemini_text_model=GEMINI_TEXT_MODEL
        )
        logger.info("✅ Queue manager and batch processor initialized")
        
        # Start background worker
        worker_task = asyncio.create_task(background_worker())
        logger.info("✅ Background worker started")
    
    yield
    
    # Cleanup
    if worker_task:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        logger.info("✅ Background worker stopped")

# FastAPI app
app = FastAPI(
    title="AI Image Editor API",
    description="API for editing images using Google Gemini's image generation capabilities",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response

# Add trusted host middleware (helps prevent invalid requests)
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=ALLOWED_HOSTS
)

# Add CORS middleware with environment-based configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=[]
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


# Global exception handler for better error handling
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception handler caught: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred"}
    )

# Handle validation errors
@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    logger.warning(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": "Invalid request format or data"}
    )

# Request model to receive input data
class ImageRequest(BaseModel):
    image_url: HttpUrl  # This validates the URL format
    prompt: str
    
    class Config:
        # Example values for API documentation
        schema_extra = {
            "example": {
                "image_url": "https://example.com/image.jpg",
                "prompt": "Make this image more colorful and vibrant"
            }
        }

# Response model for image editing
class ImageResponse(BaseModel):
    success: bool
    message: str
    storage_info: dict = None
    quality_validation: Optional[Dict[str, Any]] = None

# Response model for quality validation
class QualityValidationResponse(BaseModel):
    success: bool
    validation: Dict[str, Any]
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "validation": {
                    "is_valid": True,
                    "quality_score": 0.85,
                    "is_appropriate": True,
                    "is_clear": True,
                    "has_sufficient_detail": True,
                    "issues": [],
                    "recommendations": ["Image quality is good"],
                    "details": {
                        "image_properties": {
                            "actual_resolution": "1024x768",
                            "format": "JPEG",
                            "clarity": "high"
                        }
                    }
                }
            }
        }
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Image edited and uploaded successfully",
                "storage_info": {
                    "uploaded": True,
                    "url": "https://your-project.supabase.co/storage/v1/object/public/images/edited_image_123.jpg",
                    "filename": "edited_image_123.jpg",
                    "bucket": "images"
                }
            }
        }

# Request model for story generation
class StoryRequest(BaseModel):
    character_name: str
    character_type: str
    special_ability: str
    age_group: str  # Must be "3-6", "7-10", or "11-12"
    story_world: str
    adventure_type: str
    occasion_theme: Optional[str] = None
    character_image_url: Optional[HttpUrl] = None  # Supabase URL of the character reference image
    story_text_prompt: Optional[str] = None  # Full prompt for story text generation (from frontend)
    scene_prompts: Optional[List[str]] = None  # List of 5 scene prompts, one for each page (from frontend)
    reading_level: Optional[str] = None  # Reading level (early_reader / developing_reader / independent_reader)
    story_title: Optional[str] = None  # Story title
    
    class Config:
        schema_extra = {
            "example": {
                "character_name": "Luna",
                "character_type": "a brave dragon",
                "special_ability": "fly through clouds",
                "age_group": "7-10",
                "story_world": "the Enchanted Forest",
                "adventure_type": "treasure hunt",
                "occasion_theme": None,
                "character_image_url": "https://your-project.supabase.co/storage/v1/object/public/images/character_reference.jpg",
                "story_text_prompt": "Create a personalized 5-page children's storybook...",
                "scene_prompts": ["Scene prompt for page 1...", "Scene prompt for page 2...", ...],
                "reading_level": "developing_reader",
                "story_title": "The Great Adventure of Luna"
            }
        }

# Page model for story pages with text and scene image
class StoryPage(BaseModel):
    text: str
    scene: Optional[HttpUrl] = None  # URL to the generated scene image
    audio: Optional[HttpUrl] = None  # URL to the generated audio file
    consistency_validation: Optional[ConsistencyValidationResult] = None
    
    class Config:
        schema_extra = {
            "example": {
                "text": "Meet Luna, a brave dragon who loves adventures. Luna has a special power: Luna can fly through clouds.",
                "scene": "https://your-project.supabase.co/storage/v1/object/public/images/story_scene_page1_20240101_120000_abc123.jpg",
                "consistency_validation": {
                    "is_consistent": True,
                    "similarity_score": 0.85,
                    "validation_time_seconds": 3.2,
                    "flagged": False
                }
            }
        }

# Response model for story generation
class StoryResponse(BaseModel):
    success: bool
    pages: List[StoryPage]
    full_story: str
    word_count: int
    page_word_counts: List[int]
    consistency_summary: Optional[Dict[str, Any]] = None  # Overall validation summary
    audio_urls: Optional[List[Optional[str]]] = None  # List of audio URLs (one per page, None if failed)
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "pages": [
                    {
                        "text": "Meet Luna, a brave dragon who loves adventures. Luna has a special power: Luna can fly through clouds.",
                        "scene": "https://your-project.supabase.co/storage/v1/object/public/images/story_scene_page1_20240101_120000_abc123.jpg"
                    },
                    {
                        "text": "While exploring, Luna discovered a magical entrance that led to the Enchanted Forest.",
                        "scene": "https://your-project.supabase.co/storage/v1/object/public/images/story_scene_page2_20240101_120001_def456.jpg"
                    },
                    {
                        "text": "Suddenly, Luna realized that a treasure hunt was beginning, and Luna was right in the middle of it.",
                        "scene": "https://your-project.supabase.co/storage/v1/object/public/images/story_scene_page3_20240101_120002_ghi789.jpg"
                    },
                    {
                        "text": "When the moment of truth arrived, Luna faced the challenge head-on, even though it seemed impossible at first.",
                        "scene": "https://your-project.supabase.co/storage/v1/object/public/images/story_scene_page4_20240101_120003_jkl012.jpg"
                    },
                    {
                        "text": "The adventure came to a wonderful conclusion, and Luna felt proud of what had been accomplished.",
                        "scene": "https://your-project.supabase.co/storage/v1/object/public/images/story_scene_page5_20240101_120004_mno345.jpg"
                    }
                ],
                "full_story": "Meet Luna, a brave dragon who loves adventures...",
                "word_count": 250,
                "page_word_counts": [20, 25, 30, 28, 27]
            }
        }

def get_content_type_from_url(url):
    """Determine content type based on URL extension"""
    url_lower = url.lower()
    if url_lower.endswith(('.png', '.PNG')):
        return "image/png"
    elif url_lower.endswith(('.jpg', '.jpeg', '.JPG', '.JPEG')):
        return "image/jpeg"
    elif url_lower.endswith(('.gif', '.GIF')):
        return "image/gif"
    elif url_lower.endswith(('.webp', '.WEBP')):
        return "image/webp"
    else:
        return "image/jpeg"  # default fallback

def detect_image_mime_type(image_data: bytes) -> str:
    """Detect MIME type from image bytes using PIL"""
    try:
        image = PILImage.open(BytesIO(image_data))
        format_to_mime = {
            'PNG': 'image/png',
            'JPEG': 'image/jpeg',
            'JPG': 'image/jpeg',
            'GIF': 'image/gif',
            'WEBP': 'image/webp',
            'BMP': 'image/bmp',
            'TIFF': 'image/tiff'
        }
        return format_to_mime.get(image.format, 'image/jpeg')
    except Exception as e:
        logger.warning(f"Could not detect image format, defaulting to image/jpeg: {e}")
        return "image/jpeg"

def download_image_from_url(url):
    """Download image from URL and return image data"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to download image from URL {url}: {e}")

def optimize_image_to_jpg(image_data: bytes, quality: int = 85) -> bytes:
    """Convert and optimize image to JPG format with compression while preserving original resolution"""
    try:
        # Open image from bytes
        image = PILImage.open(BytesIO(image_data))
        original_size_info = f"{image.width}x{image.height}"
        
        # Convert to RGB if necessary (PNG with transparency, etc.)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Create white background for transparent images
            background = PILImage.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            if image.mode in ('RGBA', 'LA'):
                background.paste(image, mask=image.split()[-1])  # Use alpha channel as mask
                image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Save as JPG with compression (keeping original resolution)
        output_buffer = BytesIO()
        image.save(output_buffer, format='JPEG', quality=quality, optimize=True)
        optimized_data = output_buffer.getvalue()
        
        # Log compression results
        original_size = len(image_data)
        optimized_size = len(optimized_data)
        compression_ratio = (1 - optimized_size / original_size) * 100
        logger.info(f"Image optimized ({original_size_info}): {original_size:,} bytes → {optimized_size:,} bytes ({compression_ratio:.1f}% reduction)")
        
        return optimized_data
        
    except Exception as e:
        logger.error(f"Error optimizing image: {e}")
        # Return original data if optimization fails
        return image_data

def upload_to_supabase(image_data: bytes, filename: str, use_signed_url: bool = True) -> dict:
    """Upload image to Supabase storage and return signed or public URL"""
    if not supabase:
        logger.warning("Supabase client not available, skipping upload")
        return {"uploaded": False, "url": None, "message": "Supabase not configured"}

    try:
        # Sanitize filename
        filename = sanitize_filename(filename)
        logger.info(f"Uploading {filename} to Supabase storage bucket '{STORAGE_BUCKET}'")

        # Scan file for viruses
        scanner = get_virus_scanner()
        scan_result = scanner.scan_file(image_data, filename)
        if not scan_result["is_safe"]:
            logger.error(f"❌ File failed security scan: {scan_result['threats_found']}")
            return {
                "uploaded": False,
                "url": None,
                "message": f"File failed security scan: {', '.join(scan_result['threats_found'])}"
            }

        # Pass image_data directly as bytes to Supabase storage
        response = supabase.storage.from_(STORAGE_BUCKET).upload(filename, image_data, {
            'content-type' : 'image/jpeg',
            'upsert' : 'true'
        })

        # Check response type - response is an UploadResponse object
        if hasattr(response, 'full_path') and response.full_path:
            # Use signed URL with 30-day expiry for production
            if use_signed_url and IS_PRODUCTION:
                try:
                    signed_url_response = supabase.storage.from_(STORAGE_BUCKET).create_signed_url(
                        filename,
                        60 * 60 * 24 * 30  # 30 days in seconds
                    )
                    if signed_url_response and 'signedURL' in signed_url_response:
                        url = signed_url_response['signedURL']
                        logger.info(f"✅ Successfully uploaded with signed URL (30-day expiry)")
                    else:
                        # Fallback to public URL
                        url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(filename)
                        logger.warning("⚠️ Signed URL failed, using public URL")
                except Exception as e:
                    logger.warning(f"⚠️ Signed URL creation failed: {e}, using public URL")
                    url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(filename)
            else:
                url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(filename)
            
            logger.info(f"✅ Successfully uploaded to Supabase: {url[:100]}...")

            return {
                "uploaded": True,
                "url": url,
                "filename": filename,
                "bucket": STORAGE_BUCKET,
                "message": "Successfully uploaded to Supabase storage",
                "security_scan": scan_result
            }

        logger.error(f"❌ Unexpected Supabase response: {response}")
        return {"uploaded": False, "url": None, "message": f"Unexpected response: {response}"}

    except Exception as e:
        logger.error(f"❌ Error uploading to Supabase: {e}")
        return {"uploaded": False, "url": None, "message": f"Upload error: {e}"}

def edit_image(image_data, prompt, image_url=None):
    """Send image to Gemini API for editing/generation"""
    if not gemini_client:
        raise HTTPException(status_code=500, detail="Gemini client not initialized. Please check GEMINI_API_KEY.")
    
    logger.info(f"Sending request to Gemini API with model: {MODEL}")
    
    try:
        start_time = time.time()
        
        # Detect MIME type from image data
        mime_type = detect_image_mime_type(image_data)
        logger.info(f"Detected image MIME type: {mime_type}")
        
        # Encode image to base64 for the dictionary format
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Generate content with Gemini API using the expected dictionary format
        # The API expects contents to be a list with role and parts
        response = gemini_client.models.generate_content(
            model=MODEL,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_base64
                            }
                        }
                    ]
                }
            ],
            config=types.GenerateContentConfig(
                response_modalities=['TEXT', 'IMAGE']
            )
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Gemini API response received in {elapsed:.2f} seconds")
        
        # Extract image from response
        # Prioritize inline_data as it's the most direct source of image bytes
        edited_image_bytes = None
        for part in response.parts:
            if part.text is not None:
                logger.info(f"Gemini text response: {part.text}")
            
            # Check inline_data first - this is the most reliable source
            if hasattr(part, 'inline_data'):
                try:
                    inline_data = part.inline_data
                    logger.info(f"Found inline_data, type: {type(inline_data)}")
                    
                    # Try to get data from inline_data
                    if inline_data and hasattr(inline_data, 'data'):
                        data = inline_data.data
                        if isinstance(data, bytes):
                            edited_image_bytes = data
                            logger.info(f"✅ Image extracted from inline_data.data (bytes) ({len(edited_image_bytes)} bytes)")
                        elif isinstance(data, str):
                            # Try to decode base64
                            try:
                                edited_image_bytes = base64.b64decode(data)
                                logger.info(f"✅ Image extracted from inline_data.data (base64) ({len(edited_image_bytes)} bytes)")
                            except Exception as e:
                                logger.warning(f"Failed to decode base64 data: {e}")
                                # If it's not base64, try encoding as latin-1 (unlikely but possible)
                                edited_image_bytes = data.encode('latin-1')
                                logger.info(f"✅ Image extracted from inline_data.data (string) ({len(edited_image_bytes)} bytes)")
                    elif inline_data and hasattr(inline_data, 'bytes'):
                        edited_image_bytes = inline_data.bytes
                        logger.info(f"✅ Image extracted from inline_data.bytes ({len(edited_image_bytes)} bytes)")
                    
                    # Validate the extracted data
                    if edited_image_bytes and len(edited_image_bytes) > 1000:
                        logger.info(f"✅ Valid image extracted from inline_data ({len(edited_image_bytes)} bytes)")
                        break
                    elif edited_image_bytes:
                        logger.warning(f"Extracted data from inline_data is suspiciously small ({len(edited_image_bytes)} bytes), trying other methods...")
                        edited_image_bytes = None  # Reset to try other methods
                    else:
                        logger.warning(f"inline_data exists but no valid data found. inline_data attributes: {[a for a in dir(inline_data) if not a.startswith('_')]}")
                except Exception as e:
                    logger.warning(f"Error extracting from inline_data: {e}")
                    import traceback
                    logger.debug(f"Traceback: {traceback.format_exc()}")
            
            # Fallback to as_image() if inline_data didn't work
            if not edited_image_bytes and hasattr(part, 'as_image'):
                try:
                    gemini_image = part.as_image()
                    logger.info(f"Got Gemini Image object: {type(gemini_image)}")
                    
                    # Check if it's already a PIL Image
                    if isinstance(gemini_image, PILImage.Image):
                        img_buffer = BytesIO()
                        gemini_image.save(img_buffer, format='PNG')
                        edited_image_bytes = img_buffer.getvalue()
                        logger.info(f"✅ Image extracted from PIL Image ({len(edited_image_bytes)} bytes)")
                        break
                    # Try to get bytes from Gemini Image object
                    elif hasattr(gemini_image, 'to_bytes'):
                        edited_image_bytes = gemini_image.to_bytes()
                    elif hasattr(gemini_image, 'bytes'):
                        edited_image_bytes = gemini_image.bytes
                    elif hasattr(gemini_image, 'data'):
                        data = gemini_image.data
                        if isinstance(data, bytes):
                            edited_image_bytes = data
                        elif isinstance(data, str):
                            edited_image_bytes = base64.b64decode(data)
                    else:
                        # Log available attributes for debugging
                        attrs = [a for a in dir(gemini_image) if not a.startswith('_')]
                        logger.warning(f"Gemini Image object attributes: {attrs}")
                        # Try accessing mime_type and data if they exist
                        if hasattr(gemini_image, 'mime_type') and hasattr(gemini_image, 'data'):
                            if isinstance(gemini_image.data, bytes):
                                edited_image_bytes = gemini_image.data
                            elif isinstance(gemini_image.data, str):
                                edited_image_bytes = base64.b64decode(gemini_image.data)
                    
                    # Validate size before accepting
                    if edited_image_bytes and len(edited_image_bytes) > 1000:
                        logger.info(f"✅ Image extracted from as_image() ({len(edited_image_bytes)} bytes)")
                        break
                    elif edited_image_bytes:
                        logger.warning(f"Extracted data from as_image() too small ({len(edited_image_bytes)} bytes), trying other methods...")
                        edited_image_bytes = None  # Reset to try other methods
                except Exception as e:
                    logger.warning(f"Error extracting from as_image(): {e}")
                    import traceback
                    logger.debug(f"Traceback: {traceback.format_exc()}")
        
        if not edited_image_bytes:
            # Log more details for debugging
            logger.error(f"No valid image found in response. Response has {len(response.parts)} parts")
            for i, part in enumerate(response.parts):
                part_type = type(part).__name__
                attrs = [a for a in dir(part) if not a.startswith('_')]
                logger.error(f"Part {i}: type={part_type}, attributes={attrs}")
                # Try to log more details about each part
                if hasattr(part, 'inline_data'):
                    logger.error(f"  Part {i} inline_data: {part.inline_data}")
                if hasattr(part, 'text'):
                    logger.error(f"  Part {i} text: {part.text}")
            raise HTTPException(status_code=500, detail="No valid image was generated in the response from Gemini API")
        
        # Validate that we have a valid image before returning
        try:
            test_image = PILImage.open(BytesIO(edited_image_bytes))
            logger.info(f"✅ Validated image: {test_image.size[0]}x{test_image.size[1]}, format: {test_image.format}")
        except Exception as e:
            logger.error(f"Extracted data is not a valid image: {e}")
            raise HTTPException(status_code=500, detail=f"Invalid image data extracted from Gemini API response: {str(e)}")
        
        return edited_image_bytes
        
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        raise HTTPException(status_code=500, detail=f"Error from Gemini API: {str(e)}")

def validate_character_consistency(scene_image_data: bytes, reference_image_data: bytes, page_number: int, timeout_seconds: int = 15) -> ConsistencyValidationResult:
    """Wrapper for validation_utils.validate_character_consistency"""
    from validation_utils import validate_character_consistency as _validate_character_consistency
    return _validate_character_consistency(
        scene_image_data=scene_image_data,
        reference_image_data=reference_image_data,
        page_number=page_number,
        gemini_client=gemini_client,
        gemini_text_model=GEMINI_TEXT_MODEL,
        timeout_seconds=timeout_seconds
    )


def validate_image_quality(image_data: bytes, image_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate image quality using Gemini Vision API.
    Checks for: image quality, appropriateness, clarity, and basic properties.
    
    Returns a dictionary with validation results including:
    - is_valid: bool
    - quality_score: float (0-1)
    - issues: List[str]
    - recommendations: List[str]
    - details: Dict with specific checks
    """
    if not gemini_client:
        logger.warning("Gemini client not available for quality validation")
        return {
            "is_valid": True,  # Default to valid if validation unavailable
            "quality_score": 0.5,
            "issues": [],
            "recommendations": ["Quality validation unavailable - Gemini client not initialized"],
            "details": {"validation_available": False}
        }
    
    try:
        logger.info("Starting image quality validation with Gemini Vision API")
        
        # Detect MIME type
        mime_type = detect_image_mime_type(image_data)
        
        # Encode image to base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Create validation prompt
        validation_prompt = """Analyze this image and provide a quality assessment in the following JSON format:
{
  "quality_score": <float 0.0-1.0>,
  "is_appropriate": <boolean>,
  "is_clear": <boolean>,
  "has_sufficient_detail": <boolean>,
  "issues": [<array of issue strings>],
  "recommendations": [<array of recommendation strings>],
  "image_properties": {
    "estimated_resolution": "<width>x<height>",
    "clarity": "<low/medium/high>",
    "brightness": "<too_dark/normal/too_bright>",
    "composition": "<poor/fair/good/excellent>"
  }
}

Focus on:
1. Image clarity and sharpness
2. Appropriate content for children (no violence, adult content, etc.)
3. Sufficient detail and resolution
4. Overall visual quality
5. Any technical issues (blur, distortion, artifacts)

Be strict but fair. Return ONLY valid JSON, no additional text."""
        
        # Call Gemini API for validation
        response = gemini_client.models.generate_content(
            model=GEMINI_TEXT_MODEL,  # Use text model for analysis
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": validation_prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_base64
                            }
                        }
                    ]
                }
            ],
            config=types.GenerateContentConfig(
                response_modalities=['TEXT'],
                temperature=0.1  # Lower temperature for more consistent validation
            )
        )
        
        # Extract text response
        validation_text = ""
        for part in response.parts:
            if part.text:
                validation_text += part.text
        
        # Parse JSON response
        # Try to extract JSON from response (in case there's extra text)
        json_match = re.search(r'\{.*\}', validation_text, re.DOTALL)
        if json_match:
            validation_json = json.loads(json_match.group())
        else:
            # Try parsing the whole response
            validation_json = json.loads(validation_text)
        
        # Extract validation results
        quality_score = validation_json.get("quality_score", 0.5)
        is_appropriate = validation_json.get("is_appropriate", True)
        is_clear = validation_json.get("is_clear", True)
        has_sufficient_detail = validation_json.get("has_sufficient_detail", True)
        issues = validation_json.get("issues", [])
        recommendations = validation_json.get("recommendations", [])
        image_properties = validation_json.get("image_properties", {})
        
        # Determine overall validity
        # Image is valid if: appropriate, clear, and quality score > 0.5
        is_valid = (
            is_appropriate and 
            is_clear and 
            quality_score >= 0.5 and
            has_sufficient_detail
        )
        
        # Add basic image properties from PIL
        try:
            pil_image = PILImage.open(BytesIO(image_data))
            image_properties["actual_resolution"] = f"{pil_image.width}x{pil_image.height}"
            image_properties["format"] = pil_image.format or "unknown"
            image_properties["mode"] = pil_image.mode
            image_properties["file_size_bytes"] = len(image_data)
        except Exception as e:
            logger.warning(f"Could not extract PIL image properties: {e}")
        
        result = {
            "is_valid": is_valid,
            "quality_score": quality_score,
            "is_appropriate": is_appropriate,
            "is_clear": is_clear,
            "has_sufficient_detail": has_sufficient_detail,
            "issues": issues,
            "recommendations": recommendations,
            "details": {
                "image_properties": image_properties,
                "validation_available": True,
                "model_used": GEMINI_TEXT_MODEL
            }
        }
        
        logger.info(f"Quality validation completed: valid={is_valid}, score={quality_score:.2f}")
        if issues:
            logger.info(f"Validation issues found: {', '.join(issues)}")
        
        return result
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse validation JSON response: {e}")
        logger.error(f"Response text: {validation_text[:500] if 'validation_text' in locals() else 'N/A'}")
        return {
            "is_valid": True,  # Default to valid on parse error
            "quality_score": 0.5,
            "issues": ["Could not parse validation response"],
            "recommendations": ["Validation service error - proceeding with caution"],
            "details": {"validation_available": False, "error": "JSON parse error"}
        }
    except Exception as e:
        logger.error(f"Error during quality validation: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return {
            "is_valid": True,  # Default to valid on error
            "quality_score": 0.5,
            "issues": [f"Validation error: {str(e)}"],
            "recommendations": ["Validation service error - proceeding with caution"],
            "details": {"validation_available": False, "error": str(e)}
        }

def create_blank_base_image(width: int = 768, height: int = 512) -> bytes:
    """Create a blank white image in 768x512 dimensions to use as base for image generation"""
    try:
        # Create a white image in 768x512 dimensions (default)
        blank_image = PILImage.new('RGB', (width, height), color=(255, 255, 255))
        img_buffer = BytesIO()
        blank_image.save(img_buffer, format='PNG')
        return img_buffer.getvalue()
    except Exception as e:
        logger.error(f"Error creating blank base image: {e}")
        raise

def get_environment_details(story_world: str) -> str:
    """Get environment-specific details based on story world."""
    world_lower = story_world.lower()
    if 'enchanted forest' in world_lower or world_lower == 'forest':
        return "ENVIRONMENT DETAILS: Include magical trees with glowing elements, mystical flora, enchanted atmosphere with soft magical light, fairy-tale forest setting with whimsical details."
    elif 'outer space' in world_lower or world_lower == 'space':
        return "ENVIRONMENT DETAILS: Include planets, stars, alien landscapes, cosmic scenery, space nebulas, celestial bodies, and otherworldly terrain."
    elif 'underwater kingdom' in world_lower or world_lower == 'underwater':
        return "ENVIRONMENT DETAILS: Include coral reefs, sea creatures, underwater flora, aquatic plants, marine life, and oceanic elements."
    else:
        return "ENVIRONMENT DETAILS: Match the setting and atmosphere of the story world."

def generate_story_scene_image(story_page_text: str, page_number: int, character_name: str, character_type: str, story_world: str, reference_image_url: Optional[str] = None, scene_prompt: Optional[str] = None) -> str:
    """Generate a scene image for a story page using edit_image function and return the image URL.
    
    If scene_prompt is provided, use it; otherwise generate prompt from parameters.
    """
    if not gemini_client:
        logger.warning("Gemini client not available, returning empty scene URL")
        return ""
    
    logger.info(f"Generating scene image for page {page_number} using edit_image function")
    if reference_image_url:
        logger.info(f"Using reference character image from: {reference_image_url}")
    
    try:
        # Get base image - use reference image if provided, otherwise create a blank image
        base_image_data = None
        if reference_image_url:
            try:
                logger.info(f"Downloading reference image from: {reference_image_url}")
                base_image_data = download_image_from_url(reference_image_url)
                logger.info(f"✅ Reference image downloaded successfully ({len(base_image_data)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to download reference image, creating blank base image: {e}")
                base_image_data = None
        
        # If no reference image, create a blank white image in 768x512 dimensions
        if not base_image_data:
            logger.info("Creating blank base image for scene generation")
            base_image_data = create_blank_base_image()
            logger.info(f"✅ Blank base image created ({len(base_image_data)} bytes)")
        
        # Use provided prompt if available, otherwise generate one (for backward compatibility)
        if scene_prompt:
            prompt = scene_prompt
            logger.info(f"Using scene prompt from frontend for page {page_number}")
        else:
            # Fallback: generate prompt from parameters (for backward compatibility)
            character_reference_note = ""
            character_consistency_enforcement = ""
            negative_prompts = ""
            
            if reference_image_url and base_image_data:
                character_reference_note = f"""
CHARACTER REFERENCE:
- A reference image of {character_name} is provided below
- Use this reference image to maintain consistent character appearance across all scenes
- The character in the scene must match the appearance, style, and features shown in the reference image
- Keep the character's visual identity consistent with the reference image
"""
                character_consistency_enforcement = f"""
=== MANDATORY CHARACTER STYLE CONSISTENCY REQUIREMENTS ===
CRITICAL: The character from the provided reference image MUST be embedded with EXACT visual fidelity.

REQUIRED CHARACTER FEATURES (DO NOT CHANGE):
* Face: Exact same facial features, eye shape, nose, mouth, and expression style as reference
* Limbs: Exact same proportions, length, and structure as reference
* Body proportions: Exact same height-to-width ratio and body shape as reference
* Hair: Exact same hair style, color, texture, and length as reference
* Skin tone: Exact same skin color and tone as reference
* Clothing: Exact same clothing design, colors, patterns, and details as reference
* Overall design: Exact same character design language, style, and visual identity as reference
* Anatomy: Exact same anatomical structure - no changes to bone structure, muscle definition, or body type
* Style: The character's artistic style must remain consistent with the reference image

STRICT PROHIBITIONS:
* DO NOT alter the character's facial features
* DO NOT change the character's body proportions or anatomy
* DO NOT modify the character's hair style, color, or texture
* DO NOT change the character's skin tone or color
* DO NOT alter the character's clothing design, colors, or patterns
* DO NOT modify the character's overall design or visual identity
* DO NOT apply different artistic styles to the character than what appears in the reference
* DO NOT distort, stretch, or resize the character in ways that change their appearance
* DO NOT add features not present in the reference image
* DO NOT remove features present in the reference image

ENFORCEMENT:
The character must be reproduced with pixel-perfect fidelity to the reference image. Any deviation from the reference character's appearance is strictly prohibited. The scene style may vary, but the character's appearance must remain identical to the reference image in all aspects.
"""
                negative_prompts = """
=== NEGATIVE PROMPTS (STRICTLY AVOID) ===
DO NOT:
* Alter the character's facial features, proportions, or anatomy
* Change the character's hair style, color, or texture
* Modify the character's skin tone or color
* Alter the character's clothing design, colors, or patterns
* Change the character's body proportions or structure
* Apply different artistic styles to the character than the reference
* Distort, stretch, or resize the character in ways that change appearance
* Add features not present in the reference image
* Remove features present in the reference image
* Create variations of the character - use the exact reference character only
"""
            
            environment_details = get_environment_details(story_world)
            
            prompt = f"""Create a beautiful, colorful children's storybook illustration for this story page.

STORY PAGE TEXT (Page {page_number}):
{story_page_text}
- Embed this story page text into the image naturally.

CHARACTER INFORMATION:
- Character Name: {character_name}
- Character Type: {character_type}
- Story World: {story_world}
{environment_details}
{character_reference_note}
{character_consistency_enforcement}
ILLUSTRATION REQUIREMENTS:
1. Create a vibrant, age-appropriate children's book illustration
2. Include the main character ({character_name}) as a {character_type} - {character_name} is the clear hero of this story
3. CHARACTER PROMINENCE: The character ({character_name}) must occupy 60-70% of the composition. The character should be the dominant visual element, clearly visible and prominent in the scene
4. Match the mood, setting, and events from the story text
5. Use bright, cheerful colors suitable for children
6. Make it visually appealing and engaging
7. Ensure the scene is positive and appropriate for children
8. Include relevant details about the setting and characters
9. Style should be like a professional children's book illustration
10. IMPORTANT: The image must be in 768x512 dimensions
{"11. CRITICAL: The character must match the appearance shown in the reference image provided" if reference_image_url and base_image_data else ""}
{negative_prompts}

Generate a high-quality illustration that perfectly captures this story moment in 768x512 dimensions."""

        # Use edit_image function to generate the scene
        logger.info(f"Calling edit_image function with prompt for page {page_number}")
        scene_image_bytes = edit_image(base_image_data, prompt, reference_image_url)
        
        # Optimize image to JPG format
        logger.info("Optimizing scene image to JPG format...")
        optimized_image = optimize_image_to_jpg(scene_image_bytes)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"story_scene_page{page_number}_{timestamp}_{unique_id}.jpg"
        
        # Upload to Supabase and get URL
        storage_result = upload_to_supabase(optimized_image, filename)
        
        if storage_result.get("uploaded") and storage_result.get("url"):
            logger.info(f"✅ Scene image generated and uploaded for page {page_number}: {storage_result['url']}")
            return storage_result['url']
        else:
            logger.warning(f"Failed to upload scene image for page {page_number}")
            return ""
        
    except HTTPException as e:
        logger.error(f"HTTP error generating scene image for page {page_number}: {e.detail}")
        return ""
    except Exception as e:
        logger.error(f"Error generating scene image for page {page_number}: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return ""

def create_jwt_token(user_id: str, additional_claims: Optional[Dict] = None) -> str:
    """
    Create JWT token with expiration
    
    Args:
        user_id: User ID to encode in token
        additional_claims: Additional claims to include
        
    Returns:
        JWT token string
    """
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    
    if additional_claims:
        payload.update(additional_claims)
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt_token(token: str) -> Optional[Dict]:
    """
    Verify and decode JWT token. Tries Supabase JWT secret first, then custom JWT secret.
    
    Args:
        token: JWT token to verify
        
    Returns:
        Decoded payload or None if invalid
    """
    # Try with Supabase JWT secret first (for tokens from frontend)
    secrets_to_try = [SUPABASE_JWT_SECRET, JWT_SECRET]
    
    for secret in secrets_to_try:
        try:
            payload = jwt.decode(
                token, 
                secret, 
                algorithms=[JWT_ALGORITHM],
                options={"verify_aud": False}  # Supabase tokens may have audience claim
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError:
            # Try next secret
            continue
    
    # If all secrets failed, try to decode without verification to get user info
    # This is a fallback for development/debugging - in production, ensure SUPABASE_JWT_SECRET is set
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        logger.warning("JWT signature verification failed, but decoded without verification for user extraction")
        return payload
    except Exception as e:
        logger.warning(f"Failed to decode JWT token: {e}")
        return None


def extract_user_from_token(authorization: Optional[str]) -> Optional[str]:
    """
    Extract user ID from Authorization header
    
    Args:
        authorization: Authorization header value
        
    Returns:
        User ID or None
    """
    if not authorization:
        return None
    
    try:
        # Extract token from "Bearer <token>"
        if authorization.startswith("Bearer "):
            token = authorization[7:]
            payload = verify_jwt_token(token)
            if payload:
                return payload.get("sub")
    except Exception as e:
        logger.warning(f"Error extracting user from token: {e}")
    
    return None


@app.get("/")
@limiter.limit("60/minute")
async def root(request: Request):
    """Root endpoint with API information"""
    return {
        "message": "AI Image Editor API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "security": {
            "rate_limiting": "enabled",
            "jwt_expiration": f"{JWT_EXPIRATION_HOURS} hours"
        }
    }


@app.post("/validate-image-quality/", response_model=QualityValidationResponse)
@limiter.limit("30/minute")
async def validate_image_quality_endpoint(request: Request, body: ImageRequest):
    """
    Standalone endpoint to validate image quality without editing.
    Useful for pre-validation before processing.
    """
    try:
        # Convert HttpUrl to string for processing
        image_url_str = str(body.image_url)
        
        # Download the image from the URL provided
        logger.info(f"Downloading image for quality validation from: {image_url_str}")
        image_data = download_image_from_url(image_url_str)
        
        # Validate image quality
        validation_result = validate_image_quality(image_data, image_url_str)
        
        return QualityValidationResponse(
            success=True,
            validation=validation_result
        )
        
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in validate_image_quality_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

@app.get("/health")
@limiter.limit("30/minute")
async def health_check(request: Request):
    """Health check endpoint"""
    scanner = get_virus_scanner()
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "gemini_api_key_configured": bool(GEMINI_API_KEY),
        "gemini_client_initialized": bool(gemini_client is not None),
        "openai_api_key_configured": bool(OPENAI_API_KEY),
        "model": MODEL,
        "supabase_configured": bool(supabase is not None),
        "storage_bucket": STORAGE_BUCKET if supabase else None,
        "quality_validation_enabled": bool(gemini_client is not None),
        "virus_scanner_available": scanner.is_available(),
        "security": {
            "rate_limiting": "enabled",
            "virus_scanning": "enabled" if scanner.is_available() else "basic_checks_only"
        }
    }

@app.post("/edit-image/", response_model=ImageResponse)
@limiter.limit("20/minute")
async def edit_image_endpoint(request: Request, body: ImageRequest):
    try:
        # Convert HttpUrl to string for processing
        image_url_str = str(body.image_url)
        
        # Download the image from the URL provided
        logger.info(f"Downloading image from: {image_url_str}")
        image_data = download_image_from_url(image_url_str)

        # Validate image quality before processing
        logger.info("Validating image quality...")
        quality_validation = validate_image_quality(image_data, image_url_str)
        
        # Log validation results
        if not quality_validation.get("is_valid", True):
            logger.warning(f"Image quality validation failed: {quality_validation.get('issues', [])}")
            # Optionally raise error or continue with warning
            # For now, we'll continue but include validation in response
        
        # Send the image to Gemini API for editing
        logger.info(f"Received prompt: {body.prompt}")
        edited_image = edit_image(image_data, body.prompt, image_url_str)
        
        # Optimize image to JPG format for smaller file size
        logger.info("Optimizing image to JPG format...")
        optimized_image = optimize_image_to_jpg(edited_image)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"edited_image_{timestamp}_{unique_id}.jpg"
        
        # Upload optimized image to Supabase storage
        storage_result = upload_to_supabase(optimized_image, filename)
        
        if storage_result["uploaded"]:
            return ImageResponse(
                success=True,
                message="Image edited and uploaded successfully to Supabase storage",
                storage_info=storage_result,
                quality_validation=quality_validation
            )
        else:
            # Even if upload fails, we can still return the image data
            logger.warning("Supabase upload failed, but image was processed successfully")
            return ImageResponse(
                success=True,
                message="Image edited successfully, but storage upload failed",
                storage_info=storage_result,
                quality_validation=quality_validation
            )
            
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in edit_image_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

@app.post("/edit-image-stream/")
@limiter.limit("20/minute")
async def edit_image_stream_endpoint(request: Request, body: ImageRequest):
    """Alternative endpoint that returns the image as a stream (for direct download)"""
    try:
        # Convert HttpUrl to string for processing
        image_url_str = str(body.image_url)
        
        # Download the image from the URL provided
        logger.info(f"Downloading image from: {image_url_str}")
        image_data = download_image_from_url(image_url_str)

        # Send the image to Gemini API for editing
        logger.info(f"Received prompt: {body.prompt}")
        edited_image = edit_image(image_data, body.prompt, image_url_str)
        
        # Optimize image to JPG format for smaller file size
        logger.info("Optimizing image to JPG format...")
        optimized_image = optimize_image_to_jpg(edited_image)
        
        return StreamingResponse(
            BytesIO(optimized_image), 
            media_type="image/jpeg",
            headers={"Content-Disposition": "attachment; filename=edited_image.jpg"}
        )
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in edit_image_stream_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

# Request model for batch job creation
class BatchJobRequest(BaseModel):
    job_type: str  # 'interactive_search' or 'story_adventure'
    character_name: str
    character_type: str
    special_ability: str
    age_group: str
    story_world: str
    adventure_type: str
    occasion_theme: Optional[str] = None
    character_image_url: Optional[HttpUrl] = None
    priority: int = 5  # 1-10, 1 is highest
    user_id: Optional[str] = None
    child_profile_id: Optional[int] = None

# Response model for job creation
class JobResponse(BaseModel):
    success: bool
    job_id: int
    message: str

# Response model for job status
class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    overall_progress: int
    stages: List[Dict[str, Any]]
    error_message: Optional[str] = None
    result_data: Optional[Dict[str, Any]] = None

# Response model for PDF generation
class PDFGenerationResponse(BaseModel):
    success: bool
    pdf_url: Optional[str] = None
    message: str

async def background_worker():
    """Background worker that processes jobs from the queue"""
    logger.info("Background worker started")
    while True:
        try:
            if not queue_manager:
                await asyncio.sleep(5)
                continue
            
            # Get next job
            job = queue_manager.get_next_job()
            
            if job:
                job_id = job["id"]
                logger.info(f"Processing job {job_id}")
                await batch_processor.process_job(job_id)
            else:
                # No jobs available, wait before checking again
                await asyncio.sleep(2)
                
        except asyncio.CancelledError:
            logger.info("Background worker cancelled")
            break
        except Exception as e:
            logger.error(f"Error in background worker: {e}")
            await asyncio.sleep(5)

@app.post("/api/books/generate", response_model=JobResponse)
@limiter.limit("10/minute")
async def create_book_generation_job(request: Request, body: BatchJobRequest):
    """Create a new book generation job"""
    try:
        if not queue_manager:
            raise HTTPException(
                status_code=500,
                detail="Queue manager not initialized"
            )
        
        # Validate job_type
        if body.job_type not in ["interactive_search", "story_adventure"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid job_type. Must be 'interactive_search' or 'story_adventure'"
            )
        
        # Validate age_group
        valid_age_groups = ["3-6", "7-10", "11-12"]
        if body.age_group not in valid_age_groups:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid age_group: {body.age_group}. Must be one of: {', '.join(valid_age_groups)}"
            )
        
        # Validate priority
        if body.priority < 1 or body.priority > 10:
            raise HTTPException(
                status_code=400,
                detail="Priority must be between 1 and 10 (1 is highest)"
            )
        
        # Prepare job data
        job_data = {
            "character_name": body.character_name,
            "character_type": body.character_type,
            "special_ability": body.special_ability,
            "age_group": body.age_group,
            "story_world": body.story_world,
            "adventure_type": body.adventure_type,
            "occasion_theme": body.occasion_theme,
            "character_image_url": str(body.character_image_url) if body.character_image_url else None
        }
        
        # Create job
        job = queue_manager.create_job(
            job_type=body.job_type,
            job_data=job_data,
            user_id=body.user_id,
            child_profile_id=body.child_profile_id,
            priority=body.priority
        )
        
        return JobResponse(
            success=True,
            job_id=job["id"],
            message=f"Job {job['id']} created successfully"
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating job: {str(e)}")

@app.get("/api/books/{book_id}/status", response_model=JobStatusResponse)
@limiter.limit("60/minute")
async def get_book_status(request: Request, book_id: int):
    """Get the status of a book generation job"""
    try:
        if not queue_manager:
            raise HTTPException(
                status_code=500,
                detail="Queue manager not initialized"
            )
        
        job_status = queue_manager.get_job_status(book_id)
        
        if not job_status:
            raise HTTPException(
                status_code=404,
                detail=f"Job {book_id} not found"
            )
        
        job = job_status["job"]
        
        return JobStatusResponse(
            job_id=book_id,
            status=job["status"],
            overall_progress=job_status["overall_progress"],
            stages=job_status["stages"],
            error_message=job.get("error_message"),
            result_data=job.get("result_data")
        )
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting job status: {str(e)}")

@app.get("/api/books/")
@limiter.limit("60/minute")
async def list_all_books(request: Request, parent_id: Optional[str] = None):
    """
    Get all story data from the stories table
    
    Args:
        parent_id: Optional parent user ID to filter stories by parent's children
    
    Returns:
        List of all story/book data, optionally filtered by parent
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=500,
                detail="Database service not available"
            )
        
        # If parent_id is provided, filter by parent's children
        if parent_id:
            # First, get all child profile IDs for this parent
            child_profiles_response = supabase.table("child_profiles").select("*").eq("parent_id", parent_id).execute()
            
            if child_profiles_response.data is None or len(child_profiles_response.data) == 0:
                logger.info(f"No child profiles found for parent {parent_id}")
                return []
            
            # Extract child profile IDs
            child_profile_ids = [profile["id"] for profile in child_profiles_response.data]
            
            # Get user data for parent
            user_response = supabase.table("users").select("*").eq("id", parent_id).execute()
            user_data = user_response.data[0] if user_response.data and len(user_response.data) > 0 else None
            
            # Get all stories for these child profiles
            response = supabase.table("stories").select("*").in_("child_profile_id", child_profile_ids).order("created_at", desc=True).execute()
            
            if response.data is None:
                logger.warning("No stories found or query returned None")
                return []
            
            # Merge child profile data with stories
            stories_with_child_data = []
            for story in response.data:
                child_profile = next((cp for cp in child_profiles_response.data if cp["id"] == story["child_profile_id"]), None)
                user_name = "Unknown"
                if user_data:
                    first_name = user_data.get('first_name', '')
                    last_name = user_data.get('last_name', '')
                    user_name = f"{first_name} {last_name}".strip() or "Unknown"
                story_with_data = {
                    **story,
                    "user_name": user_name,
                    "child_profiles": child_profile
                }
                stories_with_child_data.append(story_with_data)
            
            logger.info(f"Retrieved {len(stories_with_child_data)} stories for parent {parent_id}")
            return stories_with_child_data
        else:
            # Query all stories from the stories table
            response = supabase.table("stories").select("*").execute()
            
            if response.data is None:
                logger.warning("No stories found or query returned None")
                return []
            
            logger.info(f"Retrieved {len(response.data)} stories")
            return response.data
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error listing all books: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error listing all books: {str(e)}")

@app.get("/api/books/{id}/preview")
@limiter.limit("60/minute")
async def get_book_preview(request: Request, id: str):
    """
    Get book data from the stories table by ID or UID
    
    Args:
        id: Book ID (integer) or UID (string)
    
    Returns:
        Book data from the stories table
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=500,
                detail="Database service not available"
            )
        
        # Try to find book by uid first (in case id is a string uid)
        story_response = supabase.table("stories").select("*").eq("uid", id).execute()
        
        # If no result with uid, try id (in case id is an integer)
        if not story_response.data or len(story_response.data) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Book {id} not found (tried both uid and id)"
            )
        
        book_data = story_response.data[0]
        logger.info(f"Retrieved book preview for id={id}")
        
        return book_data
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error getting book preview: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error getting book preview: {str(e)}")

@app.delete("/api/books/{id}")
@limiter.limit("30/minute")
async def delete_book(request: Request, id: str):
    """
    Delete a book from the stories table by ID or UID
    
    Args:
        id: Book ID (integer) or UID (string)
    
    Returns:
        Success message with deleted book information
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=500,
                detail="Database service not available"
            )
        
        # First, try to find the book by uid (in case id is a string uid)
        story_response = supabase.table("stories").select("*").eq("uid", id).execute()
        
        # If no result with uid, try id (in case id is an integer)
        if not story_response.data or len(story_response.data) == 0:
            # Try by numeric id
            try:
                numeric_id = int(id)
                story_response = supabase.table("stories").select("*").eq("id", numeric_id).execute()
            except ValueError:
                pass  # id is not numeric, continue with error
        
        if not story_response.data or len(story_response.data) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Book {id} not found"
            )
        
        book_data = story_response.data[0]
        book_id = book_data.get("id")
        book_uid = book_data.get("uid")
        
        # Delete the book - try by id first (more reliable)
        if book_id:
            delete_response = supabase.table("stories").delete().eq("id", book_id).execute()
        elif book_uid:
            delete_response = supabase.table("stories").delete().eq("uid", book_uid).execute()
        else:
            raise HTTPException(
                status_code=400,
                detail="Book has no valid identifier (id or uid)"
            )
        
        logger.info(f"Deleted book with id={id} (db_id={book_id}, uid={book_uid})")
        
        return {
            "success": True,
            "message": f"Book {id} deleted successfully",
            "deleted_book": {
                "id": book_id,
                "uid": book_uid,
                "title": book_data.get("story_title", "Unknown")
            }
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting book: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error deleting book: {str(e)}")

@app.get("/api/users/children")
@limiter.limit("60/minute")
async def list_child_profiles(request: Request, parent_id: Optional[str] = None):
    """
    List child profiles from the child_profiles table
    
    Args:
        parent_id: Optional parent user ID to filter children by parent
    
    Returns:
        List of child profile data, optionally filtered by parent
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=500,
                detail="Database service not available"
            )
        
        # If parent_id is provided, filter by parent
        if parent_id:
            response = supabase.table("child_profiles").select("*").eq("parent_id", parent_id).execute()
        else:
            # Query all child profiles if no parent_id provided
            response = supabase.table("child_profiles").select("*").execute()
        
        if response.data is None:
            logger.warning("No child profiles found or query returned None")
            return []
        
        logger.info(f"Retrieved {len(response.data)} child profiles" + (f" for parent {parent_id}" if parent_id else ""))
        
        return response.data
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error listing child profiles: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error listing child profiles: {str(e)}")

@app.get("/api/characters")
@limiter.limit("60/minute")
async def list_characters(request: Request):
    """
    List all created characters from the stories table
    
    Returns:
        List of character data from stories
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=500,
                detail="Database service not available"
            )
        
        # Query all stories to get character data
        # Select character-related fields from stories table
        response = supabase.table("stories").select("*").execute()
        
        if response.data is None:
            logger.warning("No characters found or query returned None")
            return []
        
        # Extract character information from stories
        # Each story contains character data (character_name, character_type, etc.)
        characters = response.data
        
        logger.info(f"Retrieved {len(characters)} characters from stories")
        
        return characters
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error listing characters: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error listing characters: {str(e)}")

@app.get("/api/dashboard/user-statistics")
@limiter.limit("30/minute")
async def get_user_statistics(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get user statistics for dashboard
    
    Args:
        start_date: ISO format date string (optional) - filter users created after this date
        end_date: ISO format date string (optional) - filter users created before this date
    
    Returns:
        Dictionary with user statistics including:
        - Total registered users
        - New users (daily/weekly/monthly)
        - Active users (users who created stories/books)
        - User role distribution
        - Users by subscription status
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=500,
                detail="Database service not available"
            )
        
        logger.info(f"Fetching user statistics (start_date={start_date}, end_date={end_date})")
        
        # === TOTAL REGISTERED USERS ===
        users_query = supabase.table("users").select("id, created_at, role, subscription_status")
        
        # Apply date filters if provided
        if start_date:
            users_query = users_query.gte("created_at", start_date)
        if end_date:
            users_query = users_query.lte("created_at", end_date)
        
        users_response = users_query.execute()
        all_users = users_response.data if users_response.data else []
        total_users = len(all_users)
        
        logger.info(f"Total users found: {total_users}")
        
        # === USER ROLE DISTRIBUTION ===
        role_distribution = {}
        subscription_distribution = {}
        
        for user in all_users:
            role = user.get('role', 'unknown')
            role_distribution[role] = role_distribution.get(role, 0) + 1
            
            sub_status = user.get('subscription_status') or 'free'
            subscription_distribution[sub_status] = subscription_distribution.get(sub_status, 0) + 1
        
        # === NEW USERS (DAILY/WEEKLY/MONTHLY) ===
        from datetime import datetime, timedelta
        
        now = datetime.now()
        yesterday = (now - timedelta(days=1)).isoformat()
        last_week = (now - timedelta(days=7)).isoformat()
        last_month = (now - timedelta(days=30)).isoformat()
        
        # New users in last 24 hours
        new_users_daily_response = supabase.table("users").select("id", count="exact").gte("created_at", yesterday).execute()
        new_users_daily = len(new_users_daily_response.data) if new_users_daily_response.data else 0
        
        # New users in last 7 days
        new_users_weekly_response = supabase.table("users").select("id", count="exact").gte("created_at", last_week).execute()
        new_users_weekly = len(new_users_weekly_response.data) if new_users_weekly_response.data else 0
        
        # New users in last 30 days
        new_users_monthly_response = supabase.table("users").select("id", count="exact").gte("created_at", last_month).execute()
        new_users_monthly = len(new_users_monthly_response.data) if new_users_monthly_response.data else 0
        
        # === ACTIVE USERS (users who created stories) ===
        # Get all child profiles with their parent_id and id
        child_profiles_response = supabase.table("child_profiles").select("id, parent_id").execute()
        child_profiles = child_profiles_response.data if child_profiles_response.data else []
        
        # Create a mapping from child_profile_id to parent_id
        child_to_parent = {profile['id']: profile['parent_id'] for profile in child_profiles}
        
        # Get all stories with their child_profile_id
        stories_response = supabase.table("stories").select("child_profile_id").execute()
        stories = stories_response.data if stories_response.data else []
        
        # Find unique parent users who have created stories
        active_user_ids = set()
        for story in stories:
            child_profile_id = story.get('child_profile_id')
            if child_profile_id and child_profile_id in child_to_parent:
                parent_id = child_to_parent[child_profile_id]
                active_user_ids.add(parent_id)
        
        active_users_count = len(active_user_ids)
        
        # === BUILD RESPONSE ===
        statistics = {
            "total_users": total_users,
            "new_users": {
                "daily": new_users_daily,
                "weekly": new_users_weekly,
                "monthly": new_users_monthly
            },
            "active_users": {
                "count": active_users_count,
                "percentage": round((active_users_count / total_users * 100), 2) if total_users > 0 else 0
            },
            "by_role": role_distribution,
            "by_subscription_status": subscription_distribution,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "date_range": {
                    "start": start_date,
                    "end": end_date
                }
            }
        }
        
        logger.info(f"User statistics generated successfully: {statistics}")
        return statistics
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error generating user statistics: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating user statistics: {str(e)}")

@app.get("/api/dashboard/user-statistics/summary")
@limiter.limit("30/minute")
async def get_user_statistics_summary(request: Request):
    """
    Get quick summary of user statistics (optimized for dashboard widgets)
    
    Returns:
        Dictionary with quick user statistics summary
    """
    try:
        if not supabase:
            raise HTTPException(
                status_code=500,
                detail="Database service not available"
            )
        
        from datetime import datetime, timedelta
        
        # Quick counts using count queries
        users_response = supabase.table("users").select("id", count="exact").execute()
        total_users = len(users_response.data) if users_response.data else 0
        
        # Recent activity (last 24 hours)
        last_24h = (datetime.now() - timedelta(hours=24)).isoformat()
        new_users_24h_response = supabase.table("users").select("id", count="exact").gte("created_at", last_24h).execute()
        new_users_24h = len(new_users_24h_response.data) if new_users_24h_response.data else 0
        
        # Get child profiles and stories for active users count
        child_profiles_response = supabase.table("child_profiles").select("id, parent_id").execute()
        child_profiles = child_profiles_response.data if child_profiles_response.data else []
        child_to_parent = {profile['id']: profile['parent_id'] for profile in child_profiles}
        
        stories_response = supabase.table("stories").select("child_profile_id").execute()
        stories = stories_response.data if stories_response.data else []
        
        active_user_ids = set()
        for story in stories:
            child_profile_id = story.get('child_profile_id')
            if child_profile_id and child_profile_id in child_to_parent:
                active_user_ids.add(child_to_parent[child_profile_id])
        
        return {
            "summary": {
                "total_users": total_users,
                "active_users": len(active_user_ids),
                "new_users_24h": new_users_24h
            },
            "generated_at": datetime.now().isoformat()
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error generating summary statistics: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating summary statistics: {str(e)}")

@app.post("/generate-story/", response_model=StoryResponse)
@limiter.limit("10/minute")
async def generate_story_endpoint(request: Request, body: StoryRequest):
    """Generate a 5-page children's story based on the provided parameters"""
    try:
        # Validate age_group
        valid_age_groups = ["3-6", "7-10", "11-12"]
        if body.age_group not in valid_age_groups:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid age_group: {body.age_group}. Must be one of: {', '.join(valid_age_groups)}"
            )
        
        logger.info(f"Generating story for character: {body.character_name}")
        logger.info(f"Age group: {body.age_group}, Adventure: {body.adventure_type}")
        
        # Validate API keys
        if not OPENAI_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."
            )
        
        if not GEMINI_API_KEY or not gemini_client:
            raise HTTPException(
                status_code=500,
                detail="Gemini API key not configured or client not initialized. Please set GEMINI_API_KEY environment variable."
            )
        
        # Generate the story using OpenAI (GPT-4) via the story library
        logger.info("Generating story with OpenAI GPT-4...")
        story_result = generate_story(
            character_name=body.character_name,
            character_type=body.character_type,
            special_ability=body.special_ability,
            age_group=body.age_group,
            story_world=body.story_world,
            adventure_type=body.adventure_type,
            occasion_theme=body.occasion_theme,
            use_api=True,  # Use OpenAI API for story generation
            api_key=OPENAI_API_KEY,
            story_text_prompt=body.story_text_prompt  # Use prompt from frontend if provided
        )
        
        logger.info(f"Story generated successfully. Word count: {story_result['word_count']}")
        
        # Generate scene images for each page using Gemini Pro image preview model
        logger.info("Generating scene images with Gemini Pro image preview model for each story page...")
        reference_image_url = str(body.character_image_url) if body.character_image_url else None
        
        # Download reference image once for consistency validation
        reference_image_data = None
        if reference_image_url:
            try:
                logger.info(f"Downloading reference image for consistency validation: {reference_image_url}")
                reference_image_data = download_image_from_url(reference_image_url)
                logger.info(f"✅ Reference image downloaded for validation ({len(reference_image_data)} bytes)")
            except Exception as e:
                logger.warning(f"Failed to download reference image for validation: {e}")
                reference_image_data = None
        
        story_pages = []
        consistency_results = []
        flagged_pages = []
        
        for i, page_text in enumerate(story_result['pages'], 1):
            logger.info(f"Generating scene image for page {i}/5...")
            # Use scene prompt from frontend if available, otherwise use None (will generate from params)
            scene_prompt = None
            if body.scene_prompts and len(body.scene_prompts) >= i:
                scene_prompt = body.scene_prompts[i - 1]  # i is 1-indexed, list is 0-indexed
                # Replace placeholder with actual page text
                scene_prompt = scene_prompt.replace(
                    f"[Page {i} text will be inserted here after story generation]",
                    page_text
                )
                logger.info(f"Using scene prompt from frontend for page {i} (with actual page text)")
            
            scene_url = generate_story_scene_image(
                story_page_text=page_text,
                page_number=i,
                character_name=body.character_name,
                character_type=body.character_type,
                story_world=body.story_world,
                reference_image_url=reference_image_url,
                scene_prompt=scene_prompt
            )
            # Convert string URL to HttpUrl if not empty, otherwise None
            scene_http_url = None
            scene_image_data = None
            consistency_validation = None
            
            if scene_url:
                try:
                    scene_http_url = HttpUrl(scene_url)
                    # Download scene image for consistency validation
                    try:
                        scene_image_data = download_image_from_url(scene_url)
                        logger.info(f"✅ Scene image downloaded for validation ({len(scene_image_data)} bytes)")
                    except Exception as e:
                        logger.warning(f"Failed to download scene image for validation: {e}")
                except Exception as e:
                    logger.warning(f"Invalid scene URL for page {i}: {e}")
                    scene_http_url = None
            
            # Perform character consistency validation if both images are available
            if reference_image_data and scene_image_data:
                logger.info(f"Performing character consistency validation for page {i}...")
                try:
                    consistency_validation = validate_character_consistency(
                        scene_image_data=scene_image_data,
                        reference_image_data=reference_image_data,
                        page_number=i,
                        timeout_seconds=15
                    )
                    consistency_results.append(consistency_validation)
                    
                    if consistency_validation.flagged:
                        flagged_pages.append(i)
                        logger.warning(f"⚠️ Page {i} flagged as INCONSISTENT (similarity: {consistency_validation.similarity_score:.3f})")
                    else:
                        logger.info(f"✅ Page {i} validated as CONSISTENT (similarity: {consistency_validation.similarity_score:.3f})")
                except Exception as e:
                    logger.error(f"Error during consistency validation for page {i}: {e}")
                    import traceback
                    logger.debug(f"Traceback: {traceback.format_exc()}")
            elif not reference_image_data:
                logger.info(f"Skipping consistency validation for page {i} - no reference image available")
            elif not scene_image_data:
                logger.warning(f"Skipping consistency validation for page {i} - scene image not available")
            
            story_pages.append(StoryPage(
                text=page_text, 
                scene=scene_http_url,
                consistency_validation=consistency_validation
            ))
        
        logger.info("All scene images generated successfully")
        
        # Generate audio for all story pages
        logger.info("Generating audio for story pages...")
        audio_urls = []
        audio_generator = None
        
        if supabase:
            try:
                audio_generator = AudioGenerator()
                if audio_generator.available:
                    # Generate audio for all pages
                    audio_data_list = audio_generator.generate_audio_for_story(
                        story_pages=story_result['pages'],
                        age_group=body.age_group,
                        timeout_per_page=60
                    )
                    
                    # Upload audio files to Supabase storage
                    for i, audio_data in enumerate(audio_data_list, 1):
                        if audio_data is None:
                            logger.warning(f"⚠️ No audio generated for page {i}, skipping upload")
                            audio_urls.append(None)
                            continue
                        
                        # Generate unique filename
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        unique_id = str(uuid.uuid4())[:8]
                        filename = f"story_audio_page{i}_{timestamp}_{unique_id}.mp3"
                        
                        # Upload to Supabase storage (try audio bucket first, fallback to images)
                        storage_bucket = "audio"
                        audio_url = None
                        
                        try:
                            # Try audio bucket first
                            try:
                                response = supabase.storage.from_(storage_bucket).upload(
                                    filename,
                                    audio_data,
                                    {
                                        'content-type': 'audio/mpeg',
                                        'upsert': 'true'
                                    }
                                )
                            except Exception as e:
                                # If audio bucket doesn't exist, use images bucket
                                logger.warning(f"Audio bucket not found, using images bucket: {e}")
                                storage_bucket = "images"
                                response = supabase.storage.from_(storage_bucket).upload(
                                    filename,
                                    audio_data,
                                    {
                                        'content-type': 'audio/mpeg',
                                        'upsert': 'true'
                                    }
                                )
                            
                            if hasattr(response, 'full_path') and response.full_path:
                                audio_url = supabase.storage.from_(storage_bucket).get_public_url(filename)
                                audio_urls.append(audio_url)
                                logger.info(f"✅ Uploaded audio for page {i}: {audio_url}")
                            else:
                                logger.error(f"❌ Failed to upload audio for page {i}: Unexpected response")
                                audio_urls.append(None)
                        except Exception as e:
                            logger.error(f"❌ Error uploading audio for page {i} to Supabase: {e}")
                            audio_urls.append(None)
                        
                    successful_uploads = sum(1 for url in audio_urls if url is not None)
                    if successful_uploads > 0:
                        logger.info(f"✅ Generated and uploaded {successful_uploads}/5 audio files")
                    else:
                        logger.warning("⚠️ Failed to generate/upload any audio files")
                    
                    # Update StoryPage objects with audio URLs (recreate since Pydantic models are immutable)
                    updated_story_pages = []
                    for idx, page in enumerate(story_pages):
                        audio_http_url = None
                        if idx < len(audio_urls) and audio_urls[idx]:
                            try:
                                audio_http_url = HttpUrl(audio_urls[idx])
                            except Exception as e:
                                logger.warning(f"Failed to create HttpUrl for audio on page {idx + 1}: {e}")
                        
                        updated_story_pages.append(StoryPage(
                            text=page.text,
                            scene=page.scene,
                            audio=audio_http_url,
                            consistency_validation=page.consistency_validation
                        ))
                    story_pages = updated_story_pages
                else:
                    logger.warning("⚠️ Audio generator not available. Install: pip install gtts>=2.5.0")
            except Exception as e:
                logger.error(f"Error during audio generation: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")
        else:
            logger.warning("⚠️ Supabase not configured, skipping audio generation")
        
        # Create consistency summary
        consistency_summary = None
        if consistency_results:
            avg_score = sum(r.similarity_score for r in consistency_results) / len(consistency_results)
            min_score = min(r.similarity_score for r in consistency_results)
            max_score = max(r.similarity_score for r in consistency_results)
            total_validation_time = sum(r.validation_time_seconds for r in consistency_results)
            consistent_count = sum(1 for r in consistency_results if r.is_consistent)
            
            consistency_summary = {
                "total_pages_validated": len(consistency_results),
                "consistent_pages": consistent_count,
                "inconsistent_pages": len(consistency_results) - consistent_count,
                "flagged_pages": flagged_pages,
                "average_similarity_score": round(avg_score, 3),
                "min_similarity_score": round(min_score, 3),
                "max_similarity_score": round(max_score, 3),
                "total_validation_time_seconds": round(total_validation_time, 2),
                "average_validation_time_seconds": round(total_validation_time / len(consistency_results), 2),
                "all_consistent": len(flagged_pages) == 0
            }
            
            logger.info("=" * 60)
            logger.info("CHARACTER CONSISTENCY VALIDATION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total pages validated: {consistency_summary['total_pages_validated']}")
            logger.info(f"Consistent pages: {consistency_summary['consistent_pages']}")
            logger.info(f"Inconsistent pages: {consistency_summary['inconsistent_pages']}")
            if flagged_pages:
                logger.warning(f"⚠️ Flagged pages (inconsistent): {flagged_pages}")
            logger.info(f"Average similarity score: {avg_score:.3f}")
            logger.info(f"Score range: {min_score:.3f} - {max_score:.3f}")
            logger.info(f"Total validation time: {total_validation_time:.2f}s")
            logger.info(f"Average validation time per page: {total_validation_time / len(consistency_results):.2f}s")
            logger.info("=" * 60)
        
        return StoryResponse(
            success=True,
            pages=story_pages,
            full_story=story_result['full_story'],
            word_count=story_result['word_count'],
            page_word_counts=story_result['page_word_counts'],
            consistency_summary=consistency_summary,
            audio_urls=audio_urls if audio_urls else None
        )
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        logger.error(f"HTTP Exception: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in generate_story_endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

def verify_purchase(story_id: int, user_id: Optional[str] = None) -> bool:
    """
    Verify if user has purchased the book/story
    
    Args:
        story_id: Story/Book ID
        user_id: User ID (optional, for direct verification)
    
    Returns:
        True if purchase verified, False otherwise
    """
    try:
        if not supabase:
            logger.warning("Supabase not available for purchase verification")
            return False
        
        # Check if purchase exists
        query = supabase.table("book_purchases").select("*").eq("story_id", story_id)
        
        if user_id:
            query = query.eq("user_id", user_id)
        
        response = query.eq("purchase_status", "completed").execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"✅ Purchase verified for story {story_id}, user {user_id}")
            return True
        
        # In production mode, enforce purchase verification
        if IS_PRODUCTION:
            logger.warning(f"❌ No purchase found for story {story_id}, user {user_id} - access denied")
            return False
        
        # Development mode: allow free access
        logger.warning(f"⚠️ No purchase found for story {story_id}, user {user_id} - allowing access (development mode)")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying purchase: {e}")
        # In production, fail closed (deny access on error)
        return not IS_PRODUCTION


@app.get("/api/books/{book_id}/pdf")
@limiter.limit("10/minute")
async def download_book_pdf(
    request: Request,
    book_id: int,
    authorization: Optional[str] = Header(None)
):
    """
    Download PDF for a book/story with purchase verification
    
    Args:
        book_id: Story/Book ID
        authorization: Bearer token (required for purchase verification)
    
    Returns:
        PDF file stream
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Storage service not available")
        
        # Extract user ID from authorization header
        user_id = extract_user_from_token(authorization)
        
        # In production, require authentication
        if IS_PRODUCTION and not user_id:
            raise HTTPException(
                status_code=401,
                detail="Authentication required to download PDF"
            )
        
        # Get story/book information
        story_response = supabase.table("stories").select("*").eq("id", book_id).execute()
        
        if not story_response.data or len(story_response.data) == 0:
            raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
        
        story = story_response.data[0]
        pdf_url = story.get("pdf_url")
        
        if not pdf_url:
            raise HTTPException(
                status_code=404,
                detail=f"PDF not available for book {book_id}. PDF may still be generating."
            )
        
        # Verify purchase before allowing download
        if not verify_purchase(book_id, user_id):
            raise HTTPException(
                status_code=403,
                detail="Purchase verification failed. Please purchase this book to download the PDF."
            )
        
        # Download PDF from storage
        logger.info(f"Downloading PDF from: {pdf_url}")
        
        # Extract filename from URL or generate one
        filename = pdf_url.split("/")[-1].split("?")[0] or f"book_{book_id}.pdf"
        
        # Download PDF bytes
        pdf_response = requests.get(pdf_url, timeout=30)
        pdf_response.raise_for_status()
        pdf_bytes = pdf_response.content
        
        # Return PDF as streaming response
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes))
            }
        )
        
    except HTTPException as e:
        raise e
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading PDF: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download PDF: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in download_book_pdf: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/api/books/{book_id}/generate-pdf", response_model=PDFGenerationResponse)
@limiter.limit("10/minute")
async def generate_book_pdf(request: Request, book_id: str):
    """
    Generate PDF on-demand for a book/story
    
    This endpoint generates a PDF from the story data and uploads it to Supabase storage.
    Returns the PDF URL for download.
    """
    try:
        start_time = time.time()
        logger.info(f"Generating PDF on-demand for book {book_id}")
        
        if not supabase:
            raise HTTPException(status_code=500, detail="Storage service not available")
        
        # Try uid first, then fallback to id
        story_response = supabase.table("stories").select("*").eq("uid", book_id).execute()
        
        # If no result with uid, try id (in case uid doesn't exist in database)
        if not story_response.data or len(story_response.data) == 0:
            logger.info(f"No story found with uid={book_id}, trying id...")
            try:
                # Try to convert to integer for id lookup
                book_id_int = int(book_id)
                story_response = supabase.table("stories").select("*").eq("id", book_id_int).execute()
            except (ValueError, TypeError):
                logger.warning(f"Could not convert {book_id} to integer for id lookup")
        
        if not story_response.data or len(story_response.data) == 0:
            raise HTTPException(status_code=404, detail=f"Book {book_id} not found (tried both uid and id)")
        
        story = story_response.data[0]
        
        # Check if PDF already exists
        if story.get("pdf_url"):
            logger.info(f"PDF already exists for book {book_id}: {story.get('pdf_url')}")
            return {
                "success": True,
                "pdf_url": story.get("pdf_url"),
                "message": "PDF already generated"
            }
        
        # Prepare data for PDF generation
        story_title = story.get("story_title") or "Untitled Story"
        story_cover = story.get("story_cover")
        scene_images = story.get("scene_images")
        
        # Check if we have at least cover or scene images
        if not story_cover and (not scene_images or len(scene_images) == 0):
            raise HTTPException(
                status_code=400,
                detail="No cover image or scene images found. Cannot generate PDF without images."
            )
        
        # Import PDF generator
        from pdf_generator import create_book_pdf_with_cover
        from io import BytesIO
        
        # Generate 6-page PDF: cover + up to 5 scene images
        logger.info(f"Generating PDF with cover and {len(scene_images)} scene images")
        
        output_buffer = BytesIO()
        success = create_book_pdf_with_cover(
            story_title=story_title,
            story_cover_url=story_cover,
            scene_urls=scene_images,  # Up to 5 scene images will be used
            output_buffer=output_buffer
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to generate PDF")
        
        pdf_bytes = output_buffer.getvalue()
        
        # Upload PDF to Supabase storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"book_{book_id}_{timestamp}_{unique_id}.pdf"
        
        logger.info(f"Uploading PDF to Supabase storage: {filename}")
        
        # Upload to 'pdfs' bucket, fallback to 'images' bucket
        storage_bucket = "pdfs"
        pdf_url = None
        
        try:
            response = supabase.storage.from_(storage_bucket).upload(
                filename,
                pdf_bytes,
                {
                    'content-type': 'application/pdf',
                    'upsert': 'true'
                }
            )
        except Exception as e:
            # Fallback to images bucket if pdfs bucket doesn't exist
            logger.warning(f"PDF bucket not found, using images bucket: {e}")
            storage_bucket = "images"
            response = supabase.storage.from_(storage_bucket).upload(
                filename,
                pdf_bytes,
                {
                    'content-type': 'application/pdf',
                    'upsert': 'true'
                }
            )
        
        if hasattr(response, 'full_path') and response.full_path:
            pdf_url = supabase.storage.from_(storage_bucket).get_public_url(filename)
            logger.info(f"✅ PDF uploaded successfully: {pdf_url}")
        else:
            raise HTTPException(status_code=500, detail="Failed to upload PDF to storage")
        
        # Update story record with PDF URL
        update_response = supabase.table("stories").update({"pdf_url": pdf_url}).eq("uid", book_id).execute()
        
        if not update_response.data:
            logger.warning(f"Failed to update story {book_id} with PDF URL")
        
        elapsed = time.time() - start_time
        logger.info(f"✅ PDF generated and uploaded successfully in {elapsed:.2f} seconds")
        
        return {
            "success": True,
            "pdf_url": pdf_url,
            "message": "PDF generated successfully"
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


@app.post("/api/books/{book_id}/purchase")
@limiter.limit("20/minute")
async def record_book_purchase(
    request: Request,
    book_id: int,
    user_id: Optional[str] = None,
    transaction_id: Optional[str] = None,
    amount_paid: Optional[float] = None,
    payment_method: Optional[str] = None
):
    """
    Record a book purchase (for purchase verification)
    
    This endpoint should be called after a successful payment
    """
    try:
        if not supabase:
            raise HTTPException(status_code=500, detail="Database service not available")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        # Check if purchase already exists
        existing = supabase.table("book_purchases").select("*").eq("story_id", book_id).eq("user_id", user_id).execute()
        
        if existing.data and len(existing.data) > 0:
            logger.info(f"Purchase already exists for story {book_id}, user {user_id}")
            return {
                "success": True,
                "message": "Purchase already recorded",
                "purchase_id": existing.data[0]["id"]
            }
        
        # Create new purchase record
        purchase_data = {
            "story_id": book_id,
            "user_id": user_id,
            "purchase_status": "completed",
            "transaction_id": transaction_id,
            "amount_paid": amount_paid,
            "payment_method": payment_method or "free"
        }
        
        response = supabase.table("book_purchases").insert(purchase_data).execute()
        
        if response.data:
            logger.info(f"Purchase recorded for story {book_id}, user {user_id}")
            return {
                "success": True,
                "message": "Purchase recorded successfully",
                "purchase_id": response.data[0]["id"]
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to record purchase")
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error recording purchase: {e}")
        raise HTTPException(status_code=500, detail=f"Error recording purchase: {str(e)}")


# ============================================================================
# STRIPE SUBSCRIPTION ENDPOINTS
# ============================================================================

class CreateSubscriptionRequest(BaseModel):
    """Request model for creating a subscription checkout session"""
    price_type: str = "monthly"  # "monthly" or "yearly"
    user_email: Optional[str] = None
    user_id: Optional[str] = None
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class SubscriptionResponse(BaseModel):
    """Response model for subscription operations"""
    success: bool
    checkout_url: Optional[str] = None
    session_id: Optional[str] = None
    message: Optional[str] = None

class SubscriptionStatusResponse(BaseModel):
    """Response model for subscription status"""
    success: bool
    is_active: bool = False
    subscription_id: Optional[str] = None
    status: Optional[str] = None
    current_period_end: Optional[str] = None
    plan_type: Optional[str] = None
    message: Optional[str] = None

class CustomerPortalResponse(BaseModel):
    """Response model for customer portal"""
    success: bool
    portal_url: Optional[str] = None
    message: Optional[str] = None


# ============================================================================
# PAYMENT INTENT ENDPOINTS (One-time payments)
# ============================================================================

class CreatePaymentIntentRequest(BaseModel):
    """Request model for creating a payment intent for one-time purchases"""
    amount: int  # Amount in cents (e.g., 999 = $9.99)
    currency: str = "usd"
    product_id: Optional[str] = None  # e.g., book_id, pdf_id
    product_type: Optional[str] = None  # e.g., "book", "pdf", "credit_pack"
    user_email: Optional[str] = None
    user_id: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None


class PaymentIntentResponse(BaseModel):
    """Response model for payment intent creation"""
    success: bool
    client_secret: Optional[str] = None
    payment_intent_id: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    message: Optional[str] = None


class ConfirmPaymentRequest(BaseModel):
    """Request model for confirming a payment"""
    payment_intent_id: str
    user_id: Optional[str] = None


class PaymentStatusResponse(BaseModel):
    """Response model for payment status"""
    success: bool
    payment_intent_id: str
    status: str
    amount: Optional[int] = None
    currency: Optional[str] = None
    message: Optional[str] = None


@app.post("/api/payments/create-intent", response_model=PaymentIntentResponse)
async def create_payment_intent(request: CreatePaymentIntentRequest):
    """
    Create a Stripe PaymentIntent for one-time purchases.
    
    This is used for:
    - One-time purchases (books, PDFs, credit packs)
    - Embedded payment forms using Stripe Elements
    - More control over the payment flow without redirecting
    
    Returns a client_secret for use with Stripe.js on the frontend.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    
    try:
        # Validate amount
        if request.amount < 50:  # Stripe minimum is $0.50
            raise HTTPException(
                status_code=400,
                detail="Amount must be at least 50 cents"
            )
        
        # Build PaymentIntent parameters
        intent_params = {
            "amount": request.amount,
            "currency": request.currency,
            "payment_method_types": ["card"],
            "metadata": {
                "user_id": request.user_id or "",
                "product_id": request.product_id or "",
                "product_type": request.product_type or "",
                "source": "drawtopia_one_time_payment"
            }
        }
        
        # Add description if provided
        if request.description:
            intent_params["description"] = request.description
        
        # Add customer email for receipt
        if request.user_email:
            intent_params["receipt_email"] = request.user_email
        
        # Merge additional metadata if provided
        if request.metadata:
            intent_params["metadata"].update(request.metadata)
        
        # Create the PaymentIntent
        payment_intent = stripe.PaymentIntent.create(**intent_params)
        
        logger.info(f"Created PaymentIntent {payment_intent.id} for amount {request.amount} {request.currency}")
        
        return PaymentIntentResponse(
            success=True,
            client_secret=payment_intent.client_secret,
            payment_intent_id=payment_intent.id,
            amount=payment_intent.amount,
            currency=payment_intent.currency
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating payment intent: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment intent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create payment intent: {str(e)}")


@app.get("/api/payments/{payment_intent_id}/status", response_model=PaymentStatusResponse)
async def get_payment_status(payment_intent_id: str):
    """
    Get the status of a PaymentIntent.
    
    Useful for checking if a payment was successful after the user completes
    the payment flow on the frontend.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    
    try:
        payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
        
        return PaymentStatusResponse(
            success=True,
            payment_intent_id=payment_intent.id,
            status=payment_intent.status,
            amount=payment_intent.amount,
            currency=payment_intent.currency,
            message=f"Payment is {payment_intent.status}"
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error retrieving payment intent: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving payment intent: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve payment status: {str(e)}")


@app.post("/api/payments/confirm", response_model=PaymentStatusResponse)
async def confirm_payment(request: ConfirmPaymentRequest):
    """
    Confirm a payment was successful and process the purchase.
    
    Call this endpoint after the payment is completed on the frontend
    to record the purchase in the database.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    
    if not supabase:
        raise HTTPException(status_code=503, detail="Database is not configured")
    
    try:
        # Retrieve the PaymentIntent to verify status
        payment_intent = stripe.PaymentIntent.retrieve(request.payment_intent_id)
        
        if payment_intent.status != "succeeded":
            return PaymentStatusResponse(
                success=False,
                payment_intent_id=payment_intent.id,
                status=payment_intent.status,
                message=f"Payment has not succeeded. Current status: {payment_intent.status}"
            )
        
        # Extract metadata
        metadata = payment_intent.metadata or {}
        user_id = request.user_id or metadata.get("user_id")
        product_id = metadata.get("product_id")
        product_type = metadata.get("product_type")
        
        # Record the purchase in the database if we have product info
        if user_id and product_id and product_type == "book":
            try:
                purchase_record = {
                    "user_id": user_id,
                    "story_id": int(product_id),
                    "purchase_status": "completed",
                    "transaction_id": payment_intent.id,
                    "amount_paid": payment_intent.amount / 100,  # Convert cents to dollars
                    "payment_method": "stripe"
                }
                supabase.table("book_purchases").insert(purchase_record).execute()
                logger.info(f"Recorded book purchase for user {user_id}, book {product_id}")
            except Exception as db_error:
                logger.error(f"Error recording purchase in database: {db_error}")
                # Don't fail the response - payment was successful
        
        logger.info(f"Payment {payment_intent.id} confirmed successfully")
        
        return PaymentStatusResponse(
            success=True,
            payment_intent_id=payment_intent.id,
            status=payment_intent.status,
            amount=payment_intent.amount,
            currency=payment_intent.currency,
            message="Payment confirmed successfully"
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error confirming payment: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming payment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to confirm payment: {str(e)}")


# ============================================================================
# STRIPE SUBSCRIPTION CHECKOUT
# ============================================================================

@app.post("/api/stripe/create-subscription-checkout", response_model=SubscriptionResponse)
async def create_subscription_checkout(request: CreateSubscriptionRequest):
    """
    Create a Stripe Checkout Session for subscription.
    This redirects the user to Stripe's hosted checkout page.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    
    try:
        # Determine which price ID to use
        if request.price_type == "yearly":
            price_id = STRIPE_PRICE_ID_YEARLY
        else:
            price_id = STRIPE_PRICE_ID_MONTHLY
        
        if not price_id:
            raise HTTPException(
                status_code=400, 
                detail=f"Price ID for {request.price_type} subscription is not configured"
            )
        
        # Set success and cancel URLs
        success_url = request.success_url or f"{FRONTEND_URL}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = request.cancel_url or f"{FRONTEND_URL}/pricing"
        
        # Build checkout session parameters
        checkout_params = {
            "mode": "subscription",
            "payment_method_types": ["card"],
            "line_items": [
                {
                    "price": price_id,
                    "quantity": 1,
                }
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "allow_promotion_codes": True,
            "billing_address_collection": "auto",
        }
        
        # Add customer email if provided
        if request.user_email:
            checkout_params["customer_email"] = request.user_email
        
        # Add metadata for tracking
        checkout_params["metadata"] = {
            "user_id": request.user_id or "",
            "price_type": request.price_type,
            "source": "drawtopia_pricing_page"
        }
        
        # Create the checkout session
        checkout_session = stripe.checkout.Session.create(**checkout_params)
        
        logger.info(f"Created Stripe checkout session: {checkout_session.id}")

        await set_user_premium(request.user_id)
        
        return SubscriptionResponse(
            success=True,
            checkout_url=checkout_session.url,
            session_id=checkout_session.id
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating subscription checkout: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create checkout session: {str(e)}")


@app.get("/api/stripe/subscription-status/{user_id}", response_model=SubscriptionStatusResponse)
async def get_subscription_status(user_id: str):
    """
    Get the subscription status for a user.
    Checks the subscriptions table in Supabase.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    
    if not supabase:
        raise HTTPException(status_code=503, detail="Database is not configured")
    
    try:
        # Query the subscriptions table for this user
        response = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("status", "active").execute()
        
        if response.data and len(response.data) > 0:
            subscription = response.data[0]
            return SubscriptionStatusResponse(
                success=True,
                is_active=True,
                subscription_id=subscription.get("stripe_subscription_id"),
                status=subscription.get("status"),
                current_period_end=subscription.get("current_period_end"),
                plan_type=subscription.get("plan_type")
            )
        else:
            return SubscriptionStatusResponse(
                success=True,
                is_active=False,
                message="No active subscription found"
            )
            
    except Exception as e:
        logger.error(f"Error checking subscription status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to check subscription status: {str(e)}")


@app.get("/api/subscriptions/status")
async def get_user_subscription_status(
    request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    Get the subscription status for the current authenticated user.
    Returns the subscription_status field from the users table.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Database is not configured")
    
    # Extract user ID from authorization header
    user_id = extract_user_from_token(authorization)
    
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to check subscription status"
        )
    
    try:
        # Query the users table for subscription_status
        response = supabase.table("users").select("id, subscription_status").eq("id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            user = response.data[0]
            subscription_status = user.get("subscription_status") or "free"
            
            return {
                "success": True,
                "user_id": user_id,
                "subscription_status": subscription_status,
                "is_premium": subscription_status == "premium"
            }
        else:
            raise HTTPException(status_code=404, detail="User not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subscription status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get subscription status: {str(e)}")


class CancelSubscriptionRequest(BaseModel):
    stripe_subscription_id: str


@app.post("/api/subscriptions/cancel")
async def cancel_subscription(
    request: Request,
    body: CancelSubscriptionRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Cancel the subscription for the current authenticated user.
    This will:
    1. Cancel the subscription in Stripe using the provided stripe_subscription_id
    2. Update the subscriptions table
    3. Update the users table subscription_status to 'free plan'
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    
    if not supabase:
        raise HTTPException(status_code=503, detail="Database is not configured")
    
    # Extract user ID from authorization header
    user_id = extract_user_from_token(authorization)
    
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required to cancel subscription"
        )
    
    stripe_subscription_id = body.stripe_subscription_id
    
    if not stripe_subscription_id:
        raise HTTPException(status_code=400, detail="stripe_subscription_id is required")
    
    try:
        # Verify the subscription belongs to this user and get subscription details
        subscription_response = supabase.table("subscriptions").select(
            "stripe_subscription_id, stripe_customer_id, status, user_id, customer_email, plan_type"
        ).eq("stripe_subscription_id", stripe_subscription_id).execute()
        
        if not subscription_response.data or len(subscription_response.data) == 0:
            raise HTTPException(status_code=404, detail="Subscription not found")
        
        subscription_record = subscription_response.data[0]
        
        # Verify the subscription belongs to the authenticated user
        if subscription_record.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="You can only cancel your own subscription")
        
        # Cancel the subscription in Stripe
        cancelled_subscription = stripe.Subscription.cancel(stripe_subscription_id)
        
        logger.info(f"Cancelled Stripe subscription {stripe_subscription_id} for user {user_id}")
        
        # Update the subscriptions table
        supabase.table("subscriptions").update({
            "status": "cancelled",
            "cancelled_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }).eq("stripe_subscription_id", stripe_subscription_id).execute()
        
        # Get user details for email
        customer_email = subscription_record.get("customer_email")
        customer_name = None
        plan_type = subscription_record.get("plan_type", "monthly")
        
        user_response = supabase.table("users").select("email, name").eq("id", user_id).execute()
        if user_response.data and len(user_response.data) > 0:
            if not customer_email:
                customer_email = user_response.data[0].get("email")
            customer_name = user_response.data[0].get("name")
        
        # Update the users table
        supabase.table("users").update({
            "subscription_status": "free plan",
            "subscription_expires": None
        }).eq("id", user_id).execute()
        
        logger.info(f"Updated user {user_id} subscription status to 'free plan'")
        
        # Send cancellation confirmation email
        if customer_email and EmailService.is_available():
            try:
                # Get the end date from cancelled subscription
                end_date = None
                if cancelled_subscription.get("current_period_end"):
                    try:
                        end_date = datetime.fromtimestamp(cancelled_subscription["current_period_end"]).isoformat()
                    except:
                        pass
                
                await EmailService.send_subscription_cancelled_email(
                    to_email=customer_email,
                    customer_name=customer_name,
                    plan_type=plan_type,
                    end_date=end_date
                )
                logger.info(f"Subscription cancellation email sent to {customer_email}")
            except Exception as email_error:
                logger.error(f"Failed to send cancellation email: {email_error}")
        
        return {
            "success": True,
            "message": "Subscription cancelled successfully",
            "user_id": user_id,
            "stripe_subscription_id": stripe_subscription_id,
            "subscription_status": "cancelled"
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error cancelling subscription {stripe_subscription_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling subscription {stripe_subscription_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel subscription: {str(e)}")


async def set_user_premium(user_id: str):
    """
    Update a user's subscription_status to 'premium'.
    No input data required - just updates the status to 'premium'.
    """
    if not supabase:
        raise HTTPException(status_code=503, detail="Database is not configured")
    
    try:
        # Update the subscription_status to "premium"
        response = supabase.table("users").update({
            "subscription_status": "premium"
        }).eq("id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            logger.info(f"Successfully updated user {user_id} subscription_status to 'premium'")
            return {
                "success": True,
                "message": f"User {user_id} subscription status updated to 'premium'",
                "user_id": user_id,
                "subscription_status": "premium"
            }
        else:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating subscription status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update subscription status: {str(e)}")


@app.post("/api/stripe/create-customer-portal", response_model=CustomerPortalResponse)
async def create_customer_portal(user_id: str, return_url: Optional[str] = None):
    """
    Create a Stripe Customer Portal session for managing subscriptions.
    Allows users to update payment method, cancel subscription, etc.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    
    if not supabase:
        raise HTTPException(status_code=503, detail="Database is not configured")
    
    try:
        # Get the customer ID from subscriptions table
        response = supabase.table("subscriptions").select("stripe_customer_id").eq("user_id", user_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="No subscription found for this user")
        
        customer_id = response.data[0].get("stripe_customer_id")
        if not customer_id:
            raise HTTPException(status_code=404, detail="Customer ID not found")
        
        # Create the portal session
        portal_session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url or f"{FRONTEND_URL}/dashboard"
        )
        
        return CustomerPortalResponse(
            success=True,
            portal_url=portal_session.url
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating portal session: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating customer portal: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create customer portal: {str(e)}")


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    This endpoint receives events from Stripe about subscription changes.
    """
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    
    # Get the raw body and signature
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        # Verify the webhook signature if secret is configured
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
        else:
            # For development, parse without verification
            event = stripe.Event.construct_from(
                json.loads(payload), stripe.api_key
            )
        
        event_type = event["type"]
        event_data = event["data"]["object"]
        
        logger.info(f"Received Stripe webhook: {event_type}")
        
        # Handle different event types
        if event_type == "checkout.session.completed":
            await handle_checkout_completed(event_data)
        elif event_type == "customer.subscription.created":
            await handle_subscription_created(event_data)
        elif event_type == "customer.subscription.updated":
            await handle_subscription_updated(event_data)
        elif event_type == "customer.subscription.deleted":
            await handle_subscription_deleted(event_data)
        elif event_type == "invoice.payment_succeeded":
            await handle_payment_succeeded(event_data)
        elif event_type == "invoice.payment_failed":
            await handle_payment_failed(event_data)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
        
        return {"status": "success"}
        
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Webhook signature verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")


async def handle_checkout_completed(session):
    """Handle successful checkout session completion"""
    try:
        if session.get("mode") != "subscription":
            return
        
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        customer_email = session.get("customer_email") or session.get("customer_details", {}).get("email")
        metadata = session.get("metadata", {})
        user_id = metadata.get("user_id")
        price_type = metadata.get("price_type", "monthly")
        
        logger.info(f"Checkout completed for subscription {subscription_id}")
        
        # Get subscription details from Stripe
        subscription = stripe.Subscription.retrieve(subscription_id)
        
        # Save to database
        if supabase:
            subscription_data = {
                "user_id": user_id if user_id else None,
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
                "customer_email": customer_email,
                "status": subscription.status,
                "plan_type": price_type,
                "current_period_start": datetime.utcnow().isoformat() + "Z",
                "current_period_end": datetime.utcnow().replace(month=(datetime.utcnow().month + 1) % 12 if datetime.utcnow().month == 12 else datetime.utcnow().month + 1).isoformat() + "Z",
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Upsert subscription record
            supabase.table("subscriptions").upsert(
                subscription_data,
                on_conflict="stripe_subscription_id"
            ).execute()
            
            logger.info(f"Saved subscription {subscription_id} to database")
            
    except Exception as e:
        logger.error(f"Error handling checkout completed: {e}")


async def handle_subscription_created(subscription):
    """Handle subscription created event"""
    try:
        subscription_id = subscription.get("id")
        customer_id = subscription.get("customer")
        status = subscription.get("status")
        
        logger.info(f"Subscription created: {subscription_id} with status {status}")
        
        if supabase:
            # Check if subscription already exists
            existing = supabase.table("subscriptions").select("id").eq("stripe_subscription_id", subscription_id).execute()
            
            if not existing.data or len(existing.data) == 0:
                # Create new subscription record
                subscription_data = {
                    "stripe_customer_id": customer_id,
                    "stripe_subscription_id": subscription_id,
                    "status": status,
                    "current_period_start": datetime.utcnow().isoformat() + "Z",
                    "current_period_end": datetime.utcnow().replace(month=(datetime.utcnow().month + 1) % 12 if datetime.utcnow().month == 12 else datetime.utcnow().month + 1).isoformat() + "Z",
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("subscriptions").insert(subscription_data).execute()
            
            # Update users table - find user by stripe_customer_id
            user_result = supabase.table("users").select("id").eq("stripe_customer_id", customer_id).execute()
            
            if user_result.data and len(user_result.data) > 0:
                user_id = user_result.data[0].get("id")
                subscription_expires = datetime.utcnow().replace(month=(datetime.utcnow().month + 1) % 12 if datetime.utcnow().month == 12 else datetime.utcnow().month + 1).isoformat() + "Z"
                
                user_update_data = {
                    "subscription_status": status,
                    "stripe_customer_id": customer_id,
                    "subscription_expires": subscription_expires
                }
                
                supabase.table("users").update(user_update_data).eq("id", user_id).execute()
                logger.info(f"Updated user {user_id} with subscription info from subscription created event")
                
    except Exception as e:
        logger.error(f"Error handling subscription created: {e}")


async def handle_subscription_updated(subscription):
    """Handle subscription updated event"""
    try:
        subscription_id = subscription.get("id")
        customer_id = subscription.get("customer")
        status = subscription.get("status")
        current_period_end = subscription.get("current_period_end")
        
        logger.info(f"Subscription updated: {subscription_id} to status {status}")
        
        if supabase:
            update_data = {
                "status": status,
                "current_period_start": datetime.utcnow().isoformat() + "Z",
                "current_period_end": datetime.utcnow().replace(month=(datetime.utcnow().month + 1) % 12 if datetime.utcnow().month == 12 else datetime.utcnow().month + 1).isoformat() + "Z",
                "updated_at": datetime.utcnow().isoformat()
            }
            
            supabase.table("subscriptions").update(update_data).eq("stripe_subscription_id", subscription_id).execute()
            
            # Update users table - find user by stripe_customer_id
            user_result = supabase.table("users").select("id").eq("stripe_customer_id", customer_id).execute()
            
            if user_result.data and len(user_result.data) > 0:
                user_id = user_result.data[0].get("id")
                subscription_expires = datetime.utcnow().replace(month=(datetime.utcnow().month + 1) % 12 if datetime.utcnow().month == 12 else datetime.utcnow().month + 1).isoformat() + "Z",
                
                user_update_data = {
                    "subscription_status": status,
                    "subscription_expires": subscription_expires
                }
                
                supabase.table("users").update(user_update_data).eq("id", user_id).execute()
                logger.info(f"Updated user {user_id} with subscription info from subscription updated event")
            
    except Exception as e:
        logger.error(f"Error handling subscription updated: {e}")


async def handle_subscription_deleted(subscription):
    """Handle subscription cancelled/deleted event"""
    try:
        subscription_id = subscription.get("id")
        customer_id = subscription.get("customer")
        
        logger.info(f"Subscription deleted: {subscription_id}")
        
        customer_email = None
        customer_name = None
        plan_type = "monthly"
        end_date = None
        
        # Get current period end date
        current_period_end = subscription.get("current_period_end")
        if current_period_end:
            try:
                end_date = datetime.fromtimestamp(current_period_end).isoformat()
            except:
                pass
        
        if supabase:
            # Get subscription details including customer email and plan type
            sub_result = supabase.table("subscriptions").select("customer_email, plan_type").eq("stripe_subscription_id", subscription_id).execute()
            if sub_result.data and len(sub_result.data) > 0:
                customer_email = sub_result.data[0].get("customer_email")
                plan_type = sub_result.data[0].get("plan_type", "monthly")
            
            supabase.table("subscriptions").update({
                "status": "cancelled",
                "cancelled_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("stripe_subscription_id", subscription_id).execute()
            
            # Update users table - find user by stripe_customer_id
            user_result = supabase.table("users").select("id, email, name").eq("stripe_customer_id", customer_id).execute()
            
            if user_result.data and len(user_result.data) > 0:
                user_id = user_result.data[0].get("id")
                if not customer_email:
                    customer_email = user_result.data[0].get("email")
                customer_name = user_result.data[0].get("name")
                
                user_update_data = {
                    "subscription_status": "cancelled",
                    "subscription_expires": None
                }
                
                supabase.table("users").update(user_update_data).eq("id", user_id).execute()
                logger.info(f"Updated user {user_id} with cancelled subscription status")
        
        # Send subscription cancelled email
        if customer_email and EmailService.is_available():
            try:
                await EmailService.send_subscription_cancelled_email(
                    to_email=customer_email,
                    customer_name=customer_name,
                    plan_type=plan_type,
                    end_date=end_date
                )
                logger.info(f"Subscription cancelled email sent to {customer_email}")
            except Exception as email_error:
                logger.error(f"Failed to send subscription cancelled email: {email_error}")
            
    except Exception as e:
        logger.error(f"Error handling subscription deleted: {e}")


async def handle_payment_succeeded(invoice):
    """Handle successful payment"""
    try:
        subscription_id = invoice.get("subscription")
        customer_id = invoice.get("customer")
        customer_email = invoice.get("customer_email")
        customer_name = invoice.get("customer_name")
        amount_paid = invoice.get("amount_paid", 0)
        currency = invoice.get("currency", "usd")
        invoice_id = invoice.get("id")
        
        if subscription_id:
            logger.info(f"Payment succeeded for subscription: {subscription_id}")
            
            plan_type = "monthly"  # Default
            
            if supabase:
                # Get subscription details including plan type
                sub_result = supabase.table("subscriptions").select("plan_type, customer_email").eq("stripe_subscription_id", subscription_id).execute()
                if sub_result.data and len(sub_result.data) > 0:
                    plan_type = sub_result.data[0].get("plan_type", "monthly")
                    if not customer_email:
                        customer_email = sub_result.data[0].get("customer_email")
                
                supabase.table("subscriptions").update({
                    "status": "active",
                    "last_payment_date": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("stripe_subscription_id", subscription_id).execute()
                
                # Update users table with active status on successful payment
                if customer_id:
                    # Get subscription details for new period end date
                    try:
                        stripe_subscription = stripe.Subscription.retrieve(subscription_id)
                        subscription_expires = datetime.utcnow().replace(month=(datetime.utcnow().month + 1) % 12 if datetime.utcnow().month == 12 else datetime.utcnow().month + 1).isoformat() + "Z",
                    except Exception:
                        subscription_expires = None
                    
                    user_result = supabase.table("users").select("id, email, name").eq("stripe_customer_id", customer_id).execute()
                    
                    if user_result.data and len(user_result.data) > 0:
                        user_id = user_result.data[0].get("id")
                        if not customer_email:
                            customer_email = user_result.data[0].get("email")
                        if not customer_name:
                            customer_name = user_result.data[0].get("name")
                        
                        user_update_data = {
                            "subscription_status": "active",
                            "subscription_expires": subscription_expires
                        }
                        
                        supabase.table("users").update(user_update_data).eq("id", user_id).execute()
                        logger.info(f"Updated user {user_id} with active subscription on payment success")
            
            # Send payment success email
            if customer_email and EmailService.is_available():
                try:
                    await EmailService.send_payment_success_email(
                        to_email=customer_email,
                        customer_name=customer_name,
                        amount=amount_paid,
                        currency=currency,
                        plan_type=plan_type,
                        subscription_id=subscription_id,
                        invoice_id=invoice_id
                    )
                    logger.info(f"Payment success email sent to {customer_email}")
                except Exception as email_error:
                    logger.error(f"Failed to send payment success email: {email_error}")
                
    except Exception as e:
        logger.error(f"Error handling payment succeeded: {e}")


async def handle_payment_failed(invoice):
    """Handle failed payment"""
    try:
        subscription_id = invoice.get("subscription")
        customer_id = invoice.get("customer")
        customer_email = invoice.get("customer_email")
        customer_name = invoice.get("customer_name")
        amount_due = invoice.get("amount_due", 0)
        currency = invoice.get("currency", "usd")
        
        # Extract failure reason from invoice
        failure_reason = None
        if invoice.get("last_payment_error"):
            failure_reason = invoice["last_payment_error"].get("message")
        elif invoice.get("status_transitions", {}).get("marked_uncollectible_at"):
            failure_reason = "Payment could not be collected"
        
        # Get next retry date if available
        next_retry_date = None
        next_payment_attempt = invoice.get("next_payment_attempt")
        if next_payment_attempt:
            try:
                next_retry_date = datetime.fromtimestamp(next_payment_attempt).strftime("%B %d, %Y")
            except:
                pass
        
        if subscription_id:
            logger.info(f"Payment failed for subscription: {subscription_id}")
            
            if supabase:
                # Get customer email from subscription if not in invoice
                if not customer_email:
                    sub_result = supabase.table("subscriptions").select("customer_email").eq("stripe_subscription_id", subscription_id).execute()
                    if sub_result.data and len(sub_result.data) > 0:
                        customer_email = sub_result.data[0].get("customer_email")
                
                # Try to get from users table
                if not customer_email and customer_id:
                    user_result = supabase.table("users").select("email, name").eq("stripe_customer_id", customer_id).execute()
                    if user_result.data and len(user_result.data) > 0:
                        customer_email = user_result.data[0].get("email")
                        if not customer_name:
                            customer_name = user_result.data[0].get("name")
                
                supabase.table("subscriptions").update({
                    "status": "past_due",
                    "updated_at": datetime.utcnow().isoformat()
                }).eq("stripe_subscription_id", subscription_id).execute()
            
            # Send payment failed email
            if customer_email and EmailService.is_available():
                try:
                    await EmailService.send_payment_failed_email(
                        to_email=customer_email,
                        customer_name=customer_name,
                        amount=amount_due,
                        currency=currency,
                        failure_reason=failure_reason,
                        next_retry_date=next_retry_date
                    )
                    logger.info(f"Payment failed email sent to {customer_email}")
                except Exception as email_error:
                    logger.error(f"Failed to send payment failed email: {email_error}")
                
    except Exception as e:
        logger.error(f"Error handling payment failed: {e}")


@app.get("/api/stripe/config")
async def get_stripe_config():
    """
    Get Stripe publishable key for frontend.
    """
    if not STRIPE_PUBLISHABLE_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    
    return {
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "monthly_price_id": STRIPE_PRICE_ID_MONTHLY,
        "yearly_price_id": STRIPE_PRICE_ID_YEARLY
    }


if __name__ == "__main__":
    print("🚀 Starting AI Image Editor Server...")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🔍 Health Check: http://localhost:8000/health")
    print("⚡ Server running on: http://localhost:8000")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True,
        server_header=False,
        date_header=False,
        timeout_keep_alive=30,
        timeout_graceful_shutdown=10
    )
