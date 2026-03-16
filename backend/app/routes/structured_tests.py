"""
Structured Test API Routes
============================
New test creation flow with structured questions, AI evaluation, and teacher review.
"""

from fastapi import APIRouter, Depends, HTTPException, Cookie, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from datetime import datetime, timezone, timedelta
from typing import Optional
import json
import logging

from app.models.database import (
    get_db, User, Subject,
    StructuredTest, StructuredQuestion, StructuredTestSubmission, EvaluationResult
)
from app.services.auth_service import decode_jwt_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/structured-tests", tags=["structured-tests"])


# ============================================================================
# AUTH DEPENDENCY (self-contained, mirrors server.py)
# ============================================================================

async def get_current_user(
    token: Optional[str] = Cookie(None, alias="auth_token"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    auth_token = token
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


# ============================================================================
# TEACHER: CREATE & MANAGE TESTS
# ============================================================================

@router.post("")
async def create_and_publish_test(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Create a test with questions and publish it in one step. No drafts stored."""
    if user.role not in ('teacher', 'admin'):
        raise HTTPException(status_code=403, detail="Only teachers can create tests")
    
    # Parse deadline
    try:
        deadline = datetime.fromisoformat(data["submission_deadline"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Valid submission_deadline required (ISO format)")
    
    questions_data = data.get("questions", [])
    if not questions_data:
        raise HTTPException(status_code=400, detail="At least one question is required")
    
    # Calculate total marks
    total_marks = sum(q.get("max_marks", 0) for q in questions_data)
    
    # Create test directly as active (published)
    test = StructuredTest(
        subject_id=data.get("subject_id"),
        standard=data.get("standard"),
        title=data.get("title", "Untitled Test"),
        school_name=data.get("school_name"),
        created_by=user.id,
        total_marks=total_marks,
        duration_minutes=data.get("duration_minutes", 60),
        submission_deadline=deadline,
        status="active",
        question_count=len(questions_data)
    )
    db.add(test)
    await db.flush()  # get test.id without committing
    
    # Add questions
    for q in questions_data:
        question = StructuredQuestion(
            test_id=test.id,
            question_number=q.get("question_number"),
            question_type=q.get("question_type"),
            question_text=q.get("question_text"),
            max_marks=q.get("max_marks", 0),
            model_answer=q.get("model_answer"),
            evaluation_points=q.get("evaluation_points"),
            solution_steps=q.get("solution_steps"),
            objective_data=q.get("objective_data"),
        )
        db.add(question)
    
    await db.commit()
    await db.refresh(test)
    
    return {
        "id": test.id,
        "title": test.title,
        "status": test.status,
        "question_count": len(questions_data),
        "total_marks": total_marks,
        "message": "Test published! Students can now take it."
    }


@router.post("/{test_id}/questions")
async def add_questions(
    test_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Add or replace all questions for a test."""
    if user.role not in ('teacher', 'admin'):
        raise HTTPException(status_code=403, detail="Only teachers can add questions")
    
    test_result = await db.execute(select(StructuredTest).where(StructuredTest.id == test_id))
    test = test_result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    questions_data = data.get("questions", [])
    if not questions_data:
        raise HTTPException(status_code=400, detail="At least one question required")
    
    # Delete existing questions
    await db.execute(delete(StructuredQuestion).where(StructuredQuestion.test_id == test_id))
    
    total_marks = 0
    for i, q in enumerate(questions_data, 1):
        question = StructuredQuestion(
            test_id=test_id,
            question_number=q.get("question_number", i),
            question_type=q["question_type"],
            question_text=q["question_text"],
            max_marks=q["max_marks"],
            model_answer=q.get("model_answer"),
            objective_data=q.get("objective_data"),
            evaluation_points=q.get("evaluation_points"),
            solution_steps=q.get("solution_steps")
        )
        db.add(question)
        total_marks += q["max_marks"]
    
    test.total_marks = total_marks
    test.question_count = len(questions_data)
    
    await db.commit()
    
    return {
        "message": f"{len(questions_data)} questions saved",
        "total_marks": total_marks,
        "question_count": len(questions_data)
    }


@router.post("/{test_id}/publish")
async def publish_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Publish test (make it active for students)."""
    if user.role not in ('teacher', 'admin'):
        raise HTTPException(status_code=403, detail="Only teachers can publish tests")
    
    test_result = await db.execute(select(StructuredTest).where(StructuredTest.id == test_id))
    test = test_result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    if test.question_count == 0:
        raise HTTPException(status_code=400, detail="Add questions before publishing")
    
    test.status = "active"
    await db.commit()
    
    return {"message": "Test published", "status": "active"}


@router.get("/{test_id}")
async def get_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get test details with questions."""
    test_result = await db.execute(select(StructuredTest).where(StructuredTest.id == test_id))
    test = test_result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    questions_result = await db.execute(
        select(StructuredQuestion)
        .where(StructuredQuestion.test_id == test_id)
        .order_by(StructuredQuestion.question_number)
    )
    questions = questions_result.scalars().all()
    
    # For students, hide answers and evaluation criteria
    hide_answers = user.role == 'student'
    
    questions_list = []
    for q in questions:
        q_dict = {
            "id": q.id,
            "question_number": q.question_number,
            "question_type": q.question_type,
            "question_text": q.question_text,
            "max_marks": q.max_marks,
        }
        if not hide_answers:
            q_dict["model_answer"] = q.model_answer
            q_dict["objective_data"] = q.objective_data
            q_dict["evaluation_points"] = q.evaluation_points
            q_dict["solution_steps"] = q.solution_steps
        elif q.question_type == "mcq":
            # Students need MCQ options to answer
            obj = q.objective_data or {}
            q_dict["objective_data"] = {"options": obj.get("options", {})}
        elif q.question_type == "match_following":
            obj = q.objective_data or {}
            q_dict["objective_data"] = {"pairs_left": [p.get("left", "") for p in obj.get("pairs", [])]}
        
        questions_list.append(q_dict)
    
    return {
        "id": test.id,
        "title": test.title,
        "subject_id": test.subject_id,
        "standard": test.standard,
        "total_marks": test.total_marks,
        "duration_minutes": test.duration_minutes,
        "submission_deadline": test.submission_deadline.isoformat() if test.submission_deadline else None,
        "status": test.status,
        "question_count": test.question_count,
        "questions": questions_list
    }


@router.get("/list/{subject_id}/{standard}")
async def list_tests(
    subject_id: str,
    standard: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List published structured tests for a subject/standard."""
    query = select(StructuredTest).where(
        StructuredTest.subject_id == subject_id,
        StructuredTest.standard == standard,
        StructuredTest.status == 'active'
    )
    
    query = query.order_by(StructuredTest.created_at.desc())
    result = await db.execute(query)
    tests = result.scalars().all()
    
    tests_list = []
    for t in tests:
        # Check if student already submitted
        submission = None
        if user.role == 'student':
            sub_result = await db.execute(
                select(StructuredTestSubmission).where(
                    StructuredTestSubmission.test_id == t.id,
                    StructuredTestSubmission.student_id == user.id
                )
            )
            submission = sub_result.scalars().first()
        
        tests_list.append({
            "id": t.id,
            "title": t.title,
            "total_marks": t.total_marks,
            "duration_minutes": t.duration_minutes,
            "submission_deadline": t.submission_deadline.isoformat() if t.submission_deadline else None,
            "status": t.status,
            "question_count": t.question_count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "submitted": submission.submitted if submission else False,
            "score": submission.total_score if submission and submission.submitted else None,
            "percentage": submission.percentage if submission and submission.submitted else None,
        })
    
    return tests_list


# ============================================================================
# STUDENT: TAKE TEST & VIEW RESULTS
# ============================================================================

@router.post("/{test_id}/start")
async def start_test(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Student starts attempting a test."""
    if user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can start tests")
    
    test_result = await db.execute(select(StructuredTest).where(StructuredTest.id == test_id))
    test = test_result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    if test.status != 'active':
        raise HTTPException(status_code=400, detail="Test is not active")
    
    # Check existing submission
    sub_result = await db.execute(
        select(StructuredTestSubmission).where(
            StructuredTestSubmission.test_id == test_id,
            StructuredTestSubmission.student_id == user.id
        )
    )
    existing = sub_result.scalars().first()
    
    if existing and existing.submitted:
        raise HTTPException(status_code=400, detail="Test already submitted")
    
    if existing:
        return {"submission_id": existing.id, "started_at": existing.started_at.isoformat(), "message": "Test already started"}
    
    # Get roll_no
    from app.models.database import StudentProfile
    profile_result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == user.id))
    profile = profile_result.scalars().first()
    roll_no = profile.roll_no if profile else "unknown"
    
    submission = StructuredTestSubmission(
        test_id=test_id,
        student_id=user.id,
        roll_no=roll_no,
        started_at=datetime.now(timezone.utc)
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    
    return {"submission_id": submission.id, "started_at": submission.started_at.isoformat(), "message": "Test started"}


@router.post("/{test_id}/submit")
async def submit_test(
    test_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Submit test answers and trigger AI evaluation."""
    if user.role != 'student':
        raise HTTPException(status_code=403, detail="Only students can submit")
    
    # Get submission
    sub_result = await db.execute(
        select(StructuredTestSubmission).where(
            StructuredTestSubmission.test_id == test_id,
            StructuredTestSubmission.student_id == user.id
        )
    )
    submission = sub_result.scalars().first()
    if not submission:
        raise HTTPException(status_code=400, detail="Test not started")
    if submission.submitted:
        raise HTTPException(status_code=400, detail="Test already submitted")
    
    answers = data.get("answers", {})
    
    # Calculate time
    started = submission.started_at
    if started and started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    time_taken = (datetime.now(timezone.utc) - started).total_seconds() if started else 0
    
    # Save submission
    submission.submitted = True
    submission.submitted_at = datetime.now(timezone.utc)
    submission.time_taken_seconds = int(time_taken)
    submission.answers_json = answers
    submission.evaluation_status = "evaluating"
    await db.commit()
    
    # Load questions
    q_result = await db.execute(
        select(StructuredQuestion)
        .where(StructuredQuestion.test_id == test_id)
        .order_by(StructuredQuestion.question_number)
    )
    questions = q_result.scalars().all()
    
    questions_data = []
    for q in questions:
        questions_data.append({
            "id": q.id,
            "question_number": q.question_number,
            "question_type": q.question_type,
            "question_text": q.question_text,
            "max_marks": q.max_marks,
            "model_answer": q.model_answer,
            "objective_data": q.objective_data,
            "evaluation_points": q.evaluation_points,
            "solution_steps": q.solution_steps
        })
    
    # Run evaluation
    try:
        from app.services.evaluation_agent import evaluate_submission
        
        evaluation = await evaluate_submission(questions_data, answers)
        
        # Save summary to submission
        submission.total_score = evaluation["total_score"]
        submission.max_score = evaluation["max_score"]
        submission.percentage = evaluation["percentage"]
        submission.improvement_summary = evaluation.get("improvement_summary", "")
        submission.evaluation_status = "completed"
        submission.evaluated_at = datetime.now(timezone.utc)
        
        # Save detailed per-question results (TTL: 2 months)
        expires_at = datetime.now(timezone.utc) + timedelta(days=60)
        
        for qr in evaluation.get("question_results", []):
            er = EvaluationResult(
                submission_id=submission.id,
                question_id=qr.get("question_id", ""),
                question_number=qr["question_number"],
                student_answer=answers.get(str(qr["question_number"]), ""),
                marks_awarded=qr["marks_awarded"],
                max_marks=qr["max_marks"],
                feedback_json=qr.get("feedback_json"),
                verified=qr.get("verified", False),
                verification_notes=qr.get("verification_notes", ""),
                expires_at=expires_at
            )
            db.add(er)
        
        await db.commit()
        
        return {
            "message": "Test evaluated successfully",
            "total_score": evaluation["total_score"],
            "max_score": evaluation["max_score"],
            "percentage": evaluation["percentage"],
            "time_taken_minutes": round(time_taken / 60, 2),
            "question_results": evaluation["question_results"]
        }
    
    except Exception as e:
        logger.error(f"Evaluation failed for test {test_id}: {e}")
        submission.evaluation_status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.get("/{test_id}/results/{student_id}")
async def get_evaluation_results(
    test_id: str,
    student_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get detailed evaluation results for a student's submission."""
    # Students can only see their own results
    if user.role == 'student' and user.id != student_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    sub_result = await db.execute(
        select(StructuredTestSubmission).where(
            StructuredTestSubmission.test_id == test_id,
            StructuredTestSubmission.student_id == student_id
        )
    )
    submission = sub_result.scalars().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    # Get detailed results (if not expired)
    er_result = await db.execute(
        select(EvaluationResult)
        .where(
            EvaluationResult.submission_id == submission.id,
            EvaluationResult.expires_at > datetime.now(timezone.utc)
        )
        .order_by(EvaluationResult.question_number)
    )
    eval_results = er_result.scalars().all()
    
    # Get questions for context
    q_result = await db.execute(
        select(StructuredQuestion)
        .where(StructuredQuestion.test_id == test_id)
        .order_by(StructuredQuestion.question_number)
    )
    questions = {q.question_number: q for q in q_result.scalars().all()}
    
    results_list = []
    for er in eval_results:
        q = questions.get(er.question_number)
        results_list.append({
            "question_number": er.question_number,
            "question_text": q.question_text if q else "",
            "question_type": q.question_type if q else "",
            "student_answer": er.student_answer,
            "marks_awarded": er.teacher_marks if er.teacher_marks is not None else er.marks_awarded,
            "max_marks": er.max_marks,
            "feedback": er.feedback_json,
            "teacher_comment": er.teacher_comment,
            "verified": er.verified
        })
    
    return {
        "test_id": test_id,
        "student_id": student_id,
        "total_score": submission.teacher_final_score if submission.teacher_final_score is not None else submission.total_score,
        "max_score": submission.max_score,
        "percentage": submission.percentage,
        "improvement_summary": submission.improvement_summary,
        "teacher_reviewed": submission.teacher_reviewed,
        "evaluation_status": submission.evaluation_status,
        "detailed_results": results_list,
        "results_available": len(results_list) > 0,
        "retained_only": len(results_list) == 0 and submission.evaluation_status == "completed"
    }


# ============================================================================
# TEACHER: REVIEW & OVERRIDE
# ============================================================================

@router.get("/{test_id}/submissions")
async def get_test_submissions(
    test_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Teacher views all submissions for a test."""
    if user.role not in ('teacher', 'admin'):
        raise HTTPException(status_code=403, detail="Only teachers can view submissions")
    
    sub_result = await db.execute(
        select(StructuredTestSubmission)
        .where(StructuredTestSubmission.test_id == test_id)
        .order_by(StructuredTestSubmission.submitted_at)
    )
    submissions = sub_result.scalars().all()

    # Batch-fetch student names
    student_ids = [s.student_id for s in submissions if s.student_id]
    name_map = {}
    if student_ids:
        from app.models.database import StudentProfile
        profiles = await db.execute(
            select(StudentProfile).where(StudentProfile.user_id.in_(student_ids))
        )
        name_map = {p.user_id: p.name for p in profiles.scalars().all()}
    
    return [{
        "id": s.id,
        "student_id": s.student_id,
        "student_name": name_map.get(s.student_id, ""),
        "roll_no": s.roll_no,
        "submitted": s.submitted,
        "total_score": s.teacher_final_score if s.teacher_final_score is not None else s.total_score,
        "max_score": s.max_score,
        "percentage": s.percentage,
        "evaluation_status": s.evaluation_status,
        "teacher_reviewed": s.teacher_reviewed,
        "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None
    } for s in submissions]


@router.post("/{test_id}/review/{student_id}")
async def teacher_review(
    test_id: str,
    student_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Teacher reviews and optionally overrides AI grading."""
    if user.role not in ('teacher', 'admin'):
        raise HTTPException(status_code=403, detail="Only teachers can review")
    
    sub_result = await db.execute(
        select(StructuredTestSubmission).where(
            StructuredTestSubmission.test_id == test_id,
            StructuredTestSubmission.student_id == student_id
        )
    )
    submission = sub_result.scalars().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    overrides = data.get("overrides", [])
    # overrides: [{question_number: 1, marks: 3, comment: "..."}]
    
    new_total = submission.total_score or 0
    
    for override in overrides:
        q_num = override["question_number"]
        new_marks = override["marks"]
        comment = override.get("comment", "")
        
        er_result = await db.execute(
            select(EvaluationResult).where(
                EvaluationResult.submission_id == submission.id,
                EvaluationResult.question_number == q_num
            )
        )
        er = er_result.scalars().first()
        if er:
            diff = new_marks - er.marks_awarded
            new_total += diff
            er.teacher_marks = new_marks
            er.teacher_comment = comment
    
    submission.teacher_reviewed = True
    submission.teacher_reviewed_at = datetime.now(timezone.utc)
    submission.teacher_final_score = max(0, round(new_total, 2))
    
    # Recalculate percentage
    if submission.max_score and submission.max_score > 0:
        submission.percentage = round((submission.teacher_final_score / submission.max_score) * 100, 2)
    
    await db.commit()
    
    return {
        "message": "Review saved",
        "final_score": submission.teacher_final_score,
        "max_score": submission.max_score,
        "percentage": submission.percentage
    }


# ============================================================================
# CLEANUP: Delete expired evaluation details (retain summary)
# ============================================================================

async def _condense_and_cleanup(db):
    """
    Core retention logic:
    1. Find submissions whose EvaluationResults have expired
    2. Condense per-question feedback into a brief 1-2 sentence improvement summary
    3. Store summary in submission.improvement_summary (preserved permanently)
    4. Delete expired EvaluationResult rows
    5. Clear raw answers_json from old submissions (no longer needed)
    Returns count of deleted records.
    """
    # Find expired evaluation results grouped by submission
    expired = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.expires_at < datetime.now(timezone.utc))
        .order_by(EvaluationResult.submission_id, EvaluationResult.question_number)
    )
    expired_results = expired.scalars().all()
    if not expired_results:
        return 0

    # Group by submission_id
    sub_groups = {}
    for er in expired_results:
        sub_groups.setdefault(er.submission_id, []).append(er)

    # For each submission, condense feedback into brief summary
    for sub_id, results in sub_groups.items():
        sub_result = await db.execute(
            select(StructuredTestSubmission).where(StructuredTestSubmission.id == sub_id)
        )
        submission = sub_result.scalars().first()
        if not submission:
            continue

        # Build brief improvement summary from per-question feedback
        improvements = []
        for er in results:
            fb = er.feedback_json or {}
            suggestion = fb.get("improvement_suggestions", "")
            if suggestion and len(suggestion.strip()) > 5:
                improvements.append(suggestion.strip())

        if improvements:
            # Condense to 1-2 sentences max
            brief = ". ".join(improvements[:3])
            if len(brief) > 250:
                brief = brief[:247] + "..."
            # Only update if not already teacher-reviewed with a custom summary
            if not submission.improvement_summary or len(submission.improvement_summary) < 10:
                submission.improvement_summary = brief
            else:
                # Append condensed detail if existing summary is short
                existing = submission.improvement_summary.strip()
                if len(existing) < 200:
                    submission.improvement_summary = f"{existing} | {brief}"[:300]

        # Clear raw answers (no longer needed after detailed results expire)
        submission.answers_json = None

    # Delete all expired evaluation results
    delete_result = await db.execute(
        delete(EvaluationResult).where(EvaluationResult.expires_at < datetime.now(timezone.utc))
    )
    await db.commit()
    return delete_result.rowcount


@router.delete("/cleanup/expired")
async def cleanup_expired_evaluations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Manual trigger: Delete expired evaluation details, retain summaries."""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")

    deleted = await _condense_and_cleanup(db)
    return {"message": "Retention policy applied", "deleted": deleted}



# ============================================================================
# STUDENT PERFORMANCE DASHBOARD
# ============================================================================

@router.get("/student/performance")
async def get_student_performance(
    subject_id: str = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get performance dashboard data for the current student, optionally filtered by subject."""
    if user.role not in ('student', 'admin'):
        raise HTTPException(status_code=403, detail="Students only")
    
    # Get all completed submissions for this student
    subs_query = (
        select(StructuredTestSubmission)
        .where(
            StructuredTestSubmission.student_id == user.id,
            StructuredTestSubmission.submitted == True,
            StructuredTestSubmission.evaluation_status == 'completed'
        )
    )
    # If subject_id is provided, filter by joining with StructuredTest
    if subject_id:
        subs_query = subs_query.join(
            StructuredTest, StructuredTestSubmission.test_id == StructuredTest.id
        ).where(StructuredTest.subject_id == subject_id)
    
    subs_query = subs_query.order_by(StructuredTestSubmission.submitted_at.asc())
    subs_result = await db.execute(subs_query)
    submissions = subs_result.scalars().all()
    
    if not submissions:
        return {
            "total_tests": 0,
            "average_percentage": 0,
            "best_percentage": 0,
            "total_marks_earned": 0,
            "total_marks_possible": 0,
            "tests_timeline": [],
            "subject_breakdown": [],
            "question_type_stats": [],
            "recent_improvement": None
        }
    
    # Get test details for subject info
    test_ids = list(set(s.test_id for s in submissions))
    tests_result = await db.execute(
        select(StructuredTest).where(StructuredTest.id.in_(test_ids))
    )
    tests_map = {t.id: t for t in tests_result.scalars().all()}
    
    # Get subject names
    subject_ids = list(set(t.subject_id for t in tests_map.values()))
    subjects_result = await db.execute(
        select(Subject).where(Subject.id.in_(subject_ids))
    )
    subjects_map = {str(s.id): s.name for s in subjects_result.scalars().all()}
    
    # Build timeline data
    tests_timeline = []
    subject_scores = {}  # subject_id -> [percentages]
    total_earned = 0
    total_possible = 0
    
    for sub in submissions:
        test = tests_map.get(sub.test_id)
        if not test:
            continue
        
        subject_name = subjects_map.get(str(test.subject_id), "Unknown")
        pct = sub.percentage or 0
        
        tests_timeline.append({
            "test_title": test.title,
            "subject": subject_name,
            "date": sub.submitted_at.isoformat() if sub.submitted_at else sub.created_at.isoformat(),
            "score": sub.total_score or 0,
            "max_score": sub.max_score or 0,
            "percentage": round(pct, 1),
        })
        
        if subject_name not in subject_scores:
            subject_scores[subject_name] = []
        subject_scores[subject_name].append(pct)
        
        total_earned += (sub.total_score or 0)
        total_possible += (sub.max_score or 0)
    
    # Subject breakdown
    subject_breakdown = []
    for subj, scores in subject_scores.items():
        subject_breakdown.append({
            "subject": subj,
            "tests_taken": len(scores),
            "average_percentage": round(sum(scores) / len(scores), 1),
            "best_percentage": round(max(scores), 1),
            "latest_percentage": round(scores[-1], 1),
        })
    subject_breakdown.sort(key=lambda x: x["average_percentage"], reverse=True)
    
    # Question type analysis from evaluation results
    question_type_stats = []
    for sub in submissions:
        er_result = await db.execute(
            select(EvaluationResult)
            .where(EvaluationResult.submission_id == sub.id)
        )
        eval_results = er_result.scalars().all()
        
        # Get questions for type info
        q_result = await db.execute(
            select(StructuredQuestion)
            .where(StructuredQuestion.test_id == sub.test_id)
        )
        q_map = {q.question_number: q for q in q_result.scalars().all()}
        
        for er in eval_results:
            q = q_map.get(er.question_number)
            if not q:
                continue
            question_type_stats.append({
                "type": q.question_type,
                "marks_awarded": er.marks_awarded,
                "max_marks": er.max_marks,
            })
    
    # Aggregate question type stats
    type_agg = {}
    for stat in question_type_stats:
        t = stat["type"]
        if t not in type_agg:
            type_agg[t] = {"earned": 0, "possible": 0, "count": 0}
        type_agg[t]["earned"] += stat["marks_awarded"]
        type_agg[t]["possible"] += stat["max_marks"]
        type_agg[t]["count"] += 1
    
    qt_breakdown = []
    for t, agg in type_agg.items():
        pct = round((agg["earned"] / agg["possible"]) * 100, 1) if agg["possible"] > 0 else 0
        qt_breakdown.append({
            "type": t,
            "questions_attempted": agg["count"],
            "accuracy_percentage": pct,
        })
    qt_breakdown.sort(key=lambda x: x["accuracy_percentage"], reverse=True)
    
    # Recent improvement (compare last 2 tests)
    percentages = [t["percentage"] for t in tests_timeline]
    recent_improvement = None
    if len(percentages) >= 2:
        recent_improvement = round(percentages[-1] - percentages[-2], 1)
    
    avg_pct = round(sum(percentages) / len(percentages), 1) if percentages else 0
    best_pct = round(max(percentages), 1) if percentages else 0
    
    return {
        "total_tests": len(submissions),
        "average_percentage": avg_pct,
        "best_percentage": best_pct,
        "total_marks_earned": round(total_earned, 1),
        "total_marks_possible": round(total_possible, 1),
        "tests_timeline": tests_timeline,
        "subject_breakdown": subject_breakdown,
        "question_type_stats": qt_breakdown,
        "recent_improvement": recent_improvement,
    }
