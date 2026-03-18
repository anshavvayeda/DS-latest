"""
StudyBuddy AI Evaluation Agent
================================
Modular evaluation system with type-specific evaluators.

Model routing:
- No AI: MCQ, True/False, Fill-in-blank, Match-following, totaling
- Gemini 2.5 Flash Lite: One-word semantic comparison  
- GPT-4o: Subjective (short/long), numerical steps, feedback generation
"""

import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Model constants for OpenRouter
MODEL_SIMPLE = "google/gemini-2.5-flash-lite"   # One-word semantic check
MODEL_COMPLEX = "openai/gpt-4o"                  # Subjective + numerical + feedback


# ============================================================================
# DETERMINISTIC EVALUATORS (No AI)
# ============================================================================

def evaluate_mcq(question: dict, student_answer: str) -> dict:
    """MCQ: exact match against correct option."""
    correct = (question.get("objective_data") or {}).get("correct", "").strip().lower()
    answer = (student_answer or "").strip().lower()
    is_correct = answer == correct
    return {
        "marks_awarded": question["max_marks"] if is_correct else 0,
        "feedback_json": {
            "correct": is_correct,
            "correct_answer": correct,
            "overall_feedback": "Correct!" if is_correct else f"Incorrect. The correct answer is '{correct}'."
        }
    }


def evaluate_true_false(question: dict, student_answer: str) -> dict:
    """True/False: exact boolean match."""
    correct = str((question.get("objective_data") or {}).get("correct", "")).strip().lower()
    answer = (student_answer or "").strip().lower()
    # Normalize
    answer_bool = answer in ("true", "t", "yes", "1")
    correct_bool = correct in ("true", "t", "yes", "1")
    is_correct = answer_bool == correct_bool
    return {
        "marks_awarded": question["max_marks"] if is_correct else 0,
        "feedback_json": {
            "correct": is_correct,
            "correct_answer": correct,
            "overall_feedback": "Correct!" if is_correct else f"Incorrect. The correct answer is '{correct}'."
        }
    }


def evaluate_fill_blank(question: dict, student_answer: str) -> dict:
    """Fill in the blank: case-insensitive exact match."""
    correct = (question.get("objective_data") or {}).get("correct", "").strip().lower()
    answer = (student_answer or "").strip().lower()
    is_correct = answer == correct
    return {
        "marks_awarded": question["max_marks"] if is_correct else 0,
        "feedback_json": {
            "correct": is_correct,
            "correct_answer": correct,
            "overall_feedback": "Correct!" if is_correct else f"Incorrect. The expected answer is '{correct}'."
        }
    }


def evaluate_match_following(question: dict, student_answer: str) -> dict:
    """Match the following: compare pairs. Student answer as JSON: {"A":"3","B":"1",...}"""
    obj_data = question.get("objective_data") or {}
    pairs = obj_data.get("pairs", [])
    
    try:
        student_matches = json.loads(student_answer) if isinstance(student_answer, str) else (student_answer or {})
    except (json.JSONDecodeError, TypeError):
        student_matches = {}
    
    if not pairs:
        return {"marks_awarded": 0, "feedback_json": {"overall_feedback": "No matching pairs defined."}}
    
    marks_per_pair = question["max_marks"] / len(pairs)
    total = 0
    details = []
    
    for i, pair in enumerate(pairs):
        left = pair.get("left", "")
        correct_right = str(pair.get("right", "")).strip().lower()
        student_right = str(student_matches.get(str(i), student_matches.get(left, ""))).strip().lower()
        matched = student_right == correct_right
        if matched:
            total += marks_per_pair
        details.append({
            "left": left,
            "correct_right": pair.get("right", ""),
            "student_right": student_matches.get(str(i), student_matches.get(left, "")),
            "matched": matched
        })
    
    return {
        "marks_awarded": round(total, 2),
        "feedback_json": {
            "match_details": details,
            "overall_feedback": f"You matched {sum(1 for d in details if d['matched'])}/{len(details)} correctly."
        }
    }


# ============================================================================
# AI-POWERED EVALUATORS
# ============================================================================

async def _call_openrouter(prompt: str, model: str, system_msg: str = None, expect_json: bool = True) -> Optional[str]:
    """Call OpenRouter API with specified model."""
    import httpx
    import os
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set")
        return None
    
    messages = []
    if system_msg:
        messages.append({"role": "system", "content": system_msg})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.1 if expect_json else 0.3,
        "max_tokens": 4000
    }
    if expect_json:
        payload["response_format"] = {"type": "json_object"}
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://studybuddy.app",
        "X-Title": "StudyBuddy Evaluation"
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code != 200:
                logger.error(f"OpenRouter {model} error {resp.status_code}: {resp.text[:300]}")
                return None
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip()
    except Exception as e:
        logger.error(f"OpenRouter call failed ({model}): {e}")
        return None


def _parse_json_response(text: str) -> Optional[dict]:
    """Extract JSON from LLM response."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try extracting from markdown code block
        import re
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try finding first { to last }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass
    return None


async def evaluate_one_word(question: dict, student_answer: str) -> dict:
    """One-word answer: semantic comparison via Gemini Flash Lite."""
    correct = (question.get("objective_data") or {}).get("correct", "")
    answer = (student_answer or "").strip()
    
    # Quick exact match first
    if answer.lower() == correct.lower():
        return {
            "marks_awarded": question["max_marks"],
            "feedback_json": {
                "correct": True,
                "overall_feedback": "Correct!"
            }
        }
    
    if not answer:
        return {
            "marks_awarded": 0,
            "feedback_json": {
                "correct": False,
                "overall_feedback": "No answer provided.",
                "correct_answer": correct
            }
        }
    
    prompt = f"""Compare these two answers semantically for the question.

Question: {question.get('question_text', '')}
Expected answer: {correct}
Student answer: {answer}

Determine if the student's answer represents the same concept as the expected answer.
Return JSON:
{{"correct": true/false, "explanation": "brief reason"}}"""
    
    raw = await _call_openrouter(prompt, MODEL_SIMPLE)
    result = _parse_json_response(raw)
    
    if result:
        is_correct = result.get("correct", False)
        return {
            "marks_awarded": question["max_marks"] if is_correct else 0,
            "feedback_json": {
                "correct": is_correct,
                "explanation": result.get("explanation", ""),
                "correct_answer": correct,
                "overall_feedback": "Correct!" if is_correct else f"Incorrect. Expected: '{correct}'. {result.get('explanation', '')}"
            }
        }
    
    # Fallback: exact match
    return {
        "marks_awarded": question["max_marks"] if answer.lower() == correct.lower() else 0,
        "feedback_json": {"correct": answer.lower() == correct.lower(), "overall_feedback": "Evaluation uncertain."}
    }


async def evaluate_subjective(question: dict, student_answer: str) -> dict:
    """Short/Long answer: rubric-based evaluation via GPT-4o."""
    answer = (student_answer or "").strip()
    if not answer:
        return {
            "marks_awarded": 0,
            "feedback_json": {
                "evaluation_points": [],
                "overall_feedback": "No answer provided.",
                "improvement_suggestions": "Please attempt the question."
            }
        }
    
    raw_eval_points = question.get("evaluation_points")
    model_answer = question.get("model_answer", "")
    max_marks = question["max_marks"]
    
    # Normalize evaluation_points: handle string, list of dicts, or None
    eval_points = []
    if isinstance(raw_eval_points, list):
        eval_points = raw_eval_points
    elif isinstance(raw_eval_points, str) and raw_eval_points.strip():
        # Convert comma-separated string to evaluation point dicts
        criteria = [c.strip() for c in raw_eval_points.split(",") if c.strip()]
        marks_each = round(max_marks / max(len(criteria), 1), 2)
        eval_points = [
            {"id": i + 1, "title": c, "expected_concept": c, "marks": marks_each}
            for i, c in enumerate(criteria)
        ]
    
    points_text = ""
    if eval_points and isinstance(eval_points[0], dict):
        for ep in eval_points:
            title = ep.get("title", "")
            marks = ep.get("marks", 0)
            concept = ep.get("expected_concept", title)
            points_text += f"\n- Point: {title} ({marks} marks)\n  Expected concept: {concept}"
    
    # If no structured rubric, use model answer for evaluation
    rubric_section = f"Evaluation rubric:{points_text}" if points_text else f"Model answer to compare against: {model_answer}"
    
    prompt = f"""You are a strict but fair exam evaluator. Evaluate the student's answer.

Question: {question.get('question_text', '')}
Maximum marks: {max_marks}

Model answer: {model_answer}

{rubric_section}

Student's answer: {answer}

Evaluate the student's answer against the model answer and rubric.
Return JSON:
{{
  "evaluation_points": [
    {{"title": "point title", "covered": true/false, "explanation": "why", "marks_given": number}}
  ],
  "overall_feedback": "summary of performance",
  "improvement_suggestions": "specific advice"
}}

Rules:
- Award marks ONLY for points where the concept is clearly covered
- Partial marks within a point are allowed if partially covered
- Total marks_given across all points must not exceed {max_marks}
- Be specific in explanations"""
    
    system_msg = "You are an experienced exam evaluator. Be fair, consistent, and provide constructive feedback."
    
    raw = await _call_openrouter(prompt, MODEL_COMPLEX, system_msg=system_msg)
    result = _parse_json_response(raw)
    
    if result:
        points_eval = result.get("evaluation_points", [])
        total = sum(p.get("marks_given", 0) for p in points_eval)
        total = min(total, question["max_marks"])  # Cap at max
        
        return {
            "marks_awarded": round(total, 2),
            "feedback_json": {
                "evaluation_points": points_eval,
                "overall_feedback": result.get("overall_feedback", ""),
                "improvement_suggestions": result.get("improvement_suggestions", "")
            }
        }
    
    # Fallback
    logger.error("Subjective evaluation LLM parse failed")
    return {
        "marks_awarded": 0,
        "feedback_json": {"overall_feedback": "Evaluation could not be completed. Please contact teacher."}
    }


async def evaluate_numerical(question: dict, student_answer: str) -> dict:
    """Numerical/Step-based: step-by-step evaluation via GPT-4o."""
    answer = (student_answer or "").strip()
    if not answer:
        return {
            "marks_awarded": 0,
            "feedback_json": {
                "steps_evaluation": [],
                "overall_feedback": "No answer provided.",
                "improvement_suggestions": "Please show your working."
            }
        }
    
    steps = question.get("solution_steps") or []
    model_answer = question.get("model_answer", "")
    
    steps_text = ""
    for s in steps:
        steps_text += f"\n- Step: {s['title']} ({s['marks']} marks)\n  Expected: {s['expected']}"
    
    prompt = f"""You are a mathematics evaluator. Check the student's solution step by step.

Question: {question.get('question_text', '')}
Maximum marks: {question['max_marks']}

Model solution: {model_answer}

Expected solution steps:{steps_text}

Student's answer/working: {answer}

For EACH step, check if the student performed it correctly.
Return JSON:
{{
  "steps_evaluation": [
    {{"title": "step title", "completed": true/false, "explanation": "what student did", "marks_given": number}}
  ],
  "overall_feedback": "summary",
  "improvement_suggestions": "advice"
}}

Rules:
- Award marks for each step independently
- If student reaches correct answer via different valid method, still award marks
- Partial marks per step are allowed
- marks_given must not exceed allocated marks for that step"""
    
    system_msg = "You are an experienced mathematics evaluator. Award marks for correct working and methodology."
    
    raw = await _call_openrouter(prompt, MODEL_COMPLEX, system_msg=system_msg)
    result = _parse_json_response(raw)
    
    if result:
        steps_eval = result.get("steps_evaluation", [])
        total = sum(s.get("marks_given", 0) for s in steps_eval)
        total = min(total, question["max_marks"])
        
        return {
            "marks_awarded": round(total, 2),
            "feedback_json": {
                "steps_evaluation": steps_eval,
                "overall_feedback": result.get("overall_feedback", ""),
                "improvement_suggestions": result.get("improvement_suggestions", "")
            }
        }
    
    logger.error("Numerical evaluation LLM parse failed")
    return {
        "marks_awarded": 0,
        "feedback_json": {"overall_feedback": "Evaluation could not be completed."}
    }


# ============================================================================
# VERIFICATION AGENT
# ============================================================================

def verify_evaluation(question: dict, eval_result: dict) -> dict:
    """Verify marks don't exceed maximum and scheme was followed."""
    max_marks = question["max_marks"]
    awarded = eval_result["marks_awarded"]
    notes = []
    
    # Check max marks cap
    if awarded > max_marks:
        notes.append(f"Marks capped from {awarded} to {max_marks}")
        eval_result["marks_awarded"] = max_marks
    
    # Check negative marks
    if awarded < 0:
        notes.append(f"Negative marks adjusted to 0")
        eval_result["marks_awarded"] = 0
    
    # Verify evaluation points total
    feedback = eval_result.get("feedback_json", {})
    
    if "evaluation_points" in feedback:
        points_total = sum(p.get("marks_given", 0) for p in feedback["evaluation_points"])
        if points_total > max_marks:
            notes.append(f"Evaluation points total ({points_total}) exceeds max ({max_marks}), capped")
            eval_result["marks_awarded"] = max_marks
    
    if "steps_evaluation" in feedback:
        steps_total = sum(s.get("marks_given", 0) for s in feedback["steps_evaluation"])
        if steps_total > max_marks:
            notes.append(f"Steps total ({steps_total}) exceeds max ({max_marks}), capped")
            eval_result["marks_awarded"] = max_marks
    
    eval_result["verified"] = True
    eval_result["verification_notes"] = "; ".join(notes) if notes else "Verified OK"
    
    return eval_result


# ============================================================================
# ORCHESTRATOR
# ============================================================================

EVALUATOR_MAP = {
    "mcq": evaluate_mcq,
    "true_false": evaluate_true_false,
    "fill_blank": evaluate_fill_blank,
    "match_following": evaluate_match_following,
}

ASYNC_EVALUATOR_MAP = {
    "one_word": evaluate_one_word,
    "short_answer": evaluate_subjective,
    "long_answer": evaluate_subjective,
    "numerical": evaluate_numerical,
}


async def evaluate_submission(questions: List[dict], answers: dict) -> dict:
    """
    Main orchestrator: evaluate all questions in a submission.
    
    Args:
        questions: List of StructuredQuestion dicts
        answers: Dict mapping question_number (str) -> student answer
    
    Returns:
        {
            total_score, max_score, percentage,
            question_results: [{question_number, marks_awarded, max_marks, feedback_json, verified}],
            improvement_summary: "..."
        }
    """
    results = []
    total_score = 0
    max_score = 0
    
    for q in questions:
        q_num = str(q["question_number"])
        q_type = q["question_type"]
        student_answer = answers.get(q_num, "")
        max_marks = q["max_marks"]
        max_score += max_marks
        
        # Route to appropriate evaluator
        if q_type in EVALUATOR_MAP:
            eval_result = EVALUATOR_MAP[q_type](q, student_answer)
        elif q_type in ASYNC_EVALUATOR_MAP:
            eval_result = await ASYNC_EVALUATOR_MAP[q_type](q, student_answer)
        else:
            eval_result = {"marks_awarded": 0, "feedback_json": {"overall_feedback": f"Unknown question type: {q_type}"}}
        
        # Verify
        eval_result = verify_evaluation(q, eval_result)
        
        eval_result["question_number"] = int(q_num)
        eval_result["question_id"] = q.get("id", "")
        eval_result["max_marks"] = max_marks
        
        total_score += eval_result["marks_awarded"]
        results.append(eval_result)
    
    total_score = round(total_score, 2)
    percentage = round((total_score / max_score * 100), 2) if max_score > 0 else 0
    
    # Generate improvement summary via GPT-4o
    improvement_summary = await _generate_improvement_summary(questions, results)
    
    return {
        "total_score": total_score,
        "max_score": max_score,
        "percentage": percentage,
        "question_results": results,
        "improvement_summary": improvement_summary
    }


async def _generate_improvement_summary(questions: List[dict], results: List[dict]) -> str:
    """Generate a brief improvement summary for PTM/long-term storage."""
    missed = []
    for r in results:
        if r["marks_awarded"] < r["max_marks"]:
            q = next((q for q in questions if str(q["question_number"]) == str(r["question_number"])), {})
            missed.append(f"Q{r['question_number']} ({q.get('question_type','')}, {r['marks_awarded']}/{r['max_marks']})")
    
    if not missed:
        return "Excellent performance. All questions answered correctly."
    
    prompt = f"""Based on these test results, write a 2-3 sentence improvement summary suitable for a parent-teacher meeting.

Questions needing improvement: {', '.join(missed)}
Overall score: {sum(r['marks_awarded'] for r in results)}/{sum(r['max_marks'] for r in results)}

Keep it constructive, specific, and brief."""
    
    raw = await _call_openrouter(prompt, MODEL_SIMPLE, expect_json=False)
    return raw or f"Needs improvement in: {', '.join(missed)}"
