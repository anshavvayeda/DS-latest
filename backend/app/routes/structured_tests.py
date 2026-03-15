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
async def create_structured_test(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Create a new structured test."""
    if user.role not in ('teacher', 'admin'):
        raise HTTPException(status_code=403, detail="Only teachers can create tests")
    
    # Parse deadline
    try:
        deadline = datetime.fromisoformat(data["submission_deadline"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Valid submission_deadline required (ISO format)")
    
    test = StructuredTest(
        subject_id=data.get("subject_id"),
        standard=data.get("standard"),
        title=data.get("title", "Untitled Test"),
        school_name=data.get("school_name"),
        created_by=user.id,
        total_marks=data.get("total_marks", 0),
        duration_minutes=data.get("duration_minutes", 60),
        submission_deadline=deadline,
        status="draft"
    )
    db.add(test)
    await db.commit()
    await db.refresh(test)
    
    return {
        "id": test.id,
        "title": test.title,
        "status": test.status,
        "message": "Test created. Add questions next."
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
    """List structured tests for a subject/standard."""
    query = select(StructuredTest).where(
        StructuredTest.subject_id == subject_id,
        StructuredTest.standard == standard
    )
    
    if user.role == 'student':
        query = query.where(StructuredTest.status == 'active')
    
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
        
        # Save detailed per-question results (TTL: 1 month)
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
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
        "results_available": len(results_list) > 0
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
    
    return [{
        "id": s.id,
        "student_id": s.student_id,
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
# CLEANUP: Delete expired evaluation details
# ============================================================================

@router.delete("/cleanup/expired")
async def cleanup_expired_evaluations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Delete evaluation details older than 1 month. Scores are preserved."""
    if user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    result = await db.execute(
        delete(EvaluationResult).where(EvaluationResult.expires_at < datetime.now(timezone.utc))
    )
    await db.commit()
    
    return {"message": f"Cleaned up expired evaluation records", "deleted": result.rowcount}
