"""Auth & Admin routes."""
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, desc
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime, timezone
import logging

from app.models.database import (
    get_db, User, StudentProfile, StudentExamScore,
    StudentPracticeProgress, StudentHomeworkStatus, AsyncSessionLocal
)
from app.services.auth_service import get_or_create_user, create_jwt_token, decode_jwt_token
from app.deps import get_current_user, require_admin, hash_password, verify_password, get_user_school, ADMIN_USERNAME, ADMIN_PASSWORD
from app.schemas import (
    AdminLoginRequest,
    AdminRegisterStudentRequest, AdminBulkRegisterRequest,
    AdminResetPasswordRequest, AdminImpersonateRequest,
    RollNoLoginRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Auth Routes

class PasswordLoginRequest(BaseModel):
    phone: str
    password: str

@router.post("/auth/login-password")
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
        raise HTTPException(status_code=401, detail="Password login not enabled for this account.")
    
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

@router.get("/auth/me")
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

@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(
        "auth_token",
        path="/",
        httponly=True,
        samesite="None",
        secure=True
    )
    return {"message": "Logged out successfully"}

# =============================================================================
# ADMIN AUTHENTICATION & MANAGEMENT ROUTES
# =============================================================================

@router.post("/admin/login")
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

@router.post("/admin/register-student")
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

@router.post("/admin/bulk-register")
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

@router.get("/admin/users")
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

@router.put("/admin/user/{user_id}/toggle-active")
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

@router.delete("/admin/user/{user_id}")
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

@router.post("/admin/reset-password")
async def admin_reset_password(
    request: AdminResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin: Reset any user's password by roll_no"""
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

@router.post("/admin/impersonate")
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

@router.get("/admin/search-user/{roll_no}")
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


@router.put("/admin/update-user/{roll_no}")
async def admin_update_user(
    roll_no: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin: Update any user's profile details by roll_no"""
    body = await request.json()

    profile_result = await db.execute(
        select(StudentProfile).where(StudentProfile.roll_no == roll_no)
    )
    profile = profile_result.scalars().first()
    if not profile:
        raise HTTPException(status_code=404, detail=f"User with roll no '{roll_no}' not found")

    user_result = await db.execute(select(User).where(User.id == profile.user_id))
    user = user_result.scalars().first()

    # Updatable profile fields
    for field in ["name", "school_name", "email", "login_phone", "parent_phone", "gender"]:
        if field in body and body[field] is not None:
            setattr(profile, field, body[field])

    if "standard" in body:
        profile.standard = int(body["standard"]) if body["standard"] else None

    # Update role on User table
    if "role" in body and body["role"] in ("student", "teacher"):
        user.role = body["role"]

    # Update active status
    if "is_active" in body and user:
        user.is_active = bool(body["is_active"])

    profile.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return {
        "message": f"User '{roll_no}' updated successfully",
        "user": {
            "user_id": str(user.id),
            "name": profile.name,
            "roll_no": profile.roll_no,
            "standard": profile.standard,
            "school_name": profile.school_name,
            "role": user.role,
            "is_active": user.is_active,
            "phone": user.phone,
            "login_phone": profile.login_phone,
            "parent_phone": profile.parent_phone,
            "email": profile.email,
            "gender": profile.gender,
        }
    }


# =============================================================================
# SCHOOL MANAGEMENT ROUTES
# =============================================================================

@router.get("/schools/list")
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

@router.post("/auth/login")
async def login_with_rollno(
    request: RollNoLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """Login using roll_no and password"""
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


# =============================================================================
# STUDENT PROFILE ROUTES
# =============================================================================
