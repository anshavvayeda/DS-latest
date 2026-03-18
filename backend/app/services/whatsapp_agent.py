"""WhatsApp Parent Agent - Agentic implementation with function calling"""
import json
import logging
import os
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from app.models.database import (
    StudentProfile, Subject, StructuredTest, StructuredTestSubmission,
    StructuredHomework, StructuredHomeworkSubmission, WhatsappParentBrief,
)

logger = logging.getLogger(__name__)

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
MAX_AGENT_LOOPS = 3

# =============================================================================
# TOOL DEFINITIONS (sent to GPT-4o for function calling)
# =============================================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_student_overview",
            "description": "Get the student's overall academic overview: average percentage, class rank, homework completion rate, strong and weak subjects. Use when the parent asks for a general update or performance summary.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_subject_performance",
            "description": "Get performance details for a specific subject: average score, number of tests, classification (strong/average/weak). Use when the parent asks about a specific subject like Maths, Science, English etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject_name": {
                        "type": "string",
                        "description": "The subject name to look up, e.g. 'Mathematics', 'English', 'Science', 'Hindi'. Use title case.",
                    }
                },
                "required": ["subject_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_tests",
            "description": "Get the student's recent test scores with subject, marks, percentage and date. Use when the parent asks about test results, exam scores, or recent performance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of recent tests to fetch (default 5, max 10)",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_homework",
            "description": "Get the list of homework assignments that the student has NOT completed yet. Use when the parent asks about pending, missing, or incomplete homework.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_class_rank",
            "description": "Get the student's rank among classmates based on test averages. Use when the parent asks about rank, position, or comparison with other students.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_improvement_tips",
            "description": "Get AI-generated study improvement tips based on the student's weak areas and recent performance. Use when the parent asks how to improve or what to focus on.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_link",
            "description": "Get the shareable dashboard link where the parent can view full performance visually. Use when the parent asks for a link, report, or dashboard.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


# =============================================================================
# TOOL EXECUTION
# =============================================================================
async def execute_tool(tool_name: str, args: dict, db: AsyncSession, profile: StudentProfile, brief: WhatsappParentBrief, base_url: str) -> str:
    """Execute an agent tool and return the result as a string"""
    try:
        if tool_name == "get_student_overview":
            return await _tool_student_overview(db, profile)
        elif tool_name == "get_subject_performance":
            return await _tool_subject_performance(db, profile, args.get("subject_name", ""))
        elif tool_name == "get_recent_tests":
            return await _tool_recent_tests(db, profile, args.get("limit", 5))
        elif tool_name == "get_pending_homework":
            return await _tool_pending_homework(db, profile)
        elif tool_name == "get_class_rank":
            return await _tool_class_rank(db, profile)
        elif tool_name == "get_improvement_tips":
            return await _tool_improvement_tips(db, profile)
        elif tool_name == "get_dashboard_link":
            return _tool_dashboard_link(brief, base_url)
        else:
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
    except Exception as e:
        logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
        return json.dumps({"error": f"Failed to fetch data: {str(e)}"})


async def _tool_student_overview(db: AsyncSession, profile: StudentProfile) -> str:
    student_id = profile.user_id
    standard = profile.standard

    # Overall test average
    avg_result = await db.execute(
        select(func.avg(StructuredTestSubmission.percentage)).where(
            StructuredTestSubmission.student_id == student_id,
            StructuredTestSubmission.submitted.is_(True),
            StructuredTestSubmission.evaluation_status == 'completed'
        )
    )
    overall_avg = round(float(avg_result.scalar() or 0), 1)

    # Tests taken count
    test_count_result = await db.execute(
        select(func.count(StructuredTestSubmission.id)).where(
            StructuredTestSubmission.student_id == student_id,
            StructuredTestSubmission.submitted.is_(True),
        )
    )
    tests_taken = test_count_result.scalar() or 0

    # Homework stats
    total_hw = (await db.execute(
        select(func.count(StructuredHomework.id)).where(
            StructuredHomework.standard == standard,
            StructuredHomework.status.in_(['active', 'expired'])
        )
    )).scalar() or 0
    completed_hw = (await db.execute(
        select(func.count(StructuredHomeworkSubmission.id)).where(
            StructuredHomeworkSubmission.student_id == student_id,
            StructuredHomeworkSubmission.completed.is_(True),
        )
    )).scalar() or 0
    hw_rate = round(completed_hw / total_hw * 100, 1) if total_hw > 0 else 0

    # Subject breakdown
    subjects = (await db.execute(select(Subject).where(Subject.standard == standard))).scalars().all()
    subject_info = {}
    for s in subjects:
        sub_avg = (await db.execute(
            select(func.avg(StructuredTestSubmission.percentage)).join(
                StructuredTest, StructuredTestSubmission.test_id == StructuredTest.id
            ).where(
                StructuredTestSubmission.student_id == student_id,
                StructuredTestSubmission.submitted.is_(True),
                StructuredTestSubmission.evaluation_status == 'completed',
                StructuredTest.subject_id == s.id,
            )
        )).scalar()
        if sub_avg is not None:
            avg_val = round(float(sub_avg), 1)
            subject_info[s.name] = {
                "average": avg_val,
                "classification": "strong" if avg_val >= 80 else ("average" if avg_val >= 60 else "needs improvement"),
            }

    strong = [n for n, d in subject_info.items() if d["classification"] == "strong"]
    weak = [n for n, d in subject_info.items() if d["classification"] == "needs improvement"]

    return json.dumps({
        "student_name": profile.name,
        "class": standard,
        "overall_average": f"{overall_avg}%",
        "tests_taken": tests_taken,
        "homework_completion": f"{completed_hw}/{total_hw} ({hw_rate}%)",
        "strong_subjects": strong or ["None identified yet"],
        "weak_subjects": weak or ["None identified yet"],
        "subjects": subject_info,
    })


async def _tool_subject_performance(db: AsyncSession, profile: StudentProfile, subject_name: str) -> str:
    student_id = profile.user_id
    standard = profile.standard

    # Find subject (fuzzy match)
    subjects = (await db.execute(select(Subject).where(Subject.standard == standard))).scalars().all()
    matched = None
    for s in subjects:
        if subject_name.lower() in s.name.lower() or s.name.lower() in subject_name.lower():
            matched = s
            break

    if not matched:
        available = [s.name for s in subjects]
        return json.dumps({"error": f"Subject '{subject_name}' not found. Available subjects: {', '.join(available)}"})

    # Get test scores for this subject
    results = (await db.execute(
        select(StructuredTestSubmission, StructuredTest).join(
            StructuredTest, StructuredTestSubmission.test_id == StructuredTest.id
        ).where(
            StructuredTestSubmission.student_id == student_id,
            StructuredTestSubmission.submitted.is_(True),
            StructuredTestSubmission.evaluation_status == 'completed',
            StructuredTest.subject_id == matched.id,
        ).order_by(StructuredTestSubmission.submitted_at.desc())
    )).all()

    tests = []
    for sub, test in results:
        tests.append({
            "test": test.title,
            "score": f"{sub.total_score}/{sub.max_score}",
            "percentage": round(sub.percentage, 1) if sub.percentage else 0,
            "date": sub.submitted_at.strftime("%d %b %Y") if sub.submitted_at else "",
        })

    avg = round(sum(t["percentage"] for t in tests) / len(tests), 1) if tests else 0
    classification = "strong" if avg >= 80 else ("average" if avg >= 60 else "needs improvement")

    return json.dumps({
        "subject": matched.name,
        "average": f"{avg}%",
        "tests_taken": len(tests),
        "classification": classification,
        "recent_tests": tests[:5],
    })


async def _tool_recent_tests(db: AsyncSession, profile: StudentProfile, limit: int = 5) -> str:
    limit = min(max(limit, 1), 10)
    results = (await db.execute(
        select(StructuredTestSubmission, StructuredTest).join(
            StructuredTest, StructuredTestSubmission.test_id == StructuredTest.id
        ).where(
            StructuredTestSubmission.student_id == profile.user_id,
            StructuredTestSubmission.submitted.is_(True),
            StructuredTestSubmission.evaluation_status == 'completed',
        ).order_by(StructuredTestSubmission.submitted_at.desc()).limit(limit)
    )).all()

    subjects = {str(s.id): s.name for s in (await db.execute(select(Subject).where(Subject.standard == profile.standard))).scalars().all()}

    tests = []
    for sub, test in results:
        tests.append({
            "test": test.title,
            "subject": subjects.get(str(test.subject_id), "Unknown"),
            "score": f"{sub.total_score}/{sub.max_score}",
            "percentage": f"{round(sub.percentage, 1)}%",
            "date": sub.submitted_at.strftime("%d %b %Y") if sub.submitted_at else "",
        })

    if not tests:
        return json.dumps({"message": "No test results available yet."})
    return json.dumps({"recent_tests": tests, "total_shown": len(tests)})


async def _tool_pending_homework(db: AsyncSession, profile: StudentProfile) -> str:
    student_id = profile.user_id
    standard = profile.standard
    subjects = (await db.execute(select(Subject).where(Subject.standard == standard))).scalars().all()

    pending = []
    for subject in subjects:
        hw_result = (await db.execute(
            select(StructuredHomework).where(
                StructuredHomework.subject_id == subject.id,
                StructuredHomework.standard == standard,
                StructuredHomework.status == 'active',
                ~StructuredHomework.id.in_(
                    select(StructuredHomeworkSubmission.homework_id).where(
                        StructuredHomeworkSubmission.student_id == student_id,
                        StructuredHomeworkSubmission.completed.is_(True),
                    )
                )
            )
        )).scalars().all()
        for hw in hw_result:
            pending.append({
                "subject": subject.name,
                "title": hw.title,
                "deadline": hw.deadline.strftime("%d %b %Y") if hw.deadline else "No deadline",
            })

    if not pending:
        return json.dumps({"message": "All homework is completed! Great job."})
    return json.dumps({"pending_count": len(pending), "pending_homework": pending})


async def _tool_class_rank(db: AsyncSession, profile: StudentProfile) -> str:
    student_id = profile.user_id
    standard = profile.standard

    classmates = (await db.execute(
        select(StudentProfile.user_id).where(StudentProfile.standard == standard)
    )).all()
    classmate_ids = [r[0] for r in classmates]

    averages = []
    for cid in classmate_ids:
        avg = (await db.execute(
            select(func.avg(StructuredTestSubmission.percentage)).where(
                StructuredTestSubmission.student_id == cid,
                StructuredTestSubmission.submitted.is_(True),
                StructuredTestSubmission.evaluation_status == 'completed'
            )
        )).scalar()
        if avg is not None:
            averages.append({"id": cid, "avg": round(float(avg), 1)})

    averages.sort(key=lambda x: x["avg"], reverse=True)
    rank = None
    student_avg = None
    for i, a in enumerate(averages):
        if a["id"] == student_id:
            rank = i + 1
            student_avg = a["avg"]
            break

    if rank is None:
        return json.dumps({"message": "Not enough test data to determine rank yet."})
    return json.dumps({
        "rank": rank,
        "total_students": len(averages),
        "student_average": f"{student_avg}%",
        "top_average": f"{averages[0]['avg']}%" if averages else "N/A",
    })


async def _tool_improvement_tips(db: AsyncSession, profile: StudentProfile) -> str:
    student_id = profile.user_id
    standard = profile.standard
    subjects = (await db.execute(select(Subject).where(Subject.standard == standard))).scalars().all()

    weak_areas = []
    for s in subjects:
        avg = (await db.execute(
            select(func.avg(StructuredTestSubmission.percentage)).join(
                StructuredTest, StructuredTestSubmission.test_id == StructuredTest.id
            ).where(
                StructuredTestSubmission.student_id == student_id,
                StructuredTestSubmission.submitted.is_(True),
                StructuredTestSubmission.evaluation_status == 'completed',
                StructuredTest.subject_id == s.id,
            )
        )).scalar()
        if avg is not None and float(avg) < 70:
            weak_areas.append({"subject": s.name, "average": round(float(avg), 1)})

    # Homework completion
    total_hw = (await db.execute(
        select(func.count(StructuredHomework.id)).where(
            StructuredHomework.standard == standard, StructuredHomework.status.in_(['active', 'expired'])
        )
    )).scalar() or 0
    completed_hw = (await db.execute(
        select(func.count(StructuredHomeworkSubmission.id)).where(
            StructuredHomeworkSubmission.student_id == student_id, StructuredHomeworkSubmission.completed.is_(True),
        )
    )).scalar() or 0
    hw_rate = round(completed_hw / total_hw * 100, 1) if total_hw > 0 else 100

    return json.dumps({
        "weak_subjects": weak_areas,
        "homework_completion_rate": f"{hw_rate}%",
        "suggestion_context": "Generate 2-3 brief, actionable tips based on the weak subjects and homework rate above.",
    })


def _tool_dashboard_link(brief: WhatsappParentBrief, base_url: str) -> str:
    url = f"{base_url}/api/whatsapp/parent-view/{brief.dashboard_token}"
    return json.dumps({"dashboard_url": url, "message": "Here is the full performance dashboard link."})


# =============================================================================
# AGENT LOOP
# =============================================================================
async def run_agent(
    user_message: str,
    chat_history: list,
    is_first_message: bool,
    db: AsyncSession,
    profile: StudentProfile,
    brief: WhatsappParentBrief,
    base_url: str,
) -> str:
    """Run the agentic loop: Sarvam AI decides tools → execute → respond"""
    student_name = profile.name or "your child"

    system_prompt = f"""You are StudyBuddy Parent Assistant, a WhatsApp chatbot agent that helps parents track their child's academic performance.

IDENTITY:
- You are an intelligent agent with access to tools that fetch real-time data from the school database.
- The student's name is *{student_name}* (Class {profile.standard}).

ABSOLUTE RULES:
1. LANGUAGE & SCRIPT: Detect the language of the parent's CURRENT message and respond ONLY in that language using its NATIVE SCRIPT.
   - If message contains Devanagari (हिन्दी) → reply in Hindi using Devanagari script
   - If message contains Gujarati script (ગુજરાતી) → reply in Gujarati using Gujarati script (ગુજરાતી લિપિ)
   - If message is in English → reply in English
   - If message mixes Hindi/English (Hinglish) → reply in Hinglish using Devanagari for Hindi words
   - CRITICAL: Gujarati (ગુજરાતી) and Hindi (हिन्दी) are DIFFERENT languages with DIFFERENT scripts. Do NOT confuse them. Gujarati uses characters like આ, ઈ, ઉ, એ, ઓ, ક, ખ, ગ. Hindi uses characters like आ, ई, उ, ए, ओ, क, ख, ग.
   - NEVER use Latin/Roman transliteration for Indian languages. Always use the native script.
2. Always refer to the child as *{student_name}* (with WhatsApp bold).
3. Keep responses SHORT for WhatsApp — 2-4 sentences. No essays.
4. Use WhatsApp *bold* for key data points.
5. NEVER fabricate data. Only share what comes from tool results.

CONVERSATION BEHAVIOR:
- FIRST MESSAGE (generic greeting like Hi/Hello/नमस्ते/કેમ છો): Greet warmly IN THE SAME LANGUAGE AND SCRIPT as the parent's message, introduce yourself, and ask what they'd like to know about *{student_name}*. Mention you can help with: test scores, homework status, subject performance, class rank, or share the dashboard link. Do NOT call any tools yet. Do NOT dump data.
  Examples:
  - Parent says "Hi" → respond in English
  - Parent says "नमस्ते" → respond fully in Hindi Devanagari (e.g., "नमस्ते! मैं StudyBuddy Assistant हूँ...")
  - Parent says "કેમ છો" → respond fully in Gujarati script (e.g., "નમસ્તે! હું StudyBuddy Assistant છું...")
- SPECIFIC QUESTION: Call the appropriate tool(s), get the data, then answer precisely. After answering, ask if they'd like the dashboard link or have more questions.
- MULTIPLE TOPICS in one message: Call multiple tools as needed.
- UNAVAILABLE DATA: If a tool returns an error or the parent asks about something you don't have tools for (fees, attendance, behavior), say politely that this information is not available and suggest contacting the school.
- DASHBOARD REQUEST: Use get_dashboard_link tool and share the URL.

TONE: Friendly, warm, professional. Like a helpful school coordinator. Not robotic."""

    messages = [{"role": "system", "content": system_prompt}]

    # Add chat history (excluding current message)
    for h in chat_history[:-1] if chat_history else []:
        messages.append({"role": h["role"], "content": h["content"]})

    messages.append({"role": "user", "content": user_message})

    # Agent loop — Sarvam AI can call tools and then we feed results back
    for loop_i in range(MAX_AGENT_LOOPS):
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                payload = {
                    "model": "sarvam-105b",
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.7,
                }
                # Only send tools if not first message (first msg = just greet)
                if not is_first_message:
                    payload["tools"] = TOOLS
                    payload["tool_choice"] = "auto"

                resp = await client.post(
                    "https://api.sarvam.ai/v1/chat/completions",
                    headers={
                        "API-Subscription-Key": SARVAM_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp_data = resp.json()

            if "choices" not in resp_data or not resp_data["choices"]:
                error_msg = resp_data.get("error", {}).get("message", str(resp_data)[:200])
                logger.error(f"Agent Sarvam AI error: {error_msg}")
                break

            choice = resp_data["choices"][0]
            message = choice["message"]
            finish_reason = choice.get("finish_reason", "")

            # If the model wants to call tool(s)
            if message.get("tool_calls"):
                messages.append(message)  # Add assistant's tool call message

                for tool_call in message["tool_calls"]:
                    fn_name = tool_call["function"]["name"]
                    fn_args = json.loads(tool_call["function"].get("arguments", "{}"))
                    logger.info(f"Agent calling tool: {fn_name}({fn_args})")

                    result = await execute_tool(fn_name, fn_args, db, profile, brief, base_url)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result,
                    })

                # Continue loop so GPT-4o can process tool results
                continue

            # Model returned a final text response
            if message.get("content"):
                return message["content"]

            break

        except Exception as e:
            logger.error(f"Agent loop {loop_i} error: {e}", exc_info=True)
            break

    # Fallback if agent loop failed
    if is_first_message:
        return (
            f"Hello! I'm StudyBuddy Assistant.\n\n"
            f"I can help you with *{student_name}*'s academic updates — "
            f"test scores, homework status, class rank, and more.\n\n"
            f"What would you like to know?"
        )
    dashboard_url = f"{base_url}/api/whatsapp/parent-view/{brief.dashboard_token}"
    return (
        f"I'm having a temporary issue. You can view *{student_name}*'s full report here:\n{dashboard_url}"
    )
