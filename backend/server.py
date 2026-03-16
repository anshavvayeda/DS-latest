from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv

from app.models.database import init_db, close_db, get_redis, init_redis, AsyncSessionLocal
from app.deps import OPENROUTER_API_KEY, ADMIN_USERNAME, ADMIN_PASSWORD

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate critical config at startup
if not OPENROUTER_API_KEY:
    logger.error("=" * 60)
    logger.error("CRITICAL: OPENROUTER_API_KEY is MISSING from environment!")
    logger.error("AI features (extraction, help, evaluation) WILL FAIL without this key.")
    logger.error("Please add OPENROUTER_API_KEY to backend/.env")
    logger.error("=" * 60)
else:
    logger.info(f"✅ OPENROUTER_API_KEY present: {OPENROUTER_API_KEY[:15]}***")

if ADMIN_USERNAME and ADMIN_PASSWORD:
    logger.info(f"✅ Admin credentials configured (username: {ADMIN_USERNAME})")
else:
    logger.warning("⚠️ Admin credentials not configured in environment")

app = FastAPI(title="StudyBuddy - Smart Learning Platform")

# CORS Configuration
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "https://13.201.25.124",
    "http://13.201.25.124",
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.preview\.emergentagent\.com",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoints (non-prefixed, for Kubernetes probes)
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "studybuddy-backend"}

@app.get("/readiness")
async def readiness_check():
    return {"status": "ready", "service": "studybuddy-backend"}

@app.on_event("startup")
async def startup():
    """Application startup - initialize all services"""
    from app.services.storage_service import (
        initialize_s3, setup_s3_lifecycle_policy,
        ensure_temp_directory, cleanup_old_temp_files
    )

    logger.info("🚀 Starting StudyBuddy backend...")

    await init_db()
    logger.info("✅ Database initialized")

    init_redis()

    try:
        initialize_s3()
        logger.info("✅ S3 storage initialized")
        setup_s3_lifecycle_policy()
    except Exception as e:
        logger.error(f"❌ CRITICAL: S3 initialization failed")
        logger.error(f"   {str(e)}")
        logger.error("   Application will continue but file operations will fail")

    try:
        ensure_temp_directory()
        cleanup_old_temp_files()
    except Exception as e:
        logger.error(f"❌ Temp storage setup failed: {e}")

    # Startup validation
    logger.info("🔍 System validation:")

    try:
        from app.services.background_extraction import ExtractionStatus, start_extraction_task
        from app.services.gpt4o_extraction import ExtractionStage, extract_with_gpt4o
        logger.info("✅ Background extraction service ready (GPT-4o pipeline)")
    except ImportError as e:
        logger.error(f"❌ Background extraction service unavailable: {e}")

    try:
        from app.models.database import Test
        logger.info("✅ Database schema loaded")
        test_columns = Test.__table__.columns.keys()
        required_cols = ['extraction_progress', 'questions_extracted_count', 'extraction_stage', 'extraction_stage_message']
        missing = [col for col in required_cols if col not in test_columns]
        if missing:
            logger.error(f"❌ Database missing columns: {missing}")
        else:
            logger.info(f"✅ Database schema validated ({len(test_columns)} columns)")
    except Exception as e:
        logger.error(f"❌ Database schema validation failed: {e}")

    asyncio.create_task(retention_cleanup_task())

    logger.info("🎉 StudyBuddy backend started successfully")

@app.on_event("shutdown")
async def shutdown():
    await close_db()


async def retention_cleanup_task():
    """
    Background cron job: Data retention policy for AI evaluation results.
    Runs once daily at midnight (00:00). Deletes expired EvaluationResult records
    (2-month TTL) after condensing per-question feedback into a brief improvement
    summary on the StructuredTestSubmission record.
    """
    await asyncio.sleep(10)
    logger.info("📋 Data retention cleanup task started (runs daily at 00:00)")

    while True:
        now = datetime.now(timezone.utc)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (next_midnight - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        try:
            async with AsyncSessionLocal() as db:
                from app.routes.structured_tests import _condense_and_cleanup
                deleted = await _condense_and_cleanup(db)
                if deleted > 0:
                    logger.info(f"🧹 Retention cleanup: deleted {deleted} expired evaluation records, summaries retained")
                else:
                    logger.info("🧹 Retention cleanup: no expired records")
        except Exception as e:
            logger.error(f"Retention cleanup task error: {e}")


# Register route modules
from app.routes.auth import router as auth_router
from app.routes.content import router as content_router
from app.routes.homework import router as homework_router
from app.routes.parent_teacher import router as parent_teacher_router
from app.routes.structured_tests import router as structured_tests_router

app.include_router(auth_router, prefix="/api")
app.include_router(content_router, prefix="/api")
app.include_router(homework_router, prefix="/api")
app.include_router(parent_teacher_router, prefix="/api")
app.include_router(structured_tests_router, prefix="/api")
