"""Content routes: subjects, chapters, PYQs, student learning."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, and_, desc, text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
import logging
import json
import uuid
import httpx
import os
import asyncio

from app.models.database import (
    get_db, User, Subject, Chapter, Test, TestQuestion,
    StudentProfile, StudentPerformance, StudentExamScore,
    StudentPracticeProgress, StudentHomeworkStatus, AsyncSessionLocal,
    PreviousYearPaper, AICache, Content,
    StructuredTest, StructuredTestSubmission,
    StructuredHomework, StructuredHomeworkSubmission
)
from app.deps import (
    get_current_user, get_optional_user, require_teacher, require_admin,
    get_user_school, OPENROUTER_API_KEY
)
from app.schemas import (
    CreateStudentProfileRequest, StudentExamScoreRequest,
    StudentPracticeProgressRequest, CreateSubjectRequest,
    UpdateSubjectRequest, CreateChapterRequest, GenerateContentRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/student/profile")
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

@router.get("/student/profile")
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

@router.post("/student/exam-score")
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

@router.get("/student/exam-scores")
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

@router.post("/student/practice-progress")
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

@router.get("/student/practice-progress")
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

@router.get("/student/progress-summary")
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

@router.get("/teacher/students")
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

@router.get("/teacher/student/{roll_no}/progress")
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

@router.post("/teacher/student/{roll_no}/exam-score")
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
@router.get("/subjects")
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
        
        # Calculate syllabus completion for students based on quiz, test, and homework completion
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
                    # 1. Practice quizzes completed (5 per chapter)
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
                    total_quizzes = total_chapters * 5
                    quiz_pct = (quizzes_completed / total_quizzes * 100) if total_quizzes > 0 else 0
                    
                    # 2. Structured tests completed
                    total_tests_result = await db.execute(
                        select(func.count(StructuredTest.id)).where(
                            StructuredTest.subject_id == s.id,
                            StructuredTest.standard == s.standard,
                        )
                    )
                    total_tests = total_tests_result.scalar() or 0
                    
                    completed_tests_result = await db.execute(
                        select(func.count(StructuredTestSubmission.id)).where(
                            StructuredTestSubmission.student_id == user.id,
                            StructuredTestSubmission.submitted == True,
                            StructuredTestSubmission.test_id.in_(
                                select(StructuredTest.id).where(
                                    StructuredTest.subject_id == s.id,
                                    StructuredTest.standard == s.standard,
                                )
                            )
                        )
                    )
                    completed_tests = completed_tests_result.scalar() or 0
                    test_pct = (completed_tests / total_tests * 100) if total_tests > 0 else 0
                    
                    # 3. Structured homework completed
                    total_hw_result = await db.execute(
                        select(func.count(StructuredHomework.id)).where(
                            StructuredHomework.subject_id == s.id,
                            StructuredHomework.standard == s.standard,
                        )
                    )
                    total_hw = total_hw_result.scalar() or 0
                    
                    completed_hw_result = await db.execute(
                        select(func.count(StructuredHomeworkSubmission.id)).where(
                            StructuredHomeworkSubmission.student_id == user.id,
                            StructuredHomeworkSubmission.completed == True,
                            StructuredHomeworkSubmission.homework_id.in_(
                                select(StructuredHomework.id).where(
                                    StructuredHomework.subject_id == s.id,
                                    StructuredHomework.standard == s.standard,
                                )
                            )
                        )
                    )
                    completed_hw = completed_hw_result.scalar() or 0
                    hw_pct = (completed_hw / total_hw * 100) if total_hw > 0 else 0
                    
                    # Combined weighted average: quizzes 40%, tests 35%, homework 25%
                    has_quizzes = total_quizzes > 0
                    has_tests = total_tests > 0
                    has_hw = total_hw > 0
                    
                    # Dynamically weight based on what content exists
                    weights = []
                    pcts = []
                    if has_quizzes:
                        weights.append(0.4)
                        pcts.append(quiz_pct)
                    if has_tests:
                        weights.append(0.35)
                        pcts.append(test_pct)
                    if has_hw:
                        weights.append(0.25)
                        pcts.append(hw_pct)
                    
                    if weights:
                        total_weight = sum(weights)
                        subject_data["syllabus_complete_percent"] = round(
                            sum(w * p for w, p in zip(weights, pcts)) / total_weight
                        )
                    else:
                        subject_data["syllabus_complete_percent"] = 0
        
        subjects_data.append(subject_data)
    
    return subjects_data

@router.post("/subjects")
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

@router.put("/subjects/{subject_id}")
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

@router.delete("/subjects/{subject_id}")
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
@router.get("/subjects/{subject_id}/chapters")
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

@router.post("/chapters")
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

@router.put("/chapters/{chapter_id}")
async def update_chapter(chapter_id: str, name: str = Form(...), db: AsyncSession = Depends(get_db), user: User = Depends(require_teacher)):
    result = await db.execute(select(Chapter).where(Chapter.id == chapter_id))
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    chapter.name = name
    await db.commit()
    return {"id": str(chapter.id), "name": chapter.name}

@router.delete("/chapters/{chapter_id}")
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
@router.put("/chapters/{chapter_id}/video")
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

@router.get("/chapters/{chapter_id}/video")
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

@router.get("/chapters/{chapter_id}/content-status")
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

@router.post("/content/upload")
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


@router.post("/chapter/{chapter_id}/generate-ai-content")
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
@router.post("/subjects/{subject_id}/upload-pyq")
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
    from app.services.storage_service import s3_client, S3_BUCKET, upload_pyq_questions_to_s3, normalize_title, sanitize_component, sanitize_school_name
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



@router.get("/pyq/{pyq_id}/extraction-status")
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

@router.get("/subjects/{subject_id}/pyqs")
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


@router.post("/pyq/{pyq_id}/generate-solutions")
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

@router.post("/pyq/{pyq_id}/generate-solution")
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




@router.get("/pyq/{pyq_id}/questions")
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


@router.get("/pyq/{pyq_id}/solution")
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


@router.post("/subject/{subject_id}/frequently-asked-pyqs")
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


@router.delete("/pyq/{pyq_id}")
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


@router.post("/student/generate-content")
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
@router.post("/student/flashcard-rating")
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

@router.get("/student/flashcard-ratings/{chapter_id}")
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

@router.post("/student/quiz-explanation")
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

@router.post("/student/submit-quiz")
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

@router.get("/student/quiz-performance/{chapter_id}")
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


@router.get("/student/classification/{subject_id}")
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
@router.post("/translate")
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

@router.post("/translate/content")
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

@router.post("/translate/batch")
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

@router.get("/")
async def api_root():
    return {"message": "StudyBuddy API", "status": "running"}


# =============================================================================
# HOMEWORK ENDPOINTS
# =============================================================================
