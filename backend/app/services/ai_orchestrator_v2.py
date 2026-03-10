"""
PRODUCTION-GRADE AI GENERATION ORCHESTRATOR V2
===============================================

100% ROBUST, PRODUCTION-READY AI CONTENT GENERATION

KEY GUARANTEES:
- ALL content generated completely before being available to students
- NO partial saves - all-or-nothing atomic commits
- Automatic retries for ALL transient failures (5 retries per component, exponential backoff)
- Background processing - never blocks HTTP requests
- Protection against timeouts, token limits, malformed JSON, rate limits
- System keeps retrying until success (no permanent failure state)

COMPONENTS GENERATED (7 total):
1. Revision Notes (JSON)
2. Flashcards (15 cards)
3. Easy Quiz (15 questions)
4. Medium Quiz (15 questions)
5. Hard Quiz (15 questions)
6. Advanced 1 Quiz (15 questions)
7. Advanced 2 Quiz (15 questions)

Total: 75 quiz questions + revision notes + 15 flashcards
"""

import os
import json
import asyncio
import re
import logging
import traceback
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_FOR_GENERATION = "google/gemini-3-flash-preview"

# RETRY CONFIGURATION (PRODUCTION-GRADE)
MAX_RETRIES_PER_COMPONENT = 5  # 5 retries per component
MAX_FULL_RETRIES = 10  # Keep retrying entire generation until success
RETRY_BASE_DELAY = 2  # Exponential: 2s, 4s, 8s, 16s, 32s
MAX_RETRY_DELAY = 64  # Cap at 64 seconds
FULL_RETRY_DELAY = 30  # Delay between full generation retries

# TOKEN CONFIGURATION
TEMPERATURE = 0.2  # Low for consistent JSON
MAX_TOKENS_QUIZ = 4000  # 15 questions with explanations
MAX_TOKENS_CONTENT = 4000  # For revision notes/flashcards

# CONTENT SIZE LIMITS
MAX_CONTENT_LENGTH = 8000  # Summarize if longer
CHUNK_SIZE = 6000  # For chunked processing

# TIMEOUT CONFIGURATION
API_TIMEOUT = 180.0  # 3 minutes per call
GENERATION_TIMEOUT = 1800  # 30 minutes total max

# QUIZ REQUIREMENTS
QUESTIONS_PER_QUIZ = 15
TOTAL_QUIZZES = 5
TOTAL_QUESTIONS = QUESTIONS_PER_QUIZ * TOTAL_QUIZZES  # 75


# =============================================================================
# STATUS ENUM
# =============================================================================

class AIStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"  # Temporary - will be retried


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class AIServiceError(Exception):
    """Base exception for AI service errors"""
    pass

class AIGenerationError(AIServiceError):
    """Raised when AI content generation fails"""
    def __init__(self, component: str, reason: str, attempts: int = 0):
        self.component = component
        self.reason = reason
        self.attempts = attempts
        super().__init__(f"{component} generation failed after {attempts} attempts: {reason}")

class AIValidationError(AIServiceError):
    """Raised when AI content validation fails"""
    def __init__(self, component: str, validation_error: str):
        self.component = component
        self.validation_error = validation_error
        super().__init__(f"{component} validation failed: {validation_error}")

class AIJSONParseError(AIServiceError):
    """Raised when JSON parsing fails"""
    def __init__(self, component: str, raw_response: str = ""):
        self.component = component
        self.raw_response = raw_response[:500] if raw_response else ""
        super().__init__(f"{component} JSON parsing failed")

class AIRetryableError(AIServiceError):
    """Raised for errors that should trigger retry"""
    def __init__(self, component: str, reason: str):
        self.component = component
        self.reason = reason
        super().__init__(f"{component}: {reason} (retryable)")


# =============================================================================
# RESULT CLASSES
# =============================================================================

@dataclass
class ComponentResult:
    """Result of a single component generation"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    attempts: int = 0


@dataclass
class GenerationResult:
    """Result of full AI generation"""
    success: bool
    revision_notes: Optional[Dict] = None
    flashcards: Optional[List] = None
    quiz_easy: Optional[Dict] = None
    quiz_medium: Optional[Dict] = None
    quiz_hard: Optional[Dict] = None
    quiz_advanced_1: Optional[Dict] = None
    quiz_advanced_2: Optional[Dict] = None
    error_component: Optional[str] = None
    error_message: Optional[str] = None
    total_attempts: int = 0
    generation_time_seconds: float = 0


# =============================================================================
# JSON EXTRACTION (STRICT - MULTIPLE STRATEGIES)
# =============================================================================

def extract_json_strict(text: str, component: str) -> Any:
    """
    STRICT JSON extraction with multiple fallback strategies.
    Handles:
    - Direct JSON
    - JSON in markdown code blocks
    - JSON with preceding text
    - Malformed JSON with common errors
    
    Returns parsed JSON (dict or list).
    Raises AIJSONParseError if extraction fails.
    """
    if not text:
        raise AIJSONParseError(component, "Empty response received")
    
    # Clean text
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)  # Remove control chars
    text = text.strip()
    
    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # Strategy 2: Extract from markdown code blocks
    code_block_patterns = [
        r'```json\s*([\s\S]*?)\s*```',
        r'```\s*([\s\S]*?)\s*```',
    ]
    for pattern in code_block_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    
    # Strategy 3: Find JSON structure manually
    # Look for first { or [
    json_start_obj = text.find('{')
    json_start_arr = text.find('[')
    
    if json_start_obj == -1 and json_start_arr == -1:
        raise AIJSONParseError(component, text)
    
    # Determine which comes first
    if json_start_obj == -1:
        json_start = json_start_arr
    elif json_start_arr == -1:
        json_start = json_start_obj
    else:
        json_start = min(json_start_obj, json_start_arr)
    
    # Find matching closing bracket using bracket counting
    bracket_count = 0
    json_end = -1
    in_string = False
    escape_next = False
    
    for i, char in enumerate(text[json_start:], json_start):
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"':
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        if char in '{[':
            bracket_count += 1
        elif char in '}]':
            bracket_count -= 1
            if bracket_count == 0:
                json_end = i + 1
                break
    
    if json_end == -1:
        raise AIJSONParseError(component, f"Unbalanced brackets in: {text[:200]}")
    
    json_str = text[json_start:json_end].strip()
    
    # Fix common JSON errors
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)  # Trailing commas
    json_str = re.sub(r'}\s*{', r'},{', json_str)  # Missing commas between objects
    json_str = re.sub(r']\s*\[', r'],[', json_str)  # Missing commas between arrays
    
    # Strategy 4: Try to parse the extracted/cleaned JSON
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # One more attempt: try to fix truncated JSON
        if json_str.count('{') > json_str.count('}'):
            json_str += '}' * (json_str.count('{') - json_str.count('}'))
        if json_str.count('[') > json_str.count(']'):
            json_str += ']' * (json_str.count('[') - json_str.count(']'))
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            raise AIJSONParseError(component, f"Parse error: {e}. Snippet: {json_str[:200]}")


# =============================================================================
# OPENROUTER API CALL WITH ROBUST RETRY
# =============================================================================

async def call_llm_with_retry(
    prompt: str,
    system_message: str,
    component_name: str,
    max_tokens: int = MAX_TOKENS_QUIZ,
) -> Any:
    """
    LLM call with production-grade retry logic.
    
    Retries on:
    - Timeout
    - Network error
    - 5xx errors
    - Rate limit (429)
    - Invalid JSON
    
    Returns parsed JSON on success.
    Raises AIGenerationError after MAX_RETRIES_PER_COMPONENT exhausted.
    """
    last_error = None
    
    for attempt in range(1, MAX_RETRIES_PER_COMPONENT + 1):
        delay = min(RETRY_BASE_DELAY ** attempt, MAX_RETRY_DELAY)
        
        try:
            logger.info(f"🔄 [{component_name}] Attempt {attempt}/{MAX_RETRIES_PER_COMPONENT}")
            
            raw_response = await _make_llm_request(
                prompt=prompt,
                system_message=system_message,
                max_tokens=max_tokens,
            )
            
            if not raw_response:
                raise AIRetryableError(component_name, "Empty API response")
            
            # Parse JSON
            parsed = extract_json_strict(raw_response, component_name)
            logger.info(f"✅ [{component_name}] JSON parsed successfully on attempt {attempt}")
            return parsed
            
        except AIJSONParseError as e:
            logger.warning(f"⚠️ [{component_name}] JSON parse error on attempt {attempt}: {e}")
            last_error = e
            
        except httpx.TimeoutException:
            logger.warning(f"⏱️ [{component_name}] Timeout on attempt {attempt}")
            last_error = AIRetryableError(component_name, f"Timeout after {API_TIMEOUT}s")
            
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 429:  # Rate limit
                logger.warning(f"🚫 [{component_name}] Rate limited on attempt {attempt}")
                delay = min(delay * 3, MAX_RETRY_DELAY)  # Triple delay for rate limit
                last_error = AIRetryableError(component_name, "Rate limited")
            elif status_code >= 500:  # Server error
                logger.warning(f"❌ [{component_name}] Server error {status_code} on attempt {attempt}")
                last_error = AIRetryableError(component_name, f"Server error {status_code}")
            else:
                # Client error (4xx except 429) - still retry
                logger.warning(f"❌ [{component_name}] Client error {status_code} on attempt {attempt}")
                last_error = AIRetryableError(component_name, f"Client error {status_code}")
                
        except httpx.RequestError as e:
            logger.warning(f"🌐 [{component_name}] Network error on attempt {attempt}: {e}")
            last_error = AIRetryableError(component_name, f"Network error: {e}")
            
        except AIServiceError as e:
            logger.warning(f"❌ [{component_name}] Service error on attempt {attempt}: {e}")
            last_error = e
            
        except Exception as e:
            logger.error(f"❌ [{component_name}] Unexpected error on attempt {attempt}: {e}")
            last_error = AIRetryableError(component_name, str(e))
        
        # Exponential backoff before retry
        if attempt < MAX_RETRIES_PER_COMPONENT:
            logger.info(f"⏳ [{component_name}] Retrying in {delay}s...")
            await asyncio.sleep(delay)
    
    # All retries exhausted for this component
    error_msg = str(last_error) if last_error else "Unknown error"
    logger.error(f"❌ [{component_name}] FAILED after {MAX_RETRIES_PER_COMPONENT} attempts: {error_msg}")
    raise AIGenerationError(component_name, error_msg, MAX_RETRIES_PER_COMPONENT)


async def _make_llm_request(
    prompt: str,
    system_message: str,
    max_tokens: int,
) -> str:
    """Internal OpenRouter API request"""
    if not OPENROUTER_API_KEY:
        raise AIServiceError("OPENROUTER_API_KEY not configured")
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://studybuddy.app",
        "X-Title": "StudyBuddy Learning Platform"
    }
    
    payload = {
        "model": MODEL_FOR_GENERATION,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "temperature": TEMPERATURE,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"}
    }
    
    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        response = await client.post(
            OPENROUTER_BASE_URL,
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            raise AIServiceError("No choices in API response")
        
        content = data["choices"][0]["message"]["content"]
        
        if not content:
            raise AIServiceError("Empty content in API response")
        
        return content.strip()


# =============================================================================
# CONTENT SUMMARIZATION (Token Safety)
# =============================================================================

async def summarize_content_if_needed(content: str, subject: str, chapter: str, standard: int) -> str:
    """
    Summarize content if it exceeds MAX_CONTENT_LENGTH.
    Ensures token safety for subsequent generations.
    """
    if len(content) <= MAX_CONTENT_LENGTH:
        return content
    
    logger.info(f"📝 Content too long ({len(content)} chars). Summarizing to prevent token overflow...")
    
    system_message = f"""You are an educational content summarizer for Class {standard} {subject}.
You MUST preserve ALL key facts, formulas, definitions, dates, numbers, and exam-important points.
Return ONLY valid JSON."""

    prompt = f"""Summarize this textbook chapter content while preserving ALL important information.

Chapter: {chapter}
Subject: {subject}
Class: {standard}

KEEP ALL:
- Definitions and their exact meanings
- Formulas and equations
- Important facts, dates, numbers
- Key concepts and their explanations
- Examples that illustrate concepts

CONTENT TO SUMMARIZE (first {CHUNK_SIZE} characters):
{content[:CHUNK_SIZE]}

Return JSON:
{{"summary": "comprehensive summary preserving all key information (max 4000 words)"}}"""

    try:
        result = await call_llm_with_retry(
            prompt=prompt,
            system_message=system_message,
            component_name="content_summary",
            max_tokens=4500,
        )
        
        if isinstance(result, dict) and "summary" in result:
            summary = result["summary"]
            logger.info(f"✅ Content summarized: {len(content)} → {len(summary)} chars")
            return summary
        else:
            logger.warning("⚠️ Summarization returned unexpected format, using truncated content")
            return content[:MAX_CONTENT_LENGTH]
            
    except Exception as e:
        logger.warning(f"⚠️ Summarization failed ({e}), using truncated content")
        return content[:MAX_CONTENT_LENGTH]


# =============================================================================
# STRICT SCHEMA VALIDATORS
# =============================================================================

def validate_revision_notes(data: Any) -> Dict[str, Any]:
    """
    STRICT validation for revision notes.
    
    Required:
    - key_concepts: list with at least 5 items
    - chapter_summary: string with at least 50 characters
    
    Raises AIValidationError if validation fails.
    """
    if not isinstance(data, dict):
        raise AIValidationError("revision_notes", f"Expected dict, got {type(data).__name__}")
    
    errors = []
    
    # Validate key_concepts
    if "key_concepts" not in data:
        errors.append("Missing 'key_concepts' field")
    elif not isinstance(data["key_concepts"], list):
        errors.append("'key_concepts' must be a list")
    elif len(data["key_concepts"]) < 5:
        errors.append(f"'key_concepts' requires at least 5 items, got {len(data['key_concepts'])}")
    else:
        for i, concept in enumerate(data["key_concepts"][:5]):
            if not isinstance(concept, dict):
                errors.append(f"key_concepts[{i}] is not a dict")
            elif "title" not in concept:
                errors.append(f"key_concepts[{i}] missing 'title'")
    
    # Validate chapter_summary
    if "chapter_summary" not in data:
        errors.append("Missing 'chapter_summary' field")
    elif not isinstance(data["chapter_summary"], str):
        errors.append("'chapter_summary' must be a string")
    elif len(data["chapter_summary"]) < 50:
        errors.append(f"'chapter_summary' too short: {len(data['chapter_summary'])} chars (min 50)")
    
    if errors:
        raise AIValidationError("revision_notes", "; ".join(errors))
    
    logger.info("✅ revision_notes validation PASSED")
    return data


def validate_flashcards(data: Any) -> List[Dict]:
    """
    STRICT validation for flashcards.
    
    Required:
    - Exactly 15 flashcards
    - Each card has front and back
    
    Returns normalized flashcard list.
    Raises AIValidationError if validation fails.
    """
    cards = data
    
    # Handle wrapped format
    if isinstance(data, dict):
        for key in ["flashcards", "cards"]:
            if key in data and isinstance(data[key], list):
                cards = data[key]
                break
        else:
            # Find any list value
            for value in data.values():
                if isinstance(value, list) and len(value) > 0:
                    cards = value
                    break
    
    if not isinstance(cards, list):
        raise AIValidationError("flashcards", f"Expected list, got {type(cards).__name__}")
    
    # STRICT: At least 15 flashcards
    if len(cards) < 15:
        raise AIValidationError("flashcards", f"Expected 15 flashcards, got {len(cards)}")
    
    # Use exactly 15
    cards = cards[:15]
    
    # Validate each card
    errors = []
    for i, card in enumerate(cards):
        if not isinstance(card, dict):
            errors.append(f"Card {i+1} is not a dict")
            continue
        
        # Check for front/question field
        has_front = any(k in card for k in ["front", "question", "q", "term", "concept"])
        has_back = any(k in card for k in ["back", "answer", "a", "definition", "explanation"])
        
        if not has_front:
            errors.append(f"Card {i+1} missing front/question")
        if not has_back:
            errors.append(f"Card {i+1} missing back/answer")
    
    if errors:
        raise AIValidationError("flashcards", "; ".join(errors[:5]))
    
    # Normalize structure
    normalized = []
    for i, card in enumerate(cards):
        front = (card.get("front") or card.get("question") or 
                 card.get("q") or card.get("term") or card.get("concept") or "")
        back = (card.get("back") or card.get("answer") or 
                card.get("a") or card.get("definition") or card.get("explanation") or "")
        
        normalized.append({
            "id": i + 1,
            "front": front,
            "back": back,
            "hint": card.get("hint", ""),
            "category": card.get("category", "general"),
            "exam_likelihood": card.get("exam_likelihood", "medium")
        })
    
    logger.info("✅ flashcards validation PASSED (15 cards)")
    return normalized


def validate_quiz(data: Any, difficulty: str) -> Dict[str, Any]:
    """
    STRICT validation for quiz.
    
    Required:
    - Exactly 15 questions
    - Each question has: question text, 4 options, correct_answer (0-3)
    
    Returns validated quiz dict.
    Raises AIValidationError if validation fails.
    """
    component_name = f"quiz_{difficulty}"
    
    if not isinstance(data, dict):
        raise AIValidationError(component_name, f"Expected dict, got {type(data).__name__}")
    
    # Check questions field
    questions = None
    if "questions" in data:
        questions = data["questions"]
    elif "quiz" in data and isinstance(data["quiz"], dict):
        questions = data["quiz"].get("questions")
    
    if questions is None:
        # Try to find questions array
        for key, value in data.items():
            if isinstance(value, list) and len(value) > 0:
                if isinstance(value[0], dict) and ("question" in value[0] or "options" in value[0]):
                    questions = value
                    break
    
    if questions is None:
        raise AIValidationError(component_name, "Missing 'questions' array")
    
    if not isinstance(questions, list):
        raise AIValidationError(component_name, f"'questions' must be list, got {type(questions).__name__}")
    
    # STRICT: At least 15 questions
    if len(questions) < 15:
        raise AIValidationError(component_name, f"Expected 15 questions, got {len(questions)}")
    
    # Use exactly 15
    questions = questions[:15]
    
    # Validate each question
    errors = []
    validated_questions = []
    
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            errors.append(f"Q{i+1} is not a dict")
            continue
        
        # Question text
        question_text = q.get("question") or q.get("text") or q.get("q")
        if not question_text:
            errors.append(f"Q{i+1} missing question text")
            continue
        
        # Options (must have exactly 4)
        options = q.get("options") or q.get("choices") or []
        if len(options) != 4:
            errors.append(f"Q{i+1} has {len(options)} options (need exactly 4)")
            continue
        
        # Correct answer
        correct_answer = q.get("correct_answer")
        if correct_answer is None:
            correct_answer = q.get("answer")
        if correct_answer is None:
            correct_answer = q.get("correct_index")
        if correct_answer is None:
            correct_answer = q.get("correct")
        
        # Handle different formats
        if isinstance(correct_answer, str):
            # Could be "A", "B", "C", "D" or "0", "1", "2", "3"
            if correct_answer.upper() in ["A", "B", "C", "D"]:
                correct_answer = ord(correct_answer.upper()) - ord('A')
            elif correct_answer in options:
                correct_answer = options.index(correct_answer)
            else:
                try:
                    correct_answer = int(correct_answer)
                except (ValueError, TypeError):
                    errors.append(f"Q{i+1} invalid correct_answer: {correct_answer}")
                    continue
        
        if not isinstance(correct_answer, int) or correct_answer < 0 or correct_answer > 3:
            errors.append(f"Q{i+1} correct_answer must be 0-3, got {correct_answer}")
            continue
        
        # Build validated question
        validated_q = {
            "id": i + 1,
            "question": question_text,
            "options": [str(opt) for opt in options[:4]],
            "correct_answer": correct_answer,
            "explanation": str(q.get("explanation", ""))[:300]  # Limit explanation length
        }
        validated_questions.append(validated_q)
    
    if len(validated_questions) < 15:
        errors.append(f"Only {len(validated_questions)} valid questions out of 15 required")
    
    if errors:
        raise AIValidationError(component_name, "; ".join(errors[:5]))
    
    # Build final quiz structure
    result = {
        "difficulty": difficulty,
        "questions": validated_questions[:15]
    }
    
    logger.info(f"✅ {component_name} validation PASSED (15 questions)")
    return result


# =============================================================================
# AGE-APPROPRIATE CONTEXT
# =============================================================================

def get_age_context(standard: int) -> dict:
    """Get age-appropriate language and complexity guidance"""
    if standard <= 4:
        return {
            "age_group": "6-10 years",
            "language": "very simple words, short sentences, fun examples",
            "complexity": "basic concepts only",
            "examples": "toys, animals, food, family, games"
        }
    elif standard <= 6:
        return {
            "age_group": "10-12 years",
            "language": "simple but complete sentences",
            "complexity": "foundational concepts",
            "examples": "school activities, sports, nature"
        }
    elif standard <= 8:
        return {
            "age_group": "12-14 years",
            "language": "clear academic language",
            "complexity": "intermediate concepts",
            "examples": "real-world applications, technology"
        }
    else:
        return {
            "age_group": "14-18 years",
            "language": "academic and technical language",
            "complexity": "advanced concepts",
            "examples": "scientific applications, board exam patterns"
        }


# =============================================================================
# GENERATION FUNCTIONS
# =============================================================================

async def generate_revision_notes(subject: str, chapter: str, content: str, standard: int) -> Dict:
    """Generate concise, exam-focused revision notes with strict validation"""
    age = get_age_context(standard)
    
    system_message = f"""You are an expert {subject} teacher creating LAST-DAY REVISION NOTES for Class {standard} students preparing for exams.
CRITICAL: Keep it concise, structured, and exam-focused. NO verbose explanations.
You MUST return ONLY valid JSON. No markdown code blocks. No explanations. No backticks.
Start your response directly with {{ and end with }}."""

    prompt = f"""Create CONCISE LAST-DAY REVISION NOTES for Class {standard} students ({age['age_group']}) preparing for exams.

Subject: {subject}
Chapter: {chapter}

TEXTBOOK CONTENT:
{content}

CRITICAL REQUIREMENTS:
- CONCISE and TO-THE-POINT (no verbose explanations)
- EXAM-FOCUSED (only what's likely to be asked)
- STRUCTURED for quick revision (bullet points, short paragraphs)
- Suitable for last-minute revision before exam

Return ONLY this JSON structure:
{{
  "key_concepts": [
    {{
      "title": "Concept Name",
      "explanation": "2-3 sentences MAX. Clear and concise using {age['language']}",
      "exam_tip": "How this is tested (1 sentence)",
      "example": "Brief example"
    }}
  ],
  "exam_important_points": [
    {{
      "point": "Important fact likely to be asked (concise)",
      "type": "definition/formula/fact",
      "memory_trick": "Short memory aid"
    }}
  ],
  "definitions": [
    {{
      "term": "Important term",
      "meaning": "Clear, concise definition (1 sentence)"
    }}
  ],
  "quick_revision_points": [
    "Short point 1", "Short point 2", "Short point 3", "Short point 4", "Short point 5"
  ],
  "chapter_summary": "2-3 sentences summarizing the entire chapter for quick revision"
}}

REMEMBER:
- Keep explanations SHORT (2-3 sentences maximum)
- Focus on EXAM-IMPORTANT content only
- Use bullet-point style writing
- Suitable for 15-minute revision before exam
- Include at least 5 key_concepts
- Include at least 6 exam_important_points
- chapter_summary must be concise (2-3 sentences)
- Use {age['language']}"""

    result = await call_llm_with_retry(
        prompt=prompt,
        system_message=system_message,
        component_name="revision_notes",
        max_tokens=MAX_TOKENS_CONTENT,
    )
    
    return validate_revision_notes(result)


async def generate_flashcards(subject: str, chapter: str, content: str, standard: int) -> List[Dict]:
    """Generate exactly 15 flashcards with strict validation"""
    age = get_age_context(standard)
    
    system_message = f"""You are creating exam-focused flashcards for Class {standard} {subject}.
You MUST return ONLY valid JSON. No markdown. No explanations. No backticks.
Start your response directly with {{ and end with }}."""

    prompt = f"""Generate EXACTLY 15 flashcards for Class {standard} students.

Subject: {subject}
Chapter: {chapter}

TEXTBOOK CONTENT:
{content}

Return ONLY this JSON:
{{
  "flashcards": [
    {{
      "id": 1,
      "front": "Question or term",
      "back": "Answer or definition",
      "hint": "Memory trick or clue",
      "category": "definition/formula/fact/concept",
      "exam_likelihood": "high/medium"
    }}
  ]
}}

REQUIREMENTS:
- EXACTLY 15 flashcards (numbered 1-15)
- Focus on exam-important content
- Include definitions, formulas, key facts
- Use {age['language']}
- Mix of difficulty levels"""

    result = await call_llm_with_retry(
        prompt=prompt,
        system_message=system_message,
        component_name="flashcards",
        max_tokens=MAX_TOKENS_CONTENT,
    )
    
    return validate_flashcards(result)


async def generate_quiz(
    subject: str, 
    chapter: str, 
    content: str, 
    standard: int,
    difficulty: str,
    description: str
) -> Dict:
    """Generate a quiz with exactly 15 questions"""
    age = get_age_context(standard)
    
    system_message = f"""You are creating a {difficulty} level practice quiz for Class {standard} {subject}.
You MUST return ONLY valid JSON. No markdown. No explanations. No backticks.
Start your response directly with {{ and end with }}."""

    prompt = f"""Generate EXACTLY 15 multiple choice questions.

Subject: {subject}
Chapter: {chapter}
Difficulty: {difficulty}
Description: {description}

CHAPTER CONTENT:
{content}

Return ONLY this JSON:
{{
  "difficulty": "{difficulty}",
  "questions": [
    {{
      "id": 1,
      "question": "Clear question text?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct_answer": 0,
      "explanation": "Brief explanation (1-2 sentences)."
    }}
  ]
}}

REQUIREMENTS:
- EXACTLY 15 questions (id: 1-15)
- EXACTLY 4 options per question
- correct_answer: 0, 1, 2, or 3 (index of correct option)
- Difficulty: {difficulty}
- Questions should match the difficulty level
- Use {age['language']}
- Explanations should be concise (max 2 sentences)"""

    result = await call_llm_with_retry(
        prompt=prompt,
        system_message=system_message,
        component_name=f"quiz_{difficulty}",
        max_tokens=MAX_TOKENS_QUIZ,
    )
    
    return validate_quiz(result, difficulty)


# =============================================================================
# QUIZ COMBINER
# =============================================================================

def combine_all_quizzes(
    quiz_easy: Dict,
    quiz_medium: Dict,
    quiz_hard: Dict,
    quiz_advanced_1: Dict,
    quiz_advanced_2: Dict
) -> Dict[str, Any]:
    """Combine 5 quizzes into storage format"""
    
    quizzes = []
    
    # Quiz 1: Easy
    quiz_easy["quiz_id"] = 1
    quiz_easy["title"] = "Easy - Basic Concepts"
    quiz_easy["description"] = "Basic recall, definitions, direct facts"
    quizzes.append(quiz_easy)
    
    # Quiz 2: Medium
    quiz_medium["quiz_id"] = 2
    quiz_medium["title"] = "Medium - Understanding"
    quiz_medium["description"] = "Application of concepts, simple problems"
    quizzes.append(quiz_medium)
    
    # Quiz 3: Hard
    quiz_hard["quiz_id"] = 3
    quiz_hard["title"] = "Hard - Challenge"
    quiz_hard["description"] = "Complex problems, multi-step reasoning"
    quizzes.append(quiz_hard)
    
    # Quiz 4: Advanced 1
    quiz_advanced_1["quiz_id"] = 4
    quiz_advanced_1["title"] = "Advanced 1 - Application"
    quiz_advanced_1["description"] = "Real-world applications, advanced problems"
    quiz_advanced_1["for_strong_students"] = True
    quizzes.append(quiz_advanced_1)
    
    # Quiz 5: Advanced 2
    quiz_advanced_2["quiz_id"] = 5
    quiz_advanced_2["title"] = "Advanced 2 - Analysis"
    quiz_advanced_2["description"] = "Analytical thinking, integration of concepts"
    quiz_advanced_2["for_strong_students"] = True
    quizzes.append(quiz_advanced_2)
    
    return {
        "quizzes": quizzes,
        "total_quizzes": 5,
        "total_questions": 75,
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# =============================================================================
# MAIN ORCHESTRATOR (STRICT ATOMIC - ALL OR NOTHING)
# =============================================================================

async def generate_full_ai_content(
    subject: str,
    chapter: str,
    content: str,
    standard: int
) -> GenerationResult:
    """
    PRODUCTION-GRADE ATOMIC ORCHESTRATOR - ALL OR NOTHING
    
    Generates ALL 7 components in memory first:
    1. Revision Notes
    2. Flashcards (15)
    3. Easy Quiz (15Q)
    4. Medium Quiz (15Q)
    5. Hard Quiz (15Q)
    6. Advanced 1 Quiz (15Q)
    7. Advanced 2 Quiz (15Q)
    
    If ANY component fails validation, ALL are discarded.
    NO partial saves. Returns complete result or error.
    """
    start_time = datetime.now(timezone.utc)
    total_attempts = 0
    
    logger.info("=" * 70)
    logger.info("🚀 PRODUCTION-GRADE AI GENERATION - ALL OR NOTHING")
    logger.info(f"   Subject: {subject}")
    logger.info(f"   Chapter: {chapter}")
    logger.info(f"   Standard: {standard}")
    logger.info(f"   Content: {len(content)} characters")
    logger.info("   Components: 7 (revision notes, flashcards, 5 quizzes)")
    logger.info("   Total Questions: 75")
    logger.info("=" * 70)
    
    try:
        # TOKEN SAFETY: Summarize large content
        processed_content = await summarize_content_if_needed(content, subject, chapter, standard)
        
        # =====================================================================
        # STEP 1: REVISION NOTES
        # =====================================================================
        logger.info("📝 [1/7] Generating Revision Notes...")
        revision_notes = await generate_revision_notes(subject, chapter, processed_content, standard)
        total_attempts += 1
        logger.info("✅ [1/7] Revision Notes VALIDATED")
        
        # =====================================================================
        # STEP 2: FLASHCARDS
        # =====================================================================
        logger.info("🃏 [2/7] Generating Flashcards (15)...")
        flashcards = await generate_flashcards(subject, chapter, processed_content, standard)
        total_attempts += 1
        logger.info("✅ [2/7] Flashcards VALIDATED (15 cards)")
        
        # =====================================================================
        # STEP 3: EASY QUIZ
        # =====================================================================
        logger.info("📋 [3/7] Generating Easy Quiz (15 questions)...")
        quiz_easy = await generate_quiz(
            subject, chapter, processed_content, standard,
            "easy", "Basic recall, definitions, direct concepts from textbook"
        )
        total_attempts += 1
        logger.info("✅ [3/7] Easy Quiz VALIDATED (15 questions)")
        
        # =====================================================================
        # STEP 4: MEDIUM QUIZ
        # =====================================================================
        logger.info("📋 [4/7] Generating Medium Quiz (15 questions)...")
        quiz_medium = await generate_quiz(
            subject, chapter, processed_content, standard,
            "medium", "Application of concepts, simple numerical problems"
        )
        total_attempts += 1
        logger.info("✅ [4/7] Medium Quiz VALIDATED (15 questions)")
        
        # =====================================================================
        # STEP 5: HARD QUIZ
        # =====================================================================
        logger.info("📋 [5/7] Generating Hard Quiz (15 questions)...")
        quiz_hard = await generate_quiz(
            subject, chapter, processed_content, standard,
            "hard", "Challenging problems, multi-step reasoning, critical thinking"
        )
        total_attempts += 1
        logger.info("✅ [5/7] Hard Quiz VALIDATED (15 questions)")
        
        # =====================================================================
        # STEP 6: ADVANCED 1 QUIZ
        # =====================================================================
        logger.info("🎯 [6/7] Generating Advanced 1 Quiz (15 questions)...")
        quiz_advanced_1 = await generate_quiz(
            subject, chapter, processed_content, standard,
            "advanced_1", "Real-world applications, advanced numerical problems for strong students"
        )
        total_attempts += 1
        logger.info("✅ [6/7] Advanced 1 Quiz VALIDATED (15 questions)")
        
        # =====================================================================
        # STEP 7: ADVANCED 2 QUIZ
        # =====================================================================
        logger.info("🎯 [7/7] Generating Advanced 2 Quiz (15 questions)...")
        quiz_advanced_2 = await generate_quiz(
            subject, chapter, processed_content, standard,
            "advanced_2", "Analytical thinking, integration of multiple concepts for strong students"
        )
        total_attempts += 1
        logger.info("✅ [7/7] Advanced 2 Quiz VALIDATED (15 questions)")
        
        # =====================================================================
        # ALL COMPONENTS VALIDATED
        # =====================================================================
        end_time = datetime.now(timezone.utc)
        generation_time = (end_time - start_time).total_seconds()
        
        logger.info("=" * 70)
        logger.info("🎉 ALL 7 COMPONENTS GENERATED AND VALIDATED SUCCESSFULLY")
        logger.info("   ✅ Revision Notes")
        logger.info("   ✅ Flashcards (15)")
        logger.info("   ✅ Easy Quiz (15 questions)")
        logger.info("   ✅ Medium Quiz (15 questions)")
        logger.info("   ✅ Hard Quiz (15 questions)")
        logger.info("   ✅ Advanced 1 Quiz (15 questions)")
        logger.info("   ✅ Advanced 2 Quiz (15 questions)")
        logger.info("   Total: 75 quiz questions + 15 flashcards")
        logger.info(f"   Generation time: {generation_time:.1f} seconds")
        logger.info("=" * 70)
        
        return GenerationResult(
            success=True,
            revision_notes=revision_notes,
            flashcards=flashcards,
            quiz_easy=quiz_easy,
            quiz_medium=quiz_medium,
            quiz_hard=quiz_hard,
            quiz_advanced_1=quiz_advanced_1,
            quiz_advanced_2=quiz_advanced_2,
            total_attempts=total_attempts,
            generation_time_seconds=generation_time
        )
        
    except (AIGenerationError, AIValidationError, AIJSONParseError) as e:
        component = getattr(e, 'component', 'unknown')
        end_time = datetime.now(timezone.utc)
        generation_time = (end_time - start_time).total_seconds()
        
        logger.error("=" * 70)
        logger.error(f"❌ ATOMIC GENERATION FAILED at component: {component}")
        logger.error(f"   Error: {str(e)}")
        logger.error("   NO partial content saved. ALL components discarded.")
        logger.error(f"   Time elapsed: {generation_time:.1f} seconds")
        logger.error("=" * 70)
        
        return GenerationResult(
            success=False,
            error_component=component,
            error_message=str(e),
            total_attempts=total_attempts,
            generation_time_seconds=generation_time
        )
        
    except Exception as e:
        end_time = datetime.now(timezone.utc)
        generation_time = (end_time - start_time).total_seconds()
        
        logger.exception(f"❌ UNEXPECTED ERROR in generation: {e}")
        
        return GenerationResult(
            success=False,
            error_component="unknown",
            error_message=f"Unexpected error: {str(e)}",
            total_attempts=total_attempts,
            generation_time_seconds=generation_time
        )


# =============================================================================
# BACKGROUND TASK RUNNER (WITH INFINITE RETRY)
# =============================================================================

async def run_generation_background_task(
    chapter_id: str,
    subject_name: str,
    chapter_name: str,
    content: str,
    standard: int,
    school_name: str
):
    """
    Background task that runs AI generation with infinite retry.
    
    This function:
    1. Attempts generation with full retry logic
    2. On failure, waits and retries entire generation
    3. NEVER marks as permanently failed - keeps retrying
    4. Only commits to DB/S3 after ALL components validated
    
    Uses shared connection pool from database.py for RDS safety.
    """
    from sqlalchemy import text
    from app.models.database import AsyncSessionLocal
    
    full_retry = 0
    
    while True:  # Keep retrying until success
        full_retry += 1
        
        try:
            logger.info(f"🔄 Background generation attempt {full_retry} for chapter {chapter_id}")
            
            # Update status to show retry count
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("""
                        UPDATE chapters 
                        SET ai_retry_count = :retry_count,
                            ai_error_message = :msg
                        WHERE id = :chapter_id
                    """),
                    {
                        "chapter_id": chapter_id, 
                        "retry_count": full_retry,
                        "msg": f"Generation attempt {full_retry} in progress..."
                    }
                )
                await session.commit()
            
            # Generate all content
            result = await generate_full_ai_content(
                subject=subject_name,
                chapter=chapter_name,
                content=content,
                standard=standard
            )
            
            if not result.success:
                logger.warning(f"⚠️ Generation attempt {full_retry} failed: {result.error_message}")
                
                # Update error in DB
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        text("""
                            UPDATE chapters 
                            SET ai_retry_count = :retry_count,
                                ai_error_message = :error_msg
                            WHERE id = :chapter_id
                        """),
                        {
                            "chapter_id": chapter_id, 
                            "retry_count": full_retry,
                            "error_msg": f"Attempt {full_retry} failed: {result.error_message}. Retrying..."
                        }
                    )
                    await session.commit()
                
                # Wait with exponential backoff before retry (capped)
                delay = min(FULL_RETRY_DELAY * (1.5 ** min(full_retry - 1, 5)), 300)  # Cap at 5 minutes
                logger.info(f"⏳ Retrying full generation in {delay:.0f}s...")
                await asyncio.sleep(delay)
                continue
            
            # =====================================================================
            # SUCCESS - ATOMIC UPLOAD TO S3
            # =====================================================================
            logger.info("📤 All components validated. Uploading to S3...")
            
            from app.services.storage_service import upload_ai_content_to_s3, normalize_chapter_slug, sanitize_school_name, sanitize_component
            
            # Combine quizzes into storage format
            practice_quiz = combine_all_quizzes(
                result.quiz_easy,
                result.quiz_medium,
                result.quiz_hard,
                result.quiz_advanced_1,
                result.quiz_advanced_2
            )
            
            # Upload all components to S3
            s3_keys = {}
            
            s3_keys["revision_notes"] = await upload_ai_content_to_s3(
                result.revision_notes, standard, subject_name, chapter_name,
                "revision_notes", school_name=school_name
            )
            logger.info("   ✅ Revision notes uploaded")
            
            s3_keys["flashcards"] = await upload_ai_content_to_s3(
                result.flashcards, standard, subject_name, chapter_name,
                "flashcards", school_name=school_name
            )
            logger.info("   ✅ Flashcards uploaded")
            
            s3_keys["practice_quiz"] = await upload_ai_content_to_s3(
                practice_quiz, standard, subject_name, chapter_name,
                "practice_quiz", school_name=school_name
            )
            logger.info("   ✅ Practice quizzes uploaded")
            
            # Build AI content prefix for DB
            class_folder = f"class{standard}"
            subject_folder = sanitize_component(subject_name)
            chapter_folder = normalize_chapter_slug(chapter_name)
            
            if school_name:
                school_folder = sanitize_school_name(school_name)
                ai_prefix = f"{school_folder}/ai_content/{class_folder}/{subject_folder}/{chapter_folder}/"
            else:
                ai_prefix = f"ai_content/{class_folder}/{subject_folder}/{chapter_folder}/"
            
            # =====================================================================
            # ATOMIC DB UPDATE - Mark as completed
            # =====================================================================
            async with AsyncSessionLocal() as session:
                await session.execute(
                    text("""
                        UPDATE chapters 
                        SET ai_generated = true,
                            ai_status = 'completed',
                            ai_content_prefix = :prefix,
                            ai_generated_at = :generated_at,
                            ai_error_message = NULL,
                            ai_retry_count = :retry_count
                        WHERE id = :chapter_id
                    """),
                    {
                        "chapter_id": chapter_id,
                        "prefix": ai_prefix,
                        "generated_at": datetime.now(timezone.utc),
                        "retry_count": full_retry
                    }
                )
                await session.commit()
            
            logger.info("=" * 70)
            logger.info("🎉 BACKGROUND GENERATION COMPLETED SUCCESSFULLY")
            logger.info(f"   Chapter: {chapter_name}")
            logger.info(f"   Subject: {subject_name}")
            logger.info(f"   Standard: {standard}")
            logger.info(f"   S3 Prefix: {ai_prefix}")
            logger.info(f"   Total Attempts: {full_retry}")
            logger.info(f"   Generation Time: {result.generation_time_seconds:.1f}s")
            logger.info("=" * 70)
            
            return  # SUCCESS - Exit the infinite loop
            
        except Exception as e:
            logger.exception(f"❌ Background task error on attempt {full_retry}: {e}")
            
            # Update error in DB
            try:
                async with AsyncSessionLocal() as session:
                    await session.execute(
                        text("""
                            UPDATE chapters 
                            SET ai_error_message = :error_msg,
                                ai_retry_count = :retry_count
                            WHERE id = :chapter_id
                        """),
                        {
                            "chapter_id": chapter_id, 
                            "error_msg": f"Attempt {full_retry} error: {str(e)}. Retrying...",
                            "retry_count": full_retry
                        }
                    )
                    await session.commit()
            except Exception as db_err:
                logger.warning(f"Failed to update error in DB: {db_err}")
            
            # Wait before retry
            delay = min(FULL_RETRY_DELAY * (1.5 ** min(full_retry - 1, 5)), 300)
            logger.info(f"⏳ Retrying in {delay:.0f}s after error...")
            await asyncio.sleep(delay)
    
    # This should never be reached due to infinite loop
