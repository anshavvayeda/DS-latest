"""WhatsApp Parent Chatbot - Meta Business API with Agentic Implementation"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import PlainTextResponse, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete, and_, desc
from datetime import datetime, timezone, timedelta
import logging
import httpx
import json
import os
import secrets

from app.models.database import (
    get_db, User, StudentProfile, Subject, Chapter,
    StructuredTest, StructuredTestSubmission, StructuredHomework,
    StructuredHomeworkSubmission, WhatsappParentBrief, WhatsappChatMemory,
    AsyncSessionLocal
)
from app.services.whatsapp_agent import run_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WHATSAPP_BASE_URL = os.getenv("WHATSAPP_BASE_URL", "")

CHAT_MEMORY_LIMIT = 20


def _get_dashboard_base_url() -> str:
    return WHATSAPP_BASE_URL or os.getenv("REACT_APP_BACKEND_URL", "")


# =============================================================================
# WEBHOOK VERIFICATION (Meta requires GET endpoint)
# =============================================================================
@router.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta WhatsApp webhook verification"""
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified successfully")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    logger.warning(f"Webhook verification failed: mode={hub_mode}")
    raise HTTPException(status_code=403, detail="Verification failed")


# =============================================================================
# WEBHOOK HANDLER (Receives messages from Meta)
# =============================================================================
@router.post("/webhook")
async def handle_webhook(request: Request):
    """Receive and process incoming WhatsApp messages"""
    try:
        body = await request.json()
    except Exception:
        return {"status": "ok"}

    # Extract message data from Meta webhook payload
    entry = body.get("entry", [])
    for e in entry:
        for change in e.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            for msg in messages:
                if msg.get("type") == "text":
                    phone = msg["from"]  # sender phone number (without +)
                    text = msg["text"]["body"]
                    logger.info(f"WhatsApp message from {phone}: {text[:50]}")
                    # Process in background to respond to Meta quickly
                    import asyncio
                    asyncio.create_task(_process_message(phone, text))

    return {"status": "ok"}


async def _process_message(phone: str, user_message: str):
    """Process incoming message: identify student, fetch data, respond"""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Find student by parent phone
            profile = await _find_student_by_parent_phone(db, phone)
            if not profile:
                await _send_whatsapp_message(
                    phone,
                    "Sorry, this phone number is not registered as a parent in StudyBuddy. "
                    "Please contact your school administrator to register your number."
                )
                return

            # 2. Get or create the parent brief (cached performance data)
            brief = await _get_or_refresh_brief(db, phone, profile)

            # 3. Load chat history BEFORE saving current message (to check if first msg)
            history = await _get_chat_history(db, phone)
            is_first_message = len(history) == 0

            # 4. Save user message to chat memory
            await _save_chat_message(db, phone, "user", user_message)

            # 5. Reload history with the new message included
            history = await _get_chat_history(db, phone)

            # 6. Generate response via GPT-4o
            response = await _generate_response(
                user_message, brief, history, profile, is_first_message
            )

            # 7. Save assistant response
            await _save_chat_message(db, phone, "assistant", response)

            # 8. Send via WhatsApp
            await _send_whatsapp_message(phone, response)

        except Exception as e:
            logger.error(f"Error processing WhatsApp message from {phone}: {e}", exc_info=True)
            await _send_whatsapp_message(
                phone,
                "Sorry, I encountered an error processing your request. Please try again later."
            )


# =============================================================================
# STUDENT IDENTIFICATION
# =============================================================================
async def _find_student_by_parent_phone(db: AsyncSession, phone: str):
    """Find student profile by parent's phone number only (not login_phone)"""
    # Try matching with various formats
    phone_variants = [phone]
    if phone.startswith("91") and len(phone) > 10:
        phone_variants.append(phone[2:])  # Strip country code
    if not phone.startswith("91") and len(phone) == 10:
        phone_variants.append("91" + phone)  # Add country code

    for p in phone_variants:
        result = await db.execute(
            select(StudentProfile).where(
                StudentProfile.parent_phone == p,
                StudentProfile.standard.isnot(None)  # Only students have a standard
            )
        )
        profile = result.scalars().first()
        if profile:
            return profile

    return None


# =============================================================================
# PERFORMANCE DATA AGGREGATION
# =============================================================================
async def _get_or_refresh_brief(db: AsyncSession, phone: str, profile: StudentProfile):
    """Get cached brief or generate fresh one"""
    result = await db.execute(
        select(WhatsappParentBrief).where(WhatsappParentBrief.phone_number == phone)
    )
    brief = result.scalars().first()

    # Refresh if older than 24 hours or doesn't exist
    should_refresh = (
        not brief
        or not brief.brief_data
        or (datetime.now(timezone.utc) - brief.last_updated) > timedelta(hours=24)
    )

    if should_refresh:
        brief_data = await _aggregate_performance(db, profile)
        if brief:
            brief.brief_data = brief_data
            brief.student_name = profile.name
            brief.roll_no = profile.roll_no
            brief.standard = profile.standard
            brief.last_updated = datetime.now(timezone.utc)
        else:
            brief = WhatsappParentBrief(
                phone_number=phone,
                student_id=profile.user_id,
                student_name=profile.name,
                roll_no=profile.roll_no,
                standard=profile.standard,
                brief_data=brief_data,
                dashboard_token=secrets.token_urlsafe(32),
            )
            db.add(brief)
        await db.commit()
        await db.refresh(brief)

    return brief


async def _aggregate_performance(db: AsyncSession, profile: StudentProfile) -> dict:
    """Aggregate all performance data for a student"""
    student_id = profile.user_id
    standard = profile.standard
    roll_no = profile.roll_no

    # 1. Get subjects
    subjects_result = await db.execute(
        select(Subject).where(Subject.standard == standard)
    )
    subjects = subjects_result.scalars().all()
    subject_map = {str(s.id): s.name for s in subjects}

    # 2. Get all test submissions with scores
    submissions_result = await db.execute(
        select(StructuredTestSubmission, StructuredTest).join(
            StructuredTest, StructuredTestSubmission.test_id == StructuredTest.id
        ).where(
            StructuredTestSubmission.student_id == student_id,
            StructuredTestSubmission.submitted.is_(True),
            StructuredTestSubmission.evaluation_status == 'completed'
        ).order_by(StructuredTestSubmission.submitted_at.desc())
    )
    submissions = submissions_result.all()

    test_scores = []
    subject_scores = {}
    for sub, test in submissions:
        subject_name = subject_map.get(str(test.subject_id), "Unknown")
        pct = round(sub.percentage, 1) if sub.percentage else 0
        test_scores.append({
            "test": test.title,
            "subject": subject_name,
            "score": f"{sub.total_score}/{sub.max_score}",
            "percentage": pct,
            "date": sub.submitted_at.strftime("%d %b %Y") if sub.submitted_at else "",
        })
        if subject_name not in subject_scores:
            subject_scores[subject_name] = []
        subject_scores[subject_name].append(pct)

    # 3. Subject-wise averages & classification
    subject_analysis = {}
    for name, scores in subject_scores.items():
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        classification = "strong" if avg >= 80 else ("average" if avg >= 60 else "weak")
        subject_analysis[name] = {
            "average": avg,
            "tests_taken": len(scores),
            "classification": classification,
        }

    # 4. Missed homework
    missed_hw = []
    for subject in subjects:
        # Get active homework not completed
        pending_result = await db.execute(
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
        )
        pending = pending_result.scalars().all()
        for hw in pending:
            missed_hw.append({
                "subject": subject.name,
                "title": hw.title,
                "deadline": hw.deadline.strftime("%d %b %Y") if hw.deadline else "",
            })

    # 5. Class rank - compare with classmates
    class_rank = None
    total_students = 0
    if test_scores:
        # Get all students in same standard
        classmates_result = await db.execute(
            select(StudentProfile.user_id).where(StudentProfile.standard == standard)
        )
        classmate_ids = [r[0] for r in classmates_result.all()]
        total_students = len(classmate_ids)

        # Get average percentage for each classmate
        student_averages = []
        for cid in classmate_ids:
            avg_result = await db.execute(
                select(func.avg(StructuredTestSubmission.percentage)).where(
                    StructuredTestSubmission.student_id == cid,
                    StructuredTestSubmission.submitted.is_(True),
                    StructuredTestSubmission.evaluation_status == 'completed'
                )
            )
            avg = avg_result.scalar()
            if avg is not None:
                student_averages.append({"id": cid, "avg": float(avg)})

        student_averages.sort(key=lambda x: x["avg"], reverse=True)
        for i, sa in enumerate(student_averages):
            if sa["id"] == student_id:
                class_rank = i + 1
                break
        total_students = len(student_averages) if student_averages else total_students

    # 6. Homework completion rate
    total_hw_result = await db.execute(
        select(func.count(StructuredHomework.id)).where(
            StructuredHomework.standard == standard,
            StructuredHomework.status.in_(['active', 'expired'])
        )
    )
    total_hw = total_hw_result.scalar() or 0

    completed_hw_result = await db.execute(
        select(func.count(StructuredHomeworkSubmission.id)).where(
            StructuredHomeworkSubmission.student_id == student_id,
            StructuredHomeworkSubmission.completed.is_(True),
        )
    )
    completed_hw = completed_hw_result.scalar() or 0

    overall_avg = round(
        sum(s["percentage"] for s in test_scores) / len(test_scores), 1
    ) if test_scores else 0

    return {
        "student_name": profile.name,
        "roll_no": roll_no,
        "standard": standard,
        "overall_average": overall_avg,
        "class_rank": class_rank,
        "total_students_ranked": total_students,
        "test_scores": test_scores[:15],  # Last 15 tests
        "subject_analysis": subject_analysis,
        "missed_homework": missed_hw[:10],
        "homework_completion": {
            "total": total_hw,
            "completed": completed_hw,
            "rate": round(completed_hw / total_hw * 100, 1) if total_hw > 0 else 0
        },
        "strong_subjects": [n for n, d in subject_analysis.items() if d["classification"] == "strong"],
        "weak_subjects": [n for n, d in subject_analysis.items() if d["classification"] == "weak"],
    }


# =============================================================================
# CHAT MEMORY
# =============================================================================
async def _save_chat_message(db: AsyncSession, phone: str, role: str, message: str):
    """Save message and trim to CHAT_MEMORY_LIMIT"""
    entry = WhatsappChatMemory(phone_number=phone, role=role, message=message)
    db.add(entry)
    await db.commit()

    # Trim old messages beyond limit
    count_result = await db.execute(
        select(func.count(WhatsappChatMemory.id)).where(
            WhatsappChatMemory.phone_number == phone
        )
    )
    count = count_result.scalar() or 0

    if count > CHAT_MEMORY_LIMIT:
        excess = count - CHAT_MEMORY_LIMIT
        oldest = await db.execute(
            select(WhatsappChatMemory.id).where(
                WhatsappChatMemory.phone_number == phone
            ).order_by(WhatsappChatMemory.created_at.asc()).limit(excess)
        )
        old_ids = [r[0] for r in oldest.all()]
        if old_ids:
            await db.execute(
                delete(WhatsappChatMemory).where(WhatsappChatMemory.id.in_(old_ids))
            )
            await db.commit()


async def _get_chat_history(db: AsyncSession, phone: str) -> list:
    """Get recent chat history"""
    result = await db.execute(
        select(WhatsappChatMemory).where(
            WhatsappChatMemory.phone_number == phone
        ).order_by(WhatsappChatMemory.created_at.asc()).limit(CHAT_MEMORY_LIMIT)
    )
    messages = result.scalars().all()
    return [{"role": m.role, "content": m.message} for m in messages]


# =============================================================================
# GPT-4o RESPONSE GENERATION (via OpenRouter)
# =============================================================================
async def _generate_response(
    user_message: str,
    brief: WhatsappParentBrief,
    history: list,
    profile: StudentProfile,
    is_first_message: bool,
) -> str:
    """Generate contextual response using GPT-4o via OpenRouter"""
    data = brief.brief_data or {}
    dashboard_url = f"{_get_dashboard_base_url()}/api/whatsapp/parent-view/{brief.dashboard_token}"
    student_name = data.get('student_name', 'your child')

    system_prompt = f"""You are StudyBuddy Parent Assistant on WhatsApp.

ABSOLUTE RULES — NEVER BREAK THESE:
1. DETECT the language of the parent's LAST message and reply ONLY in that language. Hindi message → Hindi reply. English → English. Gujarati → Gujarati. Hinglish → Hinglish.
2. Always call the child by name: {student_name}
3. DO NOT volunteer information the parent did not ask for. Be conversational, not a report generator.
4. Keep replies SHORT — 2-3 sentences max unless they ask for a detailed report.
5. Use WhatsApp *bold* formatting for key numbers/names.

CONVERSATION FLOW:
- FIRST MESSAGE: Greet the parent warmly. Say you are StudyBuddy Assistant. Tell them you can help with {student_name}'s academic updates. Ask what they'd like to know — for example: performance overview, test scores, homework status, or they can view the dashboard. Share dashboard link: {dashboard_url}
- SUBSEQUENT MESSAGES: ONLY answer what the parent specifically asks. Examples:
  * "How did my child do?" → Give brief overall average and rank only
  * "Maths mein kaisa hai?" → Give only maths data
  * "Homework pending hai?" → Give only pending homework info
  * "Dashboard link bhejo" → Send only the link
  * "Tell me everything" → Then give a full summary
  * If they ask about something NOT in the data (attendance, behavior, fees) → Say politely: "I currently only have academic data like test scores and homework. For [what they asked], please contact the school."

AVAILABLE DATA (use ONLY when asked):
- Overall Average: {data.get('overall_average', 'N/A')}%
- Class Rank: {data.get('class_rank', 'N/A')} out of {data.get('total_students_ranked', 'N/A')}
- Homework: {data.get('homework_completion', {}).get('completed', 0)} done out of {data.get('homework_completion', {}).get('total', 0)}
- Strong Subjects: {', '.join(data.get('strong_subjects', [])) or 'None yet'}
- Weak Subjects: {', '.join(data.get('weak_subjects', [])) or 'None yet'}
- Subject Analysis: {json.dumps(data.get('subject_analysis', {}), indent=2)}
- Recent Tests: {json.dumps(data.get('test_scores', [])[:8], indent=2)}
- Missed Homework: {json.dumps(data.get('missed_homework', []), indent=2)}
- Dashboard: {dashboard_url}"""

    messages = [{"role": "system", "content": system_prompt}]

    # Add full chat history
    for h in history[:-1] if history else []:
        messages.append({"role": h["role"], "content": h["content"]})

    messages.append({"role": "user", "content": user_message})

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-4o",
                    "messages": messages,
                    "max_tokens": 500,
                    "temperature": 0.7,
                },
            )
            resp_data = response.json()

            if "choices" in resp_data and resp_data["choices"]:
                return resp_data["choices"][0]["message"]["content"]

            error_msg = resp_data.get("error", {}).get("message", str(resp_data)[:200])
            logger.error(f"OpenRouter response error: {error_msg}")

    except Exception as e:
        logger.error(f"GPT-4o call failed: {e}", exc_info=True)

    # Fallback — conversational, not a data dump
    if is_first_message:
        return (
            f"Hello! I'm StudyBuddy Assistant.\n\n"
            f"I can help you with *{student_name}*'s academic updates — "
            f"test scores, homework status, and more.\n\n"
            f"What would you like to know? Or view the full dashboard:\n{dashboard_url}"
        )
    return (
        f"I'm sorry, I'm having a temporary issue generating a response. "
        f"In the meantime, you can view *{student_name}*'s full performance here:\n{dashboard_url}"
    )


# =============================================================================
# SEND WHATSAPP MESSAGE (Meta Cloud API)
# =============================================================================
async def _send_whatsapp_message(phone: str, text: str):
    """Send a text message via Meta WhatsApp Business API"""
    url = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": text},
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"WhatsApp send failed ({resp.status_code}): {resp.text}")
            else:
                logger.info(f"WhatsApp message sent to {phone}")
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")


# =============================================================================
# PUBLIC PARENT DASHBOARD (Token-based, no login)
# =============================================================================
@router.get("/parent-view/{token}", response_class=HTMLResponse)
async def public_parent_dashboard(token: str, db: AsyncSession = Depends(get_db)):
    """Render a public, view-only parent dashboard via secure token"""
    result = await db.execute(
        select(WhatsappParentBrief).where(WhatsappParentBrief.dashboard_token == token)
    )
    brief = result.scalars().first()
    if not brief or not brief.brief_data:
        return HTMLResponse(
            content="<html><body style='font-family:sans-serif;text-align:center;padding:60px;'>"
            "<h2>Dashboard not found</h2><p>This link may have expired. Please send a message on WhatsApp to get a fresh link.</p>"
            "</body></html>",
            status_code=404,
        )

    data = brief.brief_data
    name = data.get("student_name", "Student")
    standard = data.get("standard", "")
    overall_avg = data.get("overall_average", 0)
    rank = data.get("class_rank")
    total_ranked = data.get("total_students_ranked", 0)
    hw_data = data.get("homework_completion", {})
    strong = data.get("strong_subjects", [])
    weak = data.get("weak_subjects", [])
    test_scores = data.get("test_scores", [])
    missed_hw = data.get("missed_homework", [])
    subject_analysis = data.get("subject_analysis", {})

    # Build subject cards HTML
    subject_cards = ""
    for sname, sdata in subject_analysis.items():
        cls = sdata.get("classification", "no_data")
        color = "#22c55e" if cls == "strong" else ("#f59e0b" if cls == "average" else "#ef4444")
        badge = cls.capitalize()
        subject_cards += f"""
        <div style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:12px;padding:16px;display:flex;justify-content:space-between;align-items:center;">
            <div>
                <div style="font-weight:600;color:#f1f5f9;font-size:15px;">{sname}</div>
                <div style="color:#94a3b8;font-size:13px;margin-top:4px;">{sdata.get('tests_taken',0)} tests taken</div>
            </div>
            <div style="text-align:right;">
                <div style="font-weight:700;font-size:18px;color:{color};">{sdata.get('average',0)}%</div>
                <span style="font-size:11px;padding:2px 8px;border-radius:8px;background:{'rgba(34,197,94,0.15)' if cls=='strong' else ('rgba(245,158,11,0.15)' if cls=='average' else 'rgba(239,68,68,0.15)')};color:{color};font-weight:600;">{badge}</span>
            </div>
        </div>"""

    # Build test scores table
    tests_html = ""
    for t in test_scores[:10]:
        pct = t.get("percentage", 0)
        bar_color = "#22c55e" if pct >= 80 else ("#f59e0b" if pct >= 60 else "#ef4444")
        tests_html += f"""
        <div style="display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.06);">
            <div style="flex:1;">
                <div style="color:#f1f5f9;font-size:14px;font-weight:500;">{t.get('test','')}</div>
                <div style="color:#64748b;font-size:12px;">{t.get('subject','')} &bull; {t.get('date','')}</div>
            </div>
            <div style="text-align:right;min-width:60px;">
                <div style="font-weight:700;color:{bar_color};font-size:15px;">{pct}%</div>
                <div style="color:#94a3b8;font-size:11px;">{t.get('score','')}</div>
            </div>
        </div>"""

    # Build missed homework
    missed_html = ""
    if missed_hw:
        for hw in missed_hw:
            missed_html += f"""
            <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.06);">
                <div>
                    <div style="color:#fbbf24;font-size:14px;font-weight:500;">{hw.get('title','')}</div>
                    <div style="color:#64748b;font-size:12px;">{hw.get('subject','')}</div>
                </div>
                <div style="color:#94a3b8;font-size:12px;">{hw.get('deadline','')}</div>
            </div>"""
    else:
        missed_html = '<div style="color:#22c55e;text-align:center;padding:16px;">All homework completed!</div>'

    rank_html = f"<span style='font-size:28px;font-weight:700;color:#a78bfa;'>#{rank}</span><span style='color:#94a3b8;font-size:13px;'> of {total_ranked}</span>" if rank else "<span style='color:#94a3b8;'>No rank data</span>"

    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{name}'s Performance - StudyBuddy</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:'Outfit',sans-serif; background:#0a0a0f; color:#e2e8f0; min-height:100vh; padding:0; }}
  .container {{ max-width:480px; margin:0 auto; padding:16px; }}
  .header {{ text-align:center; padding:24px 0 20px; }}
  .header h1 {{ font-size:22px; font-weight:700; background:linear-gradient(135deg,#667eea,#a78bfa); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }}
  .header p {{ color:#94a3b8; font-size:13px; margin-top:4px; }}
  .card {{ background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); border-radius:16px; padding:20px; margin-bottom:16px; }}
  .card-title {{ font-size:14px; font-weight:600; color:#94a3b8; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:14px; }}
  .stat-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; }}
  .stat-box {{ text-align:center; padding:16px 12px; background:rgba(255,255,255,0.04); border-radius:12px; border:1px solid rgba(255,255,255,0.06); }}
  .stat-value {{ font-size:28px; font-weight:700; }}
  .stat-label {{ font-size:12px; color:#94a3b8; margin-top:4px; }}
  .subjects-grid {{ display:flex; flex-direction:column; gap:10px; }}
  .tag {{ display:inline-block; padding:4px 10px; border-radius:8px; font-size:12px; font-weight:600; margin:2px; }}
  .footer {{ text-align:center; padding:24px 0; color:#475569; font-size:12px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>StudyBuddy</h1>
    <p>{name} &bull; Class {standard} &bull; {brief.roll_no or ''}</p>
  </div>

  <div class="card">
    <div class="stat-grid">
      <div class="stat-box">
        <div class="stat-value" style="color:#667eea;">{overall_avg}%</div>
        <div class="stat-label">Overall Average</div>
      </div>
      <div class="stat-box">
        {rank_html}
        <div class="stat-label">Class Rank</div>
      </div>
      <div class="stat-box">
        <div class="stat-value" style="color:#22c55e;font-size:22px;">{hw_data.get('rate',0)}%</div>
        <div class="stat-label">Homework Done</div>
      </div>
      <div class="stat-box">
        <div class="stat-value" style="color:#fbbf24;font-size:22px;">{len(missed_hw)}</div>
        <div class="stat-label">Pending HW</div>
      </div>
    </div>
  </div>

  {'<div class="card"><div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px;"><span style="color:#94a3b8;font-size:13px;">Strong:</span>' + ''.join(f'<span class="tag" style="background:rgba(34,197,94,0.15);color:#22c55e;">{s}</span>' for s in strong) + '</div>' + ('<div style="display:flex;gap:6px;flex-wrap:wrap;"><span style="color:#94a3b8;font-size:13px;">Needs work:</span>' + ''.join(f'<span class="tag" style="background:rgba(239,68,68,0.15);color:#ef4444;">{s}</span>' for s in weak) + '</div>' if weak else '') + '</div>' if strong or weak else ''}

  <div class="card">
    <div class="card-title">Subject Performance</div>
    <div class="subjects-grid">{subject_cards}</div>
  </div>

  <div class="card">
    <div class="card-title">Recent Tests</div>
    {tests_html if tests_html else '<div style="color:#94a3b8;text-align:center;padding:16px;">No tests taken yet</div>'}
  </div>

  <div class="card">
    <div class="card-title">Pending Homework</div>
    {missed_html}
  </div>

  <div class="footer">
    StudyBuddy &bull; Updated {brief.last_updated.strftime('%d %b %Y, %I:%M %p') if brief.last_updated else 'recently'}
  </div>
</div>
</body></html>"""

    return HTMLResponse(content=html)
