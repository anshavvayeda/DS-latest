from fastapi import FastAPI, APIRouter, Depends, HTTPException, UploadFile, File, Cookie, Response, Form, BackgroundTasks, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, text, String, func, and_
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime, timezone
import os
import json
import asyncio  # For timeout handling
import logging
from pathlib import Path
from dotenv import load_dotenv
from passlib.context import CryptContext

from app.models.database import (
    get_db, init_db, close_db, User, Subject, Chapter, Content, 
    Quiz, PreviousYearPaper, get_redis, init_redis,
    StudentProfile, StudentExamScore, StudentPracticeProgress, StudentHomeworkStatus,
    Homework, HomeworkSolution, HomeworkQuestions, HomeworkSubmission, StudyMaterial, AICache,
    Test, TestQuestion, TestSubmission, StudentPerformance, AsyncSessionLocal,
    StructuredTest, StructuredQuestion, StructuredTestSubmission, EvaluationResult
)
from app.services.auth_service import (
    create_otp, verify_otp, get_or_create_user, create_jwt_token, decode_jwt_token
)
from app.services.storage_service import (
    upload_file_to_s3, 
    setup_s3_lifecycle_policy,
    upload_homework_pdf_to_s3,
    upload_homework_solution_pdf_to_s3,
    delete_homework_from_s3,
    delete_pyq_from_s3,
    delete_file_from_storage,
    normalize_title,
    sanitize_component,
    sanitize_school_name
)
from app.services.ai_service import (
    generate_revision_notes, generate_flashcards, generate_practice_quiz,
    generate_important_topics, evaluate_quiz_answer, explain_concept, answer_doubt
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# CRITICAL: Validate OPENROUTER_API_KEY at startup
# =============================================================================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.error("=" * 60)
    logger.error("CRITICAL: OPENROUTER_API_KEY is MISSING from environment!")
    logger.error("AI features (extraction, help, evaluation) WILL FAIL without this key.")
    logger.error("Please add OPENROUTER_API_KEY to backend/.env")
    logger.error("=" * 60)
else:
    logger.info(f"✅ OPENROUTER_API_KEY present: {OPENROUTER_API_KEY[:15]}***")

# =============================================================================
# PASSWORD HASHING SETUP
# =============================================================================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

# Admin credentials from environment
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

if ADMIN_USERNAME and ADMIN_PASSWORD:
    logger.info(f"✅ Admin credentials configured (username: {ADMIN_USERNAME})")
else:
    logger.warning("⚠️ Admin credentials not configured in environment")

app = FastAPI(title="StudyBuddy - Smart Learning Platform")

# CORS Configuration - API-first design for multi-platform support
# Supports: Web (EC2), Mobile Apps, Desktop Apps, Development
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8080",  # Desktop app development
    "http://127.0.0.1:8080",
    "https://13.201.25.124",  # EC2 Production
    "http://13.201.25.124",
]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.preview\.emergentagent\.com",  # Emergent preview subdomains
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")

# Global OTP store (in production, use Redis with TTL)
OTP_STORE = {}

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
    
    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")
    
    # Initialize Redis (optional - graceful degradation)
    init_redis()
    
    # Initialize S3 (mandatory - fail hard if missing)
    try:
        initialize_s3()
        logger.info("✅ S3 storage initialized")
        
        # Setup lifecycle policies after S3 is confirmed working
        setup_s3_lifecycle_policy()
        
    except Exception as e:
        logger.error(f"❌ CRITICAL: S3 initialization failed")
        logger.error(f"   {str(e)}")
        logger.error("   Application will continue but file operations will fail")
        logger.error("   Please configure AWS credentials in backend/.env")
    
    # Setup temporary storage directory
    try:
        ensure_temp_directory()
        # Cleanup old temporary files from previous runs
        cleanup_old_temp_files()
    except Exception as e:
        logger.error(f"❌ Temp storage setup failed: {e}")
    
    # Startup validation logs
    logger.info("🔍 System validation:")
    
    # ✅ MANDATORY: Verify NO local OCR is used
    logger.info("🚫 Enforcing GPT-4o ONLY extraction policy...")
    
    # Check that local OCR functions don't exist
    try:
        from app.services.background_extraction import background_extract_test
        import inspect
        
        # Get source code of extraction function
        source = inspect.getsource(background_extract_test)
        
        # Forbidden patterns that indicate local OCR
        forbidden = [
            'pytesseract',
            'pdf2image',
            'PdfReader',
            'extract_text()',
            'image_to_string',
            'convert_from_bytes'
        ]
        
        violations = []
        for pattern in forbidden:
            if pattern in source:
                violations.append(pattern)
        
        if violations:
            error_msg = f"❌ LOCAL OCR FORBIDDEN: Found {violations} in extraction code"
            logger.error(error_msg)
            logger.error("   GPT-4o ONLY policy violated")
            logger.error("   Extraction will fail if local OCR is attempted")
            # Don't crash startup, but warn loudly
        else:
            logger.info("✅ GPT-4o ONLY policy enforced (no local OCR detected)")
            
    except Exception as e:
        logger.warning(f"⚠️ Could not validate OCR policy: {e}")
    
    # Check background extraction service
    try:
        from app.services.background_extraction import ExtractionStatus, start_extraction_task
        from app.services.gpt4o_extraction import ExtractionStage, extract_with_gpt4o
        logger.info("✅ Background extraction service ready (GPT-4o pipeline)")
    except ImportError as e:
        logger.error(f"❌ Background extraction service unavailable: {e}")
    
    # Check database columns
    try:
        from app.models.database import Test
        logger.info("✅ Database schema loaded")
        # Check if new columns exist
        test_columns = Test.__table__.columns.keys()
        required_cols = ['extraction_progress', 'questions_extracted_count', 'extraction_stage', 'extraction_stage_message']
        missing = [col for col in required_cols if col not in test_columns]
        if missing:
            logger.error(f"❌ Database missing columns: {missing}")
            logger.error("   Please recreate database or run migrations")
        else:
            logger.info(f"✅ Database schema validated ({len(test_columns)} columns)")
    except Exception as e:
        logger.error(f"❌ Database schema validation failed: {e}")
    
    # Start background task for test cleanup
    import asyncio
    asyncio.create_task(cleanup_expired_tests_task())
    
    logger.info("🎉 StudyBuddy backend started successfully")

@app.on_event("shutdown")
async def shutdown():
    await close_db()


async def cleanup_expired_tests_task():
    """
    Background task to auto-delete tests after expires_at + 5 minutes.
    Runs every 60 seconds.
    
    Cleanup Logic (ATOMIC):
    1. Query tests where (expires_at + 5 minutes) <= now() AND status != 'deleted'
    2. For each: Delete S3 folder (test.pdf, model_answers.pdf, extracted_questions.json)
    3. If S3 delete succeeds: Mark status='deleted' in DB
    4. If S3 fails: Log error, retry next cycle
    
    5 minute grace period allows:
    - Students finishing in progress submissions
    - Teacher final review before cleanup
    """
    import asyncio
    import json as json_module
    from app.services.storage_service import delete_test_folder_from_s3
    from datetime import timedelta
    
    # Wait for app to fully start
    await asyncio.sleep(10)
    logger.info("🚀 Test cleanup background task started (runs every 60s, 5min grace period)")
    
    while True:
        try:
            async with AsyncSessionLocal() as db:
                # Use naive datetime for comparison (SQLite stores naive)
                current_time_naive = datetime.utcnow()
                
                # Find tests that have expired + 5 minutes and not yet deleted
                result = await db.execute(
                    select(Test).where(
                        Test.expires_at <= current_time_naive - timedelta(minutes=5),
                        Test.status != 'deleted'
                    )
                )
                expired_tests = result.scalars().all()
                
                if expired_tests:
                    logger.info(f"🧹 Found {len(expired_tests)} expired tests to clean up (5min grace passed)")
                
                for test in expired_tests:
                    cleanup_log = {
                        "event": "test_cleanup",
                        "test_id": test.id,
                        "title": test.title,
                        "expires_at": test.expires_at.isoformat() if test.expires_at else None,
                        "s3_folder": test.s3_folder_key,
                        "status": "pending",
                        "s3_deleted": False,
                        "db_deleted": False
                    }
                    
                    try:
                        # Step 1: Delete S3 folder first (test.pdf, model_answers.pdf, extracted_questions.json)
                        s3_success = False
                        if test.s3_folder_key:
                            try:
                                s3_success = await delete_test_folder_from_s3(test.s3_folder_key)
                                cleanup_log["s3_deleted"] = s3_success
                                
                                if not s3_success:
                                    cleanup_log["status"] = "failed"
                                    cleanup_log["error"] = "S3 deletion returned False"
                                    logger.warning(f"Test cleanup: {json_module.dumps(cleanup_log)}")
                                    continue  # Skip DB deletion, retry next cycle
                                    
                            except Exception as s3_error:
                                cleanup_log["status"] = "failed"
                                cleanup_log["error"] = f"S3 error: {str(s3_error)}"
                                logger.error(f"Test cleanup: {json_module.dumps(cleanup_log)}")
                                continue  # Skip DB deletion, retry next cycle
                        else:
                            # No S3 folder, proceed with DB cleanup
                            s3_success = True
                            cleanup_log["s3_deleted"] = True
                            cleanup_log["note"] = "No S3 folder to delete"
                        
                        # Step 2: Delete related DB records (TestQuestion, TestSubmission)
                        await db.execute(delete(TestQuestion).where(TestQuestion.test_id == test.id))
                        
                        # Step 3: Mark test as deleted (soft delete for audit trail)
                        test.status = 'deleted'
                        test.deleted_at = datetime.now(timezone.utc)
                        await db.commit()
                        
                        cleanup_log["db_deleted"] = True
                        cleanup_log["status"] = "success"
                        logger.info(f"Test cleanup: {json_module.dumps(cleanup_log)}")
                        
                    except Exception as db_error:
                        await db.rollback()
                        cleanup_log["status"] = "partial"
                        cleanup_log["error"] = f"DB error: {str(db_error)}"
                        logger.error(f"Test cleanup: {json_module.dumps(cleanup_log)}")
                        
        except Exception as e:
            logger.error(f"Test cleanup task error: {e}")
        
        # Run every 60 seconds
        await asyncio.sleep(60)


# Pydantic Models
class SendOTPRequest(BaseModel):
    identifier: str
    type: str

class VerifyOTPRequest(BaseModel):
    identifier: str
    code: str

class CreateSubjectRequest(BaseModel):
    name: str
    standard: int  # Required: Class 1-10
    description: Optional[str] = None

class UpdateSubjectRequest(BaseModel):
    name: Optional[str] = None
    standard: Optional[int] = None  # Allow updating standard
    description: Optional[str] = None

class CreateChapterRequest(BaseModel):
    subject_id: str
    name: str
    description: Optional[str] = None

class GenerateQuizRequest(BaseModel):
    subject_id: str
    chapter_ids: List[str]
    difficulty: str
    question_count: int
    question_types: List[str]
    content_source: str

class SubmitQuizRequest(BaseModel):
    quiz_id: str
    answers: List[dict]

class GenerateContentRequest(BaseModel):
    subject_id: str
    chapter_id: str
    feature_type: str
    language: str = 'english'
    content_source: str = 'ncert'
    additional_params: Optional[dict] = None

# Student Profile Request Models
class CreateStudentProfileRequest(BaseModel):
    name: str
    roll_no: str
    school_name: str
    standard: int
    gender: str  # 'male', 'female', 'other'
    email: Optional[str] = None
    login_phone: str
    parent_phone: Optional[str] = None

class StudentExamScoreRequest(BaseModel):
    subject: str
    exam_name: str
    exam_date: str  # ISO format date
    score: float
    max_score: float

class StudentPracticeProgressRequest(BaseModel):
    subject: str
    chapter: str
    practice_test_number: int
    score: Optional[float] = None

# =============================================================================
# ADMIN REQUEST MODELS
# =============================================================================

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminRegisterStudentRequest(BaseModel):
    name: str
    school_name: Optional[str] = None  # Required only for students
    standard: Optional[int] = None     # Required only for students
    roll_no: Optional[str] = None      # Required only for students
    gender: Optional[str] = 'other'    # Required only for students
    phone: str
    email: Optional[str] = None
    parent_phone: Optional[str] = None
    password: str
    is_active: bool = True
    role: str = 'student'  # 'student', 'teacher', 'maintenance'

    @validator('standard')
    def validate_standard(cls, v, values):
        # Standard is only required for students
        if v is not None and not 1 <= v <= 12:
            raise ValueError('Standard must be between 1 and 12')
        return v

    @validator('gender')
    def validate_gender(cls, v):
        if v is None:
            return 'other'
        if v.lower() not in ['male', 'female', 'other']:
            raise ValueError('Gender must be male, female, or other')
        return v.lower()

    @validator('role')
    def validate_role(cls, v):
        if v.lower() not in ['student', 'teacher', 'maintenance']:
            raise ValueError('Role must be student, teacher, or maintenance')
        return v.lower()

class AdminBulkRegisterRequest(BaseModel):
    students: List[AdminRegisterStudentRequest]

# New models for password reset and login
class AdminResetPasswordRequest(BaseModel):
    roll_no: str
    new_password: str

class AdminImpersonateRequest(BaseModel):
    roll_no: str

class RollNoLoginRequest(BaseModel):
    roll_no: str
    password: str

class UserResetPasswordRequest(BaseModel):
    roll_no: str
    old_password: str
    otp: str
    new_password: str

class RequestPasswordResetOTPRequest(BaseModel):
    roll_no: str

# Auth Helpers
async def get_current_user(
    token: Optional[str] = Cookie(None, alias="auth_token"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current user from either:
    1. Cookie (auth_token) - preferred for browser
    2. Authorization header (Bearer token) - fallback for CORS/HTTP issues
    """
    # Try cookie first
    auth_token = token
    
    # If no cookie, try Authorization header
    if not auth_token and authorization:
        if authorization.startswith("Bearer "):
            auth_token = authorization.replace("Bearer ", "")
    
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    payload = decode_jwt_token(auth_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    result = await db.execute(select(User).where(User.id == payload['user_id']))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

async def get_optional_user(token: Optional[str] = Cookie(None, alias="auth_token"), db: AsyncSession = Depends(get_db)) -> Optional[User]:
    """Return user if authenticated, None otherwise (no 401 thrown)"""
    if not token:
        return None
    
    payload = decode_jwt_token(token)
    if not payload:
        return None
    
    result = await db.execute(select(User).where(User.id == payload['user_id']))
    user = result.scalars().first()
    
    return user

async def require_teacher(user: User = Depends(get_current_user)) -> User:
    if user.role != 'teacher':
        raise HTTPException(status_code=403, detail="Teacher access required")
    return user

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_user_school(user: User, db: AsyncSession) -> Optional[str]:
    """
    Get the school name for the current user (student or teacher).
    Returns None if no profile found or if user is admin.
    """
    if user.role == 'admin':
        return None
    
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == str(user.id))
    )
    profile = result.scalars().first()
    return profile.school_name if profile else None


# ============================================================================
# HELPER FUNCTIONS - Student Performance Tracking
# ============================================================================

async def update_student_performance(
    db: AsyncSession,
    student_id: str,
    roll_no: str,
    subject_id: str,
    subject_name: str,
    standard: int,
    marks_scored: float,
    max_marks: float
):
    """Update or create student performance record after test evaluation"""
    try:
        # Calculate percentage
        percentage = (marks_scored / max_marks * 100) if max_marks > 0 else 0
        
        # Find existing performance record
        result = await db.execute(
            select(StudentPerformance).where(
                StudentPerformance.student_id == student_id,
                StudentPerformance.subject_id == subject_id
            )
        )
        performance = result.scalars().first()
        
        if performance:
            # Update existing record
            performance.total_tests_taken += 1
            performance.total_marks_scored += marks_scored
            performance.total_max_marks += max_marks
            performance.average_percentage = (performance.total_marks_scored / performance.total_max_marks * 100) if performance.total_max_marks > 0 else 0
            performance.last_test_date = datetime.now(timezone.utc)
            
            # Update classification
            if performance.average_percentage >= 80:
                performance.classification = 'strong'
            elif performance.average_percentage >= 60:
                performance.classification = 'average'
            else:
                performance.classification = 'weak'
            
            performance.updated_at = datetime.now(timezone.utc)
        else:
            # Create new record
            classification = 'strong' if percentage >= 80 else ('average' if percentage >= 60 else 'weak')
            
            performance = StudentPerformance(
                student_id=student_id,
                roll_no=roll_no,
                subject_id=subject_id,
                subject_name=subject_name,
                standard=standard,
                total_tests_taken=1,
                average_percentage=percentage,
                total_marks_scored=marks_scored,
                total_max_marks=max_marks,
                classification=classification,
                last_test_date=datetime.now(timezone.utc)
            )
            db.add(performance)
        
        await db.commit()
        logger.info(f"✅ Updated performance for student {student_id} in {subject_name}: {performance.average_percentage:.1f}% ({performance.classification})")
        
    except Exception as e:
        logger.error(f"❌ Failed to update student performance: {e}")
        await db.rollback()


# Auth Routes
@api_router.post("/auth/send-otp")
async def send_otp(request: SendOTPRequest, db: AsyncSession = Depends(get_db)):
    if request.type not in ['email', 'phone']:
        raise HTTPException(status_code=400, detail="Type must be 'email' or 'phone'")
    
    otp = await create_otp(db, request.identifier, request.type)
    if not otp:
        raise HTTPException(status_code=500, detail="Failed to send OTP")
    
    return {"message": "OTP sent successfully", "identifier": request.identifier}

@api_router.post("/auth/verify-otp")
async def verify_otp_endpoint(request: VerifyOTPRequest, response: Response, db: AsyncSession = Depends(get_db)):
    is_valid = await verify_otp(db, request.identifier, request.code)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    identifier_type = 'email' if '@' in request.identifier else 'phone'
    user = await get_or_create_user(
        db,
        email=request.identifier if identifier_type == 'email' else None,
        phone=request.identifier if identifier_type == 'phone' else None
    )
    
    token = create_jwt_token(str(user.id), user.role)
    
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="None",
        secure=True
    )
    
    # Check if student profile is completed
    profile_completed = user.profile_completed if hasattr(user, 'profile_completed') else False
    
    # For students, check if profile exists
    student_profile = None
    if user.role == 'student':
        result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
        profile = result.scalars().first()
        if profile:
            profile_completed = True
            student_profile = {
                "name": profile.name,
                "roll_no": profile.roll_no,
                "school_name": profile.school_name,
                "standard": profile.standard,
                "gender": profile.gender
            }
    
    return {
        "message": "Login successful",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "profile_completed": profile_completed
        },
        "student_profile": student_profile
    }

class PasswordLoginRequest(BaseModel):
    phone: str
    password: str

@api_router.post("/auth/login-password")
async def login_with_password(request: PasswordLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Login using phone number and password (for admin-registered users).
    """
    # Find user by phone
    result = await db.execute(select(User).where(User.phone == request.phone))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid phone number or password")
    
    # Check if user has password hash
    if not user.password_hash:
        raise HTTPException(status_code=401, detail="Password login not enabled for this account. Use OTP.")
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid phone number or password")
    
    # Check if user is active
    if hasattr(user, 'is_active') and not user.is_active:
        raise HTTPException(status_code=403, detail="Account is not active. Please contact administrator.")
    
    # Create JWT token
    token = create_jwt_token(str(user.id), user.role)
    
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="None",
        secure=True
    )
    
    # Get student profile if student
    profile_completed = user.profile_completed if hasattr(user, 'profile_completed') else False
    student_profile = None
    
    if user.role == 'student':
        profile_result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
        profile = profile_result.scalars().first()
        if profile:
            profile_completed = True
            student_profile = {
                "name": profile.name,
                "roll_no": profile.roll_no,
                "school_name": profile.school_name,
                "standard": profile.standard,
                "gender": profile.gender
            }
    
    return {
        "message": "Login successful",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "phone": user.phone,
            "role": user.role,
            "is_active": user.is_active if hasattr(user, 'is_active') else True,
            "profile_completed": profile_completed
        },
        "student_profile": student_profile
    }

@api_router.get("/auth/me")
async def get_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    # Check if student profile exists
    profile_completed = user.profile_completed if hasattr(user, 'profile_completed') else False
    student_profile = None
    
    if user.role == 'student':
        result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
        profile = result.scalars().first()
        if profile:
            profile_completed = True
            student_profile = {
                "name": profile.name,
                "roll_no": profile.roll_no,
                "school_name": profile.school_name,
                "standard": profile.standard,
                "gender": profile.gender,
                "email": profile.email,
                "login_phone": profile.login_phone,
                "parent_phone": profile.parent_phone
            }
    
    return {
        "id": str(user.id),
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "profile_completed": profile_completed,
        "student_profile": student_profile
    }

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("auth_token")
    return {"message": "Logged out successfully"}

# =============================================================================
# ADMIN AUTHENTICATION & MANAGEMENT ROUTES
# =============================================================================

@api_router.post("/admin/login")
async def admin_login(request: AdminLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Admin login using credentials from environment variables.
    Creates admin user in DB if not exists on first login.
    """
    # Validate credentials against environment
    if not ADMIN_USERNAME or not ADMIN_PASSWORD:
        raise HTTPException(status_code=500, detail="Admin credentials not configured")
    
    if request.username != ADMIN_USERNAME or request.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    
    # Check if admin user exists in DB, create if not
    result = await db.execute(select(User).where(User.role == 'admin'))
    admin_user = result.scalars().first()
    
    if not admin_user:
        # Create admin user
        admin_user = User(
            email=f"{ADMIN_USERNAME}@admin.local",
            phone=None,
            password_hash=hash_password(ADMIN_PASSWORD),
            role='admin',
            is_active=True,
            profile_completed=True
        )
        db.add(admin_user)
        await db.commit()
        await db.refresh(admin_user)
        logger.info(f"✅ Admin user created: {admin_user.id}")
    
    # Create JWT token
    token = create_jwt_token(str(admin_user.id), 'admin')
    
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="None",
        secure=True
    )
    
    return {
        "message": "Admin login successful",
        "token": token,  # Include token in response for localStorage fallback
        "user": {
            "id": str(admin_user.id),
            "role": "admin",
            "username": ADMIN_USERNAME
        }
    }

@api_router.post("/admin/register-student")
async def admin_register_student(
    request: AdminRegisterStudentRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """
    Admin: Register a single student/teacher/maintenance user with all details.
    Creates both User and StudentProfile records.
    
    School-Based Multi-Tenancy Rules:
    - Teachers MUST have a school_name (they create the school namespace)
    - Students MUST have a school_name that matches an existing teacher's school
    """
    import uuid
    
    # For teachers, school_name is required (they create the school namespace)
    if request.role == 'teacher':
        if not request.school_name or not request.school_name.strip():
            raise HTTPException(status_code=400, detail="School name is required for teachers")
    
    # For students, validate required fields AND ensure school exists
    if request.role == 'student':
        if not request.school_name:
            raise HTTPException(status_code=400, detail="School name is required for students")
        if not request.standard:
            raise HTTPException(status_code=400, detail="Standard/Class is required for students")
        if not request.roll_no:
            raise HTTPException(status_code=400, detail="Roll number is required for students")
        
        # CRITICAL: Validate that a teacher from this school exists
        school_check = await db.execute(
            select(StudentProfile.school_name)
            .join(User, User.id == StudentProfile.user_id)
            .where(User.role == 'teacher')
            .where(StudentProfile.school_name == request.school_name)
        )
        if not school_check.scalars().first():
            raise HTTPException(
                status_code=400, 
                detail=f"School '{request.school_name}' is not registered. A teacher from this school must be registered first."
            )
    
    # Convert empty email string to None to avoid unique constraint issues
    email_value = request.email.strip() if request.email and request.email.strip() else None
    
    # Check if phone already exists
    existing_phone = await db.execute(select(User).where(User.phone == request.phone))
    if existing_phone.scalars().first():
        raise HTTPException(status_code=400, detail=f"Phone number {request.phone} already registered")
    
    # Check if email already exists (if provided and not empty)
    if email_value:
        existing_email = await db.execute(select(User).where(User.email == email_value))
        if existing_email.scalars().first():
            raise HTTPException(status_code=400, detail=f"Email {email_value} already registered")
    
    # Check if roll_no already exists (for ALL roles now)
    if request.roll_no:
        existing_roll = await db.execute(select(StudentProfile).where(StudentProfile.roll_no == request.roll_no))
        if existing_roll.scalars().first():
            raise HTTPException(status_code=400, detail=f"Roll number {request.roll_no} already registered")
    else:
        raise HTTPException(status_code=400, detail="Roll number is required for all users")
    
    try:
        # Create User record
        user_id = str(uuid.uuid4())
        new_user = User(
            id=user_id,
            email=email_value,  # Use cleaned email value (None if empty)
            phone=request.phone,
            password_hash=hash_password(request.password),
            role=request.role,
            is_active=request.is_active,
            profile_completed=True
        )
        db.add(new_user)
        await db.flush()  # Flush to ensure user ID is in DB before adding profile
        
        # Create Profile for ALL users (students, teachers, maintenance)
        profile = StudentProfile(
            user_id=user_id,
            name=request.name,
            roll_no=request.roll_no,
            school_name=request.school_name or '',
            standard=request.standard if request.role == 'student' else None,
            gender=request.gender or 'other',
            email=email_value,  # Use cleaned email value
            login_phone=request.phone,
            parent_phone=request.parent_phone or request.phone
        )
        db.add(profile)
        
        await db.commit()
        logger.info(f"✅ Admin registered new {request.role}: {request.name} ({request.phone})")
    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Failed to register user: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")
    
    return {
        "message": f"{request.role.capitalize()} registered successfully",
        "user": {
            "id": user_id,
            "name": request.name,
            "phone": request.phone,
            "email": email_value,
            "role": request.role,
            "is_active": request.is_active,
            "roll_no": request.roll_no if request.role == 'student' else None,
            "standard": request.standard if request.role == 'student' else None
        }
    }

@api_router.post("/admin/bulk-register")
async def admin_bulk_register(
    request: AdminBulkRegisterRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """
    Admin: Bulk register multiple students/users.
    Returns success/failure status for each registration.
    
    School-Based Multi-Tenancy Rules:
    - Teachers MUST have a school_name
    - Students MUST have a school_name that matches an existing teacher's school
    """
    import uuid
    
    results = []
    success_count = 0
    failure_count = 0
    
    # Pre-fetch existing schools for validation (only for students)
    existing_schools_result = await db.execute(
        select(StudentProfile.school_name)
        .join(User, User.id == StudentProfile.user_id)
        .where(User.role == 'teacher')
        .where(StudentProfile.school_name.isnot(None))
        .where(StudentProfile.school_name != '')
    )
    existing_schools = set([row[0] for row in existing_schools_result.all()])
    
    for student_data in request.students:
        try:
            # Convert empty email string to None to avoid unique constraint issues
            email_value = student_data.email.strip() if student_data.email and student_data.email.strip() else None
            
            # For teachers, school_name is required
            if student_data.role == 'teacher':
                if not student_data.school_name or not student_data.school_name.strip():
                    results.append({
                        "phone": student_data.phone,
                        "name": student_data.name,
                        "status": "failed",
                        "error": "School name is required for teachers"
                    })
                    failure_count += 1
                    continue
            
            # For students, validate required fields AND check school exists
            if student_data.role == 'student':
                if not student_data.school_name:
                    results.append({
                        "phone": student_data.phone,
                        "name": student_data.name,
                        "status": "failed",
                        "error": "School name is required for students"
                    })
                    failure_count += 1
                    continue
                if not student_data.standard:
                    results.append({
                        "phone": student_data.phone,
                        "name": student_data.name,
                        "status": "failed",
                        "error": "Standard/Class is required for students"
                    })
                    failure_count += 1
                    continue
                # Validate school exists (has a teacher)
                if student_data.school_name not in existing_schools:
                    results.append({
                        "phone": student_data.phone,
                        "name": student_data.name,
                        "status": "failed",
                        "error": f"School '{student_data.school_name}' is not registered. Register a teacher first."
                    })
                    failure_count += 1
                    continue
            
            # Roll number is required for ALL roles
            if not student_data.roll_no:
                results.append({
                    "phone": student_data.phone,
                    "name": student_data.name,
                    "status": "failed",
                    "error": "Roll number is required"
                })
                failure_count += 1
                continue
            
            # Check for existing phone
            existing_phone = await db.execute(select(User).where(User.phone == student_data.phone))
            if existing_phone.scalars().first():
                results.append({
                    "phone": student_data.phone,
                    "name": student_data.name,
                    "status": "failed",
                    "error": "Phone number already registered"
                })
                failure_count += 1
                continue
            
            # Check for existing email (if provided and not empty)
            if email_value:
                existing_email = await db.execute(select(User).where(User.email == email_value))
                if existing_email.scalars().first():
                    results.append({
                        "phone": student_data.phone,
                        "name": student_data.name,
                        "status": "failed",
                        "error": f"Email {email_value} already registered"
                    })
                    failure_count += 1
                    continue
            
            # Check for existing roll_no (for ALL roles now)
            existing_roll = await db.execute(select(StudentProfile).where(StudentProfile.roll_no == student_data.roll_no))
            if existing_roll.scalars().first():
                results.append({
                    "phone": student_data.phone,
                    "name": student_data.name,
                    "status": "failed",
                    "error": f"Roll number {student_data.roll_no} already registered"
                })
                failure_count += 1
                continue
            
            # Create User
            user_id = str(uuid.uuid4())
            new_user = User(
                id=user_id,
                email=email_value,  # Use cleaned email value (None if empty)
                phone=student_data.phone,
                password_hash=hash_password(student_data.password),
                role=student_data.role,
                is_active=student_data.is_active,
                profile_completed=True
            )
            db.add(new_user)
            await db.flush()  # Flush to ensure user ID is in DB before adding profile
            
            # Create Profile for ALL roles (students, teachers, maintenance)
            profile = StudentProfile(
                user_id=user_id,
                name=student_data.name,
                roll_no=student_data.roll_no,
                school_name=student_data.school_name or '',
                standard=student_data.standard if student_data.role == 'student' else None,
                gender=student_data.gender or 'other',
                email=email_value,  # Use cleaned email value
                login_phone=student_data.phone,
                parent_phone=student_data.parent_phone or student_data.phone
            )
            db.add(profile)
            
            await db.commit()
            
            results.append({
                "phone": student_data.phone,
                "name": student_data.name,
                "roll_no": student_data.roll_no,
                "status": "success",
                "user_id": user_id
            })
            success_count += 1
            
        except Exception as e:
            await db.rollback()
            # Provide user-friendly error messages
            error_msg = str(e)
            if 'UniqueViolation' in error_msg or 'unique constraint' in error_msg.lower():
                if 'email' in error_msg.lower():
                    error_msg = "Email already registered"
                elif 'phone' in error_msg.lower():
                    error_msg = "Phone number already registered"
                elif 'roll_no' in error_msg.lower():
                    error_msg = "Roll number already registered"
                else:
                    error_msg = "Duplicate entry detected"
            results.append({
                "phone": student_data.phone,
                "name": student_data.name,
                "status": "failed",
                "error": error_msg
            })
            failure_count += 1
    
    logger.info(f"📊 Bulk registration: {success_count} success, {failure_count} failed")
    
    return {
        "message": f"Bulk registration completed: {success_count} succeeded, {failure_count} failed",
        "total": len(request.students),
        "success_count": success_count,
        "failure_count": failure_count,
        "results": results
    }

@api_router.get("/admin/users")
async def admin_list_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    standard: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_admin)
):
    """
    Admin: List all users with optional filters.
    """
    # Build query
    query = select(User).where(User.role != 'admin')  # Don't list admin users
    
    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    
    result = await db.execute(query.order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    # Get profiles for all users (students, teachers, maintenance)
    user_list = []
    for u in users:
        user_data = {
            "id": str(u.id),
            "email": u.email,
            "phone": u.phone,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None
        }
        
        # Get profile for ALL users (not just students)
        profile_result = await db.execute(
            select(StudentProfile).where(StudentProfile.user_id == str(u.id))
        )
        profile = profile_result.scalars().first()
        if profile:
            # Filter by standard if specified (only applies to students)
            if standard and u.role == 'student' and profile.standard != standard:
                continue
            user_data.update({
                "name": profile.name,
                "roll_no": profile.roll_no,
                "school_name": profile.school_name,
                "standard": profile.standard,
                "gender": profile.gender,
                "parent_phone": profile.parent_phone
            })
        
        user_list.append(user_data)
    
    return {
        "total": len(user_list),
        "users": user_list
    }

@api_router.put("/admin/user/{user_id}/toggle-active")
async def admin_toggle_user_active(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin: Toggle user active status (activate/deactivate)"""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalars().first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target_user.role == 'admin':
        raise HTTPException(status_code=400, detail="Cannot modify admin user")
    
    target_user.is_active = not target_user.is_active
    await db.commit()
    
    status = "activated" if target_user.is_active else "deactivated"
    logger.info(f"✅ Admin {status} user: {user_id}")
    
    return {
        "message": f"User {status} successfully",
        "user_id": user_id,
        "is_active": target_user.is_active
    }

@api_router.delete("/admin/user/{user_id}")
async def admin_delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin: Delete a user and their profile"""
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalars().first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if target_user.role == 'admin':
        raise HTTPException(status_code=400, detail="Cannot delete admin user")
    
    # Delete profile if exists
    await db.execute(delete(StudentProfile).where(StudentProfile.user_id == user_id))
    
    # Delete user
    await db.delete(target_user)
    await db.commit()
    
    logger.info(f"🗑️ Admin deleted user: {user_id}")
    
    return {"message": "User deleted successfully", "user_id": user_id}

@api_router.post("/admin/reset-password")
async def admin_reset_password(
    request: AdminResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin: Reset any user's password by roll_no (no OTP required)"""
    # Find user by roll_no
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.roll_no == request.roll_no)
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail=f"User with roll no '{request.roll_no}' not found")
    
    # Get the user
    user_result = await db.execute(select(User).where(User.id == profile.user_id))
    target_user = user_result.scalars().first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User account not found")
    
    if target_user.role == 'admin':
        raise HTTPException(status_code=400, detail="Cannot reset admin password via this method")
    
    # Hash and update password
    target_user.password_hash = hash_password(request.new_password)
    await db.commit()
    
    logger.info(f"🔑 Admin reset password for user: {profile.name} (Roll: {request.roll_no})")
    
    return {
        "message": f"Password reset successfully for {profile.name}",
        "roll_no": request.roll_no,
        "user_name": profile.name
    }

@api_router.post("/admin/impersonate")
async def admin_impersonate_user(
    request: AdminImpersonateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin: Login as any user by roll_no (impersonate feature)"""
    # Find user by roll_no
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.roll_no == request.roll_no)
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail=f"User with roll no '{request.roll_no}' not found")
    
    # Get the user
    user_result = await db.execute(select(User).where(User.id == profile.user_id))
    target_user = user_result.scalars().first()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User account not found")
    
    if not target_user.is_active:
        raise HTTPException(status_code=403, detail="User account is deactivated")
    
    # Create JWT token for the target user
    token = create_jwt_token(str(target_user.id), target_user.role)
    
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="None",
        secure=True
    )
    
    logger.info(f"👤 Admin impersonating user: {profile.name} (Roll: {request.roll_no})")
    
    return {
        "message": f"Logged in as {profile.name}",
        "user": {
            "id": str(target_user.id),
            "role": target_user.role,
            "name": profile.name,
            "roll_no": profile.roll_no,
            "standard": profile.standard,
            "school_name": profile.school_name
        }
    }

@api_router.get("/admin/search-user/{roll_no}")
async def admin_search_user_by_rollno(
    roll_no: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin: Search for a user by roll_no"""
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.roll_no == roll_no)
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail=f"User with roll no '{roll_no}' not found")
    
    # Get the user
    user_result = await db.execute(select(User).where(User.id == profile.user_id))
    user = user_result.scalars().first()
    
    return {
        "user_id": str(user.id) if user else None,
        "name": profile.name,
        "roll_no": profile.roll_no,
        "standard": profile.standard,
        "school_name": profile.school_name,
        "role": user.role if user else None,
        "is_active": user.is_active if user else None,
        "phone": user.phone if user else None,
        "email": profile.email
    }

# =============================================================================
# SCHOOL MANAGEMENT ROUTES
# =============================================================================

@api_router.get("/schools/list")
async def get_registered_schools(
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of unique schools from registered teachers.
    Used for student registration dropdown.
    Returns schools alphabetically sorted.
    """
    # Get all profiles for teachers
    result = await db.execute(
        select(StudentProfile.school_name, User.role)
        .join(User, User.id == StudentProfile.user_id)
        .where(User.role == 'teacher')
        .where(StudentProfile.school_name.isnot(None))
        .where(StudentProfile.school_name != '')
    )
    rows = result.all()
    
    # Extract unique school names
    schools = list(set([row[0] for row in rows if row[0] and row[0].strip()]))
    schools.sort()  # Alphabetical order
    
    return {
        "schools": schools,
        "total": len(schools)
    }


# =============================================================================
# NEW AUTH ROUTES - Roll No + Password Login
# =============================================================================

@api_router.post("/auth/login")
async def login_with_rollno(
    request: RollNoLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login using roll_no and password (replaces OTP login)"""
    # Find user by roll_no
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.roll_no == request.roll_no)
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=401, detail="Invalid roll number or password")
    
    # Get the user
    user_result = await db.execute(select(User).where(User.id == profile.user_id))
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid roll number or password")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated. Contact admin.")
    
    # Verify password
    if not user.password_hash or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid roll number or password")
    
    # Create JWT token
    token = create_jwt_token(str(user.id), user.role)
    
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="None",
        secure=True
    )
    
    logger.info(f"✅ User logged in: {profile.name} (Roll: {request.roll_no})")
    
    return {
        "message": "Login successful",
        "token": token,  # Include token in response for localStorage fallback
        "user": {
            "id": str(user.id),
            "role": user.role,
            "name": profile.name,
            "roll_no": profile.roll_no,
            "standard": profile.standard,
            "school_name": profile.school_name,
            "profile_completed": user.profile_completed
        }
    }

@api_router.post("/auth/register-teacher")
async def public_teacher_registration(
    request: AdminRegisterStudentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    PUBLIC endpoint for teacher self-registration.
    Teachers can register themselves without admin authentication.
    This creates the school namespace for students to join later.
    """
    import uuid
    
    # Only allow teacher registration through this endpoint
    if request.role != 'teacher':
        raise HTTPException(status_code=400, detail="This endpoint is only for teacher registration. Students must be registered by admin.")
    
    # School name is required for teachers
    if not request.school_name or not request.school_name.strip():
        raise HTTPException(status_code=400, detail="School name is required for teachers")
    
    # Roll number is required
    if not request.roll_no:
        raise HTTPException(status_code=400, detail="Roll number is required")
    
    # Convert empty email string to None
    email_value = request.email.strip() if request.email and request.email.strip() else None
    
    # Check if phone already exists
    existing_phone = await db.execute(select(User).where(User.phone == request.phone))
    if existing_phone.scalars().first():
        raise HTTPException(status_code=400, detail=f"Phone number {request.phone} already registered")
    
    # Check if email already exists (if provided)
    if email_value:
        existing_email = await db.execute(select(User).where(User.email == email_value))
        if existing_email.scalars().first():
            raise HTTPException(status_code=400, detail=f"Email {email_value} already registered")
    
    # Check if roll_no already exists
    existing_roll = await db.execute(select(StudentProfile).where(StudentProfile.roll_no == request.roll_no))
    if existing_roll.scalars().first():
        raise HTTPException(status_code=400, detail=f"Roll number {request.roll_no} already registered")
    
    try:
        # Create User record
        user_id = str(uuid.uuid4())
        new_user = User(
            id=user_id,
            phone=request.phone,
            email=email_value,
            password_hash=hash_password(request.password),
            role='teacher',
            is_active=True,
            profile_completed=True
        )
        db.add(new_user)
        
        # Create StudentProfile record (used for all roles including teachers)
        new_profile = StudentProfile(
            user_id=user_id,
            name=request.name,
            roll_no=request.roll_no,
            school_name=request.school_name.strip(),
            standard=None,  # Teachers don't have a standard
            gender=request.gender or 'other',
            parent_phone=request.parent_phone or request.phone
        )
        db.add(new_profile)
        
        await db.commit()
        
        logger.info(f"✅ Teacher registered: {request.name} from {request.school_name}")
        
        return {
            "message": "Teacher registered successfully. You can now login with your roll number and password.",
            "user": {
                "id": user_id,
                "name": request.name,
                "roll_no": request.roll_no,
                "school_name": request.school_name,
                "role": "teacher"
            }
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Teacher registration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@api_router.post("/auth/request-reset-otp")
async def request_password_reset_otp(
    request: RequestPasswordResetOTPRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request OTP for password reset (sent to registered phone)"""
    # Find user by roll_no
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.roll_no == request.roll_no)
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Roll number not found")
    
    # Get the user
    user_result = await db.execute(select(User).where(User.id == profile.user_id))
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")
    
    # Generate OTP (in production, send via SMS)
    otp = "123456"  # For testing - in production use: str(random.randint(100000, 999999))
    
    # Store OTP (in production, use Redis with expiry)
    OTP_STORE[request.roll_no] = {
        "otp": otp,
        "user_id": str(user.id),
        "purpose": "password_reset"
    }
    
    logger.info(f"📱 Password reset OTP generated for: {profile.name} (Roll: {request.roll_no})")
    
    # In production, send SMS here
    # For now, return success (OTP is 123456 for testing)
    phone_masked = user.phone[-4:] if user.phone else "****"
    
    return {
        "message": f"OTP sent to phone ending in {phone_masked}",
        "roll_no": request.roll_no,
        "name": profile.name
    }

@api_router.post("/auth/reset-password")
async def user_reset_password(
    request: UserResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using old password and OTP verification"""
    # Find user by roll_no
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.roll_no == request.roll_no)
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Roll number not found")
    
    # Get the user
    user_result = await db.execute(select(User).where(User.id == profile.user_id))
    user = user_result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User account not found")
    
    # Verify old password
    if not user.password_hash or not verify_password(request.old_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    
    # Verify OTP
    stored_otp = OTP_STORE.get(request.roll_no)
    if not stored_otp or stored_otp.get("otp") != request.otp:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    
    if stored_otp.get("purpose") != "password_reset":
        raise HTTPException(status_code=401, detail="Invalid OTP for this operation")
    
    # Update password
    user.password_hash = hash_password(request.new_password)
    await db.commit()
    
    # Clear OTP
    if request.roll_no in OTP_STORE:
        del OTP_STORE[request.roll_no]
    
    logger.info(f"🔑 User reset password: {profile.name} (Roll: {request.roll_no})")
    
    return {
        "message": "Password reset successfully",
        "roll_no": request.roll_no
    }

# =============================================================================
# STUDENT PROFILE ROUTES
# =============================================================================

@api_router.post("/student/profile")
async def create_student_profile(
    request: CreateStudentProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create student profile (one-time, during first registration)"""
    if user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can create student profiles")
    
    # Check if profile already exists
    existing = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Profile already exists")
    
    # Check if roll_no is unique
    roll_check = await db.execute(select(StudentProfile).where(StudentProfile.roll_no == request.roll_no))
    if roll_check.scalars().first():
        raise HTTPException(status_code=400, detail="Roll number already registered")
    
    # Validate standard
    if not 1 <= request.standard <= 10:
        raise HTTPException(status_code=400, detail="Standard must be between 1 and 10")
    
    # Validate gender
    if request.gender not in ['male', 'female', 'other']:
        raise HTTPException(status_code=400, detail="Gender must be 'male', 'female', or 'other'")
    
    # Create profile
    profile = StudentProfile(
        user_id=str(user.id),
        name=request.name,
        roll_no=request.roll_no,
        school_name=request.school_name,
        standard=request.standard,
        gender=request.gender,
        email=request.email or user.email,
        login_phone=request.login_phone,
        parent_phone=request.parent_phone or request.login_phone
    )
    db.add(profile)
    
    # Update user's profile_completed flag
    user.profile_completed = True
    
    await db.commit()
    await db.refresh(profile)
    
    return {
        "message": "Profile created successfully",
        "profile": {
            "name": profile.name,
            "roll_no": profile.roll_no,
            "school_name": profile.school_name,
            "standard": profile.standard,
            "gender": profile.gender,
            "email": profile.email,
            "login_phone": profile.login_phone,
            "parent_phone": profile.parent_phone
        }
    }

@api_router.get("/student/profile")
async def get_student_profile(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get current student's profile"""
    if user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students have profiles")
    
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    return {
        "name": profile.name,
        "roll_no": profile.roll_no,
        "school_name": profile.school_name,
        "standard": profile.standard,
        "gender": profile.gender,
        "email": profile.email,
        "login_phone": profile.login_phone,
        "parent_phone": profile.parent_phone
    }

# =============================================================================
# STUDENT ACADEMIC DATA ROUTES
# =============================================================================

@api_router.post("/student/exam-score")
async def add_exam_score(
    request: StudentExamScoreRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add a school exam score for the current student"""
    # Get student's roll_no
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found. Complete profile first.")
    
    from datetime import datetime
    exam_date = datetime.strptime(request.exam_date, "%Y-%m-%d").date()
    
    score_entry = StudentExamScore(
        roll_no=profile.roll_no,
        subject=request.subject,
        exam_name=request.exam_name,
        exam_date=exam_date,
        score=request.score,
        max_score=request.max_score
    )
    db.add(score_entry)
    await db.commit()
    
    return {"message": "Exam score added successfully"}

@api_router.get("/student/exam-scores")
async def get_exam_scores(
    subject: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all exam scores for the current student"""
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    query = select(StudentExamScore).where(StudentExamScore.roll_no == profile.roll_no)
    if subject:
        query = query.where(StudentExamScore.subject == subject)
    query = query.order_by(StudentExamScore.exam_date.desc())
    
    result = await db.execute(query)
    scores = result.scalars().all()
    
    return [
        {
            "id": str(s.id),
            "subject": s.subject,
            "exam_name": s.exam_name,
            "exam_date": str(s.exam_date),
            "score": s.score,
            "max_score": s.max_score,
            "percentage": round((s.score / s.max_score) * 100, 1) if s.max_score > 0 else 0
        }
        for s in scores
    ]

@api_router.post("/student/practice-progress")
async def update_practice_progress(
    request: StudentPracticeProgressRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update chapter-wise practice test progress"""
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Check if entry exists
    existing = await db.execute(
        select(StudentPracticeProgress).where(
            StudentPracticeProgress.roll_no == profile.roll_no,
            StudentPracticeProgress.subject == request.subject,
            StudentPracticeProgress.chapter == request.chapter,
            StudentPracticeProgress.practice_test_number == request.practice_test_number
        )
    )
    progress = existing.scalars().first()
    
    from datetime import datetime, timezone
    
    if progress:
        # Update existing
        progress.attempted = True
        progress.score = request.score
        progress.attempt_date = datetime.now(timezone.utc)
    else:
        # Create new
        progress = StudentPracticeProgress(
            roll_no=profile.roll_no,
            subject=request.subject,
            chapter=request.chapter,
            practice_test_number=request.practice_test_number,
            attempted=True,
            score=request.score,
            attempt_date=datetime.now(timezone.utc)
        )
        db.add(progress)
    
    await db.commit()
    return {"message": "Practice progress updated"}

@api_router.get("/student/practice-progress")
async def get_practice_progress(
    subject: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get practice progress for current student"""
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    query = select(StudentPracticeProgress).where(StudentPracticeProgress.roll_no == profile.roll_no)
    if subject:
        query = query.where(StudentPracticeProgress.subject == subject)
    
    result = await db.execute(query)
    progress = result.scalars().all()
    
    return [
        {
            "id": str(p.id),
            "subject": p.subject,
            "chapter": p.chapter,
            "practice_test_number": p.practice_test_number,
            "attempted": p.attempted,
            "score": p.score,
            "attempt_date": str(p.attempt_date) if p.attempt_date else None
        }
        for p in progress
    ]

@api_router.get("/student/progress-summary")
async def get_progress_summary(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get overall progress summary for current student"""
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get exam scores summary by subject
    exam_result = await db.execute(
        select(StudentExamScore).where(StudentExamScore.roll_no == profile.roll_no)
    )
    exam_scores = exam_result.scalars().all()
    
    # Calculate subject-wise averages
    subject_scores = {}
    for score in exam_scores:
        if score.subject not in subject_scores:
            subject_scores[score.subject] = {"total_score": 0, "total_max": 0, "count": 0}
        subject_scores[score.subject]["total_score"] += score.score
        subject_scores[score.subject]["total_max"] += score.max_score
        subject_scores[score.subject]["count"] += 1
    
    subject_averages = {
        subj: {
            "average_percentage": round((data["total_score"] / data["total_max"]) * 100, 1) if data["total_max"] > 0 else 0,
            "exam_count": data["count"]
        }
        for subj, data in subject_scores.items()
    }
    
    # Get practice progress summary
    practice_result = await db.execute(
        select(StudentPracticeProgress).where(StudentPracticeProgress.roll_no == profile.roll_no)
    )
    practice_progress = practice_result.scalars().all()
    
    # Calculate chapter completion
    chapter_completion = {}
    for p in practice_progress:
        key = f"{p.subject}:{p.chapter}"
        if key not in chapter_completion:
            chapter_completion[key] = {"attempted": 0, "total": 3}  # Assuming 3 tests per chapter
        if p.attempted:
            chapter_completion[key]["attempted"] += 1
    
    # Get homework status
    homework_result = await db.execute(
        select(StudentHomeworkStatus).where(StudentHomeworkStatus.roll_no == profile.roll_no)
    )
    homework_status = homework_result.scalars().all()
    
    missed_homework = sum(1 for h in homework_status if h.status == 'missed')
    completed_homework = sum(1 for h in homework_status if h.status == 'completed')
    
    return {
        "student": {
            "name": profile.name,
            "roll_no": profile.roll_no,
            "standard": profile.standard,
            "school_name": profile.school_name
        },
        "exam_performance": subject_averages,
        "chapter_completion": {
            key: round((data["attempted"] / data["total"]) * 100, 1)
            for key, data in chapter_completion.items()
        },
        "homework": {
            "completed": completed_homework,
            "missed": missed_homework,
            "total": completed_homework + missed_homework
        }
    }

# =============================================================================
# TEACHER: STUDENT DATA MANAGEMENT
# =============================================================================

@api_router.get("/teacher/students")
async def list_students(
    standard: Optional[int] = None,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db)
):
    """List all students (teachers only)"""
    query = select(StudentProfile)
    if standard:
        query = query.where(StudentProfile.standard == standard)
    query = query.order_by(StudentProfile.standard, StudentProfile.roll_no)
    
    result = await db.execute(query)
    students = result.scalars().all()
    
    return [
        {
            "roll_no": s.roll_no,
            "name": s.name,
            "standard": s.standard,
            "school_name": s.school_name,
            "email": s.email,
            "login_phone": s.login_phone
        }
        for s in students
    ]

@api_router.get("/teacher/student/{roll_no}/progress")
async def get_student_progress(
    roll_no: str,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Get specific student's progress (teachers only)"""
    # Get student profile
    result = await db.execute(select(StudentProfile).where(StudentProfile.roll_no == roll_no))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get exam scores
    exam_result = await db.execute(
        select(StudentExamScore).where(StudentExamScore.roll_no == roll_no).order_by(StudentExamScore.exam_date.desc())
    )
    exam_scores = exam_result.scalars().all()
    
    # Get practice progress
    practice_result = await db.execute(
        select(StudentPracticeProgress).where(StudentPracticeProgress.roll_no == roll_no)
    )
    practice_progress = practice_result.scalars().all()
    
    # Get homework status
    homework_result = await db.execute(
        select(StudentHomeworkStatus).where(StudentHomeworkStatus.roll_no == roll_no)
    )
    homework_status = homework_result.scalars().all()
    
    return {
        "student": {
            "roll_no": profile.roll_no,
            "name": profile.name,
            "standard": profile.standard,
            "school_name": profile.school_name
        },
        "exam_scores": [
            {
                "subject": s.subject,
                "exam_name": s.exam_name,
                "exam_date": str(s.exam_date),
                "score": s.score,
                "max_score": s.max_score,
                "percentage": round((s.score / s.max_score) * 100, 1) if s.max_score > 0 else 0
            }
            for s in exam_scores
        ],
        "practice_progress": [
            {
                "subject": p.subject,
                "chapter": p.chapter,
                "practice_test_number": p.practice_test_number,
                "attempted": p.attempted,
                "score": p.score
            }
            for p in practice_progress
        ],
        "homework": {
            "completed": sum(1 for h in homework_status if h.status == 'completed'),
            "missed": sum(1 for h in homework_status if h.status == 'missed')
        }
    }

@api_router.post("/teacher/student/{roll_no}/exam-score")
async def add_student_exam_score(
    roll_no: str,
    request: StudentExamScoreRequest,
    user: User = Depends(require_teacher),
    db: AsyncSession = Depends(get_db)
):
    """Add exam score for a student (teachers only)"""
    # Verify student exists
    result = await db.execute(select(StudentProfile).where(StudentProfile.roll_no == roll_no))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    
    from datetime import datetime
    exam_date = datetime.strptime(request.exam_date, "%Y-%m-%d").date()
    
    score_entry = StudentExamScore(
        roll_no=roll_no,
        subject=request.subject,
        exam_name=request.exam_name,
        exam_date=exam_date,
        score=request.score,
        max_score=request.max_score
    )
    db.add(score_entry)
    await db.commit()
    
    return {"message": f"Exam score added for {profile.name}"}

# Subject Routes
@api_router.get("/subjects")
async def list_subjects(
    standard: Optional[int] = None, 
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """
    List subjects with school-based filtering.
    - Unauthenticated: See all default subjects
    - Students/Teachers: See subjects from their school + default subjects (school_name is NULL)
    - Admin: See all subjects
    """
    from sqlalchemy import or_
    
    query = select(Subject).order_by(Subject.order, Subject.name)
    
    # School-based filtering only for authenticated users
    if user:
        user_school = await get_user_school(user, db)
        if user_school and user.role in ['student', 'teacher']:
            # Show subjects from their school OR default subjects (school_name is NULL)
            query = query.where(
                or_(
                    Subject.school_name == user_school,
                    Subject.school_name.is_(None)
                )
            )
    
    # Filter by standard if provided
    if standard is not None:
        query = query.where(Subject.standard == standard)
    
    result = await db.execute(query)
    subjects = result.scalars().all()
    
    subjects_data = []
    for s in subjects:
        subject_data = {
            "id": str(s.id),
            "name": s.name,
            "standard": s.standard,
            "description": s.description,
            "is_default": s.is_default,
            "syllabus_complete_percent": 0
        }
        
        # Calculate syllabus completion for students based on quiz completion
        # Each chapter has 5 quizzes, completing all 5 = 100% for that chapter
        if user and user.role == 'student':
            # Get total chapters for this subject
            chapters_result = await db.execute(
                select(func.count(Chapter.id)).where(Chapter.subject_id == s.id)
            )
            total_chapters = chapters_result.scalar() or 0
            
            if total_chapters > 0:
                # Get student profile
                student_profile_result = await db.execute(
                    select(StudentProfile).where(StudentProfile.user_id == user.id)
                )
                student_profile = student_profile_result.scalars().first()
                
                if student_profile:
                    # Count total quizzes completed (each quiz = 1 entry with attempted=True)
                    quizzes_completed_result = await db.execute(
                        select(func.count(StudentPracticeProgress.id)).where(
                            and_(
                                StudentPracticeProgress.roll_no == student_profile.roll_no,
                                StudentPracticeProgress.subject == s.name,
                                StudentPracticeProgress.attempted == True
                            )
                        )
                    )
                    quizzes_completed = quizzes_completed_result.scalar() or 0
                    
                    # Total possible quizzes = chapters * 5
                    total_quizzes = total_chapters * 5
                    
                    # Calculate percentage (each quiz = 20% of a chapter, spread across all chapters)
                    subject_data["syllabus_complete_percent"] = round((quizzes_completed / total_quizzes) * 100) if total_quizzes > 0 else 0
        
        subjects_data.append(subject_data)
    
    return subjects_data

@api_router.post("/subjects")
async def create_subject(request: CreateSubjectRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_teacher)):
    """Teacher: Create a new subject for their school"""
    # Validate standard is between 1-10
    if not 1 <= request.standard <= 10:
        raise HTTPException(status_code=400, detail="Standard must be between 1 and 10")
    
    # Get teacher's school
    teacher_school = await get_user_school(user, db)
    if not teacher_school:
        raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
    
    subject = Subject(
        name=request.name, 
        standard=request.standard, 
        description=request.description,
        school_name=teacher_school
    )
    db.add(subject)
    await db.commit()
    await db.refresh(subject)
    return {
        "id": str(subject.id), 
        "name": subject.name, 
        "standard": subject.standard, 
        "description": subject.description,
        "school_name": subject.school_name
    }

@api_router.put("/subjects/{subject_id}")
async def update_subject(
    subject_id: str,
    request: UpdateSubjectRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Teacher: Update subject name/description/standard"""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    if request.name:
        subject.name = request.name
    if request.standard:
        if not 1 <= request.standard <= 10:
            raise HTTPException(status_code=400, detail="Standard must be between 1 and 10")
        subject.standard = request.standard
    if request.description:
        subject.description = request.description
    
    await db.commit()
    await db.refresh(subject)
    return {
        "id": str(subject.id),
        "name": subject.name,
        "standard": subject.standard,
        "description": subject.description,
        "message": "Subject updated successfully"
    }

@api_router.delete("/subjects/{subject_id}")
async def delete_subject(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Teacher: Delete subject and all its chapters"""
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Delete all chapters for this subject (cascade)
    await db.execute(delete(Chapter).where(Chapter.subject_id == subject_id))
    await db.delete(subject)
    await db.commit()
    
    return {"message": f"Subject '{subject.name}' and all its chapters deleted successfully"}

# Chapter Routes  
@api_router.get("/subjects/{subject_id}/chapters")
async def list_chapters(
    subject_id: str, 
    db: AsyncSession = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user)
):
    """
    List chapters for a subject with school-based filtering.
    - Unauthenticated: See all chapters
    - Students/Teachers: Only see chapters from their school
    - Admin: See all chapters
    """
    # School-based filtering only for authenticated users
    user_school = None
    if user:
        user_school = await get_user_school(user, db)
    
    query = select(Chapter).where(Chapter.subject_id == subject_id).order_by(Chapter.order, Chapter.name)
    
    if user and user_school and user.role in ['student', 'teacher']:
        query = query.where(Chapter.school_name == user_school)
    
    result = await db.execute(query)
    chapters = result.scalars().all()
    return [{"id": str(c.id), "subject_id": str(c.subject_id), "standard": c.standard, "name": c.name, "description": c.description, "video_url": c.video_url, "order": c.order} for c in chapters]

@api_router.post("/chapters")
async def create_chapter(request: CreateChapterRequest, db: AsyncSession = Depends(get_db), user: User = Depends(require_teacher)):
    """Teacher: Create a chapter in their school"""
    # Get the parent subject to inherit standard and school
    result = await db.execute(select(Subject).where(Subject.id == request.subject_id))
    subject = result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Get teacher's school
    teacher_school = await get_user_school(user, db)
    if not teacher_school:
        raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
    
    # Verify teacher owns this subject (same school)
    if subject.school_name and subject.school_name != teacher_school:
        raise HTTPException(status_code=403, detail="Cannot add chapter to subject from another school")
    
    chapter = Chapter(
        subject_id=request.subject_id, 
        standard=subject.standard,  # Inherit standard from subject
        school_name=teacher_school,  # Set school
        name=request.name, 
        description=request.description
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return {"id": str(chapter.id), "name": chapter.name, "standard": chapter.standard, "school_name": chapter.school_name}

@api_router.put("/chapters/{chapter_id}")
async def update_chapter(chapter_id: str, name: str = Form(...), db: AsyncSession = Depends(get_db), user: User = Depends(require_teacher)):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    chapter.name = name
    await db.commit()
    return {"id": str(chapter.id), "name": chapter.name}

@api_router.delete("/chapters/{chapter_id}")
async def delete_chapter(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Teacher: Delete chapter and all its content (including S3 files)"""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Get subject for S3 cleanup
    subject_result = await db.execute(select(Subject).where(Subject.id == chapter.subject_id))
    subject = subject_result.scalars().first()
    
    chapter_name = chapter.name
    
    # Clean up S3 files
    if subject:
        from app.services.storage_service import delete_ai_content_from_s3, normalize_chapter_slug, sanitize_component, s3_client, S3_BUCKET, ensure_s3_initialized
        
        try:
            ensure_s3_initialized()
            standard = chapter.standard
            
            # Delete AI content
            await delete_ai_content_from_s3(standard, subject.name, chapter.name, "revision_notes")
            await delete_ai_content_from_s3(standard, subject.name, chapter.name, "flashcards")
            await delete_ai_content_from_s3(standard, subject.name, chapter.name, "quiz")
            
            # Delete textbook PDF
            class_folder = f"class{standard}"
            subject_folder = sanitize_component(subject.name)
            chapter_folder = normalize_chapter_slug(chapter.name)
            pdf_key = f"pdfs/{class_folder}/{subject_folder}/{chapter_folder}/textbook.pdf"
            
            s3_client.delete_object(Bucket=S3_BUCKET, Key=pdf_key)
            logger.info(f"🗑️ Deleted S3 content for chapter: {chapter.name}")
        except Exception as e:
            logger.error(f"⚠️ S3 cleanup failed: {e}")
            # Continue with DB deletion even if S3 fails
    
    # Delete all content for this chapter (cascade)
    await db.execute(delete(Content).where(Content.chapter_id == chapter_id))
    await db.delete(chapter)
    await db.commit()
    
    return {"message": f"Chapter '{chapter_name}' and all its content deleted successfully"}

# Video URL endpoints
@api_router.put("/chapters/{chapter_id}/video")
async def update_chapter_video(
    chapter_id: str,
    video_url: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Teacher: Add or update video URL for chapter"""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    chapter.video_url = video_url if video_url.strip() else None
    await db.commit()
    
    return {
        "id": str(chapter.id),
        "name": chapter.name,
        "video_url": chapter.video_url,
        "message": "Video URL updated successfully"
    }

@api_router.get("/chapters/{chapter_id}/video")
async def get_chapter_video(chapter_id: str, db: AsyncSession = Depends(get_db)):
    """Student: Get video URL for chapter"""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    if not chapter.video_url:
        raise HTTPException(status_code=404, detail="No video available for this chapter")
    
    return {
        "video_url": chapter.video_url,
        "chapter_name": chapter.name
    }

@api_router.get("/chapters/{chapter_id}/content-status")
async def get_content_status(chapter_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Content).where(Content.chapter_id == chapter_id)
    )
    contents = result.scalars().all()
    
    status = {
        'textbook': None  # Changed from 'ncert', 'school', 'previous_year'
    }
    
    for content in contents:
        # All content types map to 'textbook'
        status['textbook'] = {
            'file_name': content.file_name,
            'uploaded': True,
            'ocr_processed': content.ocr_processed
        }
    
    return status

@api_router.post("/content/upload")
async def upload_content(
    chapter_id: str = Form(...),
    content_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Get subject info for cache clearing
    subject_result = await db.execute(select(Subject).where(Subject.id == chapter.subject_id))
    subject = subject_result.scalars().first()
    
    # Check if content already exists for this chapter - delete old content
    existing_content_result = await db.execute(
        select(Content).where(Content.chapter_id == chapter_id)
    )
    existing_contents = existing_content_result.scalars().all()
    
    # Delete old content files and database entries
    from app.services.storage_service import delete_file_from_storage
    for old_content in existing_contents:
        if old_content.s3_url:
            await delete_file_from_storage(old_content.s3_url)
            logger.info(f"Deleted old content file: {old_content.s3_url}")
        await db.delete(old_content)
    
    # Clear AI cache for this chapter (so new content generates fresh AI responses)
    if subject:
        from app.services.ai_service import clear_chapter_ai_cache
        cache_cleared = await clear_chapter_ai_cache(subject.name, chapter.name)
        logger.info(f"Cleared {cache_cleared} AI cache entries for {subject.name}/{chapter.name}")
    
    # Also clear from ai_content_cache table in database
    await db.execute(
        text("DELETE FROM ai_content_cache WHERE chapter_id = :chapter_id"),
        {"chapter_id": chapter_id}
    )
    
    await db.commit()
    
    # Upload new content to S3 with deterministic path
    file_content = await file.read()
    standard = chapter.standard
    
    # Get teacher's school for S3 path
    teacher_school = await get_user_school(user, db)
    if not teacher_school:
        raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
    
    try:
        from app.services.storage_service import upload_pdf_to_s3
        s3_key = await upload_pdf_to_s3(file_content, standard, subject.name, chapter.name, teacher_school)
        # Store key, not URL
        s3_url = s3_key
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file to S3: {str(e)}")
    
    content = Content(
        chapter_id=chapter_id,
        content_type=content_type,
        file_name=file.filename,
        s3_url=s3_url,
        school_name=teacher_school,  # SET SCHOOL
        ocr_processed=False
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)
    
    # OCR removed - Gemini handles PDF processing natively
    # No local text extraction needed
    logger.info("PDF will be processed by Gemini AI when generating content")
    
    return {
        "id": str(content.id),
        "chapter_id": str(content.chapter_id),
        "file_name": content.file_name,
        "ocr_processed": content.ocr_processed,
        "message": "File uploaded successfully. Previous content and AI cache cleared.",
        "old_content_deleted": len(existing_contents)
    }


@api_router.post("/chapter/{chapter_id}/generate-ai-content")
async def generate_chapter_ai_content(
    chapter_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """
    PRODUCTION-GRADE AI GENERATION with Background Processing.
    
    This endpoint:
    1. Sets ai_status = "processing" immediately
    2. Returns success response within 2 seconds
    3. Triggers background task for actual generation
    
    Students see "Content generating, please wait" until ai_status = "completed"
    """
    from app.services.storage_service import download_pdf_from_s3
    from app.services.gpt4o_extraction import extract_text_from_pdf_with_gemini
    
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Check if already processing
    if hasattr(chapter, 'ai_status') and chapter.ai_status == "processing":
        return {
            "success": True,
            "chapter_id": chapter_id,
            "ai_status": "processing",
            "message": "AI content generation is already in progress. Please wait."
        }
    
    subject_result = await db.execute(select(Subject).where(Subject.id == chapter.subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Get teacher's school for S3 path
    teacher_school = await get_user_school(user, db)
    if not teacher_school:
        raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
    
    content_result = await db.execute(select(Content).where(Content.chapter_id == chapter_id))
    content = content_result.scalars().first()
    if not content or not content.s3_url:
        raise HTTPException(status_code=404, detail="No textbook uploaded for this chapter")
    
    # Extract text from PDF using Gemini
    try:
        pdf_bytes = await download_pdf_from_s3(chapter.standard, subject.name, chapter.name, school_name=teacher_school)
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Could not download PDF. Please re-upload.")
        
        content_text = await extract_text_from_pdf_with_gemini(pdf_bytes)
        if not content_text or len(content_text) < 100:
            raise HTTPException(status_code=400, detail="Could not extract text from PDF. Ensure PDF contains readable content.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(status_code=400, detail=f"Text extraction failed: {str(e)}")
    
    # Set status to "processing" IMMEDIATELY
    chapter.ai_status = "processing"
    chapter.ai_generated = False
    chapter.ai_error_message = None
    await db.commit()
    
    logger.info(f"✅ Chapter {chapter_id} status set to 'processing'")
    
    # Trigger background task
    from app.services.ai_orchestrator_v2 import run_generation_background_task
    
    background_tasks.add_task(
        run_generation_background_task,
        chapter_id=chapter_id,
        subject_name=subject.name,
        chapter_name=chapter.name,
        content=content_text,
        standard=chapter.standard,
        school_name=chapter.school_name
    )
    
    logger.info(f"🚀 Background generation task scheduled for chapter {chapter_id}")
    
    # Return IMMEDIATELY (< 2 seconds)
    return {
        "success": True,
        "chapter_id": chapter_id,
        "ai_status": "processing",
        "message": "AI content generation started. This may take 2-3 minutes. Refresh to check status.",
        "details": {
            "chapter_name": chapter.name,
            "subject_name": subject.name,
            "content_length": len(content_text)
        }
    }


# PYQ Endpoints
@api_router.post("/subjects/{subject_id}/upload-pyq")
async def upload_pyq(
    subject_id: str,
    standard: int = Form(...),
    year: str = Form(...),
    exam_name: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """PYQ upload - uses unified Gemini extraction"""
    from sqlalchemy.exc import IntegrityError
    from app.services.storage_service import s3_client, S3_BUCKET, upload_pyq_questions_to_s3
    from app.services.background_extraction import start_extraction_task, ExtractionStatus
    from app.models.database import AsyncSessionLocal
    import uuid
    
    result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Get teacher's school
    teacher_school = await get_user_school(user, db)
    if not teacher_school:
        raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
    
    try:
        normalized_exam_name = normalize_title(exam_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid exam name: {e}")
    
    pyq_id = str(uuid.uuid4())
    file_content = await file.read()
    
    # NEW: School-based S3 structure
    school_folder = sanitize_school_name(teacher_school)
    s3_folder_key = f"{school_folder}/pyq/class{standard}/{sanitize_component(subject.name)}/{year}/{pyq_id}"
    pyq_s3_key = f"{s3_folder_key}/pyq.pdf"
    
    try:
        s3_client.put_object(Bucket=S3_BUCKET, Key=pyq_s3_key, Body=file_content, ContentType='application/pdf')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload PYQ: {str(e)}")
    
    pyq = PreviousYearPaper(
        id=pyq_id,
        subject_id=subject_id,
        standard=standard,
        year=year,
        exam_name=exam_name,
        normalized_exam_name=normalized_exam_name,
        file_name=file.filename,
        file_path=pyq_s3_key,
        s3_folder_key=s3_folder_key,
        school_name=teacher_school,  # SET SCHOOL
        created_by=str(user.id),  # Track teacher who uploaded
        extraction_status=ExtractionStatus.PENDING,
        solution_generated=False
    )
    
    try:
        db.add(pyq)
        await db.commit()
        await db.refresh(pyq)
    except IntegrityError:
        await db.rollback()
        s3_client.delete_object(Bucket=S3_BUCKET, Key=pyq_s3_key)
        raise HTTPException(status_code=409, detail=f"PYQ '{exam_name}' for year {year} already exists")
    
    async def s3_upload_wrapper(questions):
        return await upload_pyq_questions_to_s3(questions, pyq_id, standard, subject.name, year, s3_folder_key=s3_folder_key)
    
    try:
        await start_extraction_task(
            test_id=pyq_id,
            test_pdf_bytes=file_content,
            model_answers_bytes=None,
            standard=standard,
            subject_name=subject.name,
            db_session_factory=AsyncSessionLocal,
            s3_upload_func=s3_upload_wrapper,
            content_type='pyq'
        )
    except Exception as e:
        pyq.extraction_status = 'failed'
        await db.commit()
    
    return {
        "message": "PYQ uploaded. Extraction in progress.",
        "status": "processing",
        "pyq_id": pyq.id,
        "extraction_status": pyq.extraction_status,
        "solution_generated": False
    }



@api_router.get("/pyq/{pyq_id}/extraction-status")
async def get_pyq_extraction_status(
    pyq_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Poll extraction status for a PYQ (similar to homework/tests)."""
    result = await db.execute(select(PreviousYearPaper).where(PreviousYearPaper.id == pyq_id))
    pyq = result.scalars().first()

    if not pyq:
        raise HTTPException(status_code=404, detail="PYQ not found")

    from datetime import datetime, timezone

    elapsed_seconds = 0
    if pyq.created_at:
        created = pyq.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed_seconds = int((datetime.now(timezone.utc) - created).total_seconds())

    status = pyq.extraction_status or "pending"
    stage = pyq.extraction_stage or "UPLOADED"

    # Derive a synthetic progress percentage for PYQs based on stage
    if stage == "COMPLETED" and status == "completed":
        progress = 100
    elif stage == "SAVING_TO_S3":
        progress = 80
    elif stage == "EXTRACTING_QUESTIONS":
        progress = 50
    elif stage in ("PROCESSING", "UPLOADED"):
        progress = 20
    elif stage in ("FAILED", "TIMEOUT"):
        progress = 100
    else:
        progress = 0

    # Human‑readable stage message
    if stage == "UPLOADED":
        stage_msg = "Starting extraction for PYQ..."
    elif stage == "EXTRACTING_QUESTIONS":
        stage_msg = "Extracting questions from the paper..."
    elif stage == "SAVING_TO_S3":
        stage_msg = "Saving extracted questions to cloud storage..."
    elif stage == "COMPLETED":
        stage_msg = "Extraction completed. Questions are ready!"
    elif stage == "FAILED":
        stage_msg = "Extraction failed. Please try again."
    else:
        stage_msg = "Processing PYQ..."

    should_poll = status in ["pending", "processing"] and stage != "COMPLETED"
    is_stuck = elapsed_seconds > 300 and status == "processing"

    return {
        "content_id": pyq_id,
        "content_type": "pyq",
        "pyq_id": pyq_id,
        "extraction_stage": stage,
        "extraction_status": status,
        "extraction_progress": progress,
        "extraction_stage_message": stage_msg,
        "elapsed_seconds": elapsed_seconds,
        "can_retry": status in ["failed", "timeout"] or is_stuck,
        "should_poll": should_poll and not is_stuck,
        "is_stuck": is_stuck,
        "error": None,
        "questions_extracted_count": pyq.questions_extracted_count,
        "extraction_mismatch": False,
    }

@api_router.get("/subjects/{subject_id}/pyqs")
async def get_subject_pyqs(
    subject_id: str,
    standard: int = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get PYQs for a subject, including status & metadata for UI.
    
    School-Based Multi-Tenancy:
    - Students only see PYQs from their school
    - Teachers see PYQs from their school
    - Admins see all PYQs
    """
    # Get the user's school for filtering
    user_school = await get_user_school(user, db)
    
    query = select(PreviousYearPaper).where(PreviousYearPaper.subject_id == subject_id)
    
    if standard:
        query = query.where(PreviousYearPaper.standard == standard)
    
    # Apply school-based filtering
    if user_school and user.role in ['student', 'teacher']:
        query = query.where(PreviousYearPaper.school_name == user_school)
    # Admins see all
    
    result = await db.execute(query)
    pyqs = result.scalars().all()

    from datetime import datetime

    pyq_list = []
    for p in pyqs:
        # Safely format upload date as ISO string (frontend will localize)
        upload_date = None
        if getattr(p, "created_at", None):
            try:
                upload_date = p.created_at.isoformat()
            except Exception:
                upload_date = None

        pyq_list.append({
            "id": str(p.id),
            "year": p.year,
            "exam_name": p.exam_name,
            "file_name": p.file_name,
            "upload_date": upload_date,
            "extraction_status": p.extraction_status,
            "extraction_stage": p.extraction_stage,
            "questions_extracted_count": p.questions_extracted_count or 0,
            "solution_generated": p.solution_generated,
        })

    return pyq_list


@api_router.post("/pyq/{pyq_id}/generate-solutions")
async def generate_pyq_solutions(
    pyq_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Generate solutions for PYQ using GPT-OSS-120B"""
    from app.services.storage_service import s3_client, S3_BUCKET
    from app.services.ai_service import generate_pyq_solution_from_questions
    import json
    
    result = await db.execute(select(PreviousYearPaper).where(PreviousYearPaper.id == pyq_id))
    pyq = result.scalars().first()
    
    if not pyq:
        raise HTTPException(status_code=404, detail="PYQ not found")
    
    if pyq.solution_generated:
        return {"message": "Solutions already generated", "solution_generated": True}
    
    questions_key = f"{pyq.s3_folder_key}/questions.json"
    
    try:
        questions_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=questions_key)
        questions = json.loads(questions_obj['Body'].read().decode('utf-8'))
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Questions not found. Please re-upload PYQ. Error: {str(e)}")
    
    try:
        solutions = await generate_pyq_solution_from_questions(questions, pyq.exam_name, pyq.year, pyq.standard)
        
        solutions_key = f"{pyq.s3_folder_key}/exam_solution.json"
        solutions_bytes = json.dumps(solutions, indent=2, ensure_ascii=False).encode('utf-8')
        s3_client.put_object(Bucket=S3_BUCKET, Key=solutions_key, Body=solutions_bytes, ContentType='application/json')
        
        pyq.solution_generated = True
        pyq.solution_s3_key = solutions_key
        pyq.solution_generated_at = datetime.now(timezone.utc)
        await db.commit()
        
        return {
            "message": "Solutions generated successfully",
            "solution_generated": True,
            "solutions_count": len(solutions.get('solutions', solutions.get('questions', [])))
        }
    except Exception as e:
        logger.error(f"Solution generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate solutions: {str(e)}")

    """Get all PYQs for a subject and standard"""
    query = select(PreviousYearPaper).where(PreviousYearPaper.subject_id == subject_id)
    
    if standard:
        query = query.where(PreviousYearPaper.standard == standard)
    
    result = await db.execute(query.order_by(PreviousYearPaper.year.desc()))
    pyqs = result.scalars().all()
    
    return [
        {
            "id": str(pyq.id),
            "year": pyq.year,
            "exam_name": pyq.exam_name,
            "file_name": pyq.file_name,
            "solution_cached": pyq.solution_cached
        }
        for pyq in pyqs
    ]

@api_router.post("/pyq/{pyq_id}/generate-solution")
async def generate_pyq_solution(
    pyq_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    DEPRECATED for students - solutions are now pre-generated at upload time.
    This endpoint is now READ-ONLY - fetches from S3, NEVER triggers AI.
    """
    from app.services.storage_service import fetch_pyq_solution_from_s3
    
    result = await db.execute(select(PreviousYearPaper).where(PreviousYearPaper.id == pyq_id))
    pyq = result.scalars().first()
    
    if not pyq:
        raise HTTPException(status_code=404, detail="PYQ not found")
    
    # Get subject for S3 path
    subject_result = await db.execute(select(Subject).where(Subject.id == pyq.subject_id))
    subject = subject_result.scalars().first()
    
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # READ-ONLY: Fetch pre-generated solution from S3
    if pyq.solution_generated and pyq.solution_s3_key:
        solution = await fetch_pyq_solution_from_s3(
            pyq.standard, 
            subject.name, 
            pyq.year, 
            pyq.normalized_exam_name
        )
        
        if solution:
            logger.info(f"✅ Serving pre-generated PYQ solution from S3")
            return {"success": True, "solution": solution, "from_cache": True}
    
    # Check legacy DB cache for backward compatibility
    cache_key = f"pyq_solution:{pyq_id}"
    cache_result = await db.execute(select(AICache).where(AICache.cache_key == cache_key))
    cached = cache_result.scalars().first()
    
    if cached:
        cached.access_count += 1
        cached.last_accessed = datetime.now(timezone.utc)
        await db.commit()
        logger.info(f"✅ Serving PYQ solution from legacy cache")
        return {"success": True, "solution": cached.content, "from_cache": True}
    
    # NO AI GENERATION FOR STUDENTS
    # Solution must be pre-generated by teacher at upload time
    return {
        "success": False, 
        "solution": None, 
        "error": "Solution not available yet. Please ask your teacher to upload PYQ solutions.",
        "from_cache": False
    }




@api_router.get("/pyq/{pyq_id}/questions")
async def get_pyq_questions(
    pyq_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Return extracted PYQ questions JSON from S3 for student view."""
    from app.services.storage_service import s3_client, S3_BUCKET
    import json
    from botocore.exceptions import ClientError

    result = await db.execute(select(PreviousYearPaper).where(PreviousYearPaper.id == pyq_id))
    pyq = result.scalars().first()

    if not pyq:
        raise HTTPException(status_code=404, detail="PYQ not found")

    if not pyq.s3_folder_key:
        raise HTTPException(status_code=500, detail="PYQ storage path missing")

    questions_key = f"{pyq.s3_folder_key}/questions.json"

    try:
        obj = s3_client.get_object(Bucket=S3_BUCKET, Key=questions_key)
        data = json.loads(obj["Body"].read().decode("utf-8"))
        # Some extractors return {"questions": [...]}, others return list directly
        if isinstance(data, dict) and "questions" in data:
            return {"questions": data["questions"]}
        return {"questions": data}
    except ClientError as e:
        code = e.response["Error"].get("Code", "Unknown")
        if code == "NoSuchKey":
            raise HTTPException(status_code=404, detail="Questions file not found in storage")
        raise HTTPException(status_code=500, detail=f"Failed to fetch questions: {code}")


@api_router.get("/pyq/{pyq_id}/solution")
async def get_pyq_solution(
    pyq_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Student READ-ONLY endpoint - fetches pre-generated solution from S3.
    Uses stored S3 key directly - NO path reconstruction.
    NEVER triggers AI generation.
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    import json
    from botocore.exceptions import ClientError
    
    logger.info(f"📖 [PYQ Solution] Request from user {user.id} for PYQ ID: {pyq_id}")
    
    # Fetch PYQ record from database
    result = await db.execute(select(PreviousYearPaper).where(PreviousYearPaper.id == pyq_id))
    pyq = result.scalars().first()
    
    if not pyq:
        logger.error(f"❌ [PYQ Solution] PYQ record not found in database for ID: {pyq_id}")
        logger.error(f"   User attempted: {user.role} (ID: {user.id})")
        raise HTTPException(status_code=404, detail=f"PYQ not found. ID: {pyq_id}")
    
    logger.info(f"📋 [PYQ Solution] Found: {pyq.exam_name} (Year: {pyq.year}, Standard: {pyq.standard})")
    logger.info(f"   solution_generated={pyq.solution_generated}, solution_s3_key={pyq.solution_s3_key}")
    
    # Check if solution was generated and S3 key exists
    if not pyq.solution_generated:
        logger.warning(f"⚠️ [PYQ Solution] Solution not generated for PYQ: {pyq_id}")
        return {
            "success": False,
            "available": False,
            "message": "Solution not available yet. Please contact your teacher."
        }
    
    if not pyq.solution_s3_key:
        logger.error(f"❌ [PYQ Solution] solution_s3_key is NULL for PYQ: {pyq_id}")
        logger.error(f"   This is a data integrity issue - solution_generated=True but solution_s3_key is NULL")
        return {
            "success": False,
            "available": False,
            "message": "Solution path not available. Please contact your teacher."
        }
    
    # Check S3 configuration
    if not s3_client:
        logger.error(f"❌ [PYQ Solution] S3 not configured (s3_client is None)")
        return {
            "success": False,
            "available": False,
            "message": "Storage not configured"
        }
    
    # Fetch solution directly from S3 using stored key
    logger.info(f"🔍 [PYQ Solution] Fetching from S3 using key: {pyq.solution_s3_key}")
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=pyq.solution_s3_key)
        solution_json = response['Body'].read().decode('utf-8')
        raw_solution = json.loads(solution_json)
        
        logger.info(f"✅ [PYQ Solution] Successfully fetched and parsed solution from S3")
        logger.info(f"   Solution size: {len(solution_json)} bytes")
        logger.info(f"   Raw structure keys: {raw_solution.keys() if isinstance(raw_solution, dict) else 'N/A'}")
        
        # Transform data structure to match frontend expectations
        # S3 format: {questions: [{question_no, question_text, answer_steps, final_answer}]}
        # Frontend expects: {solutions: [{question_number, question, solution_steps, final_answer}]}
        
        transformed_solution = {
            "exam_name": raw_solution.get("exam_name", pyq.exam_name),
            "year": raw_solution.get("year", pyq.year),
            "total_marks": raw_solution.get("total_marks"),
            "time_allowed": raw_solution.get("time_allowed"),
            "solutions": []
        }
        
        # Transform questions array to solutions array
        if "questions" in raw_solution and isinstance(raw_solution["questions"], list):
            for q in raw_solution["questions"]:
                solution_item = {
                    "question_number": q.get("question_no", q.get("question_number")),
                    "question": q.get("question_text", q.get("question", "")),
                    "solution_steps": q.get("answer_steps", q.get("solution_steps", [])),
                    "final_answer": q.get("final_answer", q.get("answer", "")),
                    "marks": q.get("marks"),
                    "difficulty": q.get("difficulty"),
                    "understanding": q.get("understanding"),
                    "exam_tip": q.get("exam_tip"),
                    "common_mistake": q.get("common_mistake"),
                    "topics": q.get("topics", [])
                }
                transformed_solution["solutions"].append(solution_item)
            
            logger.info(f"✅ [PYQ Solution] Transformed {len(transformed_solution['solutions'])} questions to solutions format")
        
        # If no questions/solutions array found, try to use the raw data as-is
        elif "solutions" in raw_solution:
            logger.info(f"   Solution already in expected format")
            transformed_solution = raw_solution
        else:
            logger.warning(f"⚠️ [PYQ Solution] No 'questions' or 'solutions' array found in S3 data")
            transformed_solution["solutions"] = []
        
        return {
            "success": True,
            "available": True,
            "solution": transformed_solution
        }
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        logger.error(f"❌ [PYQ Solution] S3 ClientError: {error_code}")
        logger.error(f"   Bucket: {S3_BUCKET}, Key: {pyq.solution_s3_key}")
        logger.error(f"   Error message: {e.response['Error'].get('Message', 'No message')}")
        
        if error_code == 'NoSuchKey':
            # File doesn't exist in S3 - return HTTP 500 (server error, not 404)
            raise HTTPException(
                status_code=500,
                detail=f"Solution file not found in storage. Expected at: {pyq.solution_s3_key}"
            )
        elif error_code == 'AccessDenied':
            raise HTTPException(
                status_code=500,
                detail="Access denied to storage. Please contact administrator."
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Storage error: {error_code}. Please try again later."
            )
            
    except json.JSONDecodeError as e:
        logger.error(f"❌ [PYQ Solution] JSON parse error: {e}")
        logger.error(f"   S3 key: {pyq.solution_s3_key}")
        raise HTTPException(
            status_code=500,
            detail="Solution file is corrupted. Please contact your teacher."
        )
        
    except Exception as e:
        logger.error(f"❌ [PYQ Solution] Unexpected error: {type(e).__name__}: {e}")
        logger.error(f"   S3 key: {pyq.solution_s3_key}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load solution: {str(e)}"
        )


@api_router.post("/subject/{subject_id}/frequently-asked-pyqs")
async def get_frequently_asked_pyqs(
    subject_id: str,
    standard: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Analyze all PYQs for a subject to find frequently asked questions - CACHED PERMANENTLY"""
    from app.services.ai_service import analyze_frequently_asked_pyqs
    
    # Check database cache first
    cache_key = f"frequent_pyqs:{subject_id}:{standard}"
    result = await db.execute(select(AICache).where(AICache.cache_key == cache_key))
    cached = result.scalars().first()
    
    if cached:
        # Update access count
        cached.access_count += 1
        cached.last_accessed = datetime.now(timezone.utc)
        await db.commit()
        
        logger.info(f"✅ Serving frequently asked PYQs from cache (accessed {cached.access_count} times)")
        return {
            "success": True,
            "analysis": cached.content,
            "from_cache": True
        }
    
    # Get all PYQs for this subject and standard
    result = await db.execute(
        select(PreviousYearPaper).where(
            PreviousYearPaper.subject_id == subject_id,
            PreviousYearPaper.standard == standard
        )
    )
    pyqs = result.scalars().all()
    
    if len(pyqs) < 2:
        return {
            "success": False,
            "message": "Need at least 2 PYQs to analyze patterns"
        }
    
    # Prepare data for analysis - load questions from S3
    pyq_data = []
    for pyq in pyqs:
        # Check if questions have been extracted (stored in S3)
        if pyq.questions_extracted_count and pyq.questions_extracted_count > 0:
            try:
                # Load questions from S3
                from app.services.storage_service import fetch_pyq_questions_from_s3
                questions = await fetch_pyq_questions_from_s3(pyq.s3_folder_key)
                
                if questions and len(questions) > 0:
                    pyq_data.append({
                        "id": pyq.id,
                        "exam_name": pyq.exam_name,
                        "year": pyq.year,
                        "questions": questions
                    })
                    logger.info(f"✅ Loaded {len(questions)} questions from PYQ {pyq.exam_name} {pyq.year}")
            except Exception as e:
                logger.warning(f"⚠️ Could not load questions for PYQ {pyq.id}: {e}")
    
    if len(pyq_data) < 2:
        return {
            "success": False,
            "message": "Need at least 2 PYQs with extracted questions. Please upload and extract PYQ papers first."
        }
    
    # Analyze using AI
    logger.info(f"🔍 Analyzing {len(pyq_data)} PYQs for frequently asked questions...")
    analysis = await analyze_frequently_asked_pyqs(pyq_data)
    
    if not analysis:
        return {
            "success": False,
            "message": "Failed to analyze PYQs"
        }
    
    # Cache the analysis PERMANENTLY
    ai_cache = AICache(
        cache_key=cache_key,
        cache_type="frequent_pyqs",
        content=analysis,
        access_count=1
    )
    db.add(ai_cache)
    await db.commit()
    
    logger.info(f"✅ Analyzed and cached frequently asked PYQs for subject {subject_id}")
    return {
        "success": True,
        "analysis": analysis,
        "from_cache": False
    }


@api_router.delete("/pyq/{pyq_id}")
async def delete_pyq(
    pyq_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Delete PYQ and clean up S3 files"""
    result = await db.execute(select(PreviousYearPaper).where(PreviousYearPaper.id == pyq_id))
    pyq = result.scalars().first()
    
    if not pyq:
        raise HTTPException(status_code=404, detail="PYQ not found")
    
    # Store for cache invalidation and S3 cleanup
    subject_id = pyq.subject_id
    standard = pyq.standard
    year = pyq.year
    
    # Get subject for S3 cleanup
    subject_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = subject_result.scalars().first()
    
    # Clean up S3 files
    if subject:
        from app.services.storage_service import delete_pyq_from_s3
        
        try:
            await delete_pyq_from_s3(pyq.standard, subject.name, pyq.year, pyq.exam_name)
            logger.info(f"🗑️ Deleted PYQ S3 file: {pyq.exam_name} ({pyq.year})")
        except Exception as e:
            logger.error(f"⚠️ S3 cleanup failed: {e}")
            # Continue with DB deletion
    
    # Delete PYQ
    await db.delete(pyq)
    
    # Invalidate frequent PYQs cache
    cache_key = f"frequent_pyqs:{subject_id}:{standard}"
    result = await db.execute(select(AICache).where(AICache.cache_key == cache_key))
    cache = result.scalars().first()
    if cache:
        await db.delete(cache)
        logger.info("🗑️ Invalidated frequent PYQs cache")
    
    await db.commit()
    
    return {"message": "PYQ deleted successfully"}


@api_router.post("/student/generate-content")
async def generate_student_content(request: GenerateContentRequest, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        result = await db.execute(select(Subject).where(Subject.id == request.subject_id))
        subject = result.scalars().first()
        if not subject:
            return {"content": None, "error": "Subject not found", "success": False}
        
        result = await db.execute(select(Chapter).where(Chapter.id == request.chapter_id))
        chapter = result.scalars().first()
        if not chapter:
            return {"content": None, "error": "Chapter not found", "success": False}
        
        # Get student's class/standard for age-appropriate content
        student_standard = 5  # Default
        # Load student profile from database
        student_profile_result = await db.execute(
            select(StudentProfile).where(StudentProfile.user_id == user.id)
        )
        student_profile = student_profile_result.scalars().first()
        if student_profile:
            student_standard = student_profile.standard or 5
        
        content_results = await db.execute(
            select(Content).where(
                Content.chapter_id == chapter.id
            )
        )
        contents = content_results.scalars().all()
        
        # Load textbook content for non-doubt features
        content_text = ""
        if request.feature_type != "doubt":
            for content in contents:
                if content.ocr_text:
                    content_text += content.ocr_text + "\n\n"
        
        # For doubt answering, ONLY load revision notes (not textbook content)
        revision_notes_context = ""
        chapter_topics = []
        if request.feature_type == "doubt":
            try:
                # Load revision notes from S3 for context and guardrails
                from app.services.storage_service import fetch_ai_content_from_s3
                
                # Get chapter details to fetch from correct S3 path
                revision_data = await fetch_ai_content_from_s3(
                    standard=subject.standard,
                    subject=subject.name,
                    chapter=chapter.name,
                    tool='revision_notes',
                    school_name=subject.school_name
                )
                
                if revision_data and 'key_concepts' in revision_data:
                    # Extract topics covered in this chapter
                    chapter_topics = [concept.get('title', '') for concept in revision_data.get('key_concepts', [])]
                    
                    # Extract conceptual guidelines from revision notes
                    concepts_text = "\n".join([
                        f"• {concept.get('title', '')}: {concept.get('explanation', '')[:200]}"
                        for concept in revision_data.get('key_concepts', [])[:5]  # Top 5 concepts
                    ])
                    
                    # Get chapter summary
                    chapter_summary = revision_data.get('chapter_summary', '')
                    
                    revision_notes_context = f"""Chapter Context:
{chapter_summary}

Key Topics Covered:
{concepts_text}
"""
                    logger.info(f"✅ Using revision notes for doubt (Topics: {', '.join(chapter_topics[:3])})")
                    logger.info(f"✅ Loaded {len(revision_notes_context)} chars from S3: {subject.school_name or 'default'}/ai_content/class{subject.standard}/{subject.name}/{chapter.name}/revision_notes.json")
                else:
                    logger.warning(f"⚠️ No revision notes found for chapter {chapter.id} at standard={subject.standard}, subject={subject.name}, chapter={chapter.name}, school={subject.school_name}")
            except Exception as e:
                logger.error(f"⚠️ Error loading revision notes: {e}", exc_info=True)
        
        # For non-doubt features, require textbook content
        if not content_text and request.feature_type != "doubt":
            return {
                "content": None,
                "error": f"No textbook content uploaded for this chapter. Please ask your teacher to upload the {request.content_source.upper()} textbook PDF first.",
                "success": False
            }
        
        result_content = None
        
        if request.feature_type == "revision_notes":
            result_content = await generate_revision_notes(
                subject.name, chapter.name, content_text, request.language, request.content_source, student_standard
            )
        elif request.feature_type == "flashcards":
            count = request.additional_params.get('count', 15) if request.additional_params else 15
            result_content = await generate_flashcards(
                subject.name, chapter.name, content_text, request.language, request.content_source, count, student_standard
            )
        elif request.feature_type == "quiz":
            result_content = await generate_practice_quiz(
                subject.name, chapter.name, content_text, request.language, request.content_source, student_standard
            )
        elif request.feature_type == "important":
            result_content = await generate_important_topics(
                subject.name, chapter.name, content_text, request.language, request.content_source
            )
        elif request.feature_type == "explain":
            concept = request.additional_params.get('concept', '') if request.additional_params else ''
            result_content = await explain_concept(
                subject.name, chapter.name, concept, content_text, request.language, request.content_source
            )
        elif request.feature_type == "doubt":
            question = request.additional_params.get('question', '') if request.additional_params else ''
            conversation_history = request.additional_params.get('conversation_history', []) if request.additional_params else []
            logger.info(f"🤔 Processing doubt: {question[:100]}")
            
            # Pass ONLY revision notes context and topics (not textbook, not chapter name)
            result_content = await answer_doubt(
                subject=subject.name,
                chapter_title=chapter.name,
                question=question,
                revision_notes_context=revision_notes_context,
                chapter_topics=chapter_topics,
                language=request.language,
                conversation_history=conversation_history,
                standard=student_standard
            )
            
            # Log what context was used
            if revision_notes_context:
                logger.info(f"✅ Doubt answered with {len(revision_notes_context)} chars of context")
            else:
                logger.warning(f"⚠️ Doubt answered without revision notes context")
            
            logger.info(f"✅ Doubt answer completed: {result_content is not None}")
        else:
            return {"content": None, "error": f"Feature '{request.feature_type}' not supported", "success": False}
        
        if result_content is None:
            logger.error("❌ AI service returned None for doubt")
            return {
                "content": None,
                "error": "AI service temporarily unavailable. Please try again in a few minutes.",
                "success": False
            }
        
        return {"content": result_content, "error": None, "success": True}
    
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return {
            "content": None,
            "error": "An unexpected error occurred. Please try again.",
            "success": False
        }

# Flashcard rating storage (per user, per chapter)
@api_router.post("/student/flashcard-rating")
async def save_flashcard_rating(
    chapter_id: str = Form(...),
    flashcard_id: int = Form(...),
    rating: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Save student's flashcard difficulty rating"""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return {"success": False, "error": "Cache not available"}
        key = f"flashcard_ratings:{user.id}:{chapter_id}"
        ratings = redis_client.get(key)
        ratings_dict = json.loads(ratings) if ratings else {}
        ratings_dict[str(flashcard_id)] = rating
        redis_client.setex(key, 604800, json.dumps(ratings_dict))  # 7 days TTL
        return {"success": True, "message": "Rating saved"}
    except Exception as e:
        logger.error(f"Error saving flashcard rating: {e}")
        return {"success": False, "error": str(e)}

@api_router.get("/student/flashcard-ratings/{chapter_id}")
async def get_flashcard_ratings(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get student's flashcard ratings for a chapter"""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return {"ratings": {}}
        key = f"flashcard_ratings:{user.id}:{chapter_id}"
        ratings = redis_client.get(key)
        return {"ratings": json.loads(ratings) if ratings else {}}
    except Exception as e:
        logger.error(f"Error getting flashcard ratings: {e}")
        return {"ratings": {}}

@api_router.post("/student/quiz-explanation")
async def get_quiz_explanation_endpoint(
    question: str = Form(...),
    student_answer: str = Form(...),
    correct_answer: str = Form(...),
    subject: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get AI explanation for wrong quiz answer"""
    from app.services.ai_service import get_quiz_explanation
    explanation = await get_quiz_explanation(question, student_answer, correct_answer, subject)
    return {"explanation": explanation}

@api_router.post("/student/submit-quiz")
async def submit_quiz_attempt(
    chapter_id: str = Form(...),
    quiz_id: int = Form(...),
    score: int = Form(...),
    total_questions: int = Form(...),
    answers: str = Form(...),  # JSON string
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Save quiz attempt and score"""
    try:
        redis_client = await get_redis()
        if redis_client:
            # Store quiz attempt
            attempt_key = f"quiz_attempts:{user.id}:{chapter_id}:{quiz_id}"
            attempt_data = {
                "score": score,
                "total": total_questions,
                "percentage": round((score/total_questions) * 100, 1),
                "answers": json.loads(answers) if answers else [],
                "attempted_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
            }
            redis_client.setex(attempt_key, 2592000, json.dumps(attempt_data))  # 30 days TTL
            
            # Store in chapter performance summary
            performance_key = f"quiz_performance:{user.id}:{chapter_id}"
            performance = redis_client.get(performance_key)
            performance_dict = json.loads(performance) if performance else {}
            
            quiz_key = f"quiz_{quiz_id}"
            performance_dict[quiz_key] = {
                "score": score,
                "total": total_questions,
                "percentage": round((score/total_questions) * 100, 1),
                "last_attempted": __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
            }
            
            redis_client.setex(performance_key, 2592000, json.dumps(performance_dict))  # 30 days TTL
            
        return {"success": True, "message": "Quiz attempt saved", "percentage": round((score/total_questions) * 100, 1)}
    except Exception as e:
        logger.error(f"Error saving quiz attempt: {e}")
        return {"success": False, "error": str(e)}

@api_router.get("/student/quiz-performance/{chapter_id}")
async def get_quiz_performance(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get student's quiz performance for a chapter"""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return {"performance": {}}
            
        performance_key = f"quiz_performance:{user.id}:{chapter_id}"
        performance = redis_client.get(performance_key)
        
        if performance:
            return {"performance": json.loads(performance)}
        return {"performance": {}}
    except Exception as e:
        logger.error(f"Error getting quiz performance: {e}")
        return {"performance": {}}


@api_router.get("/student/classification/{subject_id}")
async def get_student_classification(
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get student's performance classification for a subject"""
    try:
        # Get student performance for the subject
        result = await db.execute(
            select(StudentPerformance).where(
                and_(
                    StudentPerformance.student_id == user.id,
                    StudentPerformance.subject_id == subject_id
                )
            )
        )
        performance = result.scalars().first()
        
        if performance and performance.classification:
            return {"classification": performance.classification}
        
        # Default to 'average' if no performance data
        return {"classification": "average"}
    except Exception as e:
        logger.error(f"Error getting student classification: {e}")
        return {"classification": "average"}


# Translation Routes
@api_router.post("/translate")
async def translate_text_endpoint(
    text: str = Form(...),
    to_language: str = Form(default="gujarati"),
    context: str = Form(default="general"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Translate text to target language (cached)"""
    from app.services.translation_service import translate_text
    
    try:
        redis_client = await get_redis()
        translated = await translate_text(
            text=text,
            from_language="english",
            to_language=to_language,
            context=context,
            redis_client=redis_client
        )
        
        if translated:
            return {"success": True, "translated_text": translated, "original_text": text}
        else:
            return {"success": False, "error": "Translation failed", "original_text": text}
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return {"success": False, "error": str(e), "original_text": text}

@api_router.post("/translate/content")
async def translate_content_endpoint(
    content: str = Form(...),  # JSON string
    to_language: str = Form(default="gujarati"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Translate structured content (e.g., AI-generated notes, flashcards, quizzes)"""
    from app.services.translation_service import translate_content
    
    try:
        redis_client = await get_redis()
        content_dict = json.loads(content)
        
        translated = await translate_content(
            content=content_dict,
            from_language="english",
            to_language=to_language,
            redis_client=redis_client
        )
        
        if translated:
            return {"success": True, "translated_content": translated}
        else:
            return {"success": False, "error": "Translation failed"}
    except Exception as e:
        logger.error(f"Content translation error: {e}")
        return {"success": False, "error": str(e)}

@api_router.post("/translate/batch")
async def translate_batch_endpoint(
    texts: str = Form(...),  # JSON array of strings
    to_language: str = Form(default="gujarati"),
    context: str = Form(default="ui"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Translate multiple UI texts in batch"""
    from app.services.translation_service import translate_batch
    
    try:
        redis_client = await get_redis()
        texts_list = json.loads(texts)
        
        translations = await translate_batch(
            texts=texts_list,
            from_language="english",
            to_language=to_language,
            context=context,
            redis_client=redis_client
        )
        
        return {"success": True, "translations": translations}
    except Exception as e:
        logger.error(f"Batch translation error: {e}")
        return {"success": False, "error": str(e)}

@api_router.get("/")
async def api_root():
    return {"message": "StudyBuddy API", "status": "running"}


# =============================================================================
# HOMEWORK ENDPOINTS
# =============================================================================

class CreateHomeworkRequest(BaseModel):
    subject_id: str
    standard: int
    title: str

@api_router.post("/homework")
async def create_homework(
    subject_id: str = Form(...),
    standard: int = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    model_answers_file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Teacher uploads homework PDF - uses unified extraction pipeline"""
    # WRAPPED IN TRY-EXCEPT BLOCK FOR DEBUGGING 520 ERRORS
    try:
        logger.info(f"POST /api/homework received. Subject: {subject_id}, Std: {standard}, Title: {title}")
        logger.info(f"Files received - Homework: {file.filename if file else 'None'}, Model Answers: {model_answers_file.filename if model_answers_file else 'None'}")

        from datetime import timedelta
        from sqlalchemy.exc import IntegrityError
        from app.services.storage_service import s3_client, S3_BUCKET, upload_homework_questions_to_s3, normalize_title, sanitize_component
        from app.services.background_extraction import start_extraction_task, ExtractionStatus
        from app.models.database import AsyncSessionLocal
        import uuid
        
        # Verify subject
        result = await db.execute(select(Subject).where(Subject.id == subject_id))
        subject = result.scalars().first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        
        # Get teacher's school
        teacher_school = await get_user_school(user, db)
        if not teacher_school:
            raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
        
        try:
            normalized_title = normalize_title(title)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid title: {e}")
        
        homework_id = str(uuid.uuid4())
        
        logger.info(f"Reading homework PDF bytes for ID: {homework_id}")
        file_content = await file.read()
        logger.info(f"Read {len(file_content)} bytes from homework PDF")
        
        # NEW: School-based S3 structure
        school_folder = sanitize_school_name(teacher_school)
        s3_folder_key = f"{school_folder}/homework/class{standard}/{sanitize_component(subject.name)}/{homework_id}"
        homework_s3_key = f"{s3_folder_key}/homework.pdf"
        
        logger.info(f"Uploading homework to S3: {homework_s3_key}")
        try:
            s3_client.put_object(Bucket=S3_BUCKET, Key=homework_s3_key, Body=file_content, ContentType='application/pdf')
        except Exception as e:
            logger.error(f"Homework upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload homework: {str(e)}")
        
        model_answers_key = None
        model_answers_filename = None
        model_answers_content = None
        
        if model_answers_file and model_answers_file.filename:
            logger.info(f"Reading model answers PDF bytes")
            model_answers_content = await model_answers_file.read()
            logger.info(f"Read {len(model_answers_content)} bytes from model answers PDF")
            
            model_answers_key = f"{s3_folder_key}/model_answers.pdf"
            try:
                logger.info(f"Uploading model answers to S3: {model_answers_key}")
                s3_client.put_object(Bucket=S3_BUCKET, Key=model_answers_key, Body=model_answers_content, ContentType='application/pdf')
                model_answers_filename = model_answers_file.filename
            except Exception as e:
                logger.error(f"Model answers upload failed: {e}")
                s3_client.delete_object(Bucket=S3_BUCKET, Key=homework_s3_key)
                raise HTTPException(status_code=500, detail="Failed to upload model answers")
        
        expiry_date = datetime.now(timezone.utc) + timedelta(days=10)
        
        logger.info("Creating DB record")
        homework = Homework(
            id=homework_id,
            subject_id=subject_id,
            standard=standard,
            title=title,
            normalized_title=normalized_title,
            file_name=file.filename,
            file_path=homework_s3_key,
            s3_folder_key=s3_folder_key,
            school_name=teacher_school,  # SET SCHOOL
            model_answers_file=model_answers_filename,
            model_answers_path=model_answers_key,
            expiry_date=expiry_date,
            created_by=user.id,
            extraction_status=ExtractionStatus.PENDING,
            extraction_progress=0,
            questions_extracted_count=0
        )
        
        try:
            db.add(homework)
            await db.commit()
            await db.refresh(homework)
            logger.info(f"DB record created: {homework.id}")
        except IntegrityError:
            await db.rollback()
            logger.warning("DB IntegrityError - duplicate title?")
            s3_client.delete_object(Bucket=S3_BUCKET, Key=homework_s3_key)
            if model_answers_key:
                s3_client.delete_object(Bucket=S3_BUCKET, Key=model_answers_key)
            raise HTTPException(status_code=409, detail=f"Homework '{title}' already exists")
        except Exception as e:
            logger.error(f"DB Commit Error: {e}")
            raise
        
        async def s3_upload_wrapper(questions):
            # Get the homework to fetch s3_folder_key
            hw_result = await db.execute(select(Homework).where(Homework.id == homework_id))
            hw = hw_result.scalars().first()
            return await upload_homework_questions_to_s3(questions, homework_id, s3_folder_key=hw.s3_folder_key if hw else None)
        
        async def s3_solutions_upload_wrapper(solutions):
            from app.services.storage_service import upload_homework_solutions_to_s3
            # Get the homework to fetch s3_folder_key
            hw_result = await db.execute(select(Homework).where(Homework.id == homework_id))
            hw = hw_result.scalars().first()
            return await upload_homework_solutions_to_s3(solutions, homework_id, s3_folder_key=hw.s3_folder_key if hw else None)
        
        logger.info("Starting background extraction task")
        try:
            # We must use start_extraction_task which calls background_extract_test (which we renamed to extract_with_gemini logic inside)
            # Ensure imports are correct in background_extraction.py
            await start_extraction_task(
                test_id=homework_id,
                test_pdf_bytes=file_content,
                model_answers_bytes=model_answers_content,
                standard=standard,
                subject_name=subject.name,
                db_session_factory=AsyncSessionLocal,
                s3_upload_func=s3_upload_wrapper,
                s3_solutions_upload_func=s3_solutions_upload_wrapper if model_answers_content else None,
                content_type='homework'
            )
            logger.info("Background task queued successfully")
        except Exception as e:
            logger.error(f"Failed to start extraction: {e}")
            # Don't fail the request, just mark failed
            homework.extraction_status = 'failed'
            homework.extraction_error = str(e)
            await db.commit()
        
        response_data = {
            "message": "Homework uploaded. Extraction in progress.",
            "status": "processing",
            "homework_id": homework.id,
            "title": homework.title,
            "extraction_status": homework.extraction_status,
            "extraction_stage": homework.extraction_stage or 'UPLOADED',
            "extraction_progress": homework.extraction_progress,
            "poll_url": f"/api/homework/{homework_id}/extraction-status"
        }
        logger.info(f"Returning response: {response_data}")
        return response_data

    except Exception as e:
        logger.exception("HOMEWORK UPLOAD CRASHED")
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")



@api_router.get("/homework/{homework_id}/extraction-status")
async def get_homework_extraction_status(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Poll extraction status for homework"""
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    from datetime import datetime, timezone
    elapsed_seconds = 0
    if homework.extraction_started_at:
        started = homework.extraction_started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed_seconds = int((datetime.now(timezone.utc) - started).total_seconds())
    
    should_poll = homework.extraction_status == 'processing'
    is_stuck = elapsed_seconds > 180 and homework.extraction_status == 'processing'
    
    return {
        "content_id": homework_id,
        "content_type": "homework",
        "homework_id": homework_id,
        "extraction_stage": homework.extraction_stage or 'UPLOADED',
        "extraction_status": homework.extraction_status,
        "extraction_progress": homework.extraction_progress or 0,
        "extraction_stage_message": homework.extraction_stage_message or "Processing...",
        "elapsed_seconds": elapsed_seconds,
        "can_retry": homework.extraction_status in ['failed', 'timeout'] or is_stuck,
        "should_poll": should_poll and not is_stuck,
        "is_stuck": is_stuck,
        "error": homework.extraction_error,
        "questions_extracted_count": homework.questions_extracted_count,
        "extraction_mismatch": False
    }


@api_router.post("/homework/{homework_id}/retry-extraction")
async def retry_homework_extraction(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Retry failed homework extraction"""
    from app.services.storage_service import s3_client, S3_BUCKET
    from app.services.background_extraction import start_extraction_task
    from app.models.database import AsyncSessionLocal
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    if homework.extraction_status == 'processing':
        raise HTTPException(status_code=409, detail="Extraction already in progress")
    
    # Fetch PDFs from S3
    try:
        homework_pdf_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=homework.file_path)
        homework_pdf_bytes = homework_pdf_obj['Body'].read()
        
        model_answers_bytes = None
        if homework.model_answers_path:
            model_answers_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=homework.model_answers_path)
            model_answers_bytes = model_answers_obj['Body'].read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch PDFs from S3: {e}")
    
    # Get subject
    subject_result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Reset extraction status
    homework.extraction_status = 'pending'
    homework.extraction_stage = 'UPLOADED'
    homework.extraction_progress = 0
    homework.extraction_error = None
    homework.extraction_started_at = None
    homework.extraction_completed_at = None
    await db.commit()
    
    # Restart extraction
    async def s3_upload_wrapper(questions):
        from app.services.storage_service import upload_homework_questions_to_s3
        return await upload_homework_questions_to_s3(questions, homework_id, homework.standard, subject.name)
    
    async def s3_solutions_upload_wrapper(solutions):
        from app.services.storage_service import upload_homework_solutions_to_s3
        return await upload_homework_solutions_to_s3(solutions, homework_id, homework.standard, subject.name)
    
    await start_extraction_task(
        test_id=homework_id,
        test_pdf_bytes=homework_pdf_bytes,
        model_answers_bytes=model_answers_bytes,
        standard=homework.standard,
        subject_name=subject.name,
        db_session_factory=AsyncSessionLocal,
        s3_upload_func=s3_upload_wrapper,
        s3_solutions_upload_func=s3_solutions_upload_wrapper if model_answers_bytes else None,
        content_type='homework'
    )
    
    return {"message": "Extraction restarted", "status": "processing"}

@api_router.get("/homework")
async def list_homework(
    standard: Optional[int] = None,
    subject_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    List homework with verified extraction counts from S3 (if completed).
    Ensures teacher dashboard matches reality.
    
    School-Based Multi-Tenancy:
    - Students only see homework from their school
    - Teachers see homework from their school
    - Admins see all homework
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    import json
    
    # Get the user's school for filtering
    user_school = await get_user_school(user, db)
    
    query = select(Homework).where(Homework.expiry_date > datetime.now(timezone.utc))
    
    # School-based filtering
    if user_school and user.role in ['student', 'teacher']:
        query = query.where(Homework.school_name == user_school)
    # Admin sees all homework (no additional filter)
    
    if standard:
        query = query.where(Homework.standard == standard)
    if subject_id:
        query = query.where(Homework.subject_id == subject_id)
    
    query = query.order_by(Homework.created_at.desc())
    
    result = await db.execute(query)
    homework_list = result.scalars().all()
    
    response_list = []
    
    for hw in homework_list:
        hw_data = {
            "id": str(hw.id),
            "subject_id": str(hw.subject_id),
            "standard": hw.standard,
            "title": hw.title,
            "file_name": hw.file_name,
            "file_path": hw.file_path,
            "upload_date": hw.upload_date.isoformat(),
            "expiry_date": hw.expiry_date.isoformat(),
            "extraction_status": hw.extraction_status,
            "extraction_stage": hw.extraction_stage,
            "extraction_error": hw.extraction_error,
            "questions_extracted_count": hw.questions_extracted_count or 0,
            "solutions_extracted_count": getattr(hw, 'solutions_extracted_count', 0) or 0,
            "has_model_answers": bool(hw.model_answers_path),
            "extraction_mismatch": False
        }
        
        # Verify completed items against S3 if user requested strict check
        if hw.extraction_status == 'completed':
            try:
                # Check Questions
                q_key = f"{hw.s3_folder_key}/questions.json"
                q_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=q_key)
                q_data = json.loads(q_obj['Body'].read())
                real_q_count = len(q_data)
                
                # Update if different
                if real_q_count != hw_data['questions_extracted_count']:
                    hw_data['extraction_mismatch'] = True
                    hw_data['questions_extracted_count'] = real_q_count
                
                # Check Solutions (if expected)
                if hw.model_answers_path:
                    s_key = f"{hw.s3_folder_key}/solutions.json"
                    try:
                        s_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=s_key)
                        s_data = json.loads(s_obj['Body'].read())
                        real_s_count = len(s_data)
                        
                        # Compare with safe integer (0 if None)
                        db_s_count = hw_data.get('solutions_extracted_count') or 0
                        
                        if real_s_count != db_s_count:
                            hw_data['extraction_mismatch'] = True
                            hw_data['solutions_extracted_count'] = real_s_count
                    except Exception:
                        # Missing solutions.json when model answers exist
                        hw_data['extraction_mismatch'] = True
                        hw_data['solutions_extracted_count'] = 0
                        
            except Exception as e:
                logger.warning(f"S3 verification failed for list_homework item {hw.id}: {e}")
                # If S3 read fails, rely on DB but maybe flag?
                # Keeping as-is for now (trust DB fallback)
                pass
        
        response_list.append(hw_data)
            
    return response_list


@api_router.post("/homework/{homework_id}/get-solution")
async def get_homework_solution(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get AI-generated solution for homework (cached for 10 days)"""
    from datetime import timedelta
    from app.services.ai_service import generate_homework_solution
    
    # Get homework
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Check if expired (handle both timezone-aware and naive datetimes)
    now = datetime.now(timezone.utc)
    expiry = homework.expiry_date
    if expiry.tzinfo is None:
        # If stored datetime is naive, make it aware
        expiry = expiry.replace(tzinfo=timezone.utc)
    
    if expiry < now:
        raise HTTPException(status_code=410, detail="Homework has expired")
    
    # Check if solution already cached
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(HomeworkSolution).where(HomeworkSolution.homework_id == homework_id)
    )
    cached_solution = result.scalars().first()
    
    # Check if cache is still valid
    if cached_solution:
        cache_expiry = cached_solution.cache_expiry
        if cache_expiry.tzinfo is None:
            cache_expiry = cache_expiry.replace(tzinfo=timezone.utc)
        
        if cache_expiry > now:
            # Cache is valid, return it
            cached_solution.access_count += 1
            await db.commit()
            
            return {
                "homework_id": homework_id,
                "title": homework.title,
                "solution": cached_solution.solution,
                "cached": True,
                "generated_at": cached_solution.created_at.isoformat()
            }
    
    # Generate new solution
    if not homework.ocr_text:
        raise HTTPException(status_code=400, detail="Homework text not extracted. Please try again later.")
    
    solution = await generate_homework_solution(
        homework_text=homework.ocr_text,
        title=homework.title,
        standard=homework.standard
    )
    
    if not solution:
        raise HTTPException(status_code=500, detail="Failed to generate solution")
    
    # Cache solution for 10 days
    cache_expiry = datetime.now(timezone.utc) + timedelta(days=10)
    hw_solution = HomeworkSolution(
        homework_id=homework_id,
        solution=solution,
        cache_expiry=cache_expiry,
        access_count=1
    )
    db.add(hw_solution)
    await db.commit()
    
    return {
        "homework_id": homework_id,
        "title": homework.title,
        "solution": solution,
        "cached": False,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@api_router.delete("/homework/{homework_id}")
async def delete_homework(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """
    Delete homework - FIXED VERSION
    Deletes entire S3 folder and DB record
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    logger.info(f"[DELETE_HOMEWORK] Deleting homework ID: {homework_id}")
    logger.info(f"[DELETE_HOMEWORK] S3 folder: {homework.s3_folder_key}")
    
    # Delete entire S3 folder
    if homework.s3_folder_key:
        try:
            # List all objects in the folder
            response = s3_client.list_objects_v2(
                Bucket=S3_BUCKET,
                Prefix=f"{homework.s3_folder_key}/"
            )
            
            if 'Contents' in response and len(response['Contents']) > 0:
                objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
                
                # Delete all objects
                s3_client.delete_objects(
                    Bucket=S3_BUCKET,
                    Delete={'Objects': objects_to_delete}
                )
                
                logger.info(f"[DELETE_HOMEWORK] ✅ Deleted {len(objects_to_delete)} S3 objects")
            else:
                logger.info(f"[DELETE_HOMEWORK] No S3 objects found")
                
        except Exception as e:
            logger.error(f"[DELETE_HOMEWORK] ❌ S3 deletion failed: {e}")
            # Continue to delete DB record even if S3 fails
    
    # Delete from database
    await db.delete(homework)
    await db.commit()
    
    logger.info(f"[DELETE_HOMEWORK] ✅ Homework deleted from DB")
    
    return {"message": "Homework deleted successfully"}


@api_router.get("/homework/{homework_id}/solutions")
async def get_homework_solutions(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get homework solutions JSON from S3.
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    if homework.s3_folder_key:
        s3_key = f"{homework.s3_folder_key}/solutions.json"
    else:
        result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
        subject = result.scalars().first()
        if not subject:
             raise HTTPException(status_code=404, detail="Subject not found")
        
        from app.services.storage_service import sanitize_component
        s3_key = f"homework/class{homework.standard}/{sanitize_component(subject.name)}/{homework.id}/solutions.json"
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = json.loads(response['Body'].read().decode('utf-8'))
        
        # Return in format expected by frontend
        return {
            "solutions": content if isinstance(content, list) else content.get("solutions", []),
            "homework_id": homework_id
        }
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Solutions not available")
    except Exception as e:
        logger.error(f"Error fetching solutions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch solutions")


@api_router.get("/homework/{homework_id}/questions-v2", response_model=None)
async def get_homework_questions_v2(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    FIXED VERSION - Get homework questions JSON from S3.
    Ensures student frontend can fetch questions using the correct S3 path structure.
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    
    logger.info(f"[QUESTIONS_API_V2] Fetching questions for homework: {homework_id}")
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Use deterministic path structure: homework/class{std}/{subject}/{id}/questions.json
    # Fallback to DB s3_folder_key if available, otherwise reconstruct
    if homework.s3_folder_key:
        s3_key = f"{homework.s3_folder_key}/questions.json"
    else:
        # Reconstruction logic (fallback)
        result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
        subject = result.scalars().first()
        if not subject:
             raise HTTPException(status_code=404, detail="Subject not found")
        
        from app.services.storage_service import sanitize_component
        s3_key = f"homework/class{homework.standard}/{sanitize_component(subject.name)}/{homework.id}/questions.json"
    
    logger.info(f"[QUESTIONS_API_V2] S3 Key: {s3_key}")
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = json.loads(response['Body'].read().decode('utf-8'))
        
        logger.info(f"[QUESTIONS_API_V2] Retrieved {len(content) if isinstance(content, list) else 'N/A'} questions from S3")
        
        # Return in format expected by frontend
        result_data = {
            "questions_extracted": True,
            "questions": content if isinstance(content, list) else content.get("questions", []),
            "homework_id": homework_id
        }
        logger.info(f"[QUESTIONS_API_V2] Returning object with {len(result_data['questions'])} questions")
        return result_data
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Questions not found in S3: {s3_key}")
        raise HTTPException(status_code=404, detail="Questions not available")
    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch questions")


@api_router.get("/homework/{homework_id}/questions", response_model=None)
async def get_homework_questions(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    FIXED VERSION - Get homework questions JSON from S3.
    Ensures student frontend can fetch questions using the correct S3 path structure.
    """
    from app.services.storage_service import s3_client, S3_BUCKET
    
    logger.info(f"[QUESTIONS_API_V2] Fetching questions for homework: {homework_id}")
    
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Use deterministic path structure: homework/class{std}/{subject}/{id}/questions.json
    # Fallback to DB s3_folder_key if available, otherwise reconstruct
    if homework.s3_folder_key:
        s3_key = f"{homework.s3_folder_key}/questions.json"
    else:
        # Reconstruction logic (fallback)
        result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
        subject = result.scalars().first()
        if not subject:
             raise HTTPException(status_code=404, detail="Subject not found")
        
        from app.services.storage_service import sanitize_component
        s3_key = f"homework/class{homework.standard}/{sanitize_component(subject.name)}/{homework.id}/questions.json"
    
    logger.info(f"[QUESTIONS_API_V2] S3 Key: {s3_key}")
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_key)
        content = json.loads(response['Body'].read().decode('utf-8'))
        
        logger.info(f"[QUESTIONS_API_V2] Retrieved {len(content) if isinstance(content, list) else 'N/A'} questions from S3")
        
        # Return in format expected by frontend
        result_data = {
            "questions_extracted": True,
            "questions": content if isinstance(content, list) else content.get("questions", []),
            "homework_id": homework_id
        }
        logger.info(f"[QUESTIONS_API_V2] Returning object with {len(result_data['questions'])} questions")
        return result_data
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Questions not found in S3: {s3_key}")
        raise HTTPException(status_code=404, detail="Questions not available")
    except Exception as e:
        logger.error(f"Error fetching questions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch questions")


@api_router.post("/homework/{homework_id}/evaluate-answer")
async def evaluate_homework_answer(
    homework_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Evaluate student's answer using free LLM"""
    from app.services.ai_service import evaluate_student_answer
    
    question_number = request.get('question_number', 1)
    question_text = request.get('question_text')
    student_answer = request.get('student_answer')
    model_answer = request.get('model_answer')
    
    if not question_text or not student_answer:
        raise HTTPException(status_code=400, detail="question_text and student_answer required")
    
    # Validate word count (max 25 words)
    word_count = len(student_answer.split())
    if word_count > 25:
        return {
            "error": True,
            "message": f"Answer too long! Please keep it under 25 words. (Current: {word_count} words)"
        }
    
    # Evaluate answer
    evaluation = await evaluate_student_answer(
        question=question_text,
        student_answer=student_answer,
        model_answer=model_answer,
        question_number=question_number
    )
    
    return {
        "evaluation": evaluation,
        "question_number": question_number
    }


@api_router.post("/homework/{homework_id}/help")
async def get_homework_help(
    homework_id: str,
    request: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get AI help for a homework question"""
    from app.services.ai_service import help_with_question
    
    question_text = request.get('question_text')
    model_answer = request.get('model_answer')
    
    if not question_text:
        raise HTTPException(status_code=400, detail="question_text is required")
    
    # Get homework to know the standard (class level)
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    standard = homework.standard if homework else 5  # Default to class 5
    
    help_text = await help_with_question(
        question=question_text,
        model_answer=model_answer,
        standard=standard
    )
    
    return {
        "help_text": help_text
    }


@api_router.post("/homework/{homework_id}/submit")
async def submit_homework(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Submit homework (mark as submitted) - Submission record is PERMANENT for reports"""
    # Get student profile
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get homework details for permanent record
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Get subject name
    result = await db.execute(select(Subject).where(Subject.id == homework.subject_id))
    subject = result.scalars().first()
    
    # Check if already submitted
    result = await db.execute(
        select(HomeworkSubmission).where(
            HomeworkSubmission.homework_id == homework_id,
            HomeworkSubmission.student_id == str(user.id)
        )
    )
    submission = result.scalars().first()
    
    if submission:
        if submission.submitted:
            return {"message": "Already submitted", "submitted_at": submission.submitted_at.isoformat()}
        else:
            # Update to submitted
            submission.submitted = True
            submission.submitted_at = datetime.now(timezone.utc)
    else:
        # Create new submission with permanent metadata
        submission = HomeworkSubmission(
            homework_id=homework_id,
            homework_title=homework.title,
            subject_name=subject.name if subject else "Unknown",
            standard=homework.standard,
            student_id=str(user.id),
            roll_no=profile.roll_no,
            submitted=True,
            submitted_at=datetime.now(timezone.utc),
            homework_upload_date=homework.upload_date
        )
        db.add(submission)
    
    await db.commit()
    
    return {
        "message": "Homework submitted successfully",
        "submitted_at": submission.submitted_at.isoformat()
    }


@api_router.get("/homework/{homework_id}/submissions")
async def get_homework_submissions(
    homework_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Get submission status for homework (teacher only)"""
    # Get homework
    result = await db.execute(select(Homework).where(Homework.id == homework_id))
    homework = result.scalars().first()
    if not homework:
        raise HTTPException(status_code=404, detail="Homework not found")
    
    # Get all students in this standard
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.standard == homework.standard)
    )
    all_students = result.scalars().all()
    
    # Get submissions
    result = await db.execute(
        select(HomeworkSubmission).where(HomeworkSubmission.homework_id == homework_id)
    )
    submissions = result.scalars().all()
    
    # Create submission map
    submission_map = {sub.roll_no: sub for sub in submissions}
    
    # Build response
    submitted_students = []
    not_submitted_students = []
    
    for student in all_students:
        student_data = {
            "roll_no": student.roll_no,
            "name": student.name,
            "submitted_at": None
        }
        
        if student.roll_no in submission_map and submission_map[student.roll_no].submitted:
            student_data["submitted_at"] = submission_map[student.roll_no].submitted_at.isoformat()
            submitted_students.append(student_data)
        else:
            not_submitted_students.append(student_data)
    
    return {
        "homework_id": homework_id,
        "title": homework.title,
        "total_students": len(all_students),
        "submitted_count": len(submitted_students),
        "not_submitted_count": len(not_submitted_students),
        "submitted_students": submitted_students,
        "not_submitted_students": not_submitted_students
    }


@api_router.get("/teacher/students/count")
async def get_students_count(
    standard: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Get total number of students enrolled for a standard"""
    from sqlalchemy import func
    
    result = await db.execute(
        select(func.count(StudentProfile.id)).where(StudentProfile.standard == standard)
    )
    count = result.scalar()
    
    return {
        "standard": standard,
        "total_students": count or 0
    }


@api_router.get("/student/homework-history")
async def get_student_homework_history(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get student's homework submission history - PERMANENT RECORD for reports"""
    # Get student profile
    result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == str(user.id)))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    # Get all submissions for this student
    result = await db.execute(
        select(HomeworkSubmission)
        .where(HomeworkSubmission.student_id == str(user.id))
        .order_by(HomeworkSubmission.homework_upload_date.desc())
    )
    submissions = result.scalars().all()
    
    # Build response
    history = []
    for sub in submissions:
        history.append({
            "homework_id": sub.homework_id,
            "homework_title": sub.homework_title,
            "subject_name": sub.subject_name,
            "standard": sub.standard,
            "submitted": sub.submitted,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "upload_date": sub.homework_upload_date.isoformat()
        })
    
    # Calculate stats
    total_homework = len(submissions)
    submitted_count = sum(1 for sub in submissions if sub.submitted)
    completion_rate = (submitted_count / total_homework * 100) if total_homework > 0 else 0
    
    return {
        "student_name": profile.name,
        "roll_no": profile.roll_no,
        "total_homework_assigned": total_homework,
        "submitted_count": submitted_count,
        "not_submitted_count": total_homework - submitted_count,
        "completion_rate": round(completion_rate, 2),
        "history": history
    }


@api_router.get("/parent/student-homework-report/{roll_no}")
async def get_student_homework_report_for_parent(
    roll_no: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get student homework report for parents - Shows PERMANENT submission history"""
    # In future, add parent authentication check here
    
    # Get student profile
    result = await db.execute(select(StudentProfile).where(StudentProfile.roll_no == roll_no))
    profile = result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # Get all submissions for this student
    result = await db.execute(
        select(HomeworkSubmission)
        .where(HomeworkSubmission.roll_no == roll_no)
        .order_by(HomeworkSubmission.homework_upload_date.desc())
    )
    submissions = result.scalars().all()
    
    # Build response with detailed history
    history = []
    for sub in submissions:
        history.append({
            "homework_title": sub.homework_title,
            "subject_name": sub.subject_name,
            "standard": sub.standard,
            "submitted": sub.submitted,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "upload_date": sub.homework_upload_date.isoformat(),
            "days_to_submit": (sub.submitted_at - sub.homework_upload_date).days if sub.submitted_at else None
        })
    
    # Calculate comprehensive stats
    total_homework = len(submissions)
    submitted_count = sum(1 for sub in submissions if sub.submitted)
    on_time_count = sum(1 for sub in submissions if sub.submitted and (sub.submitted_at - sub.homework_upload_date).days <= 10)
    
    return {
        "student_name": profile.name,
        "roll_no": profile.roll_no,
        "standard": profile.standard,
        "school_name": profile.school_name,
        "total_homework_assigned": total_homework,
        "submitted_count": submitted_count,
        "not_submitted_count": total_homework - submitted_count,
        "completion_rate": round((submitted_count / total_homework * 100) if total_homework > 0 else 0, 2),
        "on_time_submission_rate": round((on_time_count / total_homework * 100) if total_homework > 0 else 0, 2),
        "history": history
    }


# =============================================================================
# TEST ENDPOINTS
# =============================================================================

@api_router.post("/tests")
async def create_test(
    subject_id: str = Form(...),
    standard: int = Form(...),
    title: str = Form(...),
    submission_deadline: str = Form(...),  # ISO format datetime
    duration_minutes: int = Form(...),
    file: UploadFile = File(...),
    model_answers: Optional[UploadFile] = File(None),
    marking_schema: Optional[UploadFile] = File(None),  # NEW: Marking schema PDF
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Create a new test with ASYNC background extraction.
    
    NEW: Supports optional marking schema upload for strict evaluation.
    
    Returns immediately with test_id and status='pending'.
    Frontend should poll /api/tests/{test_id}/extraction-status for progress.
    
    Pipeline:
    1. Upload PDFs to S3 (test paper, model answers, marking schema)
    2. Create test record (status='draft', extraction_status='pending')
    3. Start background extraction task
    4. Return immediately
    """
    try:
        # Log current user for debugging
        logger.info(f"[CREATE TEST] User authenticated: id={user.id}, role={user.role}, email={user.email or 'N/A'}")
        
        # Validate user object
        if not hasattr(user, 'id') or not hasattr(user, 'role'):
            logger.error(f"[CREATE TEST] Invalid user object: {user}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Invalid auth token",
                    "detail": "Authentication data is malformed",
                    "message": "Please log in again"
                }
            )
        
        # Teacher-only guard with specific error
        if user.role != 'teacher':
            logger.warning(f"[CREATE TEST] Non-teacher attempted to create test: user_id={user.id}, role={user.role}")
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Teacher account required",
                    "detail": "Only teachers can create tests",
                    "message": "You need a teacher account to create tests"
                }
            )
        
        logger.info(f"[CREATE TEST] Starting test creation: title='{title}', standard={standard}")
        
        from datetime import datetime as dt, timezone as tz
        from app.services.storage_service import (
            upload_test_pdf_to_s3, upload_test_questions_to_s3, upload_test_answers_to_s3
        )
        from app.services.background_extraction import start_extraction_task, ExtractionStatus
        
        # Get subject
        subject_result = await db.execute(select(Subject).where(Subject.id == subject_id))
        subject = subject_result.scalars().first()
        if not subject:
            logger.error(f"[CREATE TEST] Subject not found: {subject_id}")
            raise HTTPException(status_code=404, detail="Subject not found")
        
        logger.info(f"[CREATE TEST] Subject found: {subject.name}")
        
        # Get teacher's school
        teacher_school = await get_user_school(user, db)
        if not teacher_school:
            logger.error(f"[CREATE TEST] Teacher school not found for user: {user.id}")
            raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
        
        logger.info(f"[CREATE TEST] Teacher school: {teacher_school}")
        
        # Parse submission deadline
        try:
            if 'T' in submission_deadline and '+' not in submission_deadline and 'Z' not in submission_deadline:
                deadline = dt.fromisoformat(submission_deadline).replace(tzinfo=tz.utc)
            else:
                deadline_str = submission_deadline.replace('Z', '+00:00')
                deadline = dt.fromisoformat(deadline_str)
            logger.info(f"[CREATE TEST] Parsed deadline: {deadline}")
        except Exception as e:
            logger.error(f"[CREATE TEST] Error parsing deadline '{submission_deadline}': {e}")
            raise HTTPException(status_code=400, detail=f"Invalid deadline format: {submission_deadline}")
        
        # Compute expires_at (deadline + 5 minutes)
        from datetime import timedelta
        expires_at = deadline + timedelta(minutes=5)
        
        # Generate test ID
        import uuid
        test_id = str(uuid.uuid4())
        logger.info(f"[CREATE TEST] Generated test_id: {test_id}")
        
        # Read file content
        test_file_content = await file.read()
        logger.info(f"[CREATE TEST] Test PDF size: {len(test_file_content)} bytes")
        
        model_answers_content = None
        if model_answers:
            model_answers_content = await model_answers.read()
            logger.info(f"[CREATE TEST] Model answers PDF size: {len(model_answers_content)} bytes")
        
        # Upload test PDF to S3
        try:
            test_file_path, s3_folder_key = await upload_test_pdf_to_s3(
                test_file_content, test_id, standard, subject.name, teacher_school
            )
            logger.info(f"✅ [CREATE TEST] Test PDF uploaded: {test_file_path}")
        except Exception as e:
            logger.error(f"❌ [CREATE TEST] Test PDF upload failed: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to upload test PDF: {str(e)}")
        
        # Upload model answers if provided
        model_answers_path = None
        model_answers_filename = None
        if model_answers_content:
            model_answers_key = f"{s3_folder_key}/model_answers.pdf"
            try:
                from app.services.storage_service import s3_client, S3_BUCKET, ensure_s3_initialized
                ensure_s3_initialized()
                s3_client.put_object(
                    Bucket=S3_BUCKET,
                    Key=model_answers_key,
                    Body=model_answers_content,
                    ContentType='application/pdf'
                )
                model_answers_path = model_answers_key
                model_answers_filename = model_answers.filename
                logger.info(f"✅ [CREATE TEST] Model answers uploaded: {model_answers_path}")
            except Exception as e:
                logger.error(f"⚠️ [CREATE TEST] Model answers upload failed: {e}")
        
        # NEW: Upload marking schema if provided
        marking_schema_path = None
        marking_schema_filename = None
        marking_schema_text_path = None
        has_marking_schema = False
        
        if marking_schema:
            marking_schema_content = await marking_schema.read()
            if marking_schema_content:
                marking_schema_key = f"{s3_folder_key}/marking_schema.pdf"
                try:
                    from app.services.storage_service import s3_client, S3_BUCKET, ensure_s3_initialized
                    ensure_s3_initialized()
                    s3_client.put_object(
                        Bucket=S3_BUCKET,
                        Key=marking_schema_key,
                        Body=marking_schema_content,
                        ContentType='application/pdf'
                    )
                    marking_schema_path = marking_schema_key
                    marking_schema_filename = marking_schema.filename
                    has_marking_schema = True
                    logger.info(f"✅ [CREATE TEST] Marking schema uploaded: {marking_schema_path}")
                    
                    # Extract text from marking schema using Gemini
                    try:
                        from app.services.gpt4o_extraction import extract_text_from_pdf_with_gemini
                        schema_text = await extract_text_from_pdf_with_gemini(marking_schema_content)
                        
                        if schema_text:
                            # Save extracted text to S3
                            import json
                            schema_text_key = f"{s3_folder_key}/marking_schema_text.json"
                            schema_text_json = json.dumps({"text": schema_text})
                            s3_client.put_object(
                                Bucket=S3_BUCKET,
                                Key=schema_text_key,
                                Body=schema_text_json.encode('utf-8'),
                                ContentType='application/json'
                            )
                            marking_schema_text_path = schema_text_key
                            logger.info(f"✅ [CREATE TEST] Marking schema text extracted and saved: {schema_text_key}")
                    except Exception as e:
                        logger.error(f"⚠️ [CREATE TEST] Marking schema text extraction failed: {e}")
                        
                except Exception as e:
                    logger.error(f"⚠️ [CREATE TEST] Marking schema upload failed: {e}")
        
        # Create test record with status='draft' and extraction_status='pending'
        test = Test(
            id=test_id,
            subject_id=subject_id,
            standard=standard,
            title=title,
            file_name=file.filename,
            file_path=test_file_path,
            s3_folder_key=s3_folder_key,
            school_name=teacher_school,  # SET SCHOOL
            model_answers_file=model_answers_filename,
            model_answers_path=model_answers_path,
            marking_schema_file=marking_schema_filename,
            marking_schema_path=marking_schema_path,
            marking_schema_text_path=marking_schema_text_path,
            has_marking_schema=has_marking_schema,
            submission_deadline=deadline,
            expires_at=expires_at,
            duration_minutes=duration_minutes,
            created_by=user.id,
            extraction_status=ExtractionStatus.PENDING,
            extraction_progress=0,
            questions_extracted_count=0,
            status='draft'  # Will be activated after successful extraction
        )
        
        db.add(test)
        await db.commit()
        await db.refresh(test)
        
        logger.info(f"✅ [CREATE TEST] Test record created: {test.title} (ID: {test_id})")
        logger.info(f"📋 [CREATE TEST] Status: {test.status}, Extraction: {test.extraction_status}")
        
        # Start background extraction task (non-blocking)
        async def s3_upload_questions_wrapper(questions):
            """Wrapper to make S3 upload compatible with background task"""
            # Fetch test to get s3_folder_key
            test_result = await db.execute(select(Test).where(Test.id == test_id))
            test_obj = test_result.scalars().first()
            return await upload_test_questions_to_s3(questions, test_id, s3_folder_key=test_obj.s3_folder_key if test_obj else None)
        
        async def s3_upload_answers_wrapper(answers):
            """Wrapper to upload answers/solutions to S3"""
            # Fetch test to get s3_folder_key
            test_result = await db.execute(select(Test).where(Test.id == test_id))
            test_obj = test_result.scalars().first()
            return await upload_test_answers_to_s3(answers, test_id, s3_folder_key=test_obj.s3_folder_key if test_obj else None)
        
        try:
            from app.models.database import AsyncSessionLocal
            await start_extraction_task(
                test_id=test_id,
                test_pdf_bytes=test_file_content,
                model_answers_bytes=model_answers_content,
                standard=standard,
                subject_name=subject.name,
                db_session_factory=AsyncSessionLocal,
                s3_upload_func=s3_upload_questions_wrapper,
                s3_solutions_upload_func=s3_upload_answers_wrapper if model_answers_content else None,
                content_type='test'  # CRITICAL: Specify content_type for tests
            )
            logger.info(f"🚀 [CREATE TEST] Background extraction started for test: {test_id}")
        except Exception as e:
            logger.error(f"❌ [CREATE TEST] Failed to start background extraction: {e}")
            # Don't fail the request - mark extraction as failed in DB
            test.extraction_status = 'failed'
            test.extraction_error = f"Failed to start extraction: {str(e)}"
            await db.commit()
        
        logger.info(f"✅ [CREATE TEST] Test creation completed successfully: {test_id}")
        
        # CRITICAL: Test is NOT "created" until extraction completes
        # Return "processing" status, NOT "success"
        return {
            "message": "Upload successful. AI extraction in progress.",
            "status": "processing",  # NOT "success" - extraction still running
            "test_id": test.id,
            "title": test.title,
            "deadline": test.submission_deadline.isoformat(),
            "duration_minutes": test.duration_minutes,
            "extraction_status": test.extraction_status,
            "extraction_stage": test.extraction_stage or 'UPLOADED',
            "extraction_progress": test.extraction_progress,
            "test_status": test.status,  # 'draft' until extraction completes
            "poll_url": f"/api/tests/{test_id}/extraction-status",
            "ui_instruction": "Show progress modal. Poll extraction-status until completed."
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.exception(f"❌ CRITICAL [CREATE TEST]: Unexpected error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to create test",
                "detail": str(e),
                "message": "An error occurred while creating the test. Please try again."
            }
        )


@api_router.get("/tests/subject/{subject_id}/standard/{standard}")
async def list_tests(
    subject_id: str,
    standard: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    List all tests for a subject and standard.
    
    IMPORTANT: Excludes tests where:
    - status = 'deleted'
    - expires_at < now() (expired)
    
    No expired test should ever appear in UI.
    
    School-Based Multi-Tenancy:
    - Students only see tests from their school
    - Teachers see tests from their school
    - Admins see all tests
    """
    from datetime import datetime, timezone
    
    # Use naive datetime for comparison (SQLite stores naive)
    current_time_naive = datetime.utcnow()
    current_time = datetime.now(timezone.utc)
    
    # Get the user's school for filtering
    user_school = await get_user_school(user, db)
    
    # Fetch subject for S3 path construction
    subject_result = await db.execute(select(Subject).where(Subject.id == subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Build query - exclude deleted and expired tests
    # For STUDENTS: STRICT - ONLY show tests with extraction_stage = COMPLETED
    # Students must NEVER see tests still in processing
    if user.role == 'student':
        base_conditions = [
            Test.subject_id == subject_id,
            Test.standard == standard,
            Test.status == 'active',  # Must be active
            Test.extraction_stage == 'COMPLETED',  # ✅ ONLY completed extraction
            Test.extraction_status == 'completed',  # Double check
            Test.questions_extracted == True,  # Triple check
            Test.expires_at > current_time_naive  # Not expired
        ]
        
        # Add school filter for students
        if user_school:
            base_conditions.append(Test.school_name == user_school)
        else:
            # No school for this student, return empty list
            return {"tests": [], "total": 0}
        
        query = (
            select(Test)
            .where(*base_conditions)
            .order_by(Test.upload_date.desc())
        )
    else:
        # For TEACHERS: Show tests from their school
        # For ADMINS: Show all tests
        base_conditions = [
            Test.subject_id == subject_id,
            Test.standard == standard,
            Test.status != 'deleted',
            Test.expires_at > current_time_naive  # Not expired
        ]
        
        if user.role == 'teacher' and user_school:
            base_conditions.append(Test.school_name == user_school)
        
        query = (
            select(Test)
            .where(*base_conditions)
            .order_by(Test.upload_date.desc())
        )
    
    result = await db.execute(query)
    tests = result.scalars().all()
    
    test_list = []
    for test in tests:
        # Make deadline timezone-aware if it isn't
        deadline = test.submission_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        
        # For students, only show tests before deadline
        if user.role == 'student' and deadline < current_time:
            continue
        
        test_data = {
            "id": test.id,
            "title": test.title,
            "file_name": test.file_name,
            "file_path": test.file_path,
            "submission_deadline": deadline.isoformat(),
            "expires_at": test.expires_at.isoformat() if test.expires_at else None,
            "duration_minutes": test.duration_minutes,
            "upload_date": test.upload_date.isoformat(),
            "questions_extracted": test.questions_extracted,
            "extraction_status": test.extraction_status,  # pending/processing/completed/failed
            "extraction_stage": test.extraction_stage or 'UPLOADED',  # Current stage
            "extraction_stage_message": test.extraction_stage_message,  # Human-readable
            "extraction_error": test.extraction_error if user.role == 'teacher' else None,
            "status": test.status,  # draft/active
            "is_expired": deadline < current_time
        }
        
        # CRITICAL: Fetch actual question count from S3 (single source of truth)
        questions_count = None
        extraction_mismatch = False
        
        if test.extraction_stage == 'COMPLETED':
            try:
                from app.services.storage_service import fetch_test_questions_from_s3
                questions = await fetch_test_questions_from_s3(test.id, test.standard, subject.name, s3_folder_key=test.s3_folder_key)
                if questions:
                    questions_count = len(questions)
                else:
                    # S3 fetch succeeded but returned None/empty
                    extraction_mismatch = True
                    logger.error(f"EXTRACTION_MISMATCH: Test {test.id} marked COMPLETED but S3 has no questions.json")
            except Exception as e:
                # S3 fetch failed
                extraction_mismatch = True
                logger.error(f"EXTRACTION_MISMATCH: Test {test.id} marked COMPLETED but S3 fetch failed: {e}")
        
        test_data["questions_extracted_count"] = questions_count
        test_data["extraction_mismatch"] = extraction_mismatch
        
        # For students, check if they've already started/submitted
        if user.role == 'student':
            submission_result = await db.execute(
                select(TestSubmission)
                .where(
                    TestSubmission.test_id == test.id,
                    TestSubmission.student_id == user.id
                )
            )
            submission = submission_result.scalars().first()
            
            if submission:
                test_data['started'] = submission.started_at is not None
                test_data['submitted'] = submission.submitted
                test_data['started_at'] = submission.started_at.isoformat() if submission.started_at else None
                test_data['time_remaining_seconds'] = None
                
                if submission.started_at and not submission.submitted:
                    # Handle timezone-naive started_at
                    started_at = submission.started_at
                    if started_at.tzinfo is None:
                        started_at = started_at.replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
                    remaining = (test.duration_minutes * 60) - elapsed
                    test_data['time_remaining_seconds'] = max(0, int(remaining))
            else:
                test_data['started'] = False
                test_data['submitted'] = False
        
        test_list.append(test_data)
    
    return {"tests": test_list}


@api_router.delete("/tests/{test_id}")
async def delete_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Delete a test and clean up S3 files.
    Uses soft delete (status='deleted') for audit trail.
    """
    from app.services.storage_service import delete_test_folder_from_s3
    import json as json_module
    
    if user.role != 'teacher':
        raise HTTPException(status_code=403, detail="Only teachers can delete tests")
    
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalars().first()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    if test.status == 'deleted':
        return {"message": "Test already deleted"}
    
    cleanup_log = {
        "event": "test_manual_delete",
        "test_id": test_id,
        "title": test.title,
        "s3_folder": test.s3_folder_key,
        "s3_deleted": False,
        "db_deleted": False
    }
    
    # Delete S3 folder first (test.pdf, model_answers.pdf, extracted_questions.json)
    if test.s3_folder_key:
        try:
            s3_success = await delete_test_folder_from_s3(test.s3_folder_key)
            cleanup_log["s3_deleted"] = s3_success
            
            if not s3_success:
                logger.warning(f"Test delete: S3 cleanup incomplete: {json_module.dumps(cleanup_log)}")
                # Continue with DB deletion - S3 may already be empty
        except Exception as e:
            cleanup_log["error"] = str(e)
            logger.error(f"Test delete: S3 error: {json_module.dumps(cleanup_log)}")
            # Continue with DB deletion
    else:
        cleanup_log["s3_deleted"] = True
        cleanup_log["note"] = "No S3 folder"
    
    # Delete test questions record
    await db.execute(delete(TestQuestion).where(TestQuestion.test_id == test_id))
    
    # Soft delete: Mark test as deleted
    test.status = 'deleted'
    test.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    
    cleanup_log["db_deleted"] = True
    cleanup_log["status"] = "success"
    logger.info(f"Test delete: {json_module.dumps(cleanup_log)}")
    
    return {"message": "Test deleted successfully"}


@api_router.post("/tests/{test_id}/activate")
async def activate_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Manually activate a test (teacher only).
    REQUIRES: extracted_questions.json must exist in S3.
    """
    from app.services.storage_service import get_json_from_storage
    
    if user.role != 'teacher':
        raise HTTPException(status_code=403, detail="Only teachers can activate tests")
    
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalars().first()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Check if test already active
    if test.status == 'active':
        return {"message": "Test is already active", "status": "active"}
    
    # CRITICAL: Verify extracted_questions.json exists in S3
    test_questions_result = await db.execute(
        select(TestQuestion).where(TestQuestion.test_id == test_id)
    )
    test_questions = test_questions_result.scalars().first()
    
    if not test_questions or not test_questions.questions_s3_path:
        raise HTTPException(
            status_code=400,
            detail="Cannot activate: No questions found. Please re-run extraction."
        )
    
    # Verify S3 file exists
    logger.info(f"🔍 Verifying S3 file exists: {test_questions.questions_s3_path}")
    questions = await get_json_from_storage(test_questions.questions_s3_path)
    
    if not questions or not isinstance(questions, list) or len(questions) == 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot activate: Questions file missing or empty in S3. Please re-run extraction."
        )
    
    # All checks passed - activate the test
    test.status = 'active'
    test.extraction_status = 'completed'
    test.questions_extracted = True
    await db.commit()
    
    logger.info(f"✅ Test activated: {test.title} ({test_id}) with {len(questions)} questions")
    
    return {
        "message": "Test activated successfully",
        "test_id": test_id,
        "status": "active",
        "questions_count": len(questions)
    }


@api_router.post("/tests/{test_id}/retry-extraction")
async def retry_extraction(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Re-run extraction for a failed/stuck test (teacher only).
    
    Fetches the original PDF from S3 and re-runs the extraction pipeline.
    
    IDEMPOTENCY: Returns 409 if extraction is already in progress.
    """
    from app.services.storage_service import s3_client, S3_BUCKET, upload_test_questions_to_s3
    from app.services.background_extraction import start_extraction_task, get_extraction_task_status
    from app.models.database import AsyncSessionLocal
    
    if user.role != 'teacher':
        raise HTTPException(status_code=403, detail="Only teachers can retry extraction")
    
    # Get test
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalars().first()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # IDEMPOTENCY CHECK: Don't allow retry if already processing
    if test.extraction_status == 'processing':
        # Also check if background task is still running
        task_status = get_extraction_task_status(test_id)
        if task_status == 'running':
            raise HTTPException(
                status_code=409,
                detail="Extraction already in progress. Please wait for it to complete."
            )
        else:
            # Task finished but status wasn't updated - mark as failed
            logger.warning(f"[RETRY EXTRACTION] Orphaned processing status detected for {test_id}")
            test.extraction_status = 'failed'
            test.extraction_error = 'Previous extraction stalled'
            await db.commit()
    
    logger.info(f"🔄 [RETRY EXTRACTION] Starting for test: {test_id}, Previous status: {test.extraction_status}")
    
    # Reset extraction status
    test.extraction_status = 'pending'
    test.extraction_progress = 0
    test.extraction_started_at = None
    test.extraction_completed_at = None
    test.extraction_error = None
    test.questions_extracted_count = 0
    await db.commit()
    
    # Fetch PDFs from S3
    try:
        # Get test PDF
        test_pdf_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=test.file_path)
        test_pdf_bytes = test_pdf_obj['Body'].read()
        logger.info(f"✅ [RETRY EXTRACTION] Fetched test PDF from S3: {len(test_pdf_bytes)} bytes")
        
        # Get model answers if exists
        model_answers_bytes = None
        if test.model_answers_path:
            try:
                ma_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=test.model_answers_path)
                model_answers_bytes = ma_obj['Body'].read()
                logger.info(f"✅ [RETRY EXTRACTION] Fetched model answers from S3: {len(model_answers_bytes)} bytes")
            except Exception as e:
                logger.warning(f"⚠️ [RETRY EXTRACTION] Model answers not found: {e}")
        
        # Get subject name
        subject_result = await db.execute(select(Subject).where(Subject.id == test.subject_id))
        subject = subject_result.scalars().first()
        
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        
        # Start background extraction
        async def s3_upload_wrapper(questions):
            return await upload_test_questions_to_s3(questions, test_id, s3_folder_key=test.s3_folder_key)
        
        await start_extraction_task(
            test_id=test_id,
            test_pdf_bytes=test_pdf_bytes,
            model_answers_bytes=model_answers_bytes,
            standard=test.standard,
            subject_name=subject.name,
            db_session_factory=AsyncSessionLocal,
            s3_upload_func=s3_upload_wrapper
        )
        
        logger.info(f"🚀 [RETRY EXTRACTION] Background extraction started for test: {test_id}")
        
        return {
            "message": "Extraction restarted successfully",
            "test_id": test_id,
            "extraction_status": "pending",
            "poll_url": f"/api/tests/{test_id}/extraction-status"
        }
        
    except Exception as e:
        logger.error(f"❌ [RETRY EXTRACTION] Failed: {e}")
        
        # Mark as failed
        test.extraction_status = 'failed'
        test.extraction_error = f"Retry failed: {str(e)}"
        await db.commit()
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart extraction: {str(e)}"
        )


@api_router.get("/tests/{test_id}/extraction-status")
async def get_test_extraction_status(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get extraction status for a test with detailed stage information.
    
    Returns exact extraction stage for observability.
    Frontend can show progress bar based on stage.
    
    Frontend should poll this every 2-3 seconds while should_poll=true.
    """
    from datetime import datetime, timezone
    
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalars().first()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Calculate elapsed time if in progress
    elapsed_seconds = None
    if test.extraction_started_at and not test.extraction_completed_at:
        try:
            elapsed_seconds = int((datetime.now(timezone.utc) - test.extraction_started_at.replace(tzinfo=timezone.utc)).total_seconds())
        except (TypeError, AttributeError):
            # Handle timezone-naive datetime
            try:
                elapsed_seconds = int((datetime.utcnow() - test.extraction_started_at).total_seconds())
            except:
                elapsed_seconds = 0
    
    # Check for stuck extraction (>120 seconds)
    is_stuck = False
    if elapsed_seconds and elapsed_seconds > 120:
        is_stuck = True
    
    # Determine if task is running based on status
    task_running = test.extraction_status in ['pending', 'processing']
    
    # Generate proper stage message based on actual status
    stage_message = test.extraction_stage_message
    if not stage_message or stage_message == 'Waiting to start...':
        if test.extraction_stage == 'COMPLETED':
            stage_message = f'Extraction completed! {test.questions_extracted_count or 0} questions extracted.'
        elif test.extraction_stage == 'FAILED':
            stage_message = 'Extraction failed. Please retry.'
        elif test.extraction_stage == 'SAVING_TO_S3':
            stage_message = 'Saving questions to cloud storage...'
        elif test.extraction_stage == 'EXTRACTING_QUESTIONS':
            stage_message = 'AI is extracting questions from your test...'
        elif test.extraction_stage == 'PROCESSING':
            stage_message = 'Processing test PDF...'
        else:
            stage_message = 'Starting extraction...'
    
    return {
        "content_id": test_id,
        "content_type": "test",
        "test_id": test_id,
        "extraction_status": test.extraction_status or 'pending',
        "extraction_stage": test.extraction_stage or 'UPLOADED',
        "extraction_stage_message": stage_message,
        "extraction_progress": test.extraction_progress or 0,
        "questions_extracted_count": test.questions_extracted_count or 0,
        "extraction_mismatch": False,
        "test_status": test.status,
        "questions_extracted": test.questions_extracted or False,
        "task_running": task_running,
        "extraction_started_at": test.extraction_started_at.isoformat() if test.extraction_started_at else None,
        "extraction_completed_at": test.extraction_completed_at.isoformat() if test.extraction_completed_at else None,
        "elapsed_seconds": elapsed_seconds,
        "is_stuck": is_stuck,
        "expires_at": test.expires_at.isoformat() if test.expires_at else None,
        "error": test.extraction_error,
        "should_poll": test.extraction_status in ['pending', 'processing'] and not is_stuck,
        "can_retry": user.role == 'teacher' and (test.extraction_status in ['failed'] or is_stuck)
    }


@api_router.post("/admin/tests/cleanup")
async def trigger_test_cleanup(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """
    Manually trigger test cleanup (for testing/admin).
    Finds and cleans up all expired tests.
    """
    from app.services.storage_service import delete_test_folder_from_s3
    import json as json_module
    
    # Use naive datetime for comparison (SQLite stores naive)
    current_time_naive = datetime.utcnow()
    
    # Find expired tests
    result = await db.execute(
        select(Test).where(
            Test.expires_at <= current_time_naive,
            Test.status != 'deleted'
        )
    )
    expired_tests = result.scalars().all()
    
    logger.info(f"Manual cleanup: Found {len(expired_tests)} expired tests")
    
    cleanup_results = []
    
    for test in expired_tests:
        cleanup_log = {
            "test_id": test.id,
            "title": test.title,
            "expires_at": test.expires_at.isoformat() if test.expires_at else None,
            "s3_folder": test.s3_folder_key,
            "s3_deleted": False,
            "db_deleted": False,
            "status": "pending"
        }
        
        try:
            # Delete S3 first
            if test.s3_folder_key:
                s3_success = await delete_test_folder_from_s3(test.s3_folder_key)
                cleanup_log["s3_deleted"] = s3_success
                
                if not s3_success:
                    cleanup_log["status"] = "failed"
                    cleanup_log["error"] = "S3 deletion failed"
                    cleanup_results.append(cleanup_log)
                    continue
            else:
                cleanup_log["s3_deleted"] = True
            
            # Delete DB records
            await db.execute(delete(TestQuestion).where(TestQuestion.test_id == test.id))
            test.status = 'deleted'
            test.deleted_at = datetime.now(timezone.utc)
            await db.commit()
            
            cleanup_log["db_deleted"] = True
            cleanup_log["status"] = "success"
            
        except Exception as e:
            await db.rollback()
            cleanup_log["status"] = "failed"
            cleanup_log["error"] = str(e)
        
        cleanup_results.append(cleanup_log)
        logger.info(f"Manual cleanup: {json_module.dumps(cleanup_log)}")
    
    return {
        "cleaned_count": len([r for r in cleanup_results if r["status"] == "success"]),
        "failed_count": len([r for r in cleanup_results if r["status"] == "failed"]),
        "details": cleanup_results
    }


@api_router.get("/admin/tests/expired")
async def list_expired_tests(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """List all expired tests that need cleanup (for monitoring)."""
    # Use naive datetime for comparison
    current_time_naive = datetime.utcnow()
    
    result = await db.execute(
        select(Test).where(
            Test.expires_at <= current_time_naive,
            Test.status != 'deleted'
        )
    )
    expired_tests = result.scalars().all()
    
    return {
        "count": len(expired_tests),
        "current_time": datetime.now(timezone.utc).isoformat(),
        "tests": [
            {
                "id": t.id,
                "title": t.title,
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "status": t.status,
                "s3_folder": t.s3_folder_key
            }
            for t in expired_tests
        ]
    }


# =============================================================================
# PARENT DASHBOARD ENDPOINT (DB METADATA ONLY - NO S3 READS)
# =============================================================================

@api_router.get("/student/parent-dashboard")
async def get_parent_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Parent Academic Overview Dashboard.
    Returns aggregated, pre-computed data from DB only.
    NO S3 reads, NO content parsing, NO AI generation.
    
    Returns:
    - Subject-wise test performance (scores over time)
    - Subject-wise average score with Strong/Weak classification
    - Syllabus progress (practice tests attempted)
    - Homework completion stats
    - Missed homework list
    """
    from sqlalchemy import func, and_
    
    if user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can access parent dashboard")
    
    # Get student profile
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    )
    student_profile = profile_result.scalars().first()
    
    if not student_profile:
        raise HTTPException(status_code=404, detail="Student profile not found")
    
    roll_no = student_profile.roll_no
    standard = student_profile.standard
    
    # 1. Get all subjects for this standard
    subjects_result = await db.execute(
        select(Subject).where(Subject.standard == standard)
    )
    subjects = subjects_result.scalars().all()
    
    subject_data = {}
    
    for subject in subjects:
        subject_data[subject.name] = {
            "subject_id": subject.id,
            "subject_name": subject.name,
            "test_performance": [],
            "average_score": 0,
            "classification": "no_data",  # 'strong', 'average', 'weak', 'no_data'
            "syllabus_progress": {
                "total_practice_tests": 0,
                "attempted_practice_tests": 0,
                "progress_percentage": 0
            },
            "homework_stats": {
                "total_assigned": 0,
                "submitted": 0,
                "completion_percentage": 0
            },
            "missed_homework": []
        }
    
    # 2. Get Test Performance (from TestSubmission - old system - DB only)
    test_submissions_result = await db.execute(
        select(TestSubmission).where(
            TestSubmission.student_id == user.id,
            TestSubmission.submitted.is_(True),
            TestSubmission.evaluated.is_(True)
        ).order_by(TestSubmission.submitted_at)
    )
    test_submissions = test_submissions_result.scalars().all()
    
    # Group by subject and calculate scores
    subject_scores = {}
    for submission in test_submissions:
        subject_name = submission.subject_name
        if subject_name not in subject_scores:
            subject_scores[subject_name] = []
        
        # Calculate percentage
        if submission.max_score and submission.max_score > 0:
            percentage = (submission.total_score / submission.max_score) * 100
        else:
            percentage = 0
        
        subject_scores[subject_name].append({
            "test_name": submission.test_title,
            "date": submission.submitted_at.isoformat() if submission.submitted_at else None,
            "percentage": round(percentage, 1)
        })
    
    # 2b. Get AI-evaluated test performance (from StructuredTestSubmission + StructuredTest)
    # Build a subject_id -> subject_name lookup from already-fetched subjects
    subject_id_to_name = {str(s.id): s.name for s in subjects}
    
    ai_submissions_result = await db.execute(
        select(StructuredTestSubmission, StructuredTest).join(
            StructuredTest, StructuredTestSubmission.test_id == StructuredTest.id
        ).where(
            StructuredTestSubmission.student_id == user.id,
            StructuredTestSubmission.submitted.is_(True),
            StructuredTestSubmission.evaluation_status == 'completed'
        ).order_by(StructuredTestSubmission.submitted_at)
    )
    ai_submissions = ai_submissions_result.all()
    
    for submission, test in ai_submissions:
        subject_name = subject_id_to_name.get(str(test.subject_id))
        if not subject_name:
            continue
        if subject_name not in subject_scores:
            subject_scores[subject_name] = []
        
        pct = round(submission.percentage, 1) if submission.percentage is not None else 0
        subject_scores[subject_name].append({
            "test_name": test.title,
            "date": submission.submitted_at.isoformat() if submission.submitted_at else None,
            "percentage": pct
        })
    
    # Sort each subject's scores by date and update subject_data
    for subject_name, scores in subject_scores.items():
        scores.sort(key=lambda s: s["date"] or "")
        if subject_name in subject_data:
            subject_data[subject_name]["test_performance"] = scores
            
            # Calculate average score
            if scores:
                avg = sum(s["percentage"] for s in scores) / len(scores)
                subject_data[subject_name]["average_score"] = round(avg, 1)
                
                # Classify: Strong (>=80%), Average (60-79%), Needs Improvement (<60%)
                if avg >= 80:
                    subject_data[subject_name]["classification"] = "strong"
                elif avg >= 60:
                    subject_data[subject_name]["classification"] = "average"
                else:
                    subject_data[subject_name]["classification"] = "weak"
    
    # 3. Get Syllabus Progress (from StudentPracticeProgress - DB only)
    for subject_name in subject_data:
        # Count total chapters for this subject
        chapter_count_result = await db.execute(
            select(func.count(Chapter.id)).where(
                Chapter.subject_id == subject_data[subject_name]["subject_id"]
            )
        )
        chapter_count = chapter_count_result.scalar() or 0
        
        # Total practice tests = chapters × 5 (5 quizzes per chapter: Easy, Medium, Hard, Advanced 1, Advanced 2)
        total_practice_tests = chapter_count * 5
        
        # Count DISTINCT completed practice tests (avoid counting retries multiple times)
        # Each (subject, chapter, practice_test_number) combination counts as ONE attempt
        attempted_result = await db.execute(
            select(
                func.count(
                    func.distinct(
                        StudentPracticeProgress.subject + '_' + 
                        StudentPracticeProgress.chapter + '_' + 
                        func.cast(StudentPracticeProgress.practice_test_number, String)
                    )
                )
            ).where(
                StudentPracticeProgress.roll_no == roll_no,
                StudentPracticeProgress.subject == subject_name,
                StudentPracticeProgress.attempted.is_(True)
            )
        )
        attempted_count = attempted_result.scalar() or 0
        
        # Calculate progress percentage (5 quizzes = 100% per chapter, spread across subject)
        progress_pct = (attempted_count / total_practice_tests * 100) if total_practice_tests > 0 else 0
        
        subject_data[subject_name]["syllabus_progress"] = {
            "total_practice_tests": total_practice_tests,
            "attempted_practice_tests": attempted_count,
            "progress_percentage": round(progress_pct, 1),
            "chapter_count": chapter_count
        }
    
    # 4. Get Homework Stats (from HomeworkSubmission - DB only)
    for subject_name in subject_data:
        # Total homework assigned for this subject
        total_hw_result = await db.execute(
            select(func.count(HomeworkSubmission.id)).where(
                HomeworkSubmission.student_id == user.id,
                HomeworkSubmission.subject_name == subject_name,
                HomeworkSubmission.standard == standard
            )
        )
        total_hw = total_hw_result.scalar() or 0
        
        # Submitted homework
        submitted_hw_result = await db.execute(
            select(func.count(HomeworkSubmission.id)).where(
                HomeworkSubmission.student_id == user.id,
                HomeworkSubmission.subject_name == subject_name,
                HomeworkSubmission.standard == standard,
                HomeworkSubmission.submitted.is_(True)
            )
        )
        submitted_hw = submitted_hw_result.scalar() or 0
        
        # Calculate completion percentage
        completion_pct = (submitted_hw / total_hw * 100) if total_hw > 0 else 0
        
        subject_data[subject_name]["homework_stats"] = {
            "total_assigned": total_hw,
            "submitted": submitted_hw,
            "completion_percentage": round(completion_pct, 1)
        }
        
        # Get missed homework (not submitted)
        missed_hw_result = await db.execute(
            select(HomeworkSubmission).where(
                HomeworkSubmission.student_id == user.id,
                HomeworkSubmission.subject_name == subject_name,
                HomeworkSubmission.standard == standard,
                HomeworkSubmission.submitted.is_(False)
            ).order_by(HomeworkSubmission.homework_upload_date.desc())
        )
        missed_hw = missed_hw_result.scalars().all()
        
        subject_data[subject_name]["missed_homework"] = [
            {
                "homework_title": hw.homework_title,
                "due_date": hw.homework_upload_date.isoformat() if hw.homework_upload_date else None
            }
            for hw in missed_hw
        ]
    
    # Convert to list and filter out subjects with no data at all
    subjects_list = list(subject_data.values())
    
    # Calculate overall stats
    total_tests_attempted = sum(len(s["test_performance"]) for s in subjects_list)
    overall_avg = 0
    if total_tests_attempted > 0:
        all_scores = [score["percentage"] for s in subjects_list for score in s["test_performance"]]
        overall_avg = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0
    
    total_homework = sum(s["homework_stats"]["total_assigned"] for s in subjects_list)
    total_submitted = sum(s["homework_stats"]["submitted"] for s in subjects_list)
    overall_hw_completion = round(total_submitted / total_homework * 100, 1) if total_homework > 0 else 0
    
    # Collect all missed homework
    all_missed_homework = []
    for s in subjects_list:
        for hw in s["missed_homework"]:
            all_missed_homework.append({
                "subject": s["subject_name"],
                "homework_title": hw["homework_title"],
                "due_date": hw["due_date"]
            })
    
    return {
        "student_name": student_profile.name or user.name,
        "roll_no": roll_no,
        "standard": standard,
        "subjects": subjects_list,
        "overall_stats": {
            "total_tests_attempted": total_tests_attempted,
            "overall_average_score": overall_avg,
            "overall_homework_completion": overall_hw_completion,
            "total_missed_homework": len(all_missed_homework)
        },
        "all_missed_homework": all_missed_homework[:10]  # Limit to 10 most recent
    }


@api_router.get("/tests/{test_id}/questions")
async def get_test_questions(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get extracted questions for a test (from S3).
    
    CRITICAL FIX: S3 existence is PRIMARY source of truth for students.
    DB status = 'processing' must NOT block if questions exist in S3.
    
    Decision flow (CORRECT ORDER):
    1. Check if quiz is inactive → return quiz_inactive
    2. **CHECK S3 FIRST** for extracted_questions.json (PRIMARY CHECK)
    3. If S3 file exists → return questions + auto-heal DB if needed
    4. If S3 missing + DB says processing → return processing
    5. If S3 missing + DB says failed → return extraction_failed
    6. Otherwise → return not_available
    
    This ensures students can ALWAYS attempt quiz if questions exist in S3,
    regardless of potentially stale DB status.
    """
    from app.services.storage_service import get_json_from_storage
    
    # ========================================================================
    # STEP 1: Verify test exists
    # ========================================================================
    logger.info(f"📝 [QUIZ LOAD] Student attempting test_id: {test_id}")
    
    test_result = await db.execute(select(Test).where(Test.id == test_id))
    test = test_result.scalars().first()
    
    if not test:
        logger.warning(f"❌ [QUIZ LOAD] Test not found: {test_id}")
        raise HTTPException(status_code=404, detail="Test not found")
    
    logger.info(f"📊 [QUIZ LOAD] DB State:")
    logger.info(f"   - Quiz status: {test.status}")
    logger.info(f"   - Extraction status: {test.extraction_status}")
    logger.info(f"   - Questions extracted flag: {test.questions_extracted}")
    
    # ========================================================================
    # STEP 2: Check if test is active (blocks inactive quizzes)
    # ========================================================================
    if test.status != 'active':
        logger.warning(f"❌ [QUIZ LOAD] Quiz is not active - Status: {test.status}")
        logger.warning(f"   Decision: BLOCK (quiz_inactive)")
        return {
            "questions": [], 
            "message": "This quiz is no longer active.",
            "error": True,
            "error_type": "quiz_inactive"
        }
    
    # ========================================================================
    # STEP 3: Get S3 path from DB (need this to check S3)
    # ========================================================================
    result = await db.execute(
        select(TestQuestion).where(TestQuestion.test_id == test_id)
    )
    test_questions = result.scalars().first()
    
    # Build expected S3 path (even if DB record missing)
    s3_key = None
    if test_questions and test_questions.questions_s3_path:
        s3_key = test_questions.questions_s3_path
    elif test.s3_folder_key:
        # Fallback: construct from test folder key
        s3_key = f"{test.s3_folder_key}/questions.json"
    
    logger.info(f"🔍 [QUIZ LOAD] S3 Check:")
    logger.info(f"   - S3 key to check: {s3_key}")
    
    # ========================================================================
    # STEP 4: **PRIMARY CHECK** - Does S3 file exist?
    # ========================================================================
    questions = None
    s3_exists = False
    
    if s3_key:
        logger.info(f"📥 [QUIZ LOAD] Attempting S3 fetch (PRIMARY CHECK)...")
        questions = await get_json_from_storage(s3_key)
        
        if questions is not None:
            s3_exists = True
            logger.info(f"✅ [QUIZ LOAD] S3 file EXISTS: {s3_key}")
            logger.info(f"   - Questions found: {len(questions) if isinstance(questions, list) else 'N/A'}")
            
            # AUTO-HEAL: If DB says 'processing' but S3 file exists, fix DB
            if test.extraction_status == 'processing':
                logger.warning(f"🔧 [QUIZ LOAD] AUTO-HEAL: DB shows 'processing' but S3 file exists!")
                logger.warning(f"   - Updating DB status to 'completed'")
                test.extraction_status = 'completed'
                test.questions_extracted = True
                await db.commit()
                logger.info(f"✅ [QUIZ LOAD] DB healed - status updated to 'completed'")
        else:
            logger.warning(f"⚠️ [QUIZ LOAD] S3 file does NOT exist: {s3_key}")
    else:
        logger.error(f"❌ [QUIZ LOAD] Cannot determine S3 key - no DB record or folder key")
    
    # ========================================================================
    # STEP 5: Decision Logic (S3-first approach)
    # ========================================================================
    
    # If S3 file exists → ALLOW STUDENT (regardless of DB status)
    if s3_exists and questions:
        # Validate questions structure
        if not isinstance(questions, list):
            logger.error(f"❌ [QUIZ LOAD] Invalid format - expected list, got {type(questions)}")
            logger.error(f"   Decision: BLOCK (invalid_format)")
            return {
                "questions": [], 
                "message": "Questions format error. Please contact your teacher.",
                "error": True,
                "error_type": "invalid_format"
            }
        
        if len(questions) == 0:
            logger.warning(f"⚠️ [QUIZ LOAD] Questions list is empty")
            logger.warning(f"   Decision: BLOCK (empty_questions)")
            return {
                "questions": [], 
                "message": "No questions found for this quiz.",
                "error": True,
                "error_type": "empty_questions"
            }
        
        # SUCCESS: Questions exist in S3
        logger.info(f"✅ [QUIZ LOAD] Decision: ALLOW")
        logger.info(f"   - Returning {len(questions)} questions to student")
        logger.info(f"   - Source: S3 ({s3_key})")
        
        return {
            "questions": questions,
            "question_count": len(questions),
            "error": False
        }
    
    # If S3 file does NOT exist → Check DB status for reason
    logger.warning(f"⚠️ [QUIZ LOAD] S3 file missing - checking DB status for reason")
    
    if test.extraction_status == 'processing':
        logger.info(f"⏳ [QUIZ LOAD] Decision: BLOCK (processing)")
        logger.info(f"   Reason: Extraction genuinely in progress (S3 file not created yet)")
        return {
            "questions": [], 
            "message": "Questions are being prepared. Please wait a moment and try again.",
            "error": True,
            "error_type": "processing",
            "retry_allowed": True
        }
    
    if test.extraction_status == 'failed':
        logger.warning(f"❌ [QUIZ LOAD] Decision: BLOCK (extraction_failed)")
        logger.warning(f"   Reason: {test.extraction_error}")
        return {
            "questions": [], 
            "message": "Question extraction failed. Please contact your teacher.",
            "error": True,
            "error_type": "extraction_failed"
        }
    
    # S3 file missing + DB status unclear
    logger.error(f"❌ [QUIZ LOAD] Decision: BLOCK (not_available)")
    logger.error(f"   Reason: S3 file missing, DB status: {test.extraction_status}")
    return {
        "questions": [], 
        "message": "Questions not available. Please contact your teacher.",
        "error": True,
        "error_type": "not_available"
    }


@api_router.post("/tests/{test_id}/start")
async def start_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Start a test attempt (begins timer)"""
    from datetime import datetime, timezone
    
    if user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can attempt tests")
    
    # Check if test exists
    test_result = await db.execute(select(Test).where(Test.id == test_id))
    test = test_result.scalars().first()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Make deadline timezone-aware if it isn't
    deadline = test.submission_deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    
    # Check if deadline has passed
    if deadline < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Test submission deadline has passed")
    
    # Get student profile
    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user.id)
    )
    profile = profile_result.scalars().first()
    
    if not profile:
        raise HTTPException(status_code=400, detail="Student profile not found")
    
    # Get subject name
    subject_result = await db.execute(select(Subject).where(Subject.id == test.subject_id))
    subject = subject_result.scalars().first()
    
    # Check if already started
    submission_result = await db.execute(
        select(TestSubmission)
        .where(
            TestSubmission.test_id == test_id,
            TestSubmission.student_id == user.id
        )
    )
    submission = submission_result.scalars().first()
    
    if submission:
        if submission.submitted:
            raise HTTPException(status_code=400, detail="Test already submitted")
        
        # Calculate remaining time - handle timezone-naive started_at
        started_at = submission.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        remaining = (test.duration_minutes * 60) - elapsed
        
        if remaining <= 0:
            # Time expired, auto-submit
            submission.submitted = True
            submission.submitted_at = datetime.now(timezone.utc)
            submission.time_taken_seconds = int(elapsed)
            submission.auto_submitted = True
            await db.commit()
            raise HTTPException(status_code=400, detail="Test time expired")
        
        return {
            "message": "Test already started",
            "started_at": submission.started_at.isoformat(),
            "time_remaining_seconds": int(remaining),
            "duration_minutes": test.duration_minutes
        }
    
    # Create new submission
    submission = TestSubmission(
        test_id=test_id,
        test_title=test.title,
        subject_name=subject.name,
        standard=test.standard,
        student_id=user.id,
        roll_no=profile.roll_no,
        started_at=datetime.now(timezone.utc),
        test_upload_date=test.upload_date
    )
    
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    
    return {
        "message": "Test started",
        "submission_id": submission.id,
        "started_at": submission.started_at.isoformat(),
        "duration_minutes": test.duration_minutes,
        "time_remaining_seconds": test.duration_minutes * 60
    }


@api_router.post("/tests/{test_id}/submit")
async def submit_test(
    test_id: str,
    answers: str = Form(...),  # JSON string
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Submit test answers and evaluate"""
    from datetime import datetime, timezone
    import json
    
    if user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can submit tests")
    
    # Get submission
    submission_result = await db.execute(
        select(TestSubmission)
        .where(
            TestSubmission.test_id == test_id,
            TestSubmission.student_id == user.id
        )
    )
    submission = submission_result.scalars().first()
    
    if not submission:
        raise HTTPException(status_code=400, detail="Test not started")
    
    if submission.submitted:
        raise HTTPException(status_code=400, detail="Test already submitted")
    
    # Get test details
    test_result = await db.execute(select(Test).where(Test.id == test_id))
    test = test_result.scalars().first()
    
    # Calculate time taken (handle timezone-naive started_at)
    started_at = submission.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    time_taken = (datetime.now(timezone.utc) - started_at).total_seconds()
    
    # Check if time exceeded
    auto_submit = False
    if time_taken > (test.duration_minutes * 60):
        auto_submit = True
        time_taken = test.duration_minutes * 60
    
    # Parse answers (kept in memory only, not saved)
    try:
        answers_dict = json.loads(answers)
    except:
        raise HTTPException(status_code=400, detail="Invalid answers format")
    
    # Update submission metadata (NO answers saved)
    submission.submitted = True
    submission.submitted_at = datetime.now(timezone.utc)
    submission.time_taken_seconds = int(time_taken)
    submission.auto_submitted = auto_submit
    
    await db.commit()
    
    # Evaluate answers using AI (in memory only)
    try:
        from app.services.ai_service import evaluate_test_answers
        from app.services.storage_service import get_json_from_storage
        
        # Get questions from S3 (stored in tests table directly)
        if not test.questions_s3_key:
            logger.error(f"❌ No questions_s3_key found for test {test_id}")
            return {
                "message": "Test submitted but no questions found for evaluation",
                "time_taken_minutes": round(time_taken / 60, 2)
            }
        
        # Retrieve questions from S3
        questions = await get_json_from_storage(test.questions_s3_key)
        
        if not questions:
            logger.error(f"❌ Could not load questions from S3 for test {test_id}")
            logger.error(f"S3 key was: {test.questions_s3_key}")
            return {
                "message": "Test submitted but questions could not be loaded",
                "time_taken_minutes": round(time_taken / 60, 2)
            }
        
        logger.info(f"✅ Loaded {len(questions)} questions for evaluation")
        
        # Get model answers if they exist
        model_answers = None
        if test.answers_s3_key:
            model_answers = await get_json_from_storage(test.answers_s3_key)
            if model_answers:
                logger.info(f"✅ Loaded {len(model_answers)} model answers")
            else:
                logger.warning(f"⚠️ Could not load model answers from {test.answers_s3_key}")
        
        # Check if marking schema exists
        marking_schema_text = None
        if test.has_marking_schema and test.marking_schema_text_path:
            try:
                import json
                schema_json = await get_json_from_storage(test.marking_schema_text_path)
                if schema_json and 'text' in schema_json:
                    marking_schema_text = schema_json['text']
                    logger.info(f"✅ Using marking schema for evaluation of test {test_id}")
            except Exception as e:
                logger.warning(f"⚠️ Could not load marking schema: {e}")
        
        # Evaluate (in memory - results not saved anywhere)
        logger.info(f"🔄 Evaluating test {test_id} with {len(answers_dict)} answers")
        evaluation = await evaluate_test_answers(
            questions, 
            answers_dict, 
            marking_schema_text=marking_schema_text
        )
        
        if not evaluation:
            logger.error(f"❌ Evaluation returned None for test {test_id}")
            return {
                "message": "Test submitted but evaluation failed",
                "time_taken_minutes": round(time_taken / 60, 2)
            }
        
        # Calculate percentage
        total_score = float(evaluation.get('total_score', 0))
        max_score = float(evaluation.get('max_total_score', 0))
        
        if max_score == 0:
            logger.warning(f"⚠️ Max score is 0 for test {test_id}, using question count")
            max_score = float(len(questions))
        
        percentage = (total_score / max_score * 100) if max_score > 0 else 0
        
        logger.info(f"📊 Evaluation result: {total_score}/{max_score} = {percentage:.2f}%")
        
        # Save ONLY total score to database (no detailed feedback)
        submission.evaluated = True
        submission.total_score = total_score
        submission.max_score = max_score
        submission.percentage = percentage
        submission.total_questions = evaluation.get('question_count', len(questions))
        submission.evaluated_at = datetime.now(timezone.utc)
        
        await db.commit()
        
        # Update student performance tracking
        subject_result = await db.execute(select(Subject).where(Subject.id == test.subject_id))
        subject = subject_result.scalars().first()
        
        if subject:
            logger.info(f"📈 Updating student performance for subject {subject.name}")
            await update_student_performance(
                db=db,
                student_id=user.id,
                roll_no=submission.roll_no,
                subject_id=test.subject_id,
                subject_name=subject.name,
                standard=test.standard,
                marks_scored=total_score,
                max_marks=max_score
            )
        
        return {
            "message": "Test submitted and evaluated successfully",
            "total_score": total_score,
            "max_score": max_score,
            "percentage": round(percentage, 2),
            "total_questions": evaluation.get('question_count', len(questions)),
            "time_taken_minutes": round(time_taken / 60, 2),
            "auto_submitted": auto_submit
        }
    except Exception as e:
        logger.error(f"Evaluation error: {e}")
        return {
            "message": "Test submitted but evaluation failed",
            "error": str(e),
            "time_taken_minutes": round(time_taken / 60, 2)
        }


@api_router.get("/tests/{test_id}/submissions")
async def get_test_submissions(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get all submissions for a test (teacher view)"""
    if user.role != 'teacher':
        raise HTTPException(status_code=403, detail="Only teachers can view submissions")
    
    # Get test
    test_result = await db.execute(select(Test).where(Test.id == test_id))
    test = test_result.scalars().first()
    
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    # Get all students in this standard
    students_result = await db.execute(
        select(StudentProfile)
        .where(StudentProfile.standard == test.standard)
    )
    all_students = students_result.scalars().all()
    
    # Get submissions
    submissions_result = await db.execute(
        select(TestSubmission)
        .where(TestSubmission.test_id == test_id)
    )
    submissions = submissions_result.scalars().all()
    
    # Build submission map
    submission_map = {sub.student_id: sub for sub in submissions}
    
    # Build response
    student_list = []
    for student in all_students:
        submission = submission_map.get(student.user_id)
        
        student_data = {
            "student_name": student.name,
            "roll_no": student.roll_no,
            "submitted": submission.submitted if submission else False,
            "started": submission.started_at is not None if submission else False,
            "score": submission.total_score if submission and submission.evaluated else None,
            "time_taken_minutes": round(submission.time_taken_seconds / 60, 2) if submission and submission.time_taken_seconds else None,
            "submitted_at": submission.submitted_at.isoformat() if submission and submission.submitted_at else None
        }
        
        student_list.append(student_data)
    
    submitted_count = sum(1 for s in student_list if s['submitted'])
    not_submitted_count = len(student_list) - submitted_count
    
    return {
        "test_title": test.title,
        "total_students": len(student_list),
        "submitted_count": submitted_count,
        "not_submitted_count": not_submitted_count,
        "students": student_list
    }


@api_router.get("/tests/student/my-results")
async def get_student_test_results(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get all test results for a student (only scores, no details)"""
    if user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can view their results")
    
    result = await db.execute(
        select(TestSubmission)
        .where(
            TestSubmission.student_id == user.id,
            TestSubmission.submitted == True
        )
        .order_by(TestSubmission.submitted_at.desc())
    )
    submissions = result.scalars().all()
    
    results = []
    for sub in submissions:
        results.append({
            "test_title": sub.test_title,
            "subject_name": sub.subject_name,
            "standard": sub.standard,
            "submitted_at": sub.submitted_at.isoformat(),
            "time_taken_minutes": round(sub.time_taken_seconds / 60, 2) if sub.time_taken_seconds else None,
            "total_score": sub.total_score,
            "max_score": sub.max_score,
            "total_questions": sub.total_questions,
            "evaluated": sub.evaluated,
            "auto_submitted": sub.auto_submitted
        })
    
    return {"results": results}


# =============================================================================
# STUDY MATERIALS ENDPOINTS
# =============================================================================

class CreateStudyMaterialRequest(BaseModel):
    chapter_id: str
    material_type: str  # 'solved_problems', 'notes', 'reference', 'worksheet'
    title: str


@api_router.post("/chapters/{chapter_id}/study-materials")
async def upload_study_material(
    chapter_id: str,
    material_type: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Teacher uploads study material for a chapter"""
    from app.services.storage_service import sanitize_component, sanitize_school_name, s3_client, S3_BUCKET
    
    # Verify chapter exists
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Get subject info
    subject_result = await db.execute(select(Subject).where(Subject.id == chapter.subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Get teacher's school
    teacher_school = await get_user_school(user, db)
    if not teacher_school:
        raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
    
    # Construct S3 path with class/subject/chapter structure
    file_content = await file.read()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_filename = sanitize_component(file.filename.replace('.pdf', '')) + '.pdf'
    school_folder = sanitize_school_name(teacher_school)
    
    # Path: {school}/uploads/class{X}/{subject}/{chapter}/{timestamp}_{filename}
    s3_key = f"{school_folder}/uploads/class{chapter.standard}/{sanitize_component(subject.name)}/{sanitize_component(chapter.name)}/{timestamp}_{safe_filename}"
    
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType='application/pdf'
        )
        logger.info(f"✅ Study material uploaded to S3: {s3_key}")
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload study material to S3: {str(e)}")
    
    # Create study material record
    study_material = StudyMaterial(
        chapter_id=chapter_id,
        material_type=material_type,
        title=title,
        file_name=file.filename,
        file_path=s3_key,  # Store S3 key
        school_name=teacher_school,  # SET SCHOOL
        uploaded_by=user.id
    )
    db.add(study_material)
    await db.commit()
    await db.refresh(study_material)
    
    return {
        "id": str(study_material.id),
        "title": study_material.title,
        "material_type": study_material.material_type,
        "file_name": study_material.file_name,
        "message": "Study material uploaded successfully"
    }


@api_router.get("/chapters/{chapter_id}/study-materials")
async def list_study_materials(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    List all study materials for a chapter.
    
    School-Based Filtering:
    - Students/Teachers: Only see materials from their school
    - Admin: See all materials
    """
    # Get user's school
    user_school = await get_user_school(user, db)
    
    query = select(StudyMaterial).where(StudyMaterial.chapter_id == chapter_id)
    
    # Apply school-based filtering
    if user_school and user.role in ['student', 'teacher']:
        query = query.where(StudyMaterial.school_name == user_school)
    
    query = query.order_by(StudyMaterial.created_at.desc())
    
    result = await db.execute(query)
    materials = result.scalars().all()
    
    return [{
        "id": str(mat.id),
        "chapter_id": str(mat.chapter_id),
        "material_type": mat.material_type,
        "title": mat.title,
        "file_name": mat.file_name,
        "file_path": mat.file_path,  # S3 key - frontend should construct presigned URL if needed
        "uploaded_at": mat.created_at.isoformat()
    } for mat in materials]




@api_router.get("/study-materials/{material_id}/download-url")
async def get_study_material_download_url(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get presigned URL for downloading study material.
    Students can only download materials from their school.
    """
    from app.services.storage_service import generate_presigned_url
    
    result = await db.execute(select(StudyMaterial).where(StudyMaterial.id == material_id))
    material = result.scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Study material not found")
    
    # Verify school access for students/teachers
    if user.role in ['student', 'teacher']:
        user_school = await get_user_school(user, db)
        if material.school_name != user_school:
            raise HTTPException(status_code=403, detail="Access denied - different school")
    
    try:
        presigned_url = generate_presigned_url(material.file_path, expiration=3600)
        return {
            "download_url": presigned_url,
            "file_name": material.file_name,
            "expires_in": 3600
        }
    except Exception as e:
        logger.error(f"Failed to generate download URL: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate download URL")

@api_router.delete("/study-materials/{material_id}")
async def delete_study_material(
    material_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Delete study material (teacher only) - also deletes file from storage"""
    result = await db.execute(select(StudyMaterial).where(StudyMaterial.id == material_id))
    material = result.scalars().first()
    if not material:
        raise HTTPException(status_code=404, detail="Study material not found")
    
    # Delete file from S3/local storage
    if material.file_path:
        deleted = await delete_file_from_storage(material.file_path)
        if deleted:
            logger.info(f"✅ Deleted study material file: {material.file_path}")
        else:
            logger.warning(f"⚠️ Could not delete study material file: {material.file_path}")
    
    # Delete from database
    await db.delete(material)
    await db.commit()
    
    return {"message": "Study material deleted successfully"}


# =============================================================================
# PHASE 4.1: CONTROLLED AI REGENERATION (TEACHER-ONLY)
# =============================================================================
# CRITICAL RULES:
# 1. Students can NEVER trigger AI generation
# 2. Teachers must EXPLICITLY confirm regeneration
# 3. Upload does NOT auto-regenerate
# =============================================================================

@api_router.post("/teacher/content/upload")
async def teacher_upload_content(
    chapter_id: str = Form(...),
    content_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """
    Teacher uploads textbook/PYQ PDF.
    DOES NOT auto-regenerate AI content.
    Returns flag indicating if AI content exists.
    """
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Get subject info
    subject_result = await db.execute(select(Subject).where(Subject.id == chapter.subject_id))
    subject = subject_result.scalars().first()
    
    # Check if AI content already exists
    redis_client = await get_redis()
    ai_content_exists = False
    if redis_client:
        # Check for any cached AI content
        cache_key_pattern = f"ai:*{subject.name}*{chapter.name}*" if subject else None
        if cache_key_pattern:
            keys = redis_client.keys(cache_key_pattern[:50])  # Limit pattern length
            ai_content_exists = len(keys) > 0
    
    # Check database cache too
    db_cache_result = await db.execute(
        text("SELECT COUNT(*) FROM ai_content_cache WHERE chapter_id = :chapter_id"),
        {"chapter_id": chapter_id}
    )
    db_cache_count = db_cache_result.scalar() or 0
    ai_content_exists = ai_content_exists or db_cache_count > 0
    
    # Check existing content
    existing_content_result = await db.execute(
        select(Content).where(Content.chapter_id == chapter_id)
    )
    existing_contents = existing_content_result.scalars().all()
    old_content_count = len(existing_contents)
    
    # Delete old PDF (but NOT AI content yet - teacher must confirm)
    for old_content in existing_contents:
        if old_content.s3_url:
            await delete_file_from_storage(old_content.s3_url)
            logger.info(f"Deleted old PDF: {old_content.s3_url}")
        await db.delete(old_content)
    await db.commit()
    
    # Get teacher's school for S3 path
    teacher_school = await get_user_school(user, db)
    if not teacher_school:
        raise HTTPException(status_code=400, detail="Teacher profile not found or school not set")
    
    # Upload new PDF to S3 with deterministic path including school
    file_content = await file.read()
    standard = chapter.standard
    
    try:
        from app.services.storage_service import upload_pdf_to_s3
        s3_key = await upload_pdf_to_s3(file_content, standard, subject.name, chapter.name, teacher_school)
        # Store key, not URL
        s3_url = s3_key
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload PDF to S3: {str(e)}")
    
    content = Content(
        chapter_id=chapter_id,
        content_type=content_type,
        file_name=file.filename,
        s3_url=s3_url,
        ocr_processed=False
    )
    db.add(content)
    await db.commit()
    await db.refresh(content)
    
    # OCR removed - Gemini handles PDF processing natively
    # No local text extraction needed
    logger.info("PDF will be processed by Gemini AI during test extraction")
    
    return {
        "id": str(content.id),
        "chapter_id": str(content.chapter_id),
        "file_name": content.file_name,
        "ocr_processed": content.ocr_processed,
        "ai_content_exists": ai_content_exists,
        "old_content_deleted": old_content_count,
        "message": "PDF uploaded successfully. AI content NOT regenerated.",
        "regeneration_required": ai_content_exists  # Frontend should show confirmation modal
    }


@api_router.post("/teacher/chapter/{chapter_id}/regenerate-ai-content")
async def regenerate_ai_content(
    chapter_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """
    PRODUCTION-GRADE AI REGENERATION with Background Processing.
    
    This endpoint:
    1. Sets ai_status = "processing" immediately
    2. Returns success response within 2 seconds
    3. Triggers background task for actual generation
    
    Students see "Content generating, please wait" until ai_status = "completed"
    """
    from app.services.storage_service import (
        check_pdf_exists_in_s3, delete_ai_content_from_s3, sanitize_component
    )
    
    logger.info(f"🚀 AI REGENERATION REQUESTED for chapter_id: {chapter_id}")
    
    # Step 1: Verify chapter exists
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # Check if already processing
    if hasattr(chapter, 'ai_status') and chapter.ai_status == "processing":
        return {
            "success": True,
            "chapter_id": chapter_id,
            "ai_status": "processing",
            "message": "AI content generation is already in progress. Please wait."
        }
    
    # Step 2: Get subject
    subject_result = await db.execute(select(Subject).where(Subject.id == chapter.subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    standard = chapter.standard
    
    # Step 3: Validate PDF exists in S3
    try:
        pdf_exists = await check_pdf_exists_in_s3(standard, subject.name, chapter.name, school_name=chapter.school_name)
    except Exception as e:
        raise HTTPException(500, detail=f"S3 validation error: {str(e)}")
    
    if not pdf_exists:
        from app.services.storage_service import sanitize_school_name
        school_prefix = f"{sanitize_school_name(chapter.school_name)}/" if chapter.school_name else ""
        expected_path = f"{school_prefix}pdfs/class{standard}/{sanitize_component(subject.name)}/{sanitize_component(chapter.name)}/textbook.pdf"
        raise HTTPException(400, detail=f"PDF not found. Please upload textbook first. Expected: {expected_path}")
    
    # Step 4: Extract text from PDF
    from app.services.storage_service import download_pdf_from_s3
    from app.services.gpt4o_extraction import extract_text_from_pdf_with_gemini
    
    try:
        pdf_bytes = await download_pdf_from_s3(standard, subject.name, chapter.name, school_name=chapter.school_name)
        if not pdf_bytes:
            raise HTTPException(400, detail="Could not download PDF from S3. Re-upload the file.")
        
        content_text = await extract_text_from_pdf_with_gemini(pdf_bytes)
        if not content_text or len(content_text) < 100:
            raise HTTPException(400, detail="Could not extract text from PDF. Ensure the PDF contains readable content.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, detail=f"Text extraction failed: {str(e)}")
    
    # Step 5: Delete old AI content
    try:
        await delete_ai_content_from_s3(standard, subject.name, chapter.name, "revision_notes", school_name=chapter.school_name)
        await delete_ai_content_from_s3(standard, subject.name, chapter.name, "flashcards", school_name=chapter.school_name)
        await delete_ai_content_from_s3(standard, subject.name, chapter.name, "practice_quiz", school_name=chapter.school_name)
    except Exception as e:
        logger.warning(f"⚠️ Could not delete old content: {e}")
    
    # Step 6: Clear cache
    try:
        from app.services.ai_service import clear_chapter_ai_cache
        await clear_chapter_ai_cache(subject.name, chapter.name)
        await db.execute(text("DELETE FROM ai_content_cache WHERE chapter_id = :chapter_id"), {"chapter_id": chapter_id})
    except:
        pass
    
    # Step 7: Set status to "processing" IMMEDIATELY
    chapter.ai_status = "processing"
    chapter.ai_generated = False
    chapter.ai_error_message = None
    await db.commit()
    
    logger.info(f"✅ Chapter {chapter_id} status set to 'processing'")
    
    # Step 8: Trigger background task using V2 orchestrator (production-grade)
    from app.services.ai_orchestrator_v2 import run_generation_background_task
    
    background_tasks.add_task(
        run_generation_background_task,
        chapter_id=chapter_id,
        subject_name=subject.name,
        chapter_name=chapter.name,
        content=content_text,
        standard=standard,
        school_name=chapter.school_name
    )
    
    logger.info(f"🚀 Background generation task scheduled for chapter {chapter_id} (V2 orchestrator)")
    
    # Return IMMEDIATELY (< 2 seconds)
    return {
        "success": True,
        "chapter_id": chapter_id,
        "ai_status": "processing",
        "message": "AI content generation started. This process will automatically retry until successful. Refresh to check status.",
        "details": {
            "chapter_name": chapter.name,
            "subject_name": subject.name,
            "content_length": len(content_text),
            "components": "7 (revision notes, flashcards, 5 quizzes with 15 questions each)",
            "total_questions": 75
        }
    }


@api_router.get("/teacher/chapter/{chapter_id}/ai-generation-status")
async def get_ai_generation_status(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """
    Check AI generation status for a chapter.
    Returns: pending, processing, completed, or failed
    """
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    status = getattr(chapter, 'ai_status', 'pending')
    error_msg = getattr(chapter, 'ai_error_message', None)
    retry_count = getattr(chapter, 'ai_retry_count', 0)
    
    # Build user-friendly status message
    status_message = {
        "pending": "AI content has not been generated yet.",
        "processing": f"AI content is being generated (attempt {retry_count}). This may take a few minutes.",
        "completed": "AI content is ready and available to students.",
        "failed": f"Generation in retry mode (attempt {retry_count}). The system will keep trying automatically."
    }.get(status, "Unknown status")
    
    return {
        "chapter_id": chapter_id,
        "ai_status": status,
        "ai_generated": chapter.ai_generated,
        "ai_generated_at": chapter.ai_generated_at.isoformat() if chapter.ai_generated_at else None,
        "ai_content_prefix": chapter.ai_content_prefix,
        "error_message": error_msg if status in ["failed", "processing"] else None,
        "retry_count": retry_count,
        "status_message": status_message,
        "components": {
            "revision_notes": True if chapter.ai_generated else False,
            "flashcards": True if chapter.ai_generated else False,
            "quizzes": 5 if chapter.ai_generated else 0,
            "total_questions": 75 if chapter.ai_generated else 0
        }
    }


@api_router.get("/teacher/chapter/{chapter_id}/ai-content-status")
async def get_ai_content_status(
    chapter_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Check if AI content exists for a chapter"""
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    subject_result = await db.execute(select(Subject).where(Subject.id == chapter.subject_id))
    subject = subject_result.scalars().first()
    
    # Check if textbook is uploaded (file exists in storage)
    content_result = await db.execute(
        select(Content).where(Content.chapter_id == chapter_id)
    )
    content = content_result.scalars().first()
    # After OCR refactoring, Gemini handles PDF natively - just check if content exists
    textbook_uploaded = content is not None and content.s3_url is not None
    
    # Read AI status directly from database
    return {
        "chapter_id": chapter_id,
        "chapter_name": chapter.name,
        "ai_content_exists": bool(chapter.ai_generated),  # Read from DB flag
        "ai_generated": bool(chapter.ai_generated),
        "ai_content_prefix": chapter.ai_content_prefix,
        "ai_generated_at": chapter.ai_generated_at.isoformat() if chapter.ai_generated_at else None,
        "textbook_uploaded": textbook_uploaded,
        "textbook_filename": content.file_name if content else None
    }


@api_router.get("/student/chapter/{chapter_id}/content/{content_type}")
async def get_student_content_readonly(
    chapter_id: str,
    content_type: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    STUDENT READ-ONLY: Fetch AI content from S3.
    NEVER triggers AI generation.
    
    STUDENT ACCESS LOCK:
    - Students only see content when ai_status == "completed"
    - Shows "Content generating, please wait" for processing
    - Shows error message for failed (admin-only details)
    """
    from app.services.storage_service import fetch_ai_content_from_s3
    
    # Verify chapter exists
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    subject_result = await db.execute(select(Subject).where(Subject.id == chapter.subject_id))
    subject = subject_result.scalars().first()
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    standard = chapter.standard
    
    # Validate content type
    valid_types = ['revision_notes', 'flashcards', 'quiz', 'pyq']
    if content_type not in valid_types:
        raise HTTPException(status_code=400, detail="Invalid content type")
    
    logger.info(f"📖 Student fetching {content_type} for {subject.name}/{chapter.name}")
    
    # Check ai_status for proper user messaging
    ai_status = getattr(chapter, 'ai_status', 'pending')
    retry_count = getattr(chapter, 'ai_retry_count', 0)
    
    # =========================================================================
    # STUDENT ACCESS LOCK: Only show content when status == "completed"
    # =========================================================================
    
    if ai_status == "processing":
        logger.info(f"⏳ AI content is being generated (attempt {retry_count})")
        return {
            "available": False,
            "ai_status": "processing",
            "message": "Content is being generated. Please wait and refresh in a few minutes.",
            "user_friendly_message": "📚 Content is being prepared for you. Please check back in a few minutes!"
        }
    
    if ai_status == "failed":
        # Note: With V2 orchestrator, this should be temporary as it keeps retrying
        logger.info(f"⚠️ AI content generation in retry mode (attempt {retry_count})")
        return {
            "available": False,
            "ai_status": "processing",  # Show as processing to students (not failed)
            "message": "Content is being generated. Please wait and refresh in a few minutes.",
            "user_friendly_message": "📚 Content is being prepared. Please check back shortly!"
        }
    
    if ai_status == "pending" or not chapter.ai_generated:
        logger.info("⚠️ AI content not generated yet")
        return {
            "available": False,
            "ai_status": "pending",
            "message": "Content not available yet. Your teacher needs to generate the study materials.",
            "user_friendly_message": "📖 Study materials are not ready yet. Please check back later!"
        }
    
    # Map API content_type to S3 file names
    s3_tool_map = {
        'revision_notes': 'revision_notes',
        'flashcards': 'flashcards',
        'quiz': 'practice_quiz',  # API uses 'quiz', S3 uses 'practice_quiz'
        'pyq': 'pyq'
    }
    s3_tool = s3_tool_map.get(content_type, content_type)
    
    # Fetch from S3
    try:
        content = await fetch_ai_content_from_s3(standard, subject.name, chapter.name, s3_tool, school_name=chapter.school_name)
        
        if content:
            logger.info("✅ Content served from S3")
            return {
                "available": True,
                "ai_status": "completed",
                "content": content,
                "chapter_name": chapter.name,
                "subject_name": subject.name
            }
        else:
            logger.warning("⚠️ ai_status=completed but content not in S3")
            return {
                "available": False,
                "ai_status": "completed",
                "message": "Content not available yet. Please check back later."
            }
    except Exception as e:
        logger.error(f"❌ Error fetching from S3: {e}")
        return {
            "available": False,
            "message": "Unable to load content. Please try again later."
        }


# ============================================================================
# NEW ENDPOINTS - Test Statistics & Leaderboard
# ============================================================================

@api_router.get("/teacher/test/{test_id}/statistics")
async def get_test_statistics(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Get test statistics: student names and marks in descending order"""
    try:
        # Verify test exists and belongs to teacher
        test_result = await db.execute(select(Test).where(Test.id == test_id))
        test = test_result.scalars().first()
        
        if not test:
            raise HTTPException(status_code=404, detail="Test not found")
        
        if test.created_by != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get all submissions for this test with student details
        query = select(
            TestSubmission,
            StudentProfile.name
        ).join(
            StudentProfile,
            TestSubmission.roll_no == StudentProfile.roll_no
        ).where(
            TestSubmission.test_id == test_id,
            TestSubmission.evaluated == True
        ).order_by(
            TestSubmission.total_score.desc()
        )
        
        result = await db.execute(query)
        submissions = result.all()
        
        statistics = []
        for submission, student_name in submissions:
            statistics.append({
                "student_name": student_name,
                "roll_no": submission.roll_no,
                "marks_scored": submission.total_score,
                "max_marks": submission.max_score,
                "percentage": submission.percentage,
                "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None
            })
        
        return {
            "test_id": test_id,
            "test_title": test.title,
            "subject": test.subject_id,
            "standard": test.standard,
            "total_submissions": len(statistics),
            "statistics": statistics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching test statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch statistics")


@api_router.get("/teacher/subject/{subject_id}/leaderboard")
async def get_subject_leaderboard(
    subject_id: str,
    standard: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """Get subject leaderboard: students ranked by average percentage with color coding"""
    try:
        # Verify subject exists
        subject_result = await db.execute(select(Subject).where(Subject.id == subject_id))
        subject = subject_result.scalars().first()
        
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        
        # Get all student performance records for this subject and standard
        query = select(
            StudentPerformance,
            StudentProfile.name
        ).join(
            StudentProfile,
            StudentPerformance.roll_no == StudentProfile.roll_no
        ).where(
            StudentPerformance.subject_id == subject_id,
            StudentPerformance.standard == standard
        ).order_by(
            StudentPerformance.average_percentage.desc()
        )
        
        result = await db.execute(query)
        records = result.all()
        
        leaderboard = []
        for performance, student_name in records:
            leaderboard.append({
                "student_name": student_name,
                "roll_no": performance.roll_no,
                "average_percentage": round(performance.average_percentage, 2),
                "total_tests_taken": performance.total_tests_taken,
                "classification": performance.classification,  # 'strong', 'average', 'weak'
                "last_test_date": performance.last_test_date.isoformat() if performance.last_test_date else None
            })
        
        return {
            "subject_id": subject_id,
            "subject_name": subject.name,
            "standard": standard,
            "total_students": len(leaderboard),
            "leaderboard": leaderboard
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch leaderboard")


# ============================================================================
# TEACHER ANALYTICS ENDPOINT
# ============================================================================

@api_router.get("/teacher/analytics/{standard}")
async def get_teacher_analytics(
    standard: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_teacher)
):
    """
    Comprehensive teacher analytics dashboard
    Returns:
    - Summary counts (strong/average/weak students)
    - Top 3 performers with subject-wise breakdown
    - All students performance table (roll no order, subject-wise %)
    """
    from sqlalchemy import func, and_, case
    
    # Get all subjects for this standard
    subjects_result = await db.execute(
        select(Subject).where(Subject.standard == standard).order_by(Subject.name)
    )
    subjects = subjects_result.scalars().all()
    subject_names = [s.name for s in subjects]
    
    # Get all students in this standard with their profiles
    students_result = await db.execute(
        select(StudentProfile).where(
            StudentProfile.standard == standard
        ).order_by(StudentProfile.roll_no)
    )
    students = students_result.scalars().all()
    
    if not students:
        return {
            "standard": standard,
            "subjects": subject_names,
            "summary": {
                "total_students": 0,
                "strong_count": 0,
                "average_count": 0,
                "weak_count": 0
            },
            "top_performers": [],
            "students": []
        }
    
    students_data = []
    strong_count = 0
    average_count = 0
    weak_count = 0
    
    for student_profile in students:
        student_data = {
            "roll_no": student_profile.roll_no,
            "student_name": student_profile.name,
            "subjects": {},
            "overall_average": 0,
            "overall_classification": "no_data"
        }
        
        total_percentage = 0
        subjects_with_data = 0
        
        # Get performance for each subject
        for subject in subjects:
            perf_result = await db.execute(
                select(StudentPerformance).where(
                    and_(
                        StudentPerformance.student_id == student_profile.user_id,
                        StudentPerformance.subject_id == subject.id
                    )
                )
            )
            performance = perf_result.scalars().first()
            
            if performance and performance.total_tests_taken > 0:
                student_data["subjects"][subject.name] = {
                    "percentage": performance.average_percentage,
                    "classification": performance.classification,
                    "total_tests": performance.total_tests_taken
                }
                total_percentage += performance.average_percentage
                subjects_with_data += 1
            else:
                student_data["subjects"][subject.name] = {
                    "percentage": 0,
                    "classification": "no_data",
                    "total_tests": 0
                }
        
        # Calculate overall average
        if subjects_with_data > 0:
            overall_avg = total_percentage / subjects_with_data
            student_data["overall_average"] = overall_avg
            
            # Overall classification
            if overall_avg >= 80:
                student_data["overall_classification"] = "strong"
                strong_count += 1
            elif overall_avg >= 60:
                student_data["overall_classification"] = "average"
                average_count += 1
            else:
                student_data["overall_classification"] = "weak"
                weak_count += 1
        
        students_data.append(student_data)
    
    # Get top 3 performers based on overall average
    top_performers = sorted(
        [s for s in students_data if s["overall_average"] > 0],
        key=lambda x: x["overall_average"],
        reverse=True
    )[:3]
    
    # Format top performers with subject-wise breakdown
    top_performers_formatted = []
    for performer in top_performers:
        subject_wise = []
        for subject_name in subject_names:
            if performer["subjects"][subject_name]["total_tests"] > 0:
                subject_wise.append({
                    "subject_name": subject_name,
                    "percentage": performer["subjects"][subject_name]["percentage"],
                    "classification": performer["subjects"][subject_name]["classification"]
                })
        
        top_performers_formatted.append({
            "roll_no": performer["roll_no"],
            "student_name": performer["student_name"],
            "overall_average": performer["overall_average"],
            "subject_wise_performance": subject_wise
        })
    
    return {
        "standard": standard,
        "subjects": subject_names,
        "summary": {
            "total_students": len(students),
            "strong_count": strong_count,
            "average_count": average_count,
            "weak_count": weak_count
        },
        "top_performers": top_performers_formatted,
        "students": students_data
    }


# ============================================================================
# REGISTER ALL ROUTES - MUST BE AT THE END
# ============================================================================
app.include_router(api_router)

# Register structured test routes
from app.routes.structured_tests import router as structured_tests_router
app.include_router(structured_tests_router, prefix="/api")

