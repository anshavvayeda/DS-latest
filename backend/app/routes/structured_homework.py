"""Structured Homework routes: create, publish, solve with AI hints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, and_, desc
from datetime import datetime, timezone
from typing import Optional
import logging
import json
import httpx
import os

from app.models.database import (
    get_db, User, Subject, StudentProfile,
    StructuredHomework, StructuredHomeworkQuestion, StructuredHomeworkSubmission,
    AsyncSessionLocal
)
from app.deps import get_current_user, require_teacher, get_user_school, OPENROUTER_API_KEY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/structured-homework", tags=["structured-homework"])

OBJECTIVE_TYPES = ['mcq', 'true_false', 'fill_blank', 'one_word', 'match_following']


# ===== TEACHER: Create & Publish =====

@router.post("")
async def create_homework(data: dict, db: AsyncSession = Depends(get_db), user: User = Depends(require_teacher)):
    """Create homework with questions in one shot (Save & Publish)."""
    school_name = await get_user_school(user, db)

    questions_data = data.get("questions", [])
    if not questions_data:
        raise HTTPException(status_code=400, detail="At least one question required")

    hw = StructuredHomework(
        subject_id=data["subject_id"],
        standard=data["standard"],
        title=data["title"],
        school_name=school_name,
        created_by=user.id,
        deadline=datetime.fromisoformat(data["deadline"].replace("Z", "+00:00")),
        status="active",
        question_count=len(questions_data),
    )
    db.add(hw)
    await db.flush()

    for q in questions_data:
        qn = StructuredHomeworkQuestion(
            homework_id=hw.id,
            question_number=q["question_number"],
            question_type=q["question_type"],
            question_text=q["question_text"],
            model_answer=q.get("model_answer"),
            objective_data=q.get("objective_data"),
            evaluation_points=q.get("evaluation_points"),
            solution_steps=q.get("solution_steps"),
        )
        db.add(qn)

    await db.commit()
    logger.info(f"Homework '{hw.title}' created with {hw.question_count} questions by {user.id}")
    return {"id": hw.id, "title": hw.title, "question_count": hw.question_count, "status": "active"}


@router.get("/list/{subject_id}/{standard}")
async def list_homework(subject_id: str, standard: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """List active homework for a subject/standard."""
    school_name = await get_user_school(user, db)

    query = select(StructuredHomework).where(
        and_(
            StructuredHomework.subject_id == subject_id,
            StructuredHomework.standard == standard,
            StructuredHomework.status == 'active',
        )
    )
    if school_name:
        from sqlalchemy import or_
        query = query.where(or_(StructuredHomework.school_name == school_name, StructuredHomework.school_name.is_(None)))
    query = query.order_by(desc(StructuredHomework.created_at))

    result = await db.execute(query)
    hw_list = result.scalars().all()

    # Get submission status for students
    items = []
    for hw in hw_list:
        item = {
            "id": hw.id,
            "title": hw.title,
            "question_count": hw.question_count,
            "deadline": hw.deadline.isoformat() if hw.deadline else None,
            "created_at": hw.created_at.isoformat() if hw.created_at else None,
            "status": hw.status,
            "completed": False,
            "started": False,
        }
        if user.role == 'student':
            sub_result = await db.execute(
                select(StructuredHomeworkSubmission).where(
                    and_(
                        StructuredHomeworkSubmission.homework_id == hw.id,
                        StructuredHomeworkSubmission.student_id == user.id,
                    )
                ).order_by(desc(StructuredHomeworkSubmission.created_at)).limit(1)
            )
            sub = sub_result.scalar_one_or_none()
            if sub:
                item["completed"] = sub.completed
                item["started"] = True
        items.append(item)

    return {"homework": items}


@router.get("/{homework_id}")
async def get_homework(homework_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Get homework with questions (hides answers for students)."""
    result = await db.execute(select(StructuredHomework).where(StructuredHomework.id == homework_id))
    hw = result.scalar_one_or_none()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")

    q_result = await db.execute(
        select(StructuredHomeworkQuestion)
        .where(StructuredHomeworkQuestion.homework_id == homework_id)
        .order_by(StructuredHomeworkQuestion.question_number)
    )
    questions = q_result.scalars().all()

    q_list = []
    for q in questions:
        qd = {
            "id": q.id,
            "question_number": q.question_number,
            "question_type": q.question_type,
            "question_text": q.question_text,
        }
        # For MCQ/match — include options but not correct answer
        if q.question_type == 'mcq' and q.objective_data:
            qd["options"] = q.objective_data.get("options", {})
        elif q.question_type == 'match_following' and q.objective_data:
            qd["pairs_left"] = [p["left"] for p in q.objective_data.get("pairs", [])]
            qd["pairs_right"] = [p["right"] for p in q.objective_data.get("pairs", [])]
        elif q.question_type == 'true_false':
            qd["options"] = {"a": "True", "b": "False"}

        # Teacher can see answers
        if user.role == 'teacher' or user.role == 'admin':
            qd["model_answer"] = q.model_answer
            qd["objective_data"] = q.objective_data
            qd["evaluation_points"] = q.evaluation_points
            qd["solution_steps"] = q.solution_steps

        q_list.append(qd)

    return {
        "id": hw.id,
        "title": hw.title,
        "deadline": hw.deadline.isoformat() if hw.deadline else None,
        "question_count": hw.question_count,
        "questions": q_list,
    }


@router.post("/{homework_id}/start")
async def start_homework(homework_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Start or resume homework attempt."""
    result = await db.execute(select(StructuredHomework).where(StructuredHomework.id == homework_id))
    hw = result.scalar_one_or_none()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")

    # Check if already submitted (order by created_at desc, limit 1 to get latest)
    sub_result = await db.execute(
        select(StructuredHomeworkSubmission).where(
            and_(
                StructuredHomeworkSubmission.homework_id == homework_id,
                StructuredHomeworkSubmission.student_id == user.id,
            )
        ).order_by(desc(StructuredHomeworkSubmission.created_at)).limit(1)
    )
    sub = sub_result.scalar_one_or_none()
    if sub and sub.completed:
        raise HTTPException(status_code=400, detail="Homework already completed")

    if not sub:
        # Get roll_no
        profile_result = await db.execute(select(StudentProfile).where(StudentProfile.user_id == user.id))
        profile = profile_result.scalar_one_or_none()
        roll_no = profile.roll_no if profile else "unknown"

        sub = StructuredHomeworkSubmission(
            homework_id=homework_id,
            student_id=user.id,
            roll_no=roll_no,
            started_at=datetime.now(timezone.utc),
            answers_json={},
            hints_json={},
        )
        db.add(sub)
        await db.commit()

    return {
        "submission_id": sub.id,
        "started_at": sub.started_at.isoformat() if sub.started_at else None,
        "answers": sub.answers_json or {},
        "hints": sub.hints_json or {},
    }


@router.post("/{homework_id}/save-progress")
async def save_progress(homework_id: str, data: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Save partial answers as student works through homework."""
    sub_result = await db.execute(
        select(StructuredHomeworkSubmission).where(
            and_(
                StructuredHomeworkSubmission.homework_id == homework_id,
                StructuredHomeworkSubmission.student_id == user.id,
            )
        ).order_by(desc(StructuredHomeworkSubmission.created_at)).limit(1)
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Start homework first")
    if sub.completed:
        raise HTTPException(status_code=400, detail="Homework already completed")

    sub.answers_json = data.get("answers", sub.answers_json)
    sub.hints_json = data.get("hints", sub.hints_json)
    await db.commit()
    return {"status": "saved"}


@router.post("/{homework_id}/hint")
async def get_hint(homework_id: str, data: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Get AI hint for a specific question. First call: hint. Second call: reveal answer."""
    question_number = data.get("question_number")
    student_answer = data.get("student_answer", "")

    # Get the question
    q_result = await db.execute(
        select(StructuredHomeworkQuestion).where(
            and_(
                StructuredHomeworkQuestion.homework_id == homework_id,
                StructuredHomeworkQuestion.question_number == question_number,
            )
        )
    )
    question = q_result.scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Get submission to check hint history (order by created_at desc to get latest)
    sub_result = await db.execute(
        select(StructuredHomeworkSubmission).where(
            and_(
                StructuredHomeworkSubmission.homework_id == homework_id,
                StructuredHomeworkSubmission.student_id == user.id,
            )
        ).order_by(desc(StructuredHomeworkSubmission.created_at)).limit(1)
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=400, detail="Start homework first")

    hints = sub.hints_json or {}
    q_key = str(question_number)
    q_hints = hints.get(q_key, {"hint_used": False, "answer_revealed": False})

    # Determine correct answer
    correct_answer = _get_correct_answer(question)

    if q_hints.get("answer_revealed"):
        # Already revealed — return the answer again
        return {"type": "answer", "content": correct_answer}

    if q_hints.get("hint_used"):
        # Second request → reveal the answer
        q_hints["answer_revealed"] = True
        hints[q_key] = q_hints
        sub.hints_json = hints
        await db.commit()
        return {"type": "answer", "content": correct_answer}

    # First request → generate AI hint
    hint_text = await _generate_hint(question, student_answer)
    q_hints["hint_used"] = True
    hints[q_key] = q_hints
    sub.hints_json = hints
    await db.commit()
    return {"type": "hint", "content": hint_text}


@router.post("/{homework_id}/complete")
async def complete_homework(homework_id: str, data: dict, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Mark homework as complete."""
    sub_result = await db.execute(
        select(StructuredHomeworkSubmission).where(
            and_(
                StructuredHomeworkSubmission.homework_id == homework_id,
                StructuredHomeworkSubmission.student_id == user.id,
            )
        ).order_by(desc(StructuredHomeworkSubmission.created_at)).limit(1)
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=400, detail="Start homework first")

    sub.answers_json = data.get("answers", sub.answers_json)
    sub.hints_json = data.get("hints", sub.hints_json)
    sub.completed = True
    sub.completed_at = datetime.now(timezone.utc)
    sub.questions_attempted = len([v for v in (sub.answers_json or {}).values() if v and str(v).strip()])
    await db.commit()

    return {"status": "completed", "completed_at": sub.completed_at.isoformat()}


@router.get("/{homework_id}/submissions")
async def get_submissions(homework_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_teacher)):
    """Teacher view: list all submissions for a homework."""
    result = await db.execute(
        select(StructuredHomeworkSubmission)
        .where(StructuredHomeworkSubmission.homework_id == homework_id)
        .order_by(StructuredHomeworkSubmission.roll_no)
    )
    subs = result.scalars().all()
    return [{
        "id": s.id,
        "student_id": s.student_id,
        "roll_no": s.roll_no,
        "completed": s.completed,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        "questions_attempted": s.questions_attempted,
        "hints_used": sum(1 for v in (s.hints_json or {}).values() if v.get("hint_used")),
    } for s in subs]


@router.delete("/{homework_id}")
async def delete_homework(homework_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(require_teacher)):
    """Delete a homework and all its questions/submissions."""
    result = await db.execute(select(StructuredHomework).where(StructuredHomework.id == homework_id))
    hw = result.scalar_one_or_none()
    if not hw:
        raise HTTPException(status_code=404, detail="Homework not found")
    await db.execute(delete(StructuredHomeworkSubmission).where(StructuredHomeworkSubmission.homework_id == homework_id))
    await db.execute(delete(StructuredHomeworkQuestion).where(StructuredHomeworkQuestion.homework_id == homework_id))
    await db.execute(delete(StructuredHomework).where(StructuredHomework.id == homework_id))
    await db.commit()
    return {"status": "deleted"}


# ===== DATA RETENTION: cleanup after deadline =====

async def cleanup_expired_homework():
    """Delete answers/hints for homework past deadline, keep completion status."""
    async with AsyncSessionLocal() as db:
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(StructuredHomework).where(
                and_(
                    StructuredHomework.deadline < now,
                    StructuredHomework.status == 'active',
                )
            )
        )
        expired = result.scalars().all()
        cleaned = 0
        for hw in expired:
            hw.status = 'expired'
            # Clear detailed data from submissions but keep completed flag
            sub_result = await db.execute(
                select(StructuredHomeworkSubmission).where(
                    StructuredHomeworkSubmission.homework_id == hw.id
                )
            )
            for sub in sub_result.scalars().all():
                sub.answers_json = None
                sub.hints_json = None
                cleaned += 1
            # Delete questions
            await db.execute(delete(StructuredHomeworkQuestion).where(
                StructuredHomeworkQuestion.homework_id == hw.id
            ))
        await db.commit()
        return cleaned


# ===== HELPERS =====

def _get_correct_answer(question):
    """Extract the correct answer from a question."""
    if question.question_type in OBJECTIVE_TYPES and question.objective_data:
        obj = question.objective_data
        if question.question_type == 'mcq':
            correct_key = obj.get("correct", "")
            options = obj.get("options", {})
            return f"{correct_key.upper()}) {options.get(correct_key, '')}"
        elif question.question_type == 'true_false':
            return "True" if obj.get("correct") else "False"
        elif question.question_type in ('fill_blank', 'one_word'):
            return obj.get("correct", "")
        elif question.question_type == 'match_following':
            pairs = obj.get("pairs", [])
            return "\n".join([f"{p['left']} → {p['right']}" for p in pairs])
    # Subjective — return model answer
    return question.model_answer or "No answer available"


async def _generate_hint(question, student_answer: str) -> str:
    """Generate an AI hint that guides without revealing the answer."""
    correct = _get_correct_answer(question)

    prompt = f"""You are a helpful tutor giving a HINT to a student struggling with a homework question.

QUESTION: {question.question_text}
CORRECT ANSWER: {correct}
STUDENT'S ATTEMPT: {student_answer or "(no attempt yet)"}

RULES:
- Give exactly ONE hint that nudges the student toward the right answer
- Do NOT reveal the answer directly
- Keep it to 1-2 sentences max
- Be encouraging and supportive
- For MCQ: hint at the reasoning, not the letter
- For fill-in-blank: give a contextual clue
- For numerical: hint at the formula or first step
- For subjective: point toward the key concept they're missing

Respond with ONLY the hint text, nothing else."""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-flash-1.5",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 150,
                    "temperature": 0.7,
                },
            )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Hint generation failed: {e}")
        # Fallback: generic hint based on question type
        if question.question_type == 'mcq':
            return "Try eliminating the options you know are incorrect. Think about the key concept in the question."
        elif question.question_type in ('fill_blank', 'one_word'):
            return f"Think about the main topic of this question. The answer starts with '{correct[0]}...'."
        elif question.question_type == 'true_false':
            return "Read the statement carefully. Think about whether every part of it is accurate."
        else:
            return "Review your notes on this topic. Focus on the key concept the question is asking about."
