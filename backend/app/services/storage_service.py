import os
import boto3
import json
from typing import Optional
import logging
from datetime import datetime, timedelta
import re
import tempfile
from pathlib import Path
import time

logger = logging.getLogger(__name__)

# S3 Configuration - MANDATORY
S3_BUCKET = os.getenv('S3_BUCKET_NAME')
AWS_ACCESS_KEY = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')

# Temporary storage configuration
TEMP_DIR = Path("/app/backend/uploads/tmp")
TEMP_FILE_MAX_AGE_HOURS = 2  # Delete files older than 2 hours

# Initialize S3 client - FAIL HARD if not configured
s3_client = None
_s3_initialized = False

def ensure_temp_directory():
    """
    Ensure temporary upload directory exists.
    Called at startup.
    """
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"✅ Temporary directory ready: {TEMP_DIR}")
    except Exception as e:
        logger.error(f"❌ Failed to create temp directory: {e}")
        raise


def cleanup_old_temp_files():
    """
    Delete temporary files older than TEMP_FILE_MAX_AGE_HOURS.
    Called at application startup to clean up orphaned files.
    
    Returns:
        Number of files deleted
    """
    if not TEMP_DIR.exists():
        logger.info("Temp directory doesn't exist, skipping cleanup")
        return 0
    
    try:
        deleted_count = 0
        current_time = time.time()
        cutoff_time = current_time - (TEMP_FILE_MAX_AGE_HOURS * 3600)
        
        for file_path in TEMP_DIR.rglob("*"):
            if file_path.is_file():
                try:
                    file_age = file_path.stat().st_mtime
                    if file_age < cutoff_time:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"🗑️ Deleted old temp file: {file_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {file_path}: {e}")
        
        if deleted_count > 0:
            logger.info(f"✅ Startup cleanup: Deleted {deleted_count} old temp file(s)")
        else:
            logger.info("✅ Startup cleanup: No old temp files found")
        
        return deleted_count
        
    except Exception as e:
        logger.error(f"❌ Temp file cleanup failed: {e}")
        return 0


def initialize_s3():
    """
    Initialize S3 client with strict validation.
    Called once at application startup.
    MUST succeed for file operations to work.
    """
    global s3_client, _s3_initialized
    
    if _s3_initialized:
        logger.info("S3 already initialized, skipping")
        return  # Already initialized
    
    # Validate environment variables
    missing_vars = []
    if not AWS_ACCESS_KEY:
        missing_vars.append('AWS_ACCESS_KEY_ID')
    if not AWS_SECRET_KEY:
        missing_vars.append('AWS_SECRET_ACCESS_KEY')
    if not S3_BUCKET:
        missing_vars.append('S3_BUCKET_NAME')
    
    if missing_vars:
        error_msg = f"Storage not configured. Missing environment variables: {', '.join(missing_vars)}"
        logger.error(f"❌ {error_msg}")
        logger.error("   Please set these in backend/.env:")
        for var in missing_vars:
            logger.error(f"     - {var}")
        raise Exception(error_msg)
    
    # Check for dummy/placeholder values
    if AWS_ACCESS_KEY.startswith('your-') or AWS_ACCESS_KEY == 'dummy' or AWS_ACCESS_KEY == 'test':
        error_msg = "AWS credentials appear to be placeholders. Please configure real AWS credentials."
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)
    
    # Initialize boto3 S3 client
    try:
        logger.info(f"🔧 Initializing S3 client...")
        logger.info(f"   Bucket: {S3_BUCKET}")
        logger.info(f"   Region: {AWS_REGION}")
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )
        
        # Test connection by checking bucket exists and is accessible
        logger.info(f"🔍 Testing S3 connection to bucket: {S3_BUCKET}")
        s3_client.head_bucket(Bucket=S3_BUCKET)
        
        _s3_initialized = True
        logger.info(f"✅ S3 initialized successfully")
        logger.info(f"   Bucket: {S3_BUCKET}")
        logger.info(f"   Region: {AWS_REGION}")
        logger.info(f"   Access: Verified")
        
    except s3_client.exceptions.NoSuchBucket:
        error_msg = f"S3 bucket '{S3_BUCKET}' does not exist. Please create it or check the name."
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)
        
    except s3_client.exceptions.ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '403':
            error_msg = f"Access denied to S3 bucket '{S3_BUCKET}'. Check AWS credentials and permissions."
        else:
            error_msg = f"S3 connection failed: {error_code} - {e.response['Error'].get('Message', 'Unknown error')}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Failed to initialize S3: {type(e).__name__}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)

def ensure_s3_initialized():
    """Ensure S3 is initialized before use"""
    if not _s3_initialized:
        initialize_s3()


def sanitize_component(component: str) -> str:
    """
    Sanitize individual path components (class, subject, chapter names) ONLY.
    Does NOT sanitize full paths. Preserves folder structure.
    
    Examples:
        "Class 5" -> "class5"
        "Science & Tech" -> "science_tech"
    """
    # Convert to lowercase
    sanitized = component.lower()
    # Replace spaces and special chars with underscore
    sanitized = re.sub(r'[^\w]+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    return sanitized


def sanitize_school_name(school_name: str) -> str:
    """
    Sanitize school name for use in S3 paths.
    Preserves capitalization for readability.
    
    Examples:
        "Delhi Public School" -> "Delhi_Public_School"
        "Modern Academy" -> "Modern_Academy"
        "St. Mary's School" -> "St_Marys_School"
    """
    # Replace spaces and special chars with underscore
    sanitized = re.sub(r'[^\w]+', '_', school_name)
    # Collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    return sanitized or "Unknown_School"


def normalize_title(title: str) -> str:
    """
    Normalize user-entered titles for safe, deterministic S3 keys.
    Used for homework titles and PYQ exam names.
    
    Rules:
    - Lowercase
    - Trim whitespace
    - Convert spaces to underscore
    - Remove special characters except underscore
    - Collapse multiple underscores
    - Remove leading/trailing underscores
    
    Examples:
        "Algebra Basics"        -> "algebra_basics"
        "Mid Term – I"          -> "mid_term_i"
        "Final Exam (2023)"     -> "final_exam_2023"
        "  Test   1  "          -> "test_1"
    
    Returns:
        Safe, deterministic slug for S3 keys
    """
    # Strip whitespace
    normalized = title.strip()
    # Convert to lowercase
    normalized = normalized.lower()
    # Replace spaces and special chars with underscore
    normalized = re.sub(r'[^\w]+', '_', normalized)
    # Collapse multiple underscores
    normalized = re.sub(r'_+', '_', normalized)
    # Remove leading/trailing underscores
    normalized = normalized.strip('_')
    
    if not normalized:
        raise ValueError("Title cannot be empty after normalization")
    
    return normalized


def normalize_chapter_slug(chapter_name: str) -> str:
    """
    Normalize chapter name to canonical slug format with 'chapter_' prefix.
    Ensures consistent S3 paths regardless of database format.
    
    Examples:
        "4" -> "chapter_4"
        "CHAPTER 4" -> "chapter_4"
        "Chap 1" -> "chapter_1"
        "Chapter 2" -> "chapter_2"
    """
    # First sanitize
    sanitized = sanitize_component(chapter_name)
    
    # If it already starts with "chapter", keep as-is
    if sanitized.startswith('chapter_'):
        return sanitized
    
    # If it's "chap_N", convert to "chapter_N"
    if sanitized.startswith('chap_'):
        return sanitized.replace('chap_', 'chapter_', 1)
    
    # If it's just a number or doesn't have "chapter" prefix, add it
    # Extract any trailing number
    import re
    match = re.search(r'(\d+)$', sanitized)
    if match:
        number = match.group(1)
        return f"chapter_{number}"
    
    # Fallback: prefix with "chapter_"
    return f"chapter_{sanitized}"


def build_deterministic_s3_key(
    standard: int, 
    subject: str, 
    chapter: str, 
    tool: str,
    prefix: str = "ai_content",
    school_name: str = None
) -> str:
    """
    Build deterministic S3 key with STRICT folder structure.
    
    Format: {school_name}/{prefix}/class{standard}/{subject}/{chapter}/{tool}.json
    
    Example:
        standard=5, subject="Science", chapter="Acids & Bases", tool="quiz", school_name="KV"
        -> "KV/ai_content/class5/science/chapter_acids_bases/quiz.json"
    
    Args:
        standard: Class standard (1-10)
        subject: Subject name (will be sanitized)
        chapter: Chapter name (will be normalized to canonical slug)
        tool: Tool name (revision_notes, flashcards, quiz)
        prefix: Root prefix (default: "ai_content")
        school_name: School name for multi-tenancy (optional)
    
    Returns:
        Complete S3 key with proper folder structure
    """
    # Sanitize ONLY individual components, NOT the full path
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    chapter_folder = normalize_chapter_slug(chapter)  # Use canonical slug
    
    # Build deterministic path with school prefix if provided
    if school_name:
        school_folder = sanitize_school_name(school_name)
        s3_key = f"{school_folder}/{prefix}/{class_folder}/{subject_folder}/{chapter_folder}/{tool}.json"
    else:
        # Fallback to root path (legacy support)
        s3_key = f"{prefix}/{class_folder}/{subject_folder}/{chapter_folder}/{tool}.json"
        logger.warning(f"⚠️ build_deterministic_s3_key called without school_name - using legacy path")
    
    logger.info(f"📍 Built deterministic S3 key: {s3_key}")
    return s3_key


async def upload_pdf_to_s3(file_content: bytes, standard: int, subject: str, chapter: str, school_name: str = None) -> str:
    """
    Upload PDF to S3 with school-based deterministic path.
    NO LOCAL FALLBACK - fails if S3 unavailable.
    
    NEW: Path format: {school}/pdfs/class{standard}/{subject}/{chapter}/textbook.pdf
    
    Returns:
        S3 key (not full URL)
    
    Raises:
        Exception if S3 upload fails
    """
    ensure_s3_initialized()
    
    # Build deterministic key with school prefix
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    chapter_folder = normalize_chapter_slug(chapter)  # Use canonical slug
    
    # NEW: Include school in path
    if school_name:
        school_folder = sanitize_school_name(school_name)
        s3_key = f"{school_folder}/pdfs/{class_folder}/{subject_folder}/{chapter_folder}/textbook.pdf"
    else:
        # Fallback for backward compatibility
        s3_key = f"pdfs/{class_folder}/{subject_folder}/{chapter_folder}/textbook.pdf"
    
    logger.info(f"📤 UPLOAD: standard={standard}, subject='{subject}', chapter='{chapter}', school='{school_name}'")
    logger.info(f"📤 UPLOAD: Computed path: {s3_key}")
    
    try:
        logger.info(f"📤 Uploading PDF to S3: {s3_key}")
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf'
        )
        
        logger.info(f"✅ PDF uploaded successfully to S3: {s3_key}")
        return s3_key
        
    except Exception as e:
        logger.error(f"❌ S3 upload failed: {e}")
        raise Exception(f"Failed to upload PDF to S3: {e}. S3 is mandatory.")


async def upload_pyq_to_s3(file_content: bytes, standard: int, subject: str, year: str, exam_name: str) -> str:
    """
    Upload PYQ to S3 with deterministic, title-based path.
    NO LOCAL FALLBACK - fails if S3 unavailable.
    Fails if file already exists (no overwrites).
    
    Path format: pyq/class{standard}/{subject}/{year}/{normalized_exam_name}.pdf
    
    Returns:
        S3 key (not full URL)
    
    Raises:
        Exception if S3 upload fails or file already exists
    """
    ensure_s3_initialized()
    
    # Build deterministic key using normalized exam name
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    exam_slug = normalize_title(exam_name)  # Use normalize_title for safe S3 keys
    
    s3_key = f"pyq/{class_folder}/{subject_folder}/{year}/{exam_slug}.pdf"
    
    logger.info(f"📤 PYQ UPLOAD: '{exam_name}' -> slug: '{exam_slug}'")
    logger.info(f"📤 PYQ: Path: {s3_key}")
    
    # Check if file already exists - NO overwrites
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        # File exists - do NOT overwrite
        logger.warning(f"⚠️ PYQ already exists at: {s3_key}")
        raise Exception(f"PYQ '{exam_name}' for year {year} already exists. Please use a different exam name.")
    except s3_client.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404':
            pass  # File doesn't exist - proceed
        else:
            raise Exception(f"S3 check failed: {e}")
    except s3_client.exceptions.NoSuchKey:
        pass  # File doesn't exist - proceed
    
    # Upload to S3
    try:
        logger.info(f"📤 Uploading PYQ to S3: {s3_key}")
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf'
        )
        
        logger.info(f"✅ PYQ uploaded successfully to S3: {s3_key}")
        return s3_key
        
    except Exception as e:
        logger.error(f"❌ S3 upload failed: {e}")
        raise Exception(f"Failed to upload PYQ to S3: {e}")


async def upload_ai_content_to_s3(
    content: dict, 
    standard: int, 
    subject: str, 
    chapter: str, 
    tool: str,
    school_name: str = None
) -> str:
    """
    Upload AI-generated JSON content to S3 with deterministic path.
    NO LOCAL FALLBACK.
    
    Path format: {school_name}/ai_content/class{standard}/{subject}/{chapter}/{tool}.json
    
    Args:
        content: Dictionary to upload as JSON
        standard: Class standard (1-10)
        subject: Subject name
        chapter: Chapter name
        tool: Tool name (revision_notes, flashcards, quiz)
        school_name: School name for multi-tenancy (optional)
    
    Returns:
        S3 key (not full URL)
    
    Raises:
        Exception if S3 upload fails
    """
    ensure_s3_initialized()
    
    # Build deterministic key
    s3_key = build_deterministic_s3_key(standard, subject, chapter, tool, school_name=school_name)
    
    try:
        logger.info(f"📤 Uploading AI content to S3: {s3_key}")
        
        # Convert dict to JSON bytes
        json_bytes = json.dumps(content, indent=2).encode('utf-8')
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json_bytes,
            ContentType='application/json'
        )
        
        logger.info(f"✅ AI content uploaded successfully to S3: {s3_key}")
        return s3_key
        
    except Exception as e:
        logger.error(f"❌ Failed to upload AI content to S3: {e}")
        raise Exception(f"Failed to upload AI content to S3: {e}")


async def fetch_ai_content_from_s3(
    standard: int,
    subject: str,
    chapter: str,
    tool: str,
    school_name: str = None
) -> Optional[dict]:
    """
    Fetch AI-generated content from S3.
    Returns None if not found (content not generated yet).
    
    Args:
        standard: Class standard
        subject: Subject name
        chapter: Chapter name
        tool: Tool name (revision_notes, flashcards, quiz)
        school_name: School name for multi-tenancy (optional)
    
    Returns:
        Parsed JSON dict or None if not found
    """
    ensure_s3_initialized()
    
    # Build deterministic key
    s3_key = build_deterministic_s3_key(standard, subject, chapter, tool, school_name=school_name)
    
    try:
        logger.info(f"📥 Fetching AI content from S3: {s3_key}")
        
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = json.loads(response['Body'].read().decode('utf-8'))
        
        logger.info("✅ AI content fetched successfully from S3")
        return content
        
    except s3_client.exceptions.NoSuchKey:
        logger.info(f"⚠️ AI content not found in S3: {s3_key}")
        return None
    except Exception as e:
        logger.error(f"❌ Error fetching from S3: {e}")
        return None


async def check_pdf_exists_in_s3(standard: int, subject: str, chapter: str, school_name: str = None) -> bool:
    """
    Check if PDF exists in S3 before attempting AI generation.
    
    Args:
        standard: Class standard (1-10)
        subject: Subject name
        chapter: Chapter name
        school_name: School name for multi-tenancy (REQUIRED)
    
    Returns:
        True if PDF exists, False otherwise
    
    Raises:
        Exception if S3 access error (not just missing file)
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    chapter_folder = normalize_chapter_slug(chapter)  # Use canonical slug
    
    # Include school prefix if provided
    if school_name:
        school_folder = sanitize_school_name(school_name)
        s3_key = f"{school_folder}/pdfs/{class_folder}/{subject_folder}/{chapter_folder}/textbook.pdf"
    else:
        # Fallback to root path (legacy support)
        s3_key = f"pdfs/{class_folder}/{subject_folder}/{chapter_folder}/textbook.pdf"
        logger.warning(f"⚠️ check_pdf_exists_in_s3 called without school_name - using legacy path")
    
    logger.info(f"🔍 CHECK: standard={standard}, subject='{subject}', chapter='{chapter}'")
    logger.info(f"🔍 CHECK: Looking for: {s3_key} in bucket: {S3_BUCKET}")
    
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        logger.info(f"✅ PDF exists in S3: {s3_key}")
        return True
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"⚠️ PDF not found in S3 (NoSuchKey): {s3_key}")
        return False
    except s3_client.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404':
            logger.warning(f"⚠️ PDF not found in S3 (404): {s3_key}")
            return False
        else:
            logger.error(f"❌ S3 access error ({error_code}): {e}")
            raise Exception(f"S3 access error: {error_code} - {str(e)}")
    except Exception as e:
        logger.error(f"❌ Unexpected error checking S3: {e}")
        raise


async def download_pdf_from_s3(standard: int, subject: str, chapter: str, school_name: str = None) -> Optional[bytes]:
    """
    Download PDF from S3 for AI processing.
    
    Args:
        standard: Class/grade number
        subject: Subject name
        chapter: Chapter name
        school_name: School name for multi-tenancy (REQUIRED)
    
    Returns:
        PDF file bytes or None if not found
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    chapter_folder = normalize_chapter_slug(chapter)
    
    # Include school prefix if provided
    if school_name:
        school_folder = sanitize_school_name(school_name)
        s3_key = f"{school_folder}/pdfs/{class_folder}/{subject_folder}/{chapter_folder}/textbook.pdf"
    else:
        # Fallback to root path (legacy support)
        s3_key = f"pdfs/{class_folder}/{subject_folder}/{chapter_folder}/textbook.pdf"
        logger.warning(f"⚠️ download_pdf_from_s3 called without school_name - using legacy path")
    
    logger.info(f"📥 DOWNLOAD: Fetching PDF from S3: {s3_key}")
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        pdf_bytes = response['Body'].read()
        logger.info(f"✅ PDF downloaded: {len(pdf_bytes)/1024:.1f}KB")
        return pdf_bytes
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"⚠️ PDF not found in S3: {s3_key}")
        return None
    except s3_client.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404':
            logger.warning(f"⚠️ PDF not found in S3 (404): {s3_key}")
            return None
        logger.error(f"❌ S3 download error ({error_code}): {e}")
        raise Exception(f"S3 download error: {error_code}")
    except Exception as e:
        logger.error(f"❌ Unexpected error downloading PDF: {e}")
        raise


async def delete_ai_content_from_s3(standard: int, subject: str, chapter: str, tool: str, school_name: str = None) -> bool:
    """
    Delete AI content from S3 (used during regeneration).
    
    Args:
        standard: Class standard
        subject: Subject name
        chapter: Chapter name
        tool: Tool name (revision_notes, flashcards, quiz)
        school_name: School name for multi-tenancy (optional)
    
    Returns:
        True if deleted or not found, False on error
    """
    ensure_s3_initialized()
    
    s3_key = build_deterministic_s3_key(standard, subject, chapter, tool, school_name=school_name)
    
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        logger.info(f"🗑️ Deleted AI content from S3: {s3_key}")
        return True
    except Exception as e:
        logger.error(f"Error deleting from S3: {e}")
        return False


# =============================================================================
# PYQ SOLUTION S3 FUNCTIONS
# =============================================================================

async def upload_pyq_solution_to_s3(
    solution: dict,
    standard: int,
    subject: str,
    year: str,
    normalized_exam_name: str
) -> str:
    """
    Upload PYQ solution JSON to S3 with deterministic path.
    
    Path format: pyq/class{standard}/{subject}/{year}/{normalized_exam_name}_solution.json
    
    Args:
        solution: Solution dictionary to upload
        standard: Class standard
        subject: Subject name
        year: Year of the exam
        normalized_exam_name: Normalized exam name (already sanitized)
    
    Returns:
        S3 key for the solution
    
    Raises:
        Exception if upload fails
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    
    s3_key = f"pyq/{class_folder}/{subject_folder}/{year}/{normalized_exam_name}_solution.json"
    
    try:
        logger.info(f"📤 Uploading PYQ solution to S3: {s3_key}")
        
        json_bytes = json.dumps(solution, indent=2, ensure_ascii=False).encode('utf-8')
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json_bytes,
            ContentType='application/json'
        )
        
        logger.info(f"✅ PYQ solution uploaded successfully: {s3_key}")
        return s3_key
        
    except Exception as e:
        logger.error(f"❌ Failed to upload PYQ solution: {e}")
        raise Exception(f"Failed to upload PYQ solution to S3: {e}")


async def fetch_pyq_solution_from_s3(
    standard: int,
    subject: str,
    year: str,
    normalized_exam_name: str
) -> Optional[dict]:
    """
    Fetch PYQ solution from S3 (read-only for students).
    
    Returns:
        Parsed solution dict or None if not found
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    
    s3_key = f"pyq/{class_folder}/{subject_folder}/{year}/{normalized_exam_name}_solution.json"
    
    try:
        logger.info(f"📥 Fetching PYQ solution from S3: {s3_key}")
        
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = json.loads(response['Body'].read().decode('utf-8'))
        
        logger.info(f"✅ PYQ solution fetched successfully")
        return content
        
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"⚠️ PYQ solution not found: {s3_key}")
        return None
    except Exception as e:
        logger.error(f"❌ Error fetching PYQ solution: {e}")
        return None


async def delete_pyq_solution_from_s3(
    standard: int,
    subject: str,
    year: str,
    normalized_exam_name: str
) -> bool:
    """Delete PYQ solution from S3."""
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    
    s3_key = f"pyq/{class_folder}/{subject_folder}/{year}/{normalized_exam_name}_solution.json"
    
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        logger.info(f"🗑️ Deleted PYQ solution: {s3_key}")
        return True
    except Exception as e:
        logger.error(f"Error deleting PYQ solution: {e}")
        return False


# =============================================================================
# TEST S3 FUNCTIONS (Deterministic paths with auto-cleanup)
# =============================================================================

async def upload_test_pdf_to_s3(
    file_content: bytes,
    test_id: str,
    standard: int,
    subject: str,
    school_name: str = None
) -> tuple:
    """
    Upload test PDF to S3 with school-based path.
    
    Path format: {school_name}/tests/class{standard}/{subject}/{test_id}/test.pdf
    
    Returns:
        Tuple of (s3_key, s3_folder_key)
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    
    # NEW: Include school in path
    if school_name:
        school_folder = sanitize_school_name(school_name)
        s3_folder_key = f"{school_folder}/tests/{class_folder}/{subject_folder}/{test_id}"
    else:
        # Fallback for old data without school
        s3_folder_key = f"tests/{class_folder}/{subject_folder}/{test_id}"
    
    s3_key = f"{s3_folder_key}/test.pdf"
    
    try:
        logger.info(f"📤 Uploading test PDF to S3: {s3_key}")
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf'
        )
        
        logger.info(f"✅ Test PDF uploaded: {s3_key}")
        return (s3_key, s3_folder_key)
        
    except Exception as e:
        logger.error(f"❌ Test PDF upload failed: {e}")
        raise Exception(f"Failed to upload test PDF: {e}")


async def upload_test_questions_to_s3(
    questions: list,
    test_id: str,
    standard: int = None,
    subject: str = None,
    s3_folder_key: str = None
) -> str:
    """
    Upload extracted test questions to S3.
    
    NEW: Uses s3_folder_key from database (includes school prefix)
    Path format: {school}/tests/class{standard}/{subject}/{test_id}/questions.json
    
    Returns:
        S3 key for the questions JSON
    """
    ensure_s3_initialized()
    
    # NEW: Use s3_folder_key if provided
    if s3_folder_key:
        s3_key = f"{s3_folder_key}/questions.json"
    else:
        # Fallback
        class_folder = f"class{standard}"
        subject_folder = sanitize_component(subject)
        s3_key = f"tests/{class_folder}/{subject_folder}/{test_id}/questions.json"
    
    try:
        logger.info(f"📤 Uploading test questions to S3: {s3_key}")
        
        json_bytes = json.dumps(questions, indent=2, ensure_ascii=False).encode('utf-8')
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json_bytes,
            ContentType='application/json'
        )
        
        logger.info(f"✅ Test questions uploaded: {s3_key}")
        return s3_key
        
    except Exception as e:
        logger.error(f"❌ Test questions upload failed: {e}")
        raise Exception(f"Failed to upload test questions: {e}")


async def upload_test_answers_to_s3(
    answers: list,
    test_id: str,
    standard: int = None,
    subject: str = None,
    s3_folder_key: str = None
) -> str:
    """
    Upload extracted test answers/solutions to S3.
    
    NEW: Uses s3_folder_key from database (includes school prefix)
    Path format: {school}/tests/class{standard}/{subject}/{test_id}/answers.json
    
    Returns:
        S3 key for the answers JSON
    """
    ensure_s3_initialized()
    
    # NEW: Use s3_folder_key if provided
    if s3_folder_key:
        s3_key = f"{s3_folder_key}/answers.json"
    else:
        # Fallback
        class_folder = f"class{standard}"
        subject_folder = sanitize_component(subject)
        s3_key = f"tests/{class_folder}/{subject_folder}/{test_id}/answers.json"
    
    try:
        logger.info(f"📤 Uploading test answers to S3: {s3_key}")
        
        json_bytes = json.dumps(answers, indent=2, ensure_ascii=False).encode('utf-8')
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json_bytes,
            ContentType='application/json'
        )
        
        logger.info(f"✅ Test answers uploaded: {s3_key}")
        return s3_key
        
    except Exception as e:
        logger.error(f"❌ Test answers upload failed: {e}")
        raise Exception(f"Failed to upload test answers: {e}")


async def upload_homework_questions_to_s3(
    questions: list,
    homework_id: str,
    standard: int = None,
    subject: str = None,
    s3_folder_key: str = None
) -> str:
    """
    Upload extracted homework questions to S3.
    
    NEW: Uses s3_folder_key from database (includes school prefix)
    Path format: {school}/homework/class{standard}/{subject}/{homework_id}/questions.json
    
    Returns:
        S3 key for the questions JSON
    """
    ensure_s3_initialized()
    
    # NEW: Use s3_folder_key if provided, otherwise fall back to old path construction
    if s3_folder_key:
        s3_key = f"{s3_folder_key}/questions.json"
    else:
        # Fallback for backward compatibility
        class_folder = f"class{standard}"
        subject_folder = sanitize_component(subject)
        s3_key = f"homework/{class_folder}/{subject_folder}/{homework_id}/questions.json"
    
    try:
        logger.info(f"📤 Uploading homework questions to S3: {s3_key}")
        
        json_bytes = json.dumps(questions, indent=2, ensure_ascii=False).encode('utf-8')
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json_bytes,
            ContentType='application/json'
        )
        
        logger.info(f"✅ Homework questions uploaded: {s3_key}")
        return s3_key
    except Exception as e:
        logger.error(f"❌ Homework questions upload failed: {e}")
        raise Exception(f"Failed to upload homework questions: {e}")


async def upload_homework_solutions_to_s3(
    solutions: list,
    homework_id: str,
    standard: int = None,
    subject: str = None,
    s3_folder_key: str = None
) -> str:
    """
    Upload homework solutions to S3.
    
    NEW: Uses s3_folder_key from database (includes school prefix)
    """
    ensure_s3_initialized()
    
    # NEW: Use s3_folder_key if provided
    if s3_folder_key:
        s3_key = f"{s3_folder_key}/solutions.json"
    else:
        # Fallback
        class_folder = f"class{standard}"
        subject_folder = sanitize_component(subject)
        s3_key = f"homework/{class_folder}/{subject_folder}/{homework_id}/solutions.json"
    
    try:
        json_bytes = json.dumps(solutions, indent=2, ensure_ascii=False).encode('utf-8')
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=json_bytes, ContentType='application/json')
        logger.info(f"✅ Homework solutions uploaded: {s3_key}")
        return s3_key
    except Exception as e:
        logger.error(f"❌ Homework solutions upload failed: {e}")
        raise Exception(f"Failed to upload homework solutions: {e}")


async def upload_pyq_questions_to_s3(
    questions: list,
    pyq_id: str,
    standard: int = None,
    subject: str = None,
    year: str = None,
    s3_folder_key: str = None
) -> str:
    """
    Upload extracted PYQ questions to S3.
    
    NEW: Uses s3_folder_key from database (includes school prefix)
    """
    ensure_s3_initialized()
    
    # NEW: Use s3_folder_key if provided
    if s3_folder_key:
        s3_key = f"{s3_folder_key}/questions.json"
    else:
        # Fallback
        class_folder = f"class{standard}"
        subject_folder = sanitize_component(subject)
        s3_key = f"pyq/{class_folder}/{subject_folder}/{year}/{pyq_id}/questions.json"
    
    try:
        json_bytes = json.dumps(questions, indent=2, ensure_ascii=False).encode('utf-8')
        s3_client.put_object(Bucket=S3_BUCKET, Key=s3_key, Body=json_bytes, ContentType='application/json')
        logger.info(f"✅ PYQ questions uploaded: {s3_key}")
        return s3_key
    except Exception as e:
        logger.error(f"❌ PYQ questions upload failed: {e}")
        raise Exception(f"Failed to upload PYQ questions: {e}")


async def delete_test_folder_from_s3(s3_folder_key: str) -> bool:
    """
    Delete entire test folder from S3 (test.pdf, model_answers.pdf, questions.json).
    
    Idempotent: Safe to call multiple times.
    Verifies folder is empty after deletion.
    
    Args:
        s3_folder_key: The folder key (e.g., tests/class5/mathematics/{test_id})
    
    Returns:
        True if deleted successfully or folder doesn't exist
        False if deletion failed
    """
    ensure_s3_initialized()
    
    if not s3_folder_key:
        logger.warning("delete_test_folder_from_s3 called with empty folder key")
        return True  # Nothing to delete
    
    try:
        # List all objects in the folder
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=f"{s3_folder_key}/"
        )
        
        if 'Contents' not in response or len(response['Contents']) == 0:
            logger.info(f"✅ Test folder already empty or doesn't exist: {s3_folder_key}")
            return True  # Idempotent: folder doesn't exist
        
        objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
        deleted_keys = [obj['Key'] for obj in objects_to_delete]
        
        # Delete all objects
        delete_response = s3_client.delete_objects(
            Bucket=S3_BUCKET,
            Delete={'Objects': objects_to_delete}
        )
        
        # Check for errors
        errors = delete_response.get('Errors', [])
        if errors:
            logger.error(f"❌ S3 deletion errors: {errors}")
            return False
        
        logger.info(f"🗑️ Deleted {len(objects_to_delete)} objects from: {s3_folder_key}")
        logger.info(f"   Deleted files: {deleted_keys}")
        
        # Verify folder is empty
        verify_response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET,
            Prefix=f"{s3_folder_key}/",
            MaxKeys=1
        )
        
        if 'Contents' in verify_response and len(verify_response['Contents']) > 0:
            logger.error(f"❌ Folder not empty after deletion: {s3_folder_key}")
            return False
        
        logger.info(f"✅ Verified folder empty: {s3_folder_key}")
        return True
        
    except Exception as e:
        logger.error(f"Error deleting test folder: {e}")
        return False


async def fetch_test_questions_from_s3(
    test_id: str,
    standard: int = None,
    subject: str = None,
    s3_folder_key: str = None
) -> Optional[list]:
    """
    Fetch test questions from S3.
    
    Args:
        test_id: Test ID
        standard: Class standard (fallback if s3_folder_key not provided)
        subject: Subject name (fallback if s3_folder_key not provided)
        s3_folder_key: Full S3 folder path (includes school prefix)
    
    Returns:
        List of questions or None if not found
    """
    ensure_s3_initialized()
    
    # Use s3_folder_key if provided (includes school prefix)
    if s3_folder_key:
        s3_key = f"{s3_folder_key}/questions.json"
    else:
        # Fallback to legacy path (without school prefix)
        class_folder = f"class{standard}"
        subject_folder = sanitize_component(subject)
        s3_key = f"tests/{class_folder}/{subject_folder}/{test_id}/questions.json"
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        questions = json.loads(response['Body'].read().decode('utf-8'))
        logger.info(f"✅ Test questions fetched from: {s3_key}")
        return questions
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"⚠️ Test questions not found: {s3_key}")
        return None
    except Exception as e:
        logger.error(f"Error fetching test questions: {e}")
        return None




async def fetch_pyq_questions_from_s3(s3_folder_key: str) -> Optional[list]:
    """
    Fetch PYQ questions from S3.
    
    Args:
        s3_folder_key: Full S3 folder path (includes school prefix)
        Example: "KV/pyq/class5/mathematics/2024/pyq_id"
    
    Returns:
        List of questions or None if not found
    """
    ensure_s3_initialized()
    
    # Construct S3 key for questions.json
    s3_key = f"{s3_folder_key}/questions.json"
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        questions = json.loads(response['Body'].read().decode('utf-8'))
        logger.info(f"✅ PYQ questions fetched from: {s3_key}")
        return questions if isinstance(questions, list) else questions.get('questions', [])
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"⚠️ PYQ questions not found at: {s3_key}")
        return None
    except Exception as e:
        logger.error(f"❌ Error fetching PYQ questions from {s3_key}: {e}")
        return None

async def fetch_test_answers_from_s3(
    test_id: str,
    standard: int,
    subject: str
) -> Optional[list]:
    """
    Fetch test answers from S3.
    
    Path format: tests/class{standard}/{subject}/{test_id}/answers.json
    
    Returns:
        List of answers or None if not found
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    
    s3_key = f"tests/{class_folder}/{subject_folder}/{test_id}/answers.json"
    
    try:
        logger.info(f"📥 Fetching test answers from S3: {s3_key}")
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        answers = json.loads(response['Body'].read().decode('utf-8'))
        logger.info(f"✅ Fetched {len(answers)} answers from S3")
        return answers
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"⚠️ Test answers not found: {s3_key}")
        return None
    except Exception as e:
        logger.error(f"Error fetching test answers: {e}")
        return None


async def get_json_from_storage(s3_key: str, max_retries: int = 3) -> Optional[dict]:
    """
    Fetch JSON content from S3 by key with retry logic for reliability.
    Used for retrieving questions.json, solutions.json and other JSON files.
    
    Args:
        s3_key: The S3 key (path) to the JSON file
        max_retries: Number of retry attempts for transient failures (default: 3)
    
    Returns:
        Parsed JSON as dict/list, or None if not found
    """
    import time
    
    ensure_s3_initialized()
    
    if not s3_key:
        logger.warning("get_json_from_storage called with empty key")
        return None
    
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"📥 Fetching JSON from S3: {s3_key} (attempt {attempt + 1}/{max_retries})")
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
            content = json.loads(response['Body'].read().decode('utf-8'))
            logger.info(f"✅ JSON fetched successfully from: {s3_key}")
            return content
        except s3_client.exceptions.NoSuchKey:
            # File genuinely doesn't exist - no point retrying
            logger.warning(f"⚠️ JSON file not found (NoSuchKey): {s3_key}")
            return None
        except Exception as e:
            last_error = e
            error_str = str(e)
            logger.warning(f"⚠️ S3 fetch attempt {attempt + 1} failed: {error_str}")
            
            # Check if it's a transient error worth retrying
            transient_errors = ['timeout', 'connection', 'throttl', 'slow', 'retry', 'temporary', '503', '500']
            is_transient = any(err in error_str.lower() for err in transient_errors)
            
            if is_transient and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 0.5  # Exponential backoff: 0.5s, 1s, 1.5s
                logger.info(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
            
            # Non-transient error or final attempt
            logger.error(f"❌ Error fetching JSON from S3 after {attempt + 1} attempts: {e}")
            return None
    
    # Should not reach here, but safety
    logger.error(f"❌ All {max_retries} attempts failed for S3 key: {s3_key}. Last error: {last_error}")
    return None


# Legacy functions for homework/PYQs - kept for backward compatibility but with strict S3-only enforcement
async def upload_file_to_s3(file_content: bytes, file_name: str, content_type: str = 'application/pdf', school_name: str = None) -> Optional[str]:
    """
    Upload file to S3 with school-based folder structure.
    NO LOCAL FALLBACK - S3 only.
    
    Args:
        file_content: File bytes
        file_name: Original file name
        content_type: MIME type
        school_name: School name for folder structure (REQUIRED for proper organization)
    
    Returns: S3 key (not full URL)
    Raises: Exception if S3 unavailable
    """
    ensure_s3_initialized()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = sanitize_component(file_name.replace('.pdf', '')) + '.pdf'
    
    # Include school folder if provided
    if school_name:
        school_folder = sanitize_school_name(school_name)
        s3_key = f"{school_folder}/uploads/{timestamp}_{safe_name}"
    else:
        # Fallback to root uploads (for backward compatibility, but should be avoided)
        s3_key = f"uploads/{timestamp}_{safe_name}"
        logger.warning(f"⚠️ File uploaded without school_name - using root uploads folder")
    
    try:
        logger.info(f"📤 Uploading file to S3: {s3_key}")
        
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=content_type
        )
        
        logger.info(f"✅ File uploaded to S3: {s3_key}")
        return s3_key  # Return S3 key instead of full URL
        
    except Exception as e:
        logger.error(f"❌ S3 upload failed: {e}")
        raise Exception(f"Failed to upload to S3: {e}. S3 is mandatory.")


async def upload_homework_pdf_to_s3(file_content: bytes, standard: int, subject: str, homework_title: str) -> str:
    """
    Upload homework PDF to S3 with deterministic, title-based path.
    NO LOCAL FALLBACK - fails if S3 unavailable.
    Fails if file already exists (no overwrites).
    
    Path format: homework/class{standard}/{subject}/{homework_title}.pdf
    
    Returns:
        S3 key (not full URL)
    
    Raises:
        Exception if S3 upload fails or file already exists
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    title_slug = normalize_title(homework_title)  # Use normalize_title for safety
    
    s3_key = f"homework/{class_folder}/{subject_folder}/{title_slug}.pdf"
    
    logger.info(f"📤 HOMEWORK UPLOAD: '{homework_title}' -> slug: '{title_slug}'")
    logger.info(f"📤 HOMEWORK: Path: {s3_key}")
    
    # Check if file already exists
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        # File exists - do NOT overwrite
        logger.warning(f"⚠️ Homework already exists at: {s3_key}")
        raise Exception(f"Homework with title '{homework_title}' already exists. Please change the title.")
    except s3_client.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404':
            pass  # File doesn't exist - proceed
        else:
            raise Exception(f"S3 check failed: {e}")
    except s3_client.exceptions.NoSuchKey:
        pass  # File doesn't exist - proceed
    
    # Upload to S3
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf',
            Tagging='type=homework&expiry=10days'
        )
        
        logger.info(f"✅ Homework uploaded to S3: {s3_key}")
        return s3_key
        
    except Exception as e:
        logger.error(f"❌ Homework upload failed: {e}")
        raise Exception(f"Failed to upload homework to S3: {e}")


async def upload_homework_solution_pdf_to_s3(file_content: bytes, standard: int, subject: str, homework_title: str) -> str:
    """
    Upload homework solution PDF to S3 with deterministic, title-based path.
    NO LOCAL FALLBACK - fails if S3 unavailable.
    Fails if file already exists (no overwrites).
    
    Path format: homework/class{standard}/{subject}/{homework_title}_solution.pdf
    
    Returns:
        S3 key (not full URL)
    
    Raises:
        Exception if S3 upload fails or file already exists
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    title_slug = normalize_title(homework_title)  # Use normalize_title for safety
    
    s3_key = f"homework/{class_folder}/{subject_folder}/{title_slug}_solution.pdf"
    
    logger.info(f"📤 SOLUTION UPLOAD: '{homework_title}' -> slug: '{title_slug}'")
    logger.info(f"📤 SOLUTION: Path: {s3_key}")
    
    # Check if file already exists
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        # File exists - do NOT overwrite
        logger.warning(f"⚠️ Solution already exists at: {s3_key}")
        raise Exception(f"Solution for homework '{homework_title}' already exists.")
    except s3_client.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == '404':
            pass  # File doesn't exist - proceed
        else:
            raise Exception(f"S3 check failed: {e}")
    except s3_client.exceptions.NoSuchKey:
        pass  # File doesn't exist - proceed
    
    # Upload to S3
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf',
            Tagging='type=homework_solution&expiry=10days'
        )
        
        logger.info(f"✅ Solution uploaded to S3: {s3_key}")
        return s3_key
        
    except Exception as e:
        logger.error(f"❌ Solution upload failed: {e}")
        raise Exception(f"Failed to upload solution to S3: {e}")


async def delete_homework_from_s3(standard: int, subject: str, homework_title: str) -> bool:
    """
    Delete both homework and solution PDFs from S3 using title-based paths.
    
    Returns:
        True if deleted successfully, False on error
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    title_slug = normalize_title(homework_title)
    
    homework_key = f"homework/{class_folder}/{subject_folder}/{title_slug}.pdf"
    solution_key = f"homework/{class_folder}/{subject_folder}/{title_slug}_solution.pdf"
    
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=homework_key)
        logger.info(f"🗑️ Deleted homework from S3: {homework_key}")
        
        # Try to delete solution (may not exist)
        try:
            s3_client.delete_object(Bucket=S3_BUCKET, Key=solution_key)
            logger.info(f"🗑️ Deleted solution from S3: {solution_key}")
        except Exception:
            pass  # Solution may not exist
        
        return True
    except Exception as e:
        logger.error(f"Error deleting homework from S3: {e}")
        return False



def generate_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    """
    Generate a presigned URL for S3 file access.
    
    Args:
        s3_key: S3 object key (path)
        expiration: URL expiration time in seconds (default: 1 hour)
    
    Returns:
        Presigned URL string
    """
    ensure_s3_initialized()
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_BUCKET, 'Key': s3_key},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL for {s3_key}: {e}")
        raise Exception(f"Failed to generate download URL: {e}")


def delete_s3_folder(s3_folder_key: str) -> bool:
    """
    Delete an entire S3 folder and all its contents.
    
    Args:
        s3_folder_key: S3 folder path (e.g., "KV/homework/class5/science/{id}")
    
    Returns:
        True if deletion successful, False otherwise
    """
    ensure_s3_initialized()
    
    try:
        # List all objects in the folder
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET, Prefix=s3_folder_key)
        
        if 'Contents' not in response:
            logger.warning(f"⚠️ No files found in S3 folder: {s3_folder_key}")
            return True
        
        # Delete all objects in the folder
        objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
        
        if objects_to_delete:
            s3_client.delete_objects(
                Bucket=S3_BUCKET,
                Delete={'Objects': objects_to_delete}
            )
            logger.info(f"🗑️ Deleted {len(objects_to_delete)} files from S3: {s3_folder_key}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error deleting S3 folder {s3_folder_key}: {e}")
        return False


def delete_ai_content_folder(s3_base_path: str) -> bool:
    """
    Delete AI content folder (revision_notes.json, flashcards.json, practice_quiz.json).
    
    Args:
        s3_base_path: Base path for AI content (e.g., "KV/ai_content/class5/science/chapter_1")
    
    Returns:
        True if deletion successful, False otherwise
    """
    ensure_s3_initialized()
    
    try:
        files_to_delete = [
            f"{s3_base_path}/revision_notes.json",
            f"{s3_base_path}/flashcards.json",
            f"{s3_base_path}/practice_quiz.json"
        ]
        
        deleted_count = 0
        for file_key in files_to_delete:
            try:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=file_key)
                deleted_count += 1
            except Exception:
                pass  # File may not exist
        
        logger.info(f"🗑️ Deleted {deleted_count} AI content files from: {s3_base_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Error deleting AI content: {e}")
        return False

    except Exception as e:
        logger.error(f"❌ Failed to generate presigned URL for {s3_key}: {e}")
        raise Exception(f"Failed to generate download URL: {e}")


async def delete_pyq_from_s3(standard: int, subject: str, year: str, pyq_title: str) -> bool:
    """
    Delete PYQ PDF from S3 using title-based path.
    
    Returns:
        True if deleted successfully, False on error
    """
    ensure_s3_initialized()
    
    class_folder = f"class{standard}"
    subject_folder = sanitize_component(subject)
    title_slug = normalize_title(pyq_title)
    
    pyq_key = f"pyq/{class_folder}/{subject_folder}/{year}/{title_slug}.pdf"
    
    try:
        s3_client.delete_object(Bucket=S3_BUCKET, Key=pyq_key)
        logger.info(f"🗑️ Deleted PYQ from S3: {pyq_key}")
        return True
    except Exception as e:
        logger.error(f"Error deleting PYQ from S3: {e}")
        return False


async def delete_file_from_storage(file_path: str) -> bool:
    """Delete file from S3. No local storage support."""
    ensure_s3_initialized()
    
    try:
        # Extract S3 key from URL or use directly if it's a key
        if f"{S3_BUCKET}.s3." in file_path:
            s3_key = file_path.split(".amazonaws.com/")[1]
        else:
            s3_key = file_path
        
        s3_client.delete_object(Bucket=S3_BUCKET, Key=s3_key)
        logger.info(f"✅ Deleted S3 file: {s3_key}")
        return True
    except Exception as e:
        logger.error(f"Error deleting S3 file: {e}")
        return False


def setup_s3_lifecycle_policy():
    """Setup S3 lifecycle policy to auto-delete homework after 10 days."""
    if not s3_client or not S3_BUCKET:
        logger.error("S3 not configured. Cannot set lifecycle policy.")
        return False
    
    try:
        lifecycle_config = {
            'Rules': [
                {
                    'Id': 'DeleteHomeworkAfter10Days',
                    'Status': 'Enabled',
                    'Filter': {
                        'Prefix': 'homework/'
                    },
                    'Expiration': {
                        'Days': 10
                    }
                }
            ]
        }
        
        s3_client.put_bucket_lifecycle_configuration(
            Bucket=S3_BUCKET,
            LifecycleConfiguration=lifecycle_config
        )
        logger.info("✅ S3 lifecycle policy set: homework files will be deleted after 10 days")
        return True
    except Exception as e:
        logger.error(f"Error setting S3 lifecycle policy: {e}")
        return False


async def get_file_from_s3(s3_url: str) -> Optional[bytes]:
    """Fetch file from S3."""
    ensure_s3_initialized()
    
    try:
        s3_key = s3_url.split(f"{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/")[1]
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        return response['Body'].read()
    except Exception as e:
        logger.error(f"Error downloading from S3: {e}")
        return None
