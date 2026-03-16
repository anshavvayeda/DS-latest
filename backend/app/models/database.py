"""
StudyBuddy Database Schema - PostgreSQL
========================================

Tables:
-------
CORE AUTH:
- users: Base authentication (email/phone, role)
- student_profiles: Extended student data (roll_no as primary identifier)
- otp_codes: OTP verification

CONTENT MANAGEMENT:
- subjects: 5 default subjects per standard (Class 1-10)
- chapters: Chapters within subjects
- contents: Uploaded textbooks (S3 URLs only)
- previous_year_papers: PYQ metadata and S3 URLs

STUDENT ACADEMIC DATA:
- student_exam_scores: School exam scores (roll_no FK)
- student_practice_progress: Chapter-wise practice test progress
- student_homework_status: Homework completion tracking

CACHE:
- quizzes: Teacher-created quizzes
- ai_content_cache: Cached AI-generated content
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, ForeignKey, JSON, Float, Date, Index, text
from datetime import datetime, timezone
import uuid
import os
from dotenv import load_dotenv
import redis
import logging

logger = logging.getLogger(__name__)

load_dotenv()

Base = declarative_base()

# ============================================================================
# AWS RDS PostgreSQL Configuration - Environment Variable Only
# ============================================================================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Please set DATABASE_URL in your environment. "
        "Format: postgresql+asyncpg://user:password@host:port/dbname"
    )

logger.info(f"🐘 Using AWS RDS PostgreSQL: {DATABASE_URL.split('@')[1].split('/')[0] if '@' in DATABASE_URL else 'configured'}")

# Remove ssl parameter from URL if present (we'll use connect_args instead)
CLEAN_DATABASE_URL = DATABASE_URL.split('?')[0] if '?' in DATABASE_URL else DATABASE_URL

# Configure SSL for asyncpg (required for AWS RDS)
import ssl
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE  # RDS uses Amazon's CA

# Determine if we need SSL (production) or not (local development)
import os
ENV = os.getenv('ENV', 'development')
connect_args = {'ssl': ssl_context} if ENV == 'production' or 'rds.amazonaws.com' in DATABASE_URL else {}

logger.info(f"🔐 SSL Mode: {'enabled' if connect_args else 'disabled'}")

# Configure engine for AWS RDS with proper connection pooling
engine = create_async_engine(
    CLEAN_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,        # Verify connections before using
    pool_size=5,               # Base connection pool size
    max_overflow=10,           # Additional connections when needed
    pool_timeout=30,           # Timeout for getting connection from pool
    pool_recycle=1800,         # Recycle connections after 30 minutes
    connect_args=connect_args, # SSL configuration for RDS
)

AsyncSessionLocal = async_sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Redis Configuration
redis_client = None

def init_redis():
    """Initialize Redis connection on startup"""
    global redis_client
    try:
        redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30
        )
        redis_client.ping()
        logger.info("✅ Redis connected successfully")
        return redis_client
    except Exception as e:
        logger.warning(f"⚠️  Redis connection failed: {e}. Caching will be disabled.")
        redis_client = None
        return None

async def get_redis():
    """Get Redis client (initialized at startup)"""
    global redis_client
    if redis_client is None:
        init_redis()
    return redis_client

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# =============================================================================
# CORE AUTHENTICATION TABLES
# =============================================================================

class User(Base):
    """
    Base authentication table for all users (students, teachers, admin, maintenance).
    Minimal data - extended profile in student_profiles for students.
    """
    __tablename__ = "users"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=True, index=True)
    phone = Column(String(20), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)  # Hashed password for admin/password-based login
    role = Column(String(20), default='student', nullable=False)  # 'student', 'teacher', 'admin', 'maintenance'
    is_active = Column(Boolean, default=True)  # Active when payment confirmed (default True for now)
    profile_completed = Column(Boolean, default=False)  # True after first-time profile capture
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_users_created_at', 'created_at'),  # Performance index for time-based queries
    )


class StudentProfile(Base):
    """
    Extended profile for students only.
    Captured ONCE during first registration, NOT asked again.
    roll_no is the primary identifier for all student academic data.
    """
    __tablename__ = "student_profiles"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    
    # Required fields
    name = Column(String(255), nullable=False)
    roll_no = Column(String(50), unique=True, nullable=False, index=True)  # Primary identifier for ALL users
    school_name = Column(String(500), nullable=True)  # Optional for non-students
    standard = Column(Integer, nullable=True)  # Class 1-10 (NULL for teachers/maintenance)
    gender = Column(String(10), nullable=True, default='other')  # 'male', 'female', 'other'
    
    # Contact info
    email = Column(String(255), nullable=True)  # Can differ from login email
    login_phone = Column(String(20), nullable=False)
    parent_phone = Column(String(20), nullable=True)  # Can be same as login_phone
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Index for fast lookups
    __table_args__ = (
        Index('idx_student_roll_no', 'roll_no'),
        Index('idx_student_standard', 'standard'),
    )


class OTPCode(Base):
    """OTP verification codes for login"""
    __tablename__ = "otp_codes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    identifier = Column(String(255), nullable=False, index=True)  # email or phone
    code = Column(String(10), nullable=False)
    attempts = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# =============================================================================
# CONTENT MANAGEMENT TABLES
# =============================================================================

class Subject(Base):
    """Subjects per standard (5 default subjects for Class 1-10)"""
    __tablename__ = "subjects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    standard = Column(Integer, nullable=False)  # Class 1-10 - indexed via idx_subject_standard
    description = Column(Text, nullable=True)
    school_name = Column(String(500), nullable=True)  # School-based multi-tenancy - indexed via idx_subjects_school
    order = Column(Integer, default=0)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_subject_standard', 'standard'),
        Index('idx_subjects_school', 'school_name'),
    )


class Chapter(Base):
    """Chapters within subjects"""
    __tablename__ = "chapters"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(String(36), ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    standard = Column(Integer, nullable=False, index=True)  # Denormalized for faster queries
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    school_name = Column(String(500), nullable=True)  # School-based multi-tenancy - indexed via idx_chapters_school
    video_url = Column(String(500), nullable=True)  # YouTube video link
    order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    # AI content generation tracking
    ai_generated = Column(Boolean, default=False, nullable=False)
    ai_status = Column(String(20), default='pending', nullable=False)  # 'pending', 'processing', 'completed', 'failed'
    ai_content_prefix = Column(String(255), nullable=True)  # S3 prefix for AI content
    ai_generated_at = Column(DateTime(timezone=True), nullable=True)
    ai_error_message = Column(Text, nullable=True)  # Error details if generation failed
    ai_retry_count = Column(Integer, default=0, nullable=False)  # Track retry attempts
    
    __table_args__ = (
        Index('idx_chapters_school', 'school_name'),
        Index('idx_chapters_ai_status', 'ai_status'),  # Performance index for AI status queries
    )


class Content(Base):
    """
    Uploaded textbooks/content.
    Stores S3 URL only - NO file storage in DB.
    """
    __tablename__ = "contents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False, index=True)
    content_type = Column(String(20), nullable=False)  # 'textbook', 'notes', etc.
    file_name = Column(String(500), nullable=False)
    s3_url = Column(Text, nullable=False)  # S3 object URL/key only
    school_name = Column(String(500), nullable=True)  # School-based multi-tenancy
    ocr_text = Column(Text, nullable=True)  # Extracted text for AI processing
    ocr_processed = Column(Boolean, default=False)
    file_metadata = Column(JSON, nullable=True)  # Size, pages, etc.
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PreviousYearPaper(Base):
    """
    Previous Year Question Papers.
    Stores S3 URL only - NO file storage in DB.
    Solutions are pre-generated at upload time (teacher-triggered).
    """
    __tablename__ = "previous_year_papers"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(String(36), ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    standard = Column(Integer, nullable=False, index=True)
    year = Column(String(10), nullable=False)
    exam_name = Column(String(200), nullable=False)  # Display name
    normalized_exam_name = Column(String(200), nullable=False)  # Normalized for uniqueness
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)  # S3 key for PDF
    s3_folder_key = Column(String(500), nullable=True)  # Base S3 folder
    school_name = Column(String(500), nullable=True)  # School-based multi-tenancy - indexed via idx_pyq_school
    created_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)  # Teacher who uploaded
    ocr_processed = Column(Boolean, default=False)
    ocr_text = Column(Text, nullable=True)
    extraction_status = Column(String(20), default='pending')
    extraction_stage = Column(String(50), default='UPLOADED')
    questions_extracted_count = Column(Integer, default=0)
    solution_generated = Column(Boolean, default=False)
    solution_s3_key = Column(String(1000), nullable=True)  # S3 key for solution JSON
    solution_generated_at = Column(DateTime(timezone=True), nullable=True)
    solution_cached = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_pyq_unique', 'standard', 'subject_id', 'year', 'normalized_exam_name', unique=True),
        Index('idx_pyq_school', 'school_name'),
    )


# =============================================================================
# STUDENT ACADEMIC DATA TABLES
# All use roll_no as foreign key for student identification
# =============================================================================

class StudentExamScore(Base):
    """
    School exam scores.
    Lightweight - stores only scores, NOT question papers or answers.
    """
    __tablename__ = "student_exam_scores"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    roll_no = Column(String(50), ForeignKey('student_profiles.roll_no', ondelete='CASCADE'), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    exam_name = Column(String(255), nullable=False)  # 'Unit Test 1', 'Mid Term', etc.
    exam_date = Column(Date, nullable=False)
    score = Column(Float, nullable=False)
    max_score = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_exam_roll_subject', 'roll_no', 'subject'),
    )


class StudentPracticeProgress(Base):
    """
    Chapter-wise practice test progress.
    Used for calculating % chapter completion and rendering progress bars.
    """
    __tablename__ = "student_practice_progress"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    roll_no = Column(String(50), ForeignKey('student_profiles.roll_no', ondelete='CASCADE'), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    chapter = Column(String(255), nullable=False)
    practice_test_number = Column(Integer, nullable=False)  # 1, 2, 3
    attempted = Column(Boolean, default=False)
    score = Column(Float, nullable=True)  # Nullable until attempted
    attempt_date = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_practice_roll_subject', 'roll_no', 'subject'),
        Index('idx_practice_roll_chapter', 'roll_no', 'chapter'),
    )


class StudentHomeworkStatus(Base):
    """
    Homework completion tracking.
    Teacher uploads homework (feature to be added later).
    """
    __tablename__ = "student_homework_status"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    roll_no = Column(String(50), ForeignKey('student_profiles.roll_no', ondelete='CASCADE'), nullable=False, index=True)
    subject = Column(String(255), nullable=False)
    homework_id = Column(String(36), nullable=True)  # FK to homework table (to be added later)
    homework_date = Column(Date, nullable=False)
    status = Column(String(20), nullable=False)  # 'completed', 'missed', 'pending'
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_homework_roll_subject', 'roll_no', 'subject'),
        Index('idx_homework_roll_date', 'roll_no', 'homework_date'),
        Index('idx_homework_status_status', 'status'),  # Performance index for status queries
    )


# =============================================================================
# HOMEWORK TABLES
# =============================================================================

class Homework(Base):
    """Homework assignments uploaded by teachers"""
    __tablename__ = "homework"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(String(36), ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    standard = Column(Integer, nullable=False, index=True)  # Class 1-10
    title = Column(String(500), nullable=False)  # Display title
    normalized_title = Column(String(500), nullable=False)  # Normalized for uniqueness
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)  # S3 key
    s3_folder_key = Column(String(500), nullable=True)  # Base S3 folder
    school_name = Column(String(500), nullable=True)  # School-based multi-tenancy - indexed via idx_homework_school
    model_answers_file = Column(String(500), nullable=True)  # Model answers filename
    model_answers_path = Column(String(1000), nullable=True)  # Model answers S3 key
    upload_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expiry_date = Column(DateTime(timezone=True), nullable=False)  # 10 days from upload
    created_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)  # Teacher - SET NULL on delete
    ocr_text = Column(Text, nullable=True)  # Extracted text for AI processing
    ocr_processed = Column(Boolean, default=False)
    questions_extracted = Column(Boolean, default=False)
    questions_extracted_count = Column(Integer, default=0)
    solutions_extracted_count = Column(Integer, default=0)  # NEW: Track solution count
    extraction_status = Column(String(20), default='pending')
    extraction_progress = Column(Integer, default=0)
    extraction_stage = Column(String(50), default='UPLOADED')
    extraction_stage_message = Column(String(255), nullable=True)
    extraction_started_at = Column(DateTime(timezone=True), nullable=True)
    extraction_completed_at = Column(DateTime(timezone=True), nullable=True)
    extraction_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_homework_subject_standard', 'subject_id', 'standard'),
        Index('idx_homework_unique', 'standard', 'subject_id', 'normalized_title', unique=True),
        Index('idx_homework_school', 'school_name'),
    )


class HomeworkSolution(Base):
    """AI-generated solutions for homework (cached for 10 days)"""
    __tablename__ = "homework_solutions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    homework_id = Column(String(36), ForeignKey('homework.id', ondelete='CASCADE'), unique=True, nullable=False, index=True)
    solution = Column(JSON, nullable=False)  # Structured solution
    cache_expiry = Column(DateTime(timezone=True), nullable=False)  # 10 days from generation
    access_count = Column(Integer, default=0)  # Track how many students used it
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AICache(Base):
    """Generic cache for all AI-generated content - PERMANENT for reuse"""
    __tablename__ = "ai_cache"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cache_key = Column(String(500), unique=True, nullable=False, index=True)  # Unique identifier
    cache_type = Column(String(50), nullable=False, index=True)  # 'pyq_solution', 'homework_solution', 'quiz', etc.
    content = Column(JSON, nullable=False)  # The generated content
    access_count = Column(Integer, default=0)  # Track usage
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_accessed = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class HomeworkQuestions(Base):
    """Extracted questions from homework PDF"""
    __tablename__ = "homework_questions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    homework_id = Column(String(36), ForeignKey('homework.id', ondelete='CASCADE'), nullable=False, index=True)
    questions = Column(JSON, nullable=False)  # List of extracted questions with model answers
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class HomeworkSubmission(Base):
    """Student homework submissions - PERMANENT RECORD for reports"""
    __tablename__ = "homework_submissions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    homework_id = Column(String(36), nullable=False, index=True)  # NO CASCADE - keep for reports
    homework_title = Column(String(500), nullable=False)  # Store title for reports
    subject_name = Column(String(200), nullable=False)  # Store subject for reports
    standard = Column(Integer, nullable=False)  # Store standard for reports
    student_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    roll_no = Column(String(50), ForeignKey('student_profiles.roll_no', ondelete='CASCADE'), nullable=False, index=True)
    submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    homework_upload_date = Column(DateTime(timezone=True), nullable=False)  # For reporting
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_homework_submission', 'homework_id', 'student_id'),
        Index('idx_student_submissions', 'student_id', 'submitted'),  # For reports
        Index('idx_homework_submissions_created_at', 'created_at'),  # Performance index for time-based queries
    )


# =============================================================================
# TEST TABLES
# =============================================================================

class Test(Base):
    """Test assignments uploaded by teachers with time constraints"""
    __tablename__ = "tests"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(String(36), ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    standard = Column(Integer, nullable=False, index=True)  # Class 1-10
    title = Column(String(500), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)  # S3 key
    s3_folder_key = Column(String(500), nullable=True)  # Base S3 folder for this test
    school_name = Column(String(500), nullable=True)  # School-based multi-tenancy - indexed via idx_tests_school
    questions_s3_key = Column(String(1000), nullable=True)  # S3 key for questions.json
    answers_s3_key = Column(String(1000), nullable=True)  # S3 key for answers.json
    model_answers_file = Column(String(500), nullable=True)  # Model answers filename
    model_answers_path = Column(String(1000), nullable=True)  # Model answers S3 key
    
    # NEW: Marking Schema fields
    marking_schema_file = Column(String(500), nullable=True)  # Marking schema filename
    marking_schema_path = Column(String(1000), nullable=True)  # Marking schema S3 key
    marking_schema_text_path = Column(String(1000), nullable=True)  # Extracted text S3 key
    has_marking_schema = Column(Boolean, default=False)  # Quick check if schema exists
    
    submission_deadline = Column(DateTime(timezone=True), nullable=False)  # Last time to submit
    expires_at = Column(DateTime(timezone=True), nullable=False)  # submission_deadline + 5 minutes
    duration_minutes = Column(Integer, nullable=False)  # Max time period permitted (in minutes)
    upload_date = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)  # Teacher - SET NULL on delete
    ocr_text = Column(Text, nullable=True)  # Extracted text for AI processing
    ocr_processed = Column(Boolean, default=False)
    questions_extracted = Column(Boolean, default=False)
    questions_extracted_count = Column(Integer, default=0)  # Number of questions extracted so far
    solutions_extracted_count = Column(Integer, default=0)  # Number of solutions/answers extracted
    # Extraction status: 'pending', 'processing', 'partial', 'completed', 'failed'
    extraction_status = Column(String(20), default='pending')
    extraction_progress = Column(Integer, default=0)  # 0-100 percentage
    # Extraction stage for observability
    extraction_stage = Column(String(50), default='UPLOADED')  # Current stage
    extraction_stage_message = Column(String(255), nullable=True)  # Human-readable stage message
    extraction_started_at = Column(DateTime(timezone=True), nullable=True)  # When extraction started
    extraction_completed_at = Column(DateTime(timezone=True), nullable=True)  # When extraction finished
    extraction_error = Column(Text, nullable=True)  # Error message if extraction failed
    # Status: 'draft', 'active', 'expired', 'deleted'
    status = Column(String(20), default='draft', index=True)  # Start as draft
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_test_subject_standard', 'subject_id', 'standard'),
        Index('idx_test_deadline', 'submission_deadline'),
        Index('idx_test_expires_status', 'expires_at', 'status'),
        Index('idx_tests_school', 'school_name'),
    )


class TestQuestion(Base):
    """Extracted questions metadata - actual questions stored in S3"""
    __tablename__ = "test_questions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = Column(String(36), ForeignKey('tests.id', ondelete='CASCADE'), nullable=False, index=True)
    questions_s3_path = Column(String(1000), nullable=False)  # S3 URL to questions JSON file
    question_count = Column(Integer, default=0)  # Total number of questions (metadata)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class TestSubmission(Base):
    """Student test submissions metadata - PERMANENT RECORD (answers NOT saved)"""
    __tablename__ = "test_submissions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = Column(String(36), nullable=False, index=True)  # NO CASCADE - keep for reports
    test_title = Column(String(500), nullable=False)  # Store title for reports
    subject_name = Column(String(200), nullable=False)  # Store subject for reports
    standard = Column(Integer, nullable=False)  # Store standard for reports
    student_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    roll_no = Column(String(50), ForeignKey('student_profiles.roll_no', ondelete='CASCADE'), nullable=False, index=True)
    
    # Timing information (metadata)
    started_at = Column(DateTime(timezone=True), nullable=True)  # When student clicked "Attempt Test"
    submitted_at = Column(DateTime(timezone=True), nullable=True)  # When submitted or timer expired
    time_taken_seconds = Column(Integer, nullable=True)  # Actual time taken
    auto_submitted = Column(Boolean, default=False)  # True if timer expired
    
    # Submission status
    submitted = Column(Boolean, default=False)
    
    # Results metadata (ONLY total score - no answers saved)
    evaluated = Column(Boolean, default=False)
    total_score = Column(Float, nullable=True)  # Score obtained (e.g., 42.5)
    max_score = Column(Float, nullable=True)  # Maximum possible score (e.g., 50)
    percentage = Column(Float, nullable=True)  # NEW: Calculated percentage (0-100)
    total_questions = Column(Integer, nullable=True)  # Total number of questions (for display)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    
    test_upload_date = Column(DateTime(timezone=True), nullable=False)  # For reporting
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_test_submission', 'test_id', 'student_id'),
        Index('idx_student_test_submissions', 'student_id', 'submitted'),
        Index('idx_test_results', 'test_id', 'evaluated'),
        Index('idx_test_submissions_created_at', 'created_at'),  # Performance index for time-based queries
    )


class StudentPerformance(Base):
    """Student performance tracking per subject - automatically updated"""
    __tablename__ = "student_performance"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    roll_no = Column(String(50), ForeignKey('student_profiles.roll_no', ondelete='CASCADE'), nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    subject_name = Column(String(200), nullable=False)  # Denormalized for quick access
    standard = Column(Integer, nullable=False, index=True)
    
    # Performance metrics
    total_tests_taken = Column(Integer, default=0)  # Number of evaluated tests
    average_percentage = Column(Float, default=0.0)  # Average % across all tests
    total_marks_scored = Column(Float, default=0.0)  # Sum of all marks scored
    total_max_marks = Column(Float, default=0.0)  # Sum of all max marks
    
    # Classification: 'strong' (>80%), 'average' (60-79%), 'weak' (<60%)
    classification = Column(String(20), default='weak', index=True)
    
    # Timestamps
    last_test_date = Column(DateTime(timezone=True), nullable=True)  # When last test was taken
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_student_subject_performance', 'student_id', 'subject_id'),
        Index('idx_subject_classification', 'subject_id', 'classification', 'average_percentage'),
    )


# =============================================================================
# STUDY MATERIALS TABLES
# =============================================================================

class StudyMaterial(Base):
    """Additional study materials per chapter (solved problems, notes, etc.)"""
    __tablename__ = "study_materials"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False, index=True)
    material_type = Column(String(50), nullable=False)  # 'solved_problems', 'notes', 'reference', 'worksheet'
    title = Column(String(500), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(1000), nullable=False)  # S3 URL
    school_name = Column(String(500), nullable=True)  # School-based multi-tenancy
    uploaded_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)  # Teacher - SET NULL on delete
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# =============================================================================
# QUIZ & AI CACHE TABLES
# =============================================================================

class Quiz(Base):
    """Teacher-created quizzes"""
    __tablename__ = "quizzes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(String(36), ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)
    chapter_ids = Column(JSON, nullable=False)
    difficulty = Column(String(20), nullable=False)
    question_count = Column(Integer, nullable=False)
    question_types = Column(JSON, nullable=False)
    questions = Column(JSON, nullable=False)
    content_source = Column(String(20), nullable=False)
    created_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)  # Teacher - SET NULL on delete
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AIContentCache(Base):
    """Cached AI-generated content (notes, flashcards, etc.)"""
    __tablename__ = "ai_content_cache"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cache_key = Column(String(500), unique=True, nullable=False, index=True)
    subject_id = Column(String(36), ForeignKey('subjects.id', ondelete='CASCADE'), nullable=True)
    chapter_id = Column(String(36), ForeignKey('chapters.id', ondelete='CASCADE'), nullable=True)
    feature_type = Column(String(100), nullable=False)
    language = Column(String(50), default='english')
    content_source = Column(String(50), nullable=False)
    content = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

# ============================================================================
# STRUCTURED TEST & AI EVALUATION SYSTEM
# ============================================================================

class StructuredTest(Base):
    """Tests created via structured question builder (not PDF upload)"""
    __tablename__ = "structured_tests"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(String(36), ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False, index=True)
    standard = Column(Integer, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    school_name = Column(String(500), nullable=True)
    created_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    
    total_marks = Column(Float, nullable=False, default=0)
    duration_minutes = Column(Integer, nullable=False, default=60)
    submission_deadline = Column(DateTime(timezone=True), nullable=False)
    
    status = Column(String(20), default='draft')  # draft, active, expired
    question_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_stest_subject_standard', 'subject_id', 'standard'),
        Index('idx_stest_school', 'school_name'),
    )


class StructuredQuestion(Base):
    """Individual questions with structured evaluation criteria"""
    __tablename__ = "structured_questions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = Column(String(36), ForeignKey('structured_tests.id', ondelete='CASCADE'), nullable=False, index=True)
    question_number = Column(Integer, nullable=False)
    
    question_type = Column(String(30), nullable=False)
    # Types: mcq, true_false, fill_blank, one_word, match_following, short_answer, long_answer, numerical
    
    question_text = Column(Text, nullable=False)
    max_marks = Column(Float, nullable=False)
    
    model_answer = Column(Text, nullable=True)
    
    # For objective questions (stored as JSON)
    # MCQ: {options: {a:"...",b:"...",c:"...",d:"..."}, correct: "a"}
    # True/False: {correct: true/false}
    # One Word: {correct: "word"}
    # Fill Blank: {correct: "answer"}
    # Match: {pairs: [{left:"...",right:"..."}]}
    objective_data = Column(JSON, nullable=True)
    
    # Evaluation points for subjective questions (JSON array)
    # [{id:1, title:"Definition", expected_concept:"...", marks:2}, ...]
    evaluation_points = Column(JSON, nullable=True)
    
    # Solution steps for numerical questions (JSON array)
    # [{id:1, title:"Write formula", expected:"Area = pi*r^2", marks:1}, ...]
    solution_steps = Column(JSON, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_sq_test_qnum', 'test_id', 'question_number'),
    )


class StructuredTestSubmission(Base):
    """Student submissions for structured tests"""
    __tablename__ = "structured_test_submissions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = Column(String(36), ForeignKey('structured_tests.id', ondelete='CASCADE'), nullable=False, index=True)
    student_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    roll_no = Column(String(50), nullable=False)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    time_taken_seconds = Column(Integer, nullable=True)
    auto_submitted = Column(Boolean, default=False)
    submitted = Column(Boolean, default=False)
    
    # Answers JSON: {"1": "answer text", "2": "b", ...}
    answers_json = Column(JSON, nullable=True)
    
    # Evaluation status
    evaluation_status = Column(String(20), default='pending')  # pending, evaluating, completed, failed
    
    # Summary scores (kept permanently)
    total_score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    percentage = Column(Float, nullable=True)
    class_rank = Column(Integer, nullable=True)
    improvement_summary = Column(Text, nullable=True)  # Brief improvement points for PTM
    
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Teacher review
    teacher_reviewed = Column(Boolean, default=False)
    teacher_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    teacher_final_score = Column(Float, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_sts_test_student', 'test_id', 'student_id'),
    )


class EvaluationResult(Base):
    """Detailed per-question evaluation feedback (TTL: 2 months)"""
    __tablename__ = "evaluation_results"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    submission_id = Column(String(36), ForeignKey('structured_test_submissions.id', ondelete='CASCADE'), nullable=False, index=True)
    question_id = Column(String(36), ForeignKey('structured_questions.id', ondelete='CASCADE'), nullable=False)
    question_number = Column(Integer, nullable=False)
    
    student_answer = Column(Text, nullable=True)
    marks_awarded = Column(Float, nullable=False, default=0)
    max_marks = Column(Float, nullable=False)
    
    # Detailed feedback JSON
    # {
    #   evaluation_points: [{title, covered: bool, explanation, marks_given}],
    #   steps_evaluation: [{title, completed: bool, explanation, marks_given}],
    #   overall_feedback: "...",
    #   improvement_suggestions: "..."
    # }
    feedback_json = Column(JSON, nullable=True)
    
    # Verification
    verified = Column(Boolean, default=False)
    verification_notes = Column(Text, nullable=True)
    
    # Teacher override
    teacher_marks = Column(Float, nullable=True)
    teacher_comment = Column(Text, nullable=True)
    
    expires_at = Column(DateTime(timezone=True), nullable=False)  # 2 months from evaluation
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('idx_er_submission', 'submission_id'),
        Index('idx_er_expires', 'expires_at'),
    )



async def init_db():
    """
    Initialize database tables and perform health check.
    Creates all tables if they don't exist (fresh RDS instance).
    Fails fast if database is unreachable.
    """
    try:
        # Health check: Test database connection
        logger.info("🔍 Performing database health check...")
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()  # Not awaited, it's already fetched
        
        logger.info("✅ Database connection successful")
        
        # Create all tables (safe for fresh RDS instance)
        logger.info("📋 Creating database tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("✅ Database tables initialized")
        
    except Exception as e:
        logger.error("=" * 70)
        logger.error("❌ DATABASE CONNECTION FAILED")
        logger.error(f"Error: {e}")
        logger.error("=" * 70)
        logger.error("Possible issues:")
        logger.error("  1. DATABASE_URL is incorrect or not set")
        logger.error("  2. AWS RDS instance is not accessible")
        logger.error("  3. Security group rules are blocking connection")
        logger.error("  4. Database credentials are invalid")
        logger.error("=" * 70)
        logger.error("🛑 Application startup aborted due to database failure")
        logger.error("=" * 70)
        raise RuntimeError(f"Failed to connect to database: {e}")

async def close_db():
    """Close database connections"""
    global redis_client
    if redis_client:
        redis_client.close()
    await engine.dispose()
