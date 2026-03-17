"""Parent dashboard & teacher routes: analytics, study materials, leaderboard."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, and_, desc, distinct, text, String
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
import logging
import json
import uuid
import httpx
import os

from app.models.database import (
    get_db, User, Subject, Chapter, StudentProfile,
    StudentPerformance, StudentExamScore, StudentPracticeProgress,
    StructuredTest, StructuredTestSubmission, AsyncSessionLocal,
    Content, HomeworkSubmission, StudyMaterial, Test, TestQuestion,
    StructuredHomework, StructuredHomeworkSubmission
)
from app.deps import (
    get_current_user, require_teacher, require_admin,
    get_user_school, OPENROUTER_API_KEY
)

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# PARENT DASHBOARD ENDPOINT (DB METADATA ONLY - NO S3 READS)
# =============================================================================

@router.get("/student/parent-dashboard")
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
    
    # 2. Get Test Performance (from AI-evaluated tests only)
    subject_id_to_name = {str(s.id): s.name for s in subjects}
    subject_scores = {}
    
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
    
    # 4. Get Homework Stats (from HomeworkSubmission + StructuredHomeworkSubmission)
    for subject_name in subject_data:
        subject_id = subject_data[subject_name]["subject_id"]
        
        # Old PDF homework stats
        total_hw_result = await db.execute(
            select(func.count(HomeworkSubmission.id)).where(
                HomeworkSubmission.student_id == user.id,
                HomeworkSubmission.subject_name == subject_name,
                HomeworkSubmission.standard == standard
            )
        )
        total_hw = total_hw_result.scalar() or 0
        
        submitted_hw_result = await db.execute(
            select(func.count(HomeworkSubmission.id)).where(
                HomeworkSubmission.student_id == user.id,
                HomeworkSubmission.subject_name == subject_name,
                HomeworkSubmission.standard == standard,
                HomeworkSubmission.submitted.is_(True)
            )
        )
        submitted_hw = submitted_hw_result.scalar() or 0
        
        # AI Homework stats
        ai_hw_result = await db.execute(
            select(func.count(StructuredHomework.id)).where(
                StructuredHomework.subject_id == subject_id,
                StructuredHomework.standard == standard,
            )
        )
        total_ai_hw = ai_hw_result.scalar() or 0
        
        completed_ai_hw_result = await db.execute(
            select(func.count(StructuredHomeworkSubmission.id)).where(
                StructuredHomeworkSubmission.student_id == user.id,
                StructuredHomeworkSubmission.completed.is_(True),
                StructuredHomeworkSubmission.homework_id.in_(
                    select(StructuredHomework.id).where(
                        StructuredHomework.subject_id == subject_id,
                        StructuredHomework.standard == standard,
                    )
                )
            )
        )
        completed_ai_hw = completed_ai_hw_result.scalar() or 0
        
        # Combined totals
        combined_total = total_hw + total_ai_hw
        combined_completed = submitted_hw + completed_ai_hw
        completion_pct = (combined_completed / combined_total * 100) if combined_total > 0 else 0
        
        subject_data[subject_name]["homework_stats"] = {
            "total_assigned": combined_total,
            "submitted": combined_completed,
            "completion_percentage": round(completion_pct, 1),
            "pdf_homework": total_hw,
            "ai_homework": total_ai_hw,
            "ai_homework_completed": completed_ai_hw,
        }
        
        # Get missed PDF homework (not submitted)
        missed_hw_result = await db.execute(
            select(HomeworkSubmission).where(
                HomeworkSubmission.student_id == user.id,
                HomeworkSubmission.subject_name == subject_name,
                HomeworkSubmission.standard == standard,
                HomeworkSubmission.submitted.is_(False)
            ).order_by(HomeworkSubmission.homework_upload_date.desc())
        )
        missed_hw = missed_hw_result.scalars().all()
        
        # Get pending AI homework (not completed)
        pending_ai_hw_result = await db.execute(
            select(StructuredHomework).where(
                StructuredHomework.subject_id == subject_id,
                StructuredHomework.standard == standard,
                StructuredHomework.status == 'active',
                ~StructuredHomework.id.in_(
                    select(StructuredHomeworkSubmission.homework_id).where(
                        StructuredHomeworkSubmission.student_id == user.id,
                        StructuredHomeworkSubmission.completed.is_(True),
                    )
                )
            ).order_by(StructuredHomework.deadline.desc())
        )
        pending_ai_hw = pending_ai_hw_result.scalars().all()
        
        subject_data[subject_name]["missed_homework"] = [
            {
                "homework_title": hw.homework_title,
                "due_date": hw.homework_upload_date.isoformat() if hw.homework_upload_date else None,
                "type": "pdf"
            }
            for hw in missed_hw
        ] + [
            {
                "homework_title": hw.title,
                "due_date": hw.deadline.isoformat() if hw.deadline else None,
                "type": "ai"
            }
            for hw in pending_ai_hw
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


@router.get("/tests/{test_id}/questions")
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


# =============================================================================

class CreateStudyMaterialRequest(BaseModel):
    chapter_id: str
    material_type: str  # 'solved_problems', 'notes', 'reference', 'worksheet'
    title: str


@router.post("/chapters/{chapter_id}/study-materials")
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


@router.get("/chapters/{chapter_id}/study-materials")
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




@router.get("/study-materials/{material_id}/download-url")
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

@router.delete("/study-materials/{material_id}")
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

@router.post("/teacher/content/upload")
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


@router.post("/teacher/chapter/{chapter_id}/regenerate-ai-content")
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


@router.get("/teacher/chapter/{chapter_id}/ai-generation-status")
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


@router.get("/teacher/chapter/{chapter_id}/ai-content-status")
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


@router.get("/student/chapter/{chapter_id}/content/{content_type}")
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



@router.get("/teacher/subject/{subject_id}/leaderboard")
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

@router.get("/teacher/analytics/{standard}")
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
