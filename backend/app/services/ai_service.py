import os
import json
import hashlib
import re
import asyncio
from typing import Optional, Dict, List, Any, Tuple
from app.models.database import get_redis
import logging
from dotenv import load_dotenv
import httpx

load_dotenv()

logger = logging.getLogger(__name__)

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# Model assignment based on task type (Updated Feb 2026)
# Using anthropic/claude-sonnet-4.5 for AI content generation (best reliability)
# Using google/gemini-2.5-flash-lite for evaluation tasks
MODEL_FOR_EVALUATION = "google/gemini-2.5-flash-lite"  # For grading/evaluation
MODEL_FOR_GENERATION = "anthropic/claude-sonnet-4.5"  # For AI content generation (quiz, notes, flashcards)

# STRICT ATOMIC PIPELINE CONFIGURATION
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s
STRUCTURED_OUTPUT_TEMPERATURE = 0.3  # Low temperature for consistent JSON
MAX_CONTENT_LENGTH = 5000  # Prevent token overflow

if OPENROUTER_API_KEY:
    logger.info(f"✅ OpenRouter configured with models:")
    logger.info(f"   - Evaluation: {MODEL_FOR_EVALUATION}")
    logger.info(f"   - Generation: {MODEL_FOR_GENERATION}")
    logger.info(f"   - Retry Policy: {MAX_RETRIES} attempts with exponential backoff")
else:
    logger.warning("⚠️ OPENROUTER_API_KEY not set - AI features will not work")


# =============================================================================
# CUSTOM EXCEPTIONS FOR STRICT ATOMIC PIPELINE
# =============================================================================

class AIServiceError(Exception):
    """Base exception for AI service errors"""
    pass

class AIGenerationError(AIServiceError):
    """Raised when AI content generation fails"""
    def __init__(self, component: str, reason: str, attempt: int = 0):
        self.component = component
        self.reason = reason
        self.attempt = attempt
        super().__init__(f"{component} generation failed: {reason} (attempt {attempt})")

class AIValidationError(AIServiceError):
    """Raised when AI content validation fails"""
    def __init__(self, component: str, validation_error: str):
        self.component = component
        self.validation_error = validation_error
        super().__init__(f"{component} validation failed: {validation_error}")

class AIJSONParseError(AIServiceError):
    """Raised when JSON parsing fails after all retries"""
    def __init__(self, component: str, raw_response: str = ""):
        self.component = component
        self.raw_response = raw_response[:200] if raw_response else ""
        super().__init__(f"{component} JSON parsing failed. Response snippet: {self.raw_response}")


# =============================================================================
# STAGE 1: STRICT JSON EXTRACTION (CLAUDE-OPTIMIZED)
# =============================================================================

def extract_json_strict(text: str) -> str:
    """
    STRICT JSON extraction for Claude responses.
    Handles common Claude output patterns:
    - JSON wrapped in markdown code blocks
    - JSON with preceding text/explanation
    - Multiple JSON blocks (uses first valid one)
    - Control characters and whitespace issues
    """
    if not text:
        raise AIJSONParseError("unknown", "Empty response received")
    
    # Step 1: Remove control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    text = text.strip()
    
    # Step 2: Try to find JSON in markdown code blocks first (most common)
    json_block_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```', text)
    if json_block_match:
        return json_block_match.group(1).strip()
    
    # Step 3: If response starts with text before JSON, find the JSON block
    # Look for first { or [ that starts a JSON structure
    json_start_obj = text.find('{')
    json_start_arr = text.find('[')
    
    if json_start_obj == -1 and json_start_arr == -1:
        raise AIJSONParseError("unknown", f"No JSON found in response: {text[:100]}")
    
    # Determine which comes first
    if json_start_obj == -1:
        json_start = json_start_arr
        json_end_char = ']'
    elif json_start_arr == -1:
        json_start = json_start_obj
        json_end_char = '}'
    else:
        if json_start_obj < json_start_arr:
            json_start = json_start_obj
            json_end_char = '}'
        else:
            json_start = json_start_arr
            json_end_char = ']'
    
    # Find the matching closing bracket
    bracket_count = 0
    json_end = -1
    for i, char in enumerate(text[json_start:], json_start):
        if char in '{[':
            bracket_count += 1
        elif char in '}]':
            bracket_count -= 1
            if bracket_count == 0:
                json_end = i + 1
                break
    
    if json_end == -1:
        raise AIJSONParseError("unknown", f"Unbalanced JSON brackets in response")
    
    json_str = text[json_start:json_end].strip()
    
    # Step 4: Fix common JSON errors from LLM output
    # Remove trailing commas before closing brackets
    json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    # Fix missing commas between objects
    json_str = re.sub(r'}\s*{', r'},{', json_str)
    
    return json_str


def extract_json_from_response(text: str) -> Optional[str]:
    """Legacy function - wrapper around extract_json_strict for backward compatibility"""
    try:
        return extract_json_strict(text)
    except AIJSONParseError:
        return None


# =============================================================================
# STAGE 2: RETRY WRAPPER WITH EXPONENTIAL BACKOFF
# =============================================================================

async def call_llm_with_retry(
    prompt: str,
    system_message: str,
    component_name: str,
    timeout: float = 90.0,
    max_tokens: int = 3500
) -> Dict[str, Any]:
    """
    STAGE 2: LLM call with strict retry logic and exponential backoff.
    
    Returns parsed JSON dict on success.
    Raises AIGenerationError after all retries exhausted.
    """
    last_error = None
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"🔄 [{component_name}] Attempt {attempt}/{MAX_RETRIES}")
            
            # Make the API call
            raw_response = await _call_openrouter_api(
                prompt=prompt,
                system_message=system_message,
                timeout=timeout,
                max_tokens=max_tokens,
                temperature=STRUCTURED_OUTPUT_TEMPERATURE
            )
            
            if not raw_response:
                raise AIGenerationError(component_name, "Empty response from API", attempt)
            
            # Try to parse JSON
            try:
                json_str = extract_json_strict(raw_response)
                parsed = json.loads(json_str)
                logger.info(f"✅ [{component_name}] Successfully parsed JSON on attempt {attempt}")
                return parsed
            except (json.JSONDecodeError, AIJSONParseError) as e:
                logger.warning(f"⚠️ [{component_name}] JSON parse error on attempt {attempt}: {e}")
                last_error = AIJSONParseError(component_name, raw_response)
                
        except httpx.TimeoutException:
            logger.warning(f"⏱️ [{component_name}] Timeout on attempt {attempt}")
            last_error = AIGenerationError(component_name, f"Timeout after {timeout}s", attempt)
        except AIServiceError as e:
            logger.warning(f"❌ [{component_name}] API error on attempt {attempt}: {e}")
            last_error = e
        except Exception as e:
            logger.error(f"❌ [{component_name}] Unexpected error on attempt {attempt}: {e}")
            last_error = AIGenerationError(component_name, str(e), attempt)
        
        # Exponential backoff before retry
        if attempt < MAX_RETRIES:
            delay = RETRY_DELAYS[attempt - 1]
            logger.info(f"⏳ [{component_name}] Retrying in {delay}s...")
            await asyncio.sleep(delay)
    
    # All retries exhausted
    logger.error(f"❌ [{component_name}] FAILED after {MAX_RETRIES} attempts")
    raise AIGenerationError(component_name, f"Failed after {MAX_RETRIES} retries: {last_error}", MAX_RETRIES)


async def _call_openrouter_api(
    prompt: str,
    system_message: str,
    timeout: float,
    max_tokens: int,
    temperature: float
) -> str:
    """Internal function to make OpenRouter API call"""
    api_key = OPENROUTER_API_KEY
    
    if not api_key:
        raise AIServiceError("OpenRouter API key not set")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
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
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"}
    }
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            OPENROUTER_BASE_URL,
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            raise AIServiceError(f"OpenRouter API returned {response.status_code}: {response.text[:200]}")
        
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            raise AIServiceError("No choices in OpenRouter response")
        
        content = data["choices"][0]["message"]["content"]
        
        if not content:
            raise AIServiceError("Empty content in OpenRouter response")
        
        return content.strip()


# =============================================================================
# STAGE 3: STRICT VALIDATION FUNCTIONS
# =============================================================================

def validate_revision_notes(notes: Dict[str, Any]) -> None:
    """
    STRICT validation for revision notes.
    Raises AIValidationError if validation fails.
    """
    errors = []
    
    # Check required fields exist
    required_fields = ["key_concepts", "exam_important_points", "chapter_summary"]
    for field in required_fields:
        if field not in notes:
            errors.append(f"Missing required field: {field}")
    
    # Validate key_concepts
    if "key_concepts" in notes:
        concepts = notes["key_concepts"]
        if not isinstance(concepts, list):
            errors.append("key_concepts must be a list")
        elif len(concepts) < 3:
            errors.append(f"key_concepts must have at least 3 items, got {len(concepts)}")
        else:
            for i, concept in enumerate(concepts):
                if not isinstance(concept, dict):
                    errors.append(f"key_concepts[{i}] must be a dict")
                elif "title" not in concept or "explanation" not in concept:
                    errors.append(f"key_concepts[{i}] missing title or explanation")
    
    # Validate exam_important_points
    if "exam_important_points" in notes:
        points = notes["exam_important_points"]
        if not isinstance(points, list):
            errors.append("exam_important_points must be a list")
        elif len(points) < 3:
            errors.append(f"exam_important_points must have at least 3 items, got {len(points)}")
    
    # Validate chapter_summary
    if "chapter_summary" in notes:
        summary = notes["chapter_summary"]
        if not isinstance(summary, str):
            errors.append("chapter_summary must be a string")
        elif len(summary) < 50:
            errors.append(f"chapter_summary too short: {len(summary)} chars (min 50)")
    
    # Check for apology/error text that indicates failure
    full_text = json.dumps(notes).lower()
    bad_phrases = ["i apologize", "i'm sorry", "i cannot", "unable to", "error generating"]
    for phrase in bad_phrases:
        if phrase in full_text:
            errors.append(f"Response contains failure indicator: '{phrase}'")
            break
    
    if errors:
        raise AIValidationError("revision_notes", "; ".join(errors))
    
    logger.info("✅ Revision notes validation PASSED")


def validate_flashcards(flashcards: Any) -> List[Dict]:
    """
    STRICT validation for flashcards.
    Raises AIValidationError if validation fails.
    Returns the validated flashcard list.
    """
    errors = []
    
    # Handle wrapped format
    cards = flashcards
    if isinstance(flashcards, dict):
        if "flashcards" in flashcards:
            cards = flashcards["flashcards"]
        elif "cards" in flashcards:
            cards = flashcards["cards"]
        else:
            # Try to find first list value
            for key, value in flashcards.items():
                if isinstance(value, list):
                    cards = value
                    break
    
    if not isinstance(cards, list):
        raise AIValidationError("flashcards", f"Expected list, got {type(cards).__name__}")
    
    if len(cards) < 10:
        raise AIValidationError("flashcards", f"Minimum 10 flashcards required, got {len(cards)}")
    
    # Validate each flashcard
    for i, card in enumerate(cards):
        if not isinstance(card, dict):
            errors.append(f"Card {i} is not a dict")
            continue
        
        # Check required fields (flexible naming)
        has_question = any(k in card for k in ["front", "question", "q"])
        has_answer = any(k in card for k in ["back", "answer", "a"])
        
        if not has_question:
            errors.append(f"Card {i} missing question/front")
        if not has_answer:
            errors.append(f"Card {i} missing answer/back")
    
    if errors:
        raise AIValidationError("flashcards", "; ".join(errors[:5]))  # Limit error messages
    
    # Normalize flashcard structure
    normalized = []
    for i, card in enumerate(cards):
        normalized.append({
            "id": card.get("id", i + 1),
            "front": card.get("front") or card.get("question") or card.get("q", ""),
            "back": card.get("back") or card.get("answer") or card.get("a", ""),
            "hint": card.get("hint", ""),
            "category": card.get("category", "general"),
            "exam_likelihood": card.get("exam_likelihood", "medium")
        })
    
    logger.info(f"✅ Flashcards validation PASSED ({len(normalized)} cards)")
    return normalized


def validate_quiz(quiz_data: Dict[str, Any], quiz_type: str, min_questions: int = 10) -> Dict:
    """
    STRICT validation for quiz data.
    Raises AIValidationError if validation fails.
    Returns validated quiz structure.
    """
    errors = []
    
    # Check for quizzes array
    if "quizzes" not in quiz_data:
        raise AIValidationError(quiz_type, "Missing 'quizzes' array in response")
    
    quizzes = quiz_data["quizzes"]
    if not isinstance(quizzes, list):
        raise AIValidationError(quiz_type, f"'quizzes' must be a list, got {type(quizzes).__name__}")
    
    if len(quizzes) < 3:
        raise AIValidationError(quiz_type, f"Expected 3 quizzes, got {len(quizzes)}")
    
    # Validate each quiz
    for q_idx, quiz in enumerate(quizzes):
        if not isinstance(quiz, dict):
            errors.append(f"Quiz {q_idx} is not a dict")
            continue
        
        if "questions" not in quiz:
            errors.append(f"Quiz {q_idx} missing 'questions' array")
            continue
        
        questions = quiz["questions"]
        if not isinstance(questions, list):
            errors.append(f"Quiz {q_idx} 'questions' is not a list")
            continue
        
        if len(questions) < min_questions:
            errors.append(f"Quiz {q_idx} has {len(questions)} questions (min {min_questions})")
        
        # Validate each question
        for i, q in enumerate(questions[:min_questions]):  # Only validate required count
            if not isinstance(q, dict):
                errors.append(f"Quiz {q_idx} Q{i} is not a dict")
                continue
            
            if "question" not in q and "text" not in q:
                errors.append(f"Quiz {q_idx} Q{i} missing question text")
            
            if "options" not in q and "choices" not in q:
                errors.append(f"Quiz {q_idx} Q{i} missing options")
            else:
                opts = q.get("options") or q.get("choices", [])
                if len(opts) != 4:
                    errors.append(f"Quiz {q_idx} Q{i} has {len(opts)} options (need 4)")
            
            if "correct_answer" not in q and "correct_index" not in q and "answer" not in q:
                errors.append(f"Quiz {q_idx} Q{i} missing correct answer")
    
    if errors:
        raise AIValidationError(quiz_type, "; ".join(errors[:10]))  # Limit error messages
    
    logger.info(f"✅ {quiz_type} validation PASSED ({len(quizzes)} quizzes)")
    return quiz_data


# =============================================================================
# STAGE 4: ATOMIC GENERATION FUNCTIONS (MEMORY-FIRST)
# =============================================================================

def get_age_context(standard: int) -> dict:
    """Get age-appropriate language and complexity guidance based on class standard"""
    if standard <= 4:
        return {
            "age_group": "6-10 years",
            "language_style": "very simple words, short sentences, fun examples from daily life",
            "complexity": "basic concepts only, use pictures/stories/games analogies",
            "tone": "playful, encouraging, like talking to a young child",
            "examples": "toys, animals, food, family, games, cartoons",
            "attention_span": "short explanations, colorful examples",
            "math_level": "basic arithmetic, counting, simple patterns"
        }
    elif standard <= 6:
        return {
            "age_group": "10-12 years",
            "language_style": "simple but complete sentences, relatable examples",
            "complexity": "foundational concepts with clear explanations",
            "tone": "friendly, supportive, like an encouraging older sibling",
            "examples": "school activities, sports, nature, simple science experiments",
            "attention_span": "moderate explanations with engaging examples",
            "math_level": "fractions, decimals, basic geometry, word problems"
        }
    elif standard <= 8:
        return {
            "age_group": "12-14 years",
            "language_style": "clear academic language with proper terminology",
            "complexity": "intermediate concepts with logical reasoning",
            "tone": "informative, respectful, encouraging critical thinking",
            "examples": "real-world applications, technology, current events",
            "attention_span": "detailed explanations acceptable",
            "math_level": "algebra basics, geometry proofs, data analysis"
        }
    else:  # Class 9-12
        return {
            "age_group": "14-18 years",
            "language_style": "academic and technical language, proper subject terminology",
            "complexity": "advanced concepts with analytical depth",
            "tone": "professional, intellectually engaging, exam-focused",
            "examples": "scientific applications, career relevance, board exam patterns",
            "attention_span": "comprehensive explanations with depth",
            "math_level": "advanced algebra, calculus basics, complex problem solving"
        }


async def generate_revision_notes_atomic(
    subject: str, 
    chapter: str, 
    content: str, 
    standard: int
) -> Dict[str, Any]:
    """
    ATOMIC revision notes generation with strict validation.
    Returns validated notes dict or raises exception.
    """
    # Prevent token overflow
    content_trimmed = content[:MAX_CONTENT_LENGTH] if len(content) > MAX_CONTENT_LENGTH else content
    age_context = get_age_context(standard)
    
    system_message = f"""You are an expert {subject} teacher creating revision notes for Class {standard} students.
You MUST return ONLY valid JSON. No explanations. No markdown. No commentary.
Return exactly the structure specified."""

    prompt = f"""Create revision notes for Class {standard} students.

Subject: {subject}
Chapter: {chapter}

TEXTBOOK CONTENT:
{content_trimmed}

You MUST return ONLY this exact JSON structure (no other text):
{{
  "key_concepts": [
    {{
      "title": "Concept Title",
      "explanation": "Clear explanation for Class {standard}",
      "why_important": "Real-life relevance",
      "exam_tip": "How this appears in exams",
      "example": "Relatable example"
    }}
  ],
  "exam_important_points": [
    {{
      "point": "Specific fact likely to be asked",
      "type": "definition/formula/fact",
      "memory_trick": "Easy way to remember"
    }}
  ],
  "definitions_to_memorize": [
    {{
      "term": "Important term",
      "meaning": "Clear definition",
      "example": "Example"
    }}
  ],
  "quick_revision_points": [
    "Point 1",
    "Point 2"
  ],
  "chapter_summary": "3-4 sentence summary of the chapter"
}}

Include at least 5 key_concepts and 6 exam_important_points.
Use {age_context['language_style']}."""

    # Call with retry
    notes = await call_llm_with_retry(
        prompt=prompt,
        system_message=system_message,
        component_name="revision_notes",
        timeout=90.0,
        max_tokens=3500
    )
    
    # Strict validation
    validate_revision_notes(notes)
    
    return notes


async def generate_flashcards_atomic(
    subject: str, 
    chapter: str, 
    content: str, 
    standard: int,
    count: int = 15
) -> List[Dict]:
    """
    ATOMIC flashcards generation with strict validation.
    Returns validated flashcard list or raises exception.
    """
    content_trimmed = content[:MAX_CONTENT_LENGTH] if len(content) > MAX_CONTENT_LENGTH else content
    age_context = get_age_context(standard)
    
    system_message = f"""You are creating exam-focused flashcards for Class {standard} students.
You MUST return ONLY valid JSON. No explanations. No markdown. No backticks.
Return exactly the structure specified."""

    prompt = f"""Create exactly {count} flashcards for Class {standard}.

Subject: {subject}
Chapter: {chapter}

TEXTBOOK CONTENT:
{content_trimmed}

CRITICAL RULE: Every "back" answer MUST be exactly 1 or 2 words only. No sentences.
Example: front: "What is the process by which plants make food?" → back: "Photosynthesis"

You MUST return ONLY this exact JSON structure:
{{
  "flashcards": [
    {{
      "id": 1,
      "front": "Question where the answer is 1-2 words",
      "back": "OneOrTwoWords",
      "hint": "Memory trick",
      "category": "definition/formula/fact/concept",
      "exam_likelihood": "high/medium/low"
    }}
  ]
}}

Create exactly {count} flashcards focused on exam-important content.
Use {age_context['language_style']}."""

    # Call with retry
    result = await call_llm_with_retry(
        prompt=prompt,
        system_message=system_message,
        component_name="flashcards",
        timeout=90.0,
        max_tokens=3000
    )
    
    # Strict validation (returns normalized list)
    flashcards = validate_flashcards(result)
    
    return flashcards


async def generate_basic_quiz_atomic(
    subject: str, 
    chapter: str, 
    content: str, 
    standard: int
) -> Dict[str, Any]:
    """
    ATOMIC basic quiz generation (Easy, Medium, Hard) with strict validation.
    Returns validated quiz dict or raises exception.
    """
    content_trimmed = content[:MAX_CONTENT_LENGTH] if len(content) > MAX_CONTENT_LENGTH else content
    age_context = get_age_context(standard)
    
    system_message = f"""You are creating practice quizzes for Class {standard} students.
You MUST return ONLY valid JSON. No explanations. No markdown. No text before or after JSON.
Return exactly the structure specified."""

    prompt = f"""Create 3 practice quizzes for Class {standard}.

Subject: {subject}
Chapter: {chapter}

TEXTBOOK CONTENT:
{content_trimmed}

Create THREE quizzes with EXACTLY 10 questions EACH:
- Quiz 1: Easy (basic recall, definitions)
- Quiz 2: Medium (understanding, simple application)
- Quiz 3: Hard (problem-solving, critical thinking)

You MUST return ONLY this exact JSON:
{{
  "quizzes": [
    {{
      "quiz_id": 1,
      "difficulty": "Easy",
      "title": "Basic Concepts Quiz",
      "questions": [
        {{
          "id": 1,
          "question": "Question text",
          "options": ["A", "B", "C", "D"],
          "correct_answer": "A",
          "explanation": "Why this is correct"
        }}
      ]
    }},
    {{
      "quiz_id": 2,
      "difficulty": "Medium",
      "title": "Understanding Quiz",
      "questions": []
    }},
    {{
      "quiz_id": 3,
      "difficulty": "Hard",
      "title": "Challenge Quiz",
      "questions": []
    }}
  ]
}}

Each quiz MUST have exactly 10 questions with 4 options each.
Use {age_context['language_style']}."""

    # Call with retry
    result = await call_llm_with_retry(
        prompt=prompt,
        system_message=system_message,
        component_name="basic_quiz",
        timeout=120.0,
        max_tokens=4000
    )
    
    # Strict validation
    validated = validate_quiz(result, "basic_quiz", min_questions=10)
    
    return validated


async def generate_advanced_quiz_atomic(
    subject: str, 
    chapter: str, 
    content: str, 
    standard: int
) -> Dict[str, Any]:
    """
    ATOMIC advanced quiz generation (for strong students) with strict validation.
    Returns validated quiz dict or raises exception.
    """
    content_trimmed = content[:MAX_CONTENT_LENGTH] if len(content) > MAX_CONTENT_LENGTH else content
    age_context = get_age_context(standard)
    
    system_message = f"""You are creating ADVANCED practice quizzes for strong Class {standard} students.
You MUST return ONLY valid JSON. No explanations. No markdown. No text before or after JSON.
Return exactly the structure specified."""

    prompt = f"""Create 3 ADVANCED quizzes for strong Class {standard} students.

Subject: {subject}
Chapter: {chapter}

TEXTBOOK CONTENT:
{content_trimmed}

Create THREE advanced quizzes with EXACTLY 10 questions EACH:
- Quiz 4: Advanced Application (real-world problems)
- Quiz 5: Advanced Analysis (analytical thinking)
- Quiz 6: Advanced Problem Solving (multi-step reasoning)

Questions should NOT be directly from textbook - they should test deep understanding.

You MUST return ONLY this exact JSON:
{{
  "quizzes": [
    {{
      "quiz_id": 4,
      "difficulty": "Advanced",
      "title": "Advanced Application Quiz",
      "for_strong_students": true,
      "questions": [
        {{
          "id": 1,
          "question": "Question text",
          "options": ["A", "B", "C", "D"],
          "correct_answer": "A",
          "explanation": "Why this is correct"
        }}
      ]
    }},
    {{
      "quiz_id": 5,
      "difficulty": "Advanced",
      "title": "Advanced Analysis Quiz",
      "for_strong_students": true,
      "questions": []
    }},
    {{
      "quiz_id": 6,
      "difficulty": "Advanced",
      "title": "Advanced Problem Solving Quiz",
      "for_strong_students": true,
      "questions": []
    }}
  ]
}}

Each quiz MUST have exactly 10 questions with 4 options each.
Use {age_context['language_style']}."""

    # Call with retry
    result = await call_llm_with_retry(
        prompt=prompt,
        system_message=system_message,
        component_name="advanced_quiz",
        timeout=120.0,
        max_tokens=4000
    )
    
    # Strict validation
    validated = validate_quiz(result, "advanced_quiz", min_questions=10)
    
    return validated


# =============================================================================
# STAGE 5: ATOMIC ORCHESTRATOR (ALL-OR-NOTHING)
# =============================================================================

async def generate_all_ai_content_atomic(
    subject: str,
    chapter: str,
    content: str,
    standard: int
) -> Tuple[Dict, List, Dict, Dict]:
    """
    STRICT ATOMIC ORCHESTRATOR - ALL OR NOTHING.
    
    Generates all 4 components in memory first.
    If ANY component fails, the entire operation fails.
    Returns tuple of (revision_notes, flashcards, basic_quiz, advanced_quiz).
    Raises AIGenerationError or AIValidationError on failure.
    """
    logger.info("=" * 60)
    logger.info("🚀 STARTING STRICT ATOMIC AI GENERATION")
    logger.info(f"   Subject: {subject}")
    logger.info(f"   Chapter: {chapter}")
    logger.info(f"   Standard: {standard}")
    logger.info(f"   Content length: {len(content)} chars")
    logger.info("=" * 60)
    
    # STAGE 4: Memory-first generation (no early uploads)
    # Each component must succeed or the entire operation fails
    
    try:
        # Component 1: Revision Notes
        logger.info("📝 [1/4] Generating Revision Notes...")
        revision_notes = await generate_revision_notes_atomic(subject, chapter, content, standard)
        logger.info("✅ [1/4] Revision Notes COMPLETE")
        
        # Component 2: Flashcards
        logger.info("🃏 [2/4] Generating Flashcards...")
        flashcards = await generate_flashcards_atomic(subject, chapter, content, standard)
        logger.info("✅ [2/4] Flashcards COMPLETE")
        
        # Component 3: Basic Quiz
        logger.info("📋 [3/4] Generating Basic Quiz...")
        basic_quiz = await generate_basic_quiz_atomic(subject, chapter, content, standard)
        logger.info("✅ [3/4] Basic Quiz COMPLETE")
        
        # Component 4: Advanced Quiz
        logger.info("🎯 [4/4] Generating Advanced Quiz...")
        advanced_quiz = await generate_advanced_quiz_atomic(subject, chapter, content, standard)
        logger.info("✅ [4/4] Advanced Quiz COMPLETE")
        
        logger.info("=" * 60)
        logger.info("🎉 ALL 4 COMPONENTS GENERATED SUCCESSFULLY")
        logger.info("=" * 60)
        
        return (revision_notes, flashcards, basic_quiz, advanced_quiz)
        
    except (AIGenerationError, AIValidationError, AIJSONParseError) as e:
        logger.error("=" * 60)
        logger.error(f"❌ ATOMIC GENERATION FAILED: {e}")
        logger.error("   All components will be discarded.")
        logger.error("=" * 60)
        raise


# =============================================================================
# LEGACY SUPPORT - call_llm function (for other parts of the codebase)
# =============================================================================

async def call_llm(
    prompt: str, 
    use_high_quality: bool = False, 
    system_message: str = None, 
    expect_json: bool = False, 
    model_override: str = None, 
    timeout: float = 120.0,
    task_type: str = "generation"
) -> Optional[str]:
    """
    Legacy LLM call function for backward compatibility.
    For new code, use call_llm_with_retry instead.
    """
    try:
        api_key = OPENROUTER_API_KEY
        
        if not api_key:
            logger.error("❌ OPENROUTER_API_KEY not configured")
            raise AIServiceError("OpenRouter API key not set")
        
        # Select model based on task type
        if model_override:
            model = model_override
        elif task_type == "evaluation":
            model = MODEL_FOR_EVALUATION
        else:
            model = MODEL_FOR_GENERATION
        
        logger.info(f"⚡ Using OpenRouter model: {model} (task: {task_type})")
        
        # Prepare messages
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        # Prepare request
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://studybuddy.app",
            "X-Title": "StudyBuddy Learning Platform"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": STRUCTURED_OUTPUT_TEMPERATURE if expect_json else 0.7,
            "max_tokens": 3500
        }
        
        if expect_json:
            payload["response_format"] = {"type": "json_object"}
        
        # Make API call with timeout
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_BASE_URL,
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"❌ OpenRouter API error {response.status_code}: {error_text}")
                raise AIServiceError(f"OpenRouter API returned {response.status_code}: {error_text}")
            
            response_data = response.json()
            
            # Extract content
            if "choices" not in response_data or not response_data["choices"]:
                logger.error("❌ No choices in OpenRouter response")
                return None
            
            content = response_data["choices"][0]["message"]["content"]
            
            if not content:
                logger.error("❌ Empty content in OpenRouter response")
                return None
            
            result = content.strip()
            logger.info(f"✅ Got OpenRouter response: {len(result)} chars")
            
            # Clean and extract JSON if needed
            if expect_json:
                result = extract_json_from_response(result)
            
            return result
        
    except httpx.TimeoutException:
        logger.error(f"⏱️ OpenRouter API call timed out after {timeout}s")
        raise AIServiceError(f"Request timed out after {timeout}s")
    except Exception as e:
        logger.error(f"❌ OpenRouter API call failed: {e}")
        import traceback
        traceback.print_exc()
        raise AIServiceError(f"API call failed: {str(e)}")

def get_cache_key(params: dict) -> str:
    """Generate cache key from parameters"""
    param_str = json.dumps(params, sort_keys=True)
    return hashlib.md5(param_str.encode()).hexdigest()

async def get_cached_content(cache_key: str) -> Optional[str]:
    """Get cached content, returns None if not found or Redis unavailable"""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return None
        cached = redis_client.get(f"ai:{cache_key}")
        if cached:
            logger.info(f"Cache HIT for key: {cache_key[:8]}")
            # Check if it's a cached failure
            if cached == "__FAILED__":
                return None
        return cached if cached != "__FAILED__" else None
    except Exception as e:
        logger.warning(f"Redis cache read failed: {e}")
        return None

async def set_cached_content(cache_key: str, content: Optional[str], ttl: int = 604800):
    """Cache content permanently (7 days default) - shared across all students"""
    try:
        redis_client = await get_redis()
        if not redis_client:
            return
        if content is None:
            # Cache failures for 5 minutes to avoid repeated failed calls
            redis_client.setex(f"ai:{cache_key}", 300, "__FAILED__")
            logger.info(f"Cached FAILURE for key: {cache_key[:8]}")
        else:
            redis_client.setex(f"ai:{cache_key}", ttl, content)
            logger.info(f"Cached SUCCESS for key: {cache_key[:8]} (TTL: {ttl}s)")
    except Exception as e:
        logger.warning(f"Redis cache write failed: {e}")


async def clear_chapter_ai_cache(subject_name: str, chapter_name: str):
    """Clear all AI-generated content cache for a specific chapter.
    Called when teacher uploads new content for a chapter."""
    try:
        redis_client = await get_redis()
        if not redis_client:
            logger.warning("Redis not available - cannot clear AI cache")
            return 0
        
        # Generate possible cache keys for this chapter
        features = ['revision_notes_v3', 'flashcards_v3', 'quiz_v3', 'important', 'explain', 'doubt']
        languages = ['english', 'hindi', 'gujarati']
        sources = ['ncert', 'state']
        standards = list(range(1, 13))  # Class 1-12
        
        deleted_count = 0
        for feature in features:
            for lang in languages:
                for source in sources:
                    for standard in standards:
                        params = {
                            'feature': feature,
                            'subject': subject_name,
                            'chapter': chapter_name,
                            'language': lang,
                            'source': source,
                            'standard': standard
                        }
                        # Also try with count for flashcards
                        if feature == 'flashcards_v3':
                            params['count'] = 15
                        
                        cache_key = get_cache_key(params)
                        result = redis_client.delete(f"ai:{cache_key}")
                        if result:
                            deleted_count += 1
        
        logger.info(f"Cleared {deleted_count} AI cache entries for {subject_name}/{chapter_name}")
        return deleted_count
    except Exception as e:
        logger.error(f"Failed to clear AI cache: {e}")
        return 0


async def clear_pyq_ai_cache(pyq_id: str):
    """Clear AI-generated solution cache for a specific PYQ.
    Called when teacher uploads new PYQ or updates existing one."""
    try:
        redis_client = await get_redis()
        if not redis_client:
            logger.warning("Redis not available - cannot clear PYQ cache")
            return 0
        
        # Clear PYQ solution cache (stored in ai_content_cache table, not Redis typically)
        # But also clear any Redis keys that might exist
        deleted_count = 0
        pattern = f"ai:*pyq*{pyq_id[:8]}*"
        keys = redis_client.keys(pattern)
        if keys:
            deleted_count = redis_client.delete(*keys)
        
        logger.info(f"Cleared {deleted_count} PYQ cache entries for PYQ {pyq_id[:8]}")
        return deleted_count
    except Exception as e:
        logger.error(f"Failed to clear PYQ cache: {e}")
        return 0


async def generate_revision_notes(subject: str, chapter: str, content: str, language: str = 'english', source: str = 'ncert', standard: int = 5) -> Optional[Dict]:
    """Generate structured revision notes with caching - age-appropriate and exam-focused"""
    cache_key = get_cache_key({
        'feature': 'revision_notes_v3',
        'subject': subject,
        'chapter': chapter,
        'language': language,
        'source': source,
        'standard': standard
    })
    
    cached = await get_cached_content(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except:
            pass
    
    content_to_use = content[:6000] if len(content) > 6000 else content
    age_context = get_age_context(standard)
    
    prompt = f"""You are an expert teacher creating revision notes for Class {standard} students ({age_context['age_group']}).

**IMPORTANT GUIDELINES:**
- Language Style: {age_context['language_style']}
- Complexity Level: {age_context['complexity']}
- Tone: {age_context['tone']}
- Use examples related to: {age_context['examples']}

**Subject:** {subject}
**Chapter:** {chapter}
**Class:** {standard}
**Source:** {source.upper()} Textbook

**TEXTBOOK CONTENT:**
{content_to_use}

**YOUR TASK:**
1. DO NOT copy-paste from the textbook. Read, understand, and EXPLAIN concepts in your own words
2. Make it easy to understand for a Class {standard} student
3. Identify points/facts/numbers that are LIKELY TO COME IN EXAMS (mark these clearly)
4. Structure the content logically for easy revision
5. Add memory tricks and mnemonics where helpful

Return ONLY a JSON object:
{{
  "key_concepts": [
    {{
      "title": "Concept Title",
      "explanation": "Clear explanation in simple words appropriate for Class {standard}",
      "why_important": "Why this matters / real-life connection",
      "exam_tip": "How this might appear in exam",
      "example": "Relatable example for {age_context['age_group']}"
    }}
  ],
  "exam_important_points": [
    {{
      "point": "Specific fact/number/detail likely to be asked in exam",
      "type": "definition/date/formula/fact/numerical",
      "memory_trick": "Easy way to remember this"
    }}
  ],
  "formulas_and_rules": [
    {{
      "formula": "Formula or rule (if applicable)",
      "when_to_use": "Situation where this applies",
      "common_mistakes": "What students often get wrong"
    }}
  ],
  "definitions_to_memorize": [
    {{
      "term": "Important term",
      "meaning": "Clear definition for Class {standard}",
      "example": "Example to understand it better"
    }}
  ],
  "quick_revision_points": [
    "Point 1 - short and memorable",
    "Point 2 - key takeaway"
  ],
  "chapter_summary": "A 3-4 sentence summary capturing the essence of the chapter",
  "exam_prediction": "What type of questions might come from this chapter (1 mark, 2 mark, long answer, etc.)"
}}

Include at least 5 key_concepts and 6+ exam_important_points. Make explanations engaging for Class {standard}."""
    
    system_message = f"You are an expert {subject} teacher who excels at explaining concepts to Class {standard} students in an engaging, age-appropriate manner. You understand what appears in exams and help students prepare effectively."
    
    response = await call_llm(prompt, use_high_quality=True, expect_json=True, timeout=120.0, system_message=system_message)
    
    if response:
        try:
            notes = json.loads(response)
            await set_cached_content(cache_key, json.dumps(notes))
            return notes
        except json.JSONDecodeError as e:
            logger.error(f"Invalid revision notes JSON: {e}")
    
    return None

async def generate_flashcards(subject: str, chapter: str, content: str, language: str = 'english', source: str = 'ncert', count: int = 15, standard: int = 5) -> Optional[List[Dict]]:
    """Generate exam-focused flashcards with age-appropriate content"""
    cache_key = get_cache_key({
        'feature': 'flashcards_v3',
        'subject': subject,
        'chapter': chapter,
        'language': language,
        'source': source,
        'count': count,
        'standard': standard
    })
    
    cached = await get_cached_content(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except:
            return None
    
    content_to_use = content[:6000] if len(content) > 6000 else content
    age_context = get_age_context(standard)
    
    prompt = f"""You are creating exam-focused flashcards for Class {standard} students ({age_context['age_group']}).

**IMPORTANT GUIDELINES:**
- Language: {age_context['language_style']}
- Complexity: {age_context['complexity']}
- Focus on content that is LIKELY TO APPEAR IN EXAMS

**Subject:** {subject}
**Chapter:** {chapter}
**Class:** {standard}
**Source:** {source.upper()} Textbook

**TEXTBOOK CONTENT:**
{content_to_use}

**YOUR TASK:**
Create exactly {count} flashcards. CRITICAL RULE: Every answer on the back MUST be exactly 1 or 2 words. No sentences, no explanations — just the exact keyword(s).

**Question types to use (all must have 1-2 word answers):**
1. "What is the term for...?" → Answer: "Photosynthesis"
2. "Name the..." → Answer: "Carbon dioxide"
3. "Who discovered...?" → Answer: "Isaac Newton"
4. "What is the formula for...?" → Answer: "A = lr2"
5. "Fill in the blank: The capital of India is ___" → Answer: "New Delhi"
6. "What year did...?" → Answer: "1947"

**PRIORITY ORDER:**
1. One-word definitions and key terms
2. Important names, dates, numbers
3. Formulas (keep answer to the formula only)
4. Fill-in-the-blank style

Return ONLY a JSON array:
[
  {{
    "id": 1,
    "front": "Question designed so the answer is 1-2 words",
    "back": "OneOrTwoWords",
    "hint": "Memory trick or first letter clue",
    "category": "definition/formula/fact/concept/mcq",
    "exam_likelihood": "high/medium/low",
    "marks_type": "1-mark/2-mark/long-answer"
  }}
]

REMEMBER: The "back" field must NEVER be a sentence. It must be exactly 1 or 2 words (or a short formula). This is critical.
Make questions progressively harder. Use language appropriate for {age_context['age_group']}."""
    
    system_message = f"You are an expert {subject} teacher who creates effective flashcards that help Class {standard} students prepare for exams. You know exactly what questions appear in exams."
    
    response = await call_llm(prompt, use_high_quality=True, expect_json=True, timeout=120.0, system_message=system_message)
    
    if response:
        try:
            # Log raw response for debugging
            logger.info(f"🔍 Flashcards raw response length: {len(response)} chars")
            logger.info(f"🔍 First 200 chars: {response[:200]}")
            
            # Clean up JSON (same as quiz generation)
            cleaned = response.strip()
            if cleaned.startswith('```'):
                cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                cleaned = re.sub(r'\s*```$', '', cleaned)
            
            # Remove control characters
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
            # Fix trailing commas
            cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
            # Fix missing commas between objects
            cleaned = re.sub(r'}\s*{', r'},{', cleaned)
            
            logger.info(f"🔍 After cleaning, first 200 chars: {cleaned[:200]}")
            
            flashcards = json.loads(cleaned)
            logger.info(f"🔍 Parsed type: {type(flashcards)}, is_list: {isinstance(flashcards, list)}")
            
            # Handle both array and wrapped object formats
            if isinstance(flashcards, dict):
                logger.info(f"🔍 Got dict, keys: {list(flashcards.keys())}")
                if "flashcards" in flashcards:
                    flashcards = flashcards["flashcards"]
                    logger.info(f"🔍 Unwrapped from 'flashcards' key")
                elif "cards" in flashcards:
                    flashcards = flashcards["cards"]
                    logger.info(f"🔍 Unwrapped from 'cards' key")
                else:
                    # Try to get first array value
                    for key, value in flashcards.items():
                        if isinstance(value, list) and len(value) > 0:
                            flashcards = value
                            logger.info(f"🔍 Unwrapped from '{key}' key")
                            break
            
            if isinstance(flashcards, list) and len(flashcards) > 0:
                # Ensure all flashcards have IDs
                for i, card in enumerate(flashcards):
                    if 'id' not in card:
                        card['id'] = i + 1
                response_str = json.dumps(flashcards)
                await set_cached_content(cache_key, response_str)
                logger.info(f"✅ Generated {len(flashcards)} flashcards")
                return flashcards
            else:
                logger.error(f"Flashcards validation failed: type={type(flashcards)}, is_list={isinstance(flashcards, list)}, len={len(flashcards) if isinstance(flashcards, list) else 'N/A'}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid flashcards JSON: {e}")
            logger.error(f"Cleaned response snippet: {cleaned[:500]}...")
    
    return None

async def get_flashcard_rotation(user_id: str, chapter_id: str, flashcard_ratings: Dict[int, str]) -> List[int]:
    """Use free LLM to determine optimal flashcard rotation based on Easy/Medium/Hard ratings"""
    # Build summary of ratings
    easy_cards = [k for k, v in flashcard_ratings.items() if v == 'easy']
    medium_cards = [k for k, v in flashcard_ratings.items() if v == 'medium']
    hard_cards = [k for k, v in flashcard_ratings.items() if v == 'hard']
    unrated_cards = [k for k, v in flashcard_ratings.items() if v == 'unrated']
    
    # Simple spaced repetition logic without LLM call (more reliable)
    # Hard cards: 3x frequency, Medium: 2x, Easy: 1x, Unrated: 2x
    rotation = []
    
    # Add hard cards 3 times
    for card_id in hard_cards:
        rotation.extend([card_id] * 3)
    
    # Add medium cards 2 times
    for card_id in medium_cards:
        rotation.extend([card_id] * 2)
    
    # Add unrated cards 2 times (need more practice)
    for card_id in unrated_cards:
        rotation.extend([card_id] * 2)
    
    # Add easy cards 1 time
    rotation.extend(easy_cards)
    
    # Shuffle to mix up the order
    import random
    random.shuffle(rotation)
    
    return rotation

async def generate_important_topics(subject: str, chapter: str, content: str, language: str = 'english', source: str = 'ncert', standard: int = 5) -> Optional[Dict]:
    """Generate structured important exam topics"""
    cache_key = get_cache_key({
        'feature': 'important_v2',
        'subject': subject,
        'chapter': chapter,
        'language': language,
        'source': source,
        'standard': standard
    })
    
    cached = await get_cached_content(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except:
            pass
    
    content_to_use = content[:5000] if len(content) > 5000 else content
    age_context = get_age_context(standard)
    
    prompt = f"""You are helping Class {standard} students ({age_context['age_group']}) prepare for exams.

Subject: {subject}
Chapter: {chapter}

TEXTBOOK CONTENT:
{content_to_use}

Based ONLY on the above content, create a comprehensive exam preparation guide.

Return ONLY a JSON object:
{{
  "must_know_topics": [
    {{"topic": "Topic name", "importance": "high/medium", "likely_questions": "Type of questions expected", "tip": "How to prepare"}}
  ],
  "key_definitions": [
    {{"term": "Term", "definition": "Simple definition", "example": "Example if any"}}
  ],
  "formulas_and_rules": [
    {{"name": "Formula/Rule name", "formula": "The formula or rule", "when_to_use": "Explanation", "example": "Example"}}
  ],
  "common_mistakes": [
    {{"mistake": "Common mistake students make", "correct_approach": "What to do instead"}}
  ],
  "expected_questions": [
    {{"question_type": "MCQ/Fill in blanks/Short answer/Long answer", "sample": "Sample question", "answer_hint": "How to approach"}}
  ],
  "last_minute_revision": [
    "Quick point 1 to remember",
    "Quick point 2 to remember"
  ]
}}

Include at least 4-5 items in must_know_topics. Use language appropriate for Class {standard} ({age_context['language_style']})."""
    
    response = await call_llm(prompt, use_high_quality=True, expect_json=True, timeout=90.0)
    
    if response:
        try:
            topics = json.loads(response)
            await set_cached_content(cache_key, json.dumps(topics))
            return topics
        except json.JSONDecodeError as e:
            logger.error(f"Invalid important topics JSON: {e}")
    
    return None

def shuffle_quiz_options(quiz_data: Dict) -> Dict:
    """
    Post-process quiz data to shuffle MCQ options so correct answer isn't always option A.
    This ensures students can't guess by always picking the first option.
    """
    import random
    
    if not quiz_data or "quizzes" not in quiz_data:
        return quiz_data
    
    for quiz in quiz_data["quizzes"]:
        if "questions" not in quiz:
            continue
            
        for question in quiz["questions"]:
            if "options" not in question or "correct_answer" not in question:
                continue
            
            options = question["options"]
            correct_answer_text = question["correct_answer"]
            
            # Find the correct answer in the options list
            # Handle both "Option A" format and direct text format
            correct_index = None
            for i, opt in enumerate(options):
                if opt == correct_answer_text:
                    correct_index = i
                    break
                # Also check if correct_answer is "A", "B", "C", "D" format
                if correct_answer_text in ["A", "B", "C", "D"]:
                    correct_index = ord(correct_answer_text) - ord("A")
                    if correct_index < len(options):
                        correct_answer_text = options[correct_index]
                    break
            
            if correct_index is None:
                # Try to find by partial match (in case of formatting differences)
                for i, opt in enumerate(options):
                    if correct_answer_text.strip().lower() in opt.strip().lower() or opt.strip().lower() in correct_answer_text.strip().lower():
                        correct_index = i
                        correct_answer_text = opt
                        break
            
            if correct_index is None:
                # If we still can't find the correct answer, skip shuffling this question
                logger.warning(f"Could not find correct answer '{question['correct_answer']}' in options for question: {question.get('question', '')[:50]}...")
                continue
            
            # Shuffle the options
            shuffled_options = options.copy()
            random.shuffle(shuffled_options)
            
            # Update the question with shuffled options and new correct answer text
            question["options"] = shuffled_options
            question["correct_answer"] = correct_answer_text
    
    return quiz_data


async def generate_practice_quiz(subject: str, chapter: str, content: str, language: str = 'english', source: str = 'ncert', standard: int = 5) -> Optional[Dict]:
    """Generate 5 practice quizzes with 20 questions each (100 total questions)"""
    cache_key = get_cache_key({
        'feature': 'quiz_v5',  # Updated version for shuffled answers and unique questions
        'subject': subject,
        'chapter': chapter,
        'language': language,
        'source': source,
        'standard': standard
    })
    
    cached = await get_cached_content(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except:
            return None
    
    content_to_use = content[:6000] if len(content) > 6000 else content
    age_context = get_age_context(standard)
    
    prompt = f"""Create 5 comprehensive practice quizzes for Class {standard} students studying {subject} - {chapter}.

**TEXTBOOK CONTENT:**
{content_to_use}

Create FIVE quizzes with 20 questions EACH (total 100 questions):

**Quiz 1 - Easy (20 questions):**
- Focus: Direct concepts, formulas, definitions, must-know facts
- Type: Basic recall, direct from textbook, fundamental understanding
- Difficulty: Must know for exam
- Example: "What is the formula for area of a circle?", "Define photosynthesis"

**Quiz 2 - Medium (20 questions):**
- Focus: Slightly more challenging than Easy, requires understanding
- Type: Application of direct concepts, numerical problems from textbook examples
- Difficulty: Must know for exam, but requires some thinking
- Example: "Calculate area if radius is 7cm", "Explain why plants need sunlight"

**Quiz 3 - Hard (20 questions):**
- Focus: Challenging questions, may not be directly from textbook
- Type: Complex numericals, deeper conceptual questions, problem-solving
- Difficulty: Should know for exam, requires critical thinking
- Example: Multi-step problems, analysis questions, "what if" scenarios

**Quiz 4 - Advanced 1 (20 questions):**
- Focus: Application-oriented, NOT directly from textbook
- Type: Real-world applications, advanced numericals based on concepts
- Difficulty: Could know type, for strong students only
- Example: "A farmer has circular field...", "Design an experiment to..."
- Note: Based on chapter concepts but questions are original

**Quiz 5 - Advanced 2 (20 questions):**
- Focus: Application-oriented, NOT directly from textbook
- Type: Complex applications, analytical thinking, creative problem-solving
- Difficulty: Could know type, for strong students only
- Example: Higher-order thinking, integration of multiple concepts
- Note: Based on chapter concepts but requires deep understanding

**IMPORTANT REQUIREMENTS:**
1. Each quiz must have EXACTLY 20 questions
2. All questions must be age-appropriate for Class {standard} ({age_context})
3. Each question must have 4 options (A, B, C, D)
4. Provide clear, educational explanations
5. Advanced quizzes should NOT copy textbook questions
6. Use simple language suitable for Class {standard} students
7. **CRITICAL: ALL 100 QUESTIONS MUST BE UNIQUE** - Do NOT repeat any question across the 5 quizzes. Each quiz must cover different aspects of the chapter. No two questions should test the same concept in the same way.
8. The correct_answer field should contain the EXACT TEXT of the correct option, not just "A", "B", "C", or "D"

Return ONLY valid JSON in this exact format (no markdown, no extra text):
{{
  "quizzes": [
    {{
      "quiz_id": 1,
      "difficulty": "Easy",
      "title": "Basic Quiz",
      "description": "Must-know questions for exam",
      "questions": [
        {{
          "id": 1,
          "question": "Question text here",
          "options": ["Option A", "Option B", "Option C", "Option D"],
          "correct_answer": "Option A",
          "explanation": "Why this answer is correct"
        }}
        // ... 19 more questions
      ]
    }},
    {{
      "quiz_id": 2,
      "difficulty": "Medium",
      "title": "Understanding Quiz",
      "description": "Must-know with some thinking required",
      "questions": [20 questions]
    }},
    {{
      "quiz_id": 3,
      "difficulty": "Hard",
      "title": "Challenge Quiz",
      "description": "Should-know for strong preparation",
      "questions": [20 questions]
    }},
    {{
      "quiz_id": 4,
      "difficulty": "Advanced",
      "title": "Advanced Quiz 1",
      "description": "Application-based for strong students",
      "questions": [20 questions]
    }},
    {{
      "quiz_id": 5,
      "difficulty": "Advanced",
      "title": "Advanced Quiz 2",
      "description": "Complex applications for strong students",
      "questions": [20 questions]
    }}
  ]
}}

CRITICAL: Return ONLY the JSON object above. No markdown code blocks, no explanations, just pure JSON."""
    
    # Retry logic with increased timeout for 100 questions
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await call_llm(prompt, use_high_quality=True, expect_json=True, timeout=180.0)
            
            if response:
                try:
                    # Clean up common JSON issues
                    cleaned = response.strip()
                    if cleaned.startswith('```'):
                        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                        cleaned = re.sub(r'\s*```$', '', cleaned)
                    
                    # Remove control characters and normalize quotes
                    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
                    
                    # Fix common LLM JSON errors
                    # 1. Remove trailing commas before closing braces/brackets
                    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
                    # 2. Ensure proper comma between array/object elements
                    cleaned = re.sub(r'}\s*{', r'},{', cleaned)
                    cleaned = re.sub(r']\s*\[', r'],[', cleaned)
                    
                    quiz_data = json.loads(cleaned)
                    if isinstance(quiz_data, dict) and "quizzes" in quiz_data:
                        # Validate we have 5 quizzes
                        if len(quiz_data["quizzes"]) == 5:
                            # Shuffle options so correct answer isn't always first
                            quiz_data = shuffle_quiz_options(quiz_data)
                            logger.info("✅ Shuffled MCQ options for all quizzes")
                            await set_cached_content(cache_key, json.dumps(quiz_data))
                            return quiz_data
                        else:
                            logger.warning(f"Expected 5 quizzes, got {len(quiz_data['quizzes'])}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid quiz JSON (attempt {attempt+1}): {e}")
                    # Log the problematic area
                    error_pos = e.pos if hasattr(e, 'pos') else 0
                    snippet = cleaned[max(0, error_pos-50):min(len(cleaned), error_pos+50)]
                    logger.error(f"JSON error near: ...{snippet}...")
            
            if attempt < max_retries - 1:
                logger.warning(f"Quiz generation attempt {attempt + 1} failed. Retrying...")
                await asyncio.sleep(3)
                continue
            
        except Exception as e:
            logger.error(f"Quiz generation failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(3)
                continue
    
    await set_cached_content(cache_key, None)
    return None



async def generate_basic_quiz(subject: str, chapter: str, content: str, language: str = 'english', source: str = 'ncert', standard: int = 5) -> Optional[Dict]:
    """Generate 3 basic practice quizzes (Easy, Medium, Hard) - 30 questions total (10 each)"""
    cache_key = get_cache_key({
        'feature': 'quiz_basic_v2',
        'subject': subject,
        'chapter': chapter,
        'language': language,
        'source': source,
        'standard': standard
    })
    
    cached = await get_cached_content(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except:
            return None
    
    content_to_use = content[:6000] if len(content) > 6000 else content
    age_context = get_age_context(standard)
    
    prompt = f"""Create 3 practice quizzes for Class {standard} students studying {subject} - {chapter}.

**TEXTBOOK CONTENT:**
{content_to_use}

Create THREE quizzes with EXACTLY 10 questions EACH (total 30 questions):

**Quiz 1 - Easy (10 questions):**
- Focus: Direct concepts, formulas, definitions from textbook
- Type: Basic recall, must-know facts
- Example: "What is the formula for area of a circle?"

**Quiz 2 - Medium (10 questions):**
- Focus: Application of concepts, simple numericals
- Type: Understanding with some thinking
- Example: "Calculate area if radius is 7cm"

**Quiz 3 - Hard (10 questions):**
- Focus: Challenging problems, deeper understanding
- Type: Complex numericals, analytical thinking
- Example: Multi-step problems, "what if" scenarios

**CRITICAL REQUIREMENTS:**
1. Each quiz MUST have EXACTLY 10 questions
2. Age-appropriate for Class {standard} ({age_context})
3. Each question MUST have 4 options (A, B, C, D)
4. Provide clear, educational explanations
5. Use simple language
6. **ALL 30 QUESTIONS MUST BE UNIQUE** - No repeated questions across quizzes
7. The correct_answer field should contain the EXACT TEXT of the correct option

Return ONLY valid JSON (no markdown, no extra text):
{{
  "quizzes": [
    {{
      "quiz_id": 1,
      "difficulty": "Easy",
      "title": "Basic Concepts Quiz",
      "description": "Must-know questions",
      "questions": [
        {{
          "id": 1,
          "question": "Question text here",
          "options": ["Option A", "Option B", "Option C", "Option D"],
          "correct_answer": "Option A",
          "explanation": "Why this is correct"
        }}
      ]
    }},
    {{
      "quiz_id": 2,
      "difficulty": "Medium",
      "title": "Understanding Quiz",
      "description": "Application questions",
      "questions": [10 questions]
    }},
    {{
      "quiz_id": 3,
      "difficulty": "Hard",
      "title": "Challenge Quiz",
      "description": "Problem-solving questions",
      "questions": [10 questions]
    }}
  ]
}}"""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await call_llm(prompt, use_high_quality=True, expect_json=True, timeout=90.0)
            
            if response:
                try:
                    # Aggressive JSON cleaning
                    cleaned = response.strip()
                    if cleaned.startswith('```'):
                        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                        cleaned = re.sub(r'\s*```$', '', cleaned)
                    
                    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
                    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
                    cleaned = re.sub(r'}\s*{', r'},{', cleaned)
                    cleaned = re.sub(r']\s*\[', r'],[', cleaned)
                    
                    quiz_data = json.loads(cleaned)
                    if isinstance(quiz_data, dict) and "quizzes" in quiz_data and len(quiz_data["quizzes"]) == 3:
                        # Validate each quiz has 10 questions
                        all_valid = all(len(q.get("questions", [])) == 10 for q in quiz_data["quizzes"])
                        if all_valid:
                            # Shuffle options so correct answer isn't always first
                            quiz_data = shuffle_quiz_options(quiz_data)
                            await set_cached_content(cache_key, json.dumps(quiz_data))
                            logger.info(f"✅ Generated 3 basic quizzes (30 questions total) with shuffled options")
                            return quiz_data
                        else:
                            logger.warning(f"Quiz validation failed - not all quizzes have 10 questions")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid basic quiz JSON (attempt {attempt+1}): {e}")
                    if attempt == max_retries - 1:
                        error_pos = e.pos if hasattr(e, 'pos') else 0
                        snippet = cleaned[max(0, error_pos-100):min(len(cleaned), error_pos+100)]
                        logger.error(f"JSON error near: ...{snippet}...")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
                
        except Exception as e:
            logger.error(f"Basic quiz generation failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
    
    return None


async def generate_advanced_quiz(subject: str, chapter: str, content: str, language: str = 'english', source: str = 'ncert', standard: int = 5) -> Optional[Dict]:
    """Generate 3 advanced practice quizzes (for strong students only) - 30 questions total (10 each)"""
    cache_key = get_cache_key({
        'feature': 'quiz_advanced_v2',
        'subject': subject,
        'chapter': chapter,
        'language': language,
        'source': source,
        'standard': standard
    })
    
    cached = await get_cached_content(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except:
            return None
    
    content_to_use = content[:6000] if len(content) > 6000 else content
    age_context = get_age_context(standard)
    
    prompt = f"""Create 3 ADVANCED practice quizzes for strong Class {standard} students studying {subject} - {chapter}.

**TEXTBOOK CONTENT:**
{content_to_use}

Create THREE advanced quizzes with EXACTLY 10 questions EACH (total 30 questions):

**Quiz 4 - Advanced Application (10 questions):**
- Focus: Real-world applications, NOT directly from textbook
- Type: Application-oriented problems
- Example: "A farmer has circular field of radius 50m. If he wants to fence it..."

**Quiz 5 - Advanced Analysis (10 questions):**
- Focus: Analytical thinking, integration of concepts
- Type: "What would happen if...", cause-effect
- Example: Complex scenarios requiring deep understanding

**Quiz 6 - Advanced Problem Solving (10 questions):**
- Focus: Creative problem-solving, multi-step reasoning
- Type: Challenging applications, hypothesis testing
- Example: Design experiments, solve complex word problems

**CRITICAL REQUIREMENTS:**
1. Each quiz MUST have EXACTLY 10 questions
2. Questions are CHALLENGING but age-appropriate for Class {standard}
3. Each question MUST have 4 options (A, B, C, D)
4. Provide detailed explanations
5. NOT direct textbook questions - application-based
6. **ALL 30 QUESTIONS MUST BE UNIQUE** - No repeated questions across quizzes
7. The correct_answer field should contain the EXACT TEXT of the correct option

Return ONLY valid JSON (no markdown):
{{
  "quizzes": [
    {{
      "quiz_id": 4,
      "difficulty": "Advanced",
      "title": "Advanced Application Quiz",
      "description": "Real-world applications",
      "for_strong_students": true,
      "questions": [10 questions]
    }},
    {{
      "quiz_id": 5,
      "difficulty": "Advanced",
      "title": "Advanced Analysis Quiz",
      "description": "Analytical thinking",
      "for_strong_students": true,
      "questions": [10 questions]
    }},
    {{
      "quiz_id": 6,
      "difficulty": "Advanced",
      "title": "Advanced Problem Solving Quiz",
      "description": "Creative problem-solving",
      "for_strong_students": true,
      "questions": [10 questions]
    }}
  ]
}}"""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await call_llm(prompt, use_high_quality=True, expect_json=True, timeout=90.0)
            
            if response:
                try:
                    # Aggressive JSON cleaning
                    cleaned = response.strip()
                    if cleaned.startswith('```'):
                        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                        cleaned = re.sub(r'\s*```$', '', cleaned)
                    
                    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
                    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
                    cleaned = re.sub(r'}\s*{', r'},{', cleaned)
                    cleaned = re.sub(r']\s*\[', r'],[', cleaned)
                    
                    quiz_data = json.loads(cleaned)
                    if isinstance(quiz_data, dict) and "quizzes" in quiz_data and len(quiz_data["quizzes"]) == 3:
                        # Validate each quiz has 10 questions
                        all_valid = all(len(q.get("questions", [])) == 10 for q in quiz_data["quizzes"])
                        if all_valid:
                            # Shuffle options so correct answer isn't always first
                            quiz_data = shuffle_quiz_options(quiz_data)
                            await set_cached_content(cache_key, json.dumps(quiz_data))
                            logger.info(f"✅ Generated 3 advanced quizzes (30 questions total) with shuffled options")
                            return quiz_data
                        else:
                            logger.warning(f"Advanced quiz validation failed - not all quizzes have 10 questions")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid advanced quiz JSON (attempt {attempt+1}): {e}")
                    if attempt == max_retries - 1:
                        error_pos = e.pos if hasattr(e, 'pos') else 0
                        snippet = cleaned[max(0, error_pos-100):min(len(cleaned), error_pos+100)]
                        logger.error(f"JSON error near: ...{snippet}...")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
                
        except Exception as e:
            logger.error(f"Advanced quiz generation failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
    
    return None
    cache_key = get_cache_key({
        'feature': 'quiz_basic_v1',
        'subject': subject,
        'chapter': chapter,
        'language': language,
        'source': source,
        'standard': standard
    })
    
    cached = await get_cached_content(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except:
            return None
    
    content_to_use = content[:6000] if len(content) > 6000 else content
    age_context = get_age_context(standard)
    
    prompt = f"""Create 3 practice quizzes for Class {standard} students studying {subject} - {chapter}.

**TEXTBOOK CONTENT:**
{content_to_use}

Create THREE quizzes with 20 questions EACH (total 60 questions):

**Quiz 1 - Easy (20 questions):**
- Focus: Direct concepts, formulas, definitions, must-know facts
- Type: Basic recall, direct from textbook, fundamental understanding
- Difficulty: Must know for exam
- Example: "What is the formula for area of a circle?", "Define photosynthesis"

**Quiz 2 - Medium (20 questions):**
- Focus: Slightly more challenging, requires understanding
- Type: Application of direct concepts, numerical problems from textbook
- Difficulty: Must know for exam, requires some thinking
- Example: "Calculate area if radius is 7cm", "Explain why plants need sunlight"

**Quiz 3 - Hard (20 questions):**
- Focus: Challenging questions, may not be directly from textbook
- Type: Complex numericals, deeper conceptual questions, problem-solving
- Difficulty: Should know for exam, requires critical thinking
- Example: Multi-step problems, analysis questions, "what if" scenarios

**REQUIREMENTS:**
1. Each quiz must have EXACTLY 20 questions
2. All questions age-appropriate for Class {standard} ({age_context})
3. Each question must have 4 options (A, B, C, D)
4. Provide clear, educational explanations
5. Use simple language suitable for Class {standard}

Return ONLY valid JSON (no markdown, no extra text):
{{
  "quizzes": [
    {{
      "quiz_id": 1,
      "difficulty": "Easy",
      "title": "Basic Quiz",
      "description": "Must-know questions for exam",
      "questions": [
        {{
          "id": 1,
          "question": "Question text here",
          "options": ["Option A", "Option B", "Option C", "Option D"],
          "correct_answer": "Option A",
          "explanation": "Why this answer is correct"
        }}
      ]
    }},
    {{
      "quiz_id": 2,
      "difficulty": "Medium",
      "title": "Understanding Quiz",
      "description": "Must-know with thinking required",
      "questions": [20 questions]
    }},
    {{
      "quiz_id": 3,
      "difficulty": "Hard",
      "title": "Challenge Quiz",
      "description": "Should-know for strong preparation",
      "questions": [20 questions]
    }}
  ]
}}"""
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await call_llm(prompt, use_high_quality=True, expect_json=True, timeout=120.0)
            
            if response:
                try:
                    cleaned = response.strip()
                    if cleaned.startswith('```'):
                        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
                        cleaned = re.sub(r'\s*```$', '', cleaned)
                    
                    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
                    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
                    cleaned = re.sub(r'}\s*{', r'},{', cleaned)
                    
                    quiz_data = json.loads(cleaned)
                    if isinstance(quiz_data, dict) and "quizzes" in quiz_data and len(quiz_data["quizzes"]) == 3:
                        await set_cached_content(cache_key, json.dumps(quiz_data))
                        logger.info(f"✅ Generated {len(quiz_data['quizzes'])} basic quizzes")
                        return quiz_data
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid basic quiz JSON (attempt {attempt+1}): {e}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
                
        except Exception as e:
            logger.error(f"Basic quiz generation failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2)
                continue
    
    return None


async def get_quiz_explanation(question: str, student_answer: str, correct_answer: str, subject: str, standard: int = 5) -> str:
    """Generate age-appropriate explanation for wrong answer"""
    age_context = get_age_context(standard)
    
    prompt = f"""A Class {standard} student ({age_context['age_group']}) answered a {subject} question incorrectly.

Question: {question}
Student's Answer: {student_answer}
Correct Answer: {correct_answer}

Provide a kind, encouraging explanation (2-3 sentences) that:
1. Gently explains why their answer was not correct
2. Explains the correct answer using a simple analogy or example
3. Encourages them to keep trying

Be warm and supportive like a caring teacher. Use language appropriate for {age_context['age_group']} ({age_context['language_style']})."""
    
    response = await call_llm(prompt, use_high_quality=False, timeout=30.0)
    return response or "That's okay! Let's learn from this. The correct answer helps us understand the concept better. Keep practicing, you're doing great!"

async def explain_concept(subject: str, chapter: str, concept: str, content: str, language: str = 'english', source: str = 'ncert', standard: int = 5) -> Optional[Dict]:
    """Explain concept in story-telling way for students"""
    cache_key = get_cache_key({
        'feature': 'explain_v2',
        'subject': subject,
        'chapter': chapter,
        'concept': concept,
        'language': language,
        'source': source,
        'standard': standard
    })
    
    cached = await get_cached_content(cache_key)
    if cached:
        try:
            return json.loads(cached)
        except:
            pass
    
    content_to_use = content[:4000] if len(content) > 4000 else content
    age_context = get_age_context(standard)
    
    prompt = f"""You are a fun, engaging teacher explaining concepts to Class {standard} students ({age_context['age_group']}) through storytelling.

Subject: {subject}
Chapter: {chapter}

TEXTBOOK CONTENT:
{content_to_use}

Explain the main concepts from this chapter in a story-telling way that a {age_context['age_group']} student would love.

Return ONLY a JSON object:
{{
  "story_title": "An engaging title for the story",
  "characters": ["Character 1 - who helps explain", "Character 2 - the curious learner"],
  "story": "A fun story that teaches the concepts. Use dialogue, adventures, and real-world examples. Make it engaging with 'Imagine...' and 'Let's say...' Start with an interesting hook. The story should be 300-400 words.",
  "key_takeaways": [
    {{"concept": "Concept name", "simple_explanation": "What we learned", "real_life_example": "Where we see this in daily life"}}
  ],
  "fun_facts": [
    "Interesting fact related to the topic"
  ],
  "try_this": "A simple activity or experiment the child can do at home to understand the concept better"
}}

Make it FUN, engaging, and educational! Use {age_context['language_style']} and exciting descriptions."""
    
    response = await call_llm(prompt, use_high_quality=True, expect_json=True, timeout=90.0)
    
    if response:
        try:
            explanation = json.loads(response)
            await set_cached_content(cache_key, json.dumps(explanation))
            return explanation
        except json.JSONDecodeError as e:
            logger.error(f"Invalid explain JSON: {e}")
    
    return None

async def answer_doubt(
    subject: str,
    chapter_title: str, 
    question: str,
    revision_notes_context: str = "",
    chapter_topics: List[str] = None,
    language: str = 'english',
    conversation_history: List[Dict] = None,
    standard: int = 5
) -> Optional[Dict]:
    """
    Answer student doubts using ONLY revision notes for context and guardrails.
    Does NOT use textbook content or chapter name for answering.
    """
    age_context = get_age_context(standard)
    chapter_topics = chapter_topics or []
    
    # Build conversation context
    history_text = ""
    if conversation_history:
        for msg in conversation_history[-5:]:  # Last 5 messages
            role = "Student" if msg.get('role') == 'user' else "Teacher"
            history_text += f"{role}: {msg.get('content', '')}\n"
    
    # Build guardrails from chapter topics
    topics_text = ", ".join(chapter_topics) if chapter_topics else "this chapter's topics"
    
    # Prepare context from revision notes
    context_section = ""
    if revision_notes_context:
        context_section = f"""
==================== CHAPTER CONTEXT - READ THIS CAREFULLY ====================
{revision_notes_context}

CRITICAL: Use ONLY the information above to answer questions about this chapter.
If asked "what is taught in this chapter", summarize the topics and concepts listed above.
DO NOT give generic answers - use the specific information provided above.
==================================================================================
"""
    else:
        context_section = f"""
Note: Revision notes are not available for this chapter yet. 
You may use general knowledge about {subject} topics for Class {standard}, 
but mention that detailed chapter notes are not available yet.
"""
    
    system_message = f"""You are a helpful tutor for Class {standard} students ({age_context['age_group']}) studying {subject}.

CRITICAL RULES - READ CAREFULLY:
1. You MUST ONLY use information from the "CHAPTER CONTEXT" provided below
2. If the chapter context is provided, answer ONLY based on what's in that context
3. DO NOT use your general knowledge about {subject} if context is provided
4. If asked "what is taught in this chapter", summarize what's in the CHAPTER CONTEXT
5. If the question cannot be answered from the context, say: "I don't have information about that in this chapter's notes. Let me help you with the topics we've covered."

IMPORTANT GUARDRAILS:
- Chapter name: {chapter_title} (this is just a label, don't interpret it literally)
- Topics covered: {topics_text}
- If question is unrelated to these topics, politely redirect
- Use {age_context['language_style']} and real-life examples
- Be encouraging and supportive

{context_section}

WHAT YOU MUST DO:
1. Read the CHAPTER CONTEXT carefully
2. Answer based ONLY on what's in the context
3. If context is empty, use general knowledge but mention that revision notes aren't available
4. Never give generic answers when specific context is provided
"""

    prompt = f"""Previous conversation:
{history_text}

Student's question: {question}

IMPORTANT INSTRUCTIONS:
1. First, check if the CHAPTER CONTEXT above contains relevant information
2. If YES: Answer using ONLY the information from that context
3. If NO: Let the student know the topic isn't covered in the available notes

Guidelines for answering:
- Quote key concepts from the chapter context when relevant
- Use the exact topics mentioned in the context
- If asked "what is taught", list the topics from the context
- Explain concepts from the context using simple language
- Add examples to make it clear (can be your own examples)
- Break down complex ideas step-by-step
- Be encouraging and patient

DO NOT:
- Give generic answers when specific context is provided
- Ignore the chapter context
- Use general knowledge if context is available
- Interpret the chapter name "{chapter_title}" literally

Return ONLY a JSON object:
{{
  "answer": "Your answer based on the chapter context provided above",
  "is_on_topic": true/false,
  "follow_up_suggestions": ["Question about topic from context", "Another question about context"],
  "related_concepts": ["Concepts actually mentioned in the chapter context"],
  "used_context": true/false
}}"""
    
    try:
        response = await call_llm(
            prompt, 
            use_high_quality=False,
            system_message=system_message, 
            expect_json=True,
            model_override="google/gemini-3-flash-preview",  # Use Gemini 3 Flash Preview for better quality
            timeout=45.0
        )
        
        if response:
            try:
                answer_data = json.loads(response)
                return answer_data
            except json.JSONDecodeError:
                # Return as plain text if JSON parsing fails
                return {
                    "answer": response,
                    "is_on_topic": True,
                    "follow_up_suggestions": [],
                    "related_concepts": [],
                    "used_web_search": False
                }
        
        return {
            "answer": f"I'm having trouble understanding your question. Could you please rephrase it? I'm here to help you with topics related to {chapter_title}!",
            "is_on_topic": True,
            "follow_up_suggestions": [f"What topics are covered in {chapter_title}?", "Can you explain a key concept?"],
            "related_concepts": [],
            "used_web_search": False
        }
    
    except Exception as e:
        logger.error(f"Error in answer_doubt: {e}")
        return {
            "answer": "I encountered an error while processing your question. Please try again!",
            "is_on_topic": True,
            "follow_up_suggestions": [],
            "related_concepts": [],
            "used_web_search": False
        }

# Placeholder functions for features not yet implemented
async def generate_quiz(*args, **kwargs):
    return {"questions": []}

async def evaluate_quiz_answer(*args, **kwargs):
    return {
        "is_correct": False,
        "score": 0.0,
        "feedback": "Feature coming soon",
        "concept": "General"
    }



async def generate_pyq_solution_from_questions(questions: list, exam_name: str, year: str, standard: int = 5) -> Dict:
    """
    Generate age-appropriate solutions for PYQ questions using Gemini 3 Flash Preview.
    Takes extracted questions array and generates detailed step-by-step solutions.
    """
    try:
        system_msg = f"""You are an expert teacher creating solutions for Class {standard} students.

CRITICAL RULES:
- Solutions MUST be age-appropriate for Class {standard}
- For OBJECTIVE questions: Explain correct answer + why others are wrong
- For SUBJECTIVE questions: Provide step-by-step solutions with clear reasoning
- Use simple language suitable for kids
- Support ALL math symbols (÷, ×, √, ², ³, π, ∑, ∫)
- Include tips to remember concepts
- Be thorough but not overwhelming"""

        prompt = f"""Generate comprehensive solutions for this Previous Year Paper.

**Exam:** {exam_name}
**Year:** {year}
**Class:** {standard}

**Questions:**
{json.dumps(questions, indent=2)}

For EACH question, provide:

1. **For Objective Questions:**
   - Correct answer
   - Why it's correct
   - Why other options are wrong (if multiple choice)
   - Quick tip to remember

2. **For Subjective Questions:**
   - Step-by-step solution (numbered steps)
   - Clear explanations
   - Final answer
   - Key concept to remember

Return ONLY valid JSON:
{{
  "exam_name": "{exam_name}",
  "year": "{year}",
  "solutions": [
    {{
      "question_number": "1",
      "question_text": "Copy exact question here",
      "question_type": "objective" or "subjective",
      "solution_steps": [
        "Step 1: ...",
        "Step 2: ...",
        "Step 3: ..."
      ],
      "final_answer": "Clear final answer",
      "key_concept": "Main concept for this question",
      "tips": "Quick tip to remember"
    }}
  ]
}}"""

        # Use Gemini 3 Flash Preview for PYQ solutions
        logger.info(f"Generating PYQ solutions with Gemini 3 Flash Preview for Class {standard}")
        
        response = await call_llm(
            prompt=prompt,
            system_message=system_msg,
            use_high_quality=False,
            model_override="google/gemini-3-flash-preview",  # Use Gemini 3 Flash Preview
            expect_json=True,
            timeout=180.0
        )
        
        if not response:
            raise Exception("No response from AI")
        
        # Parse JSON
        json_str = extract_json_from_response(response)
        solutions = json.loads(json_str)
        
        # Validate structure
        if "solutions" not in solutions or not isinstance(solutions["solutions"], list):
            raise Exception("Invalid solution format - missing 'solutions' array")
        
        logger.info(f"✅ Generated solutions for {len(solutions['solutions'])} questions")
        return solutions
        
    except Exception as e:
        logger.error(f"PYQ solution generation failed: {e}")
        raise


async def generate_pyq_solution(question_paper_text: str, exam_name: str, year: str, standard: int = 5) -> Optional[Dict]:
    """
    Generate comprehensive solutions for Previous Year Question Paper.
    Uses high-quality LLM for detailed step-by-step solutions.
    
    Returns structured JSON format for UI rendering:
    {
        "exam_name": "mid_term_i",
        "year": 2022,
        "questions": [
            {
                "question_no": 1,
                "question_text": "...",
                "answer_steps": ["Step 1...", "Step 2..."],
                "final_answer": "..."
            }
        ]
    }
    """
    age_context = get_age_context(standard)
    
    prompt = f"""You are an expert teacher for Class {standard} students ({age_context['age_group']}). 
Generate comprehensive solutions for this previous year question paper.

**IMPORTANT GUIDELINES:**
- Language: {age_context['language_style']}
- Complexity: {age_context['complexity']}
- Tone: {age_context['tone']}
- Use examples related to: {age_context['examples']}

**Exam:** {exam_name}
**Year:** {year}
**Class:** {standard}

**Question Paper:**
{question_paper_text[:15000]}

**YOUR TASK:**
1. Extract ALL questions from the paper (preserve question numbering)
2. Provide step-by-step solutions appropriate for Class {standard}
3. Explain concepts clearly - don't assume prior knowledge
4. Include formulas/diagrams descriptions where needed
5. Ensure mathematical symbols and equations are properly formatted

**CRITICAL: Output MUST be valid JSON in this EXACT format:**
{{
  "exam_name": "{exam_name.lower().replace(' ', '_')}",
  "year": {year},
  "questions": [
    {{
      "question_no": 1,
      "question_text": "Extract the exact question text here",
      "answer_steps": [
        "Step 1: Identify what is being asked...",
        "Step 2: Apply the relevant formula or concept...",
        "Step 3: Perform the calculation..."
      ],
      "final_answer": "The complete final answer"
    }},
    {{
      "question_no": 2,
      "question_text": "Next question...",
      "answer_steps": ["..."],
      "final_answer": "..."
    }}
  ]
}}

Rules:
- Each question MUST have: question_no, question_text, answer_steps (array), final_answer
- answer_steps MUST be an array of strings, each step on a new line
- Preserve mathematical notation (use standard notation like x², π, √, etc.)
- Be thorough but {age_context['language_style']}
- Output ONLY valid JSON, no additional text"""

    system_message = f"You are an expert teacher solving previous year question papers for Class {standard} students. Output ONLY valid JSON."
    
    solution_json = await call_llm(
        prompt=prompt,
        use_high_quality=False,
        model_override="google/gemini-3-flash-preview",  # Use Gemini 3 Flash Preview
        system_message=system_message,
        expect_json=True,
        timeout=180.0
    )
    
    if solution_json:
        try:
            parsed = json.loads(solution_json)
            # Validate structure
            if "questions" in parsed and isinstance(parsed["questions"], list):
                return parsed
            else:
                logger.error("PYQ solution missing 'questions' array")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid PYQ solution JSON: {e}")
    
    return None



async def generate_homework_solution(homework_text: str, title: str, standard: int) -> Optional[Dict]:
    """
    Generate comprehensive solution for homework assignment.
    Uses GPT OSS 120B (Free) model for cost-effective homework help.
    Returns structured solution with explanations.
    """
    age_context = get_age_context(standard)
    
    prompt = f"""You are an expert teacher for Class {standard} students ({age_context['age_group']}). Provide comprehensive solutions for this homework assignment.

**IMPORTANT GUIDELINES:**
- Language: {age_context['language_style']}
- Complexity: {age_context['complexity']}
- Tone: {age_context['tone']}
- Use examples related to: {age_context['examples']}

**Homework Title:** {title}
**Class:** {standard}

**Homework Questions:**
{homework_text[:15000]}

**YOUR TASK:**
1. Extract ALL questions from the homework
2. Provide step-by-step solutions that a Class {standard} student can follow
3. Explain the "why" behind each step, not just the "how"
4. Use simple language and relatable examples
5. Point out common mistakes to avoid
6. Add tips for similar problems in exams

Provide detailed solutions in this JSON format:
{{
  "title": "{title}",
  "class": {standard},
  "total_questions": 10,
  "solutions": [
    {{
      "question_number": 1,
      "question": "Extract the exact question text",
      "understanding": "First, let's understand what the question is asking...",
      "solution_steps": [
        "Step 1: ...",
        "Step 2: ...",
        "Step 3: ..."
      ],
      "final_answer": "The complete answer",
      "key_concepts": ["concept1", "concept2"],
      "difficulty": "easy/medium/hard",
      "common_mistake": "Students often make this mistake...",
      "exam_tip": "In exams, questions like this appear as..."
    }}
  ],
  "general_tips": ["Study tip 1 based on this homework", "Study tip 2"],
  "revision_points": ["Key point 1 to remember", "Key point 2 from this homework"],
  "practice_suggestions": ["Practice more of...", "Focus on understanding..."]
}}

Use {age_context['tone']} throughout. Be encouraging and help build confidence."""

    system_message = f"You are a patient, encouraging teacher who helps Class {standard} students understand their homework. You explain things step-by-step in language that {age_context['age_group']} can easily follow."
    
    # Use GPT OSS 120B Free model for homework help (cost-effective)
    solution_json = await call_llm(
        prompt=prompt,
        use_high_quality=False,  # Use free model for homework
        system_message=system_message,
        expect_json=True,
        timeout=120.0
    )
    
    if solution_json:
        try:
            return json.loads(solution_json)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid homework solution JSON: {e}")
    
    return None


# =============================================================================
# HOMEWORK QUESTION EXTRACTION AND ANSWER EVALUATION
# =============================================================================

async def extract_homework_questions(homework_text: str, model_answers_text: str = None) -> Optional[Dict]:
    """
    Extract individual questions from homework PDF using OCR text.
    Optionally match with model answers if provided.
    
    Returns:
    {
        "questions": [
            {
                "question_number": 1,
                "question_text": "What is photosynthesis?",
                "model_answer": "Process by which plants make food..." (if available),
                "marks": 5
            },
            ...
        ]
    }
    """
    try:
        system_msg = """You are an expert at analyzing homework assignments and extracting individual questions.
Your task is to identify and extract each question from the provided text."""

        prompt = f"""Analyze this homework text and extract all individual questions.
For each question, identify:
1. Question number
2. Complete question text
3. Estimated marks (if mentioned, otherwise assume 5 marks)

Homework Text:
{homework_text[:3000]}  # Limit to avoid token overflow

{"Model Answers Text: " + model_answers_text[:2000] if model_answers_text else ""}

Return as JSON array:
[
  {{
    "question_number": 1,
    "question_text": "...",
    "model_answer": "..." (if available),
    "marks": 5
  }},
  ...
]"""

        # Use free model for extraction
        response = await call_llm(
            prompt=prompt,
            system_message=system_msg,
            use_high_quality=False,
            model_override="google/gemini-2.5-flash",  # Fast and free for simple extraction
            expect_json=True,
            timeout=45.0
        )
        
        if not response:
            return None
            
        # Parse JSON response
        json_str = extract_json_from_response(response)
        questions_data = json.loads(json_str)
        
        return {"questions": questions_data}
        
    except Exception as e:
        logger.error(f"Error extracting homework questions: {e}")
        return None


async def evaluate_student_answer(
    question: str,
    student_answer: str,
    model_answer: str = None,
    question_number: int = 1
) -> Dict:
    """
    Evaluate student's answer using Gemini 3 Flash (FREE via Emergent Universal Key).
    Provides constructive feedback with positive tone.
    Ignores spelling and minor grammar mistakes.
    
    Returns:
    {
        "is_correct": bool,
        "feedback": str,
        "score": float (0-1),
        "corrected_answer": str (if minor mistakes)
    }
    """
    try:
        system_msg = """You are a supportive, encouraging teacher evaluating a young student's answer.
        
CRITICAL RULES:
- Ignore ALL spelling mistakes and minor grammar errors
- Focus ONLY on whether they understood the concept
- Be extremely positive and encouraging
- Support math symbols (÷, ×, √, ², ³, π, etc.)
- If the core idea is correct, mark it as correct even with mistakes
- Always start feedback with something positive"""

        prompt = f"""Question {question_number}: {question}

Student's Answer: {student_answer}

{f"Model Answer (for reference): {model_answer}" if model_answer else ""}

Evaluate this answer with these STRICT GUIDELINES:

1. **IGNORE spelling mistakes** - "photosynthasis" = "photosynthesis" ✅
2. **IGNORE grammar errors** - focus on concept understanding
3. **Support math symbols** - ÷, ×, √, ², ³, π, ∑, ∫, etc.
4. **Be lenient** - if core concept is right, mark correct
5. **Be encouraging** - always start with praise

Provide feedback in clear points like:
✅ What they got right
📝 What to improve (if needed)  
💡 Simple tip (if applicable)

Return ONLY valid JSON (no markdown):
{{
  "is_correct": true,
  "feedback": "🌟 Great work! You understood the main concept...\n\n✅ Correct points:\n- Point 1\n- Point 2\n\n📝 Small improvement:\n- Suggestion",
  "score": 0.9,
  "corrected_answer": "Corrected version with proper spelling"
}}"""

        # Use OpenRouter with free GPT model for evaluation
        response = await call_llm(
            prompt=prompt,
            system_message=system_msg,
            expect_json=True,
            timeout=30.0,
            task_type="evaluation"  # Uses openai/gpt-oss-120b:free
        )
        
        if not response:
            return {
                "is_correct": None,
                "feedback": "⚡ Couldn't evaluate right now. Please try again!",
                "score": 0.5
            }
            
        # Parse JSON response
        json_str = extract_json_from_response(response)
        evaluation = json.loads(json_str)
        
        # Ensure feedback uses clear formatting
        if 'feedback' in evaluation:
            evaluation['feedback'] = evaluation['feedback'].strip()
        
        return evaluation
        
    except Exception as e:
        logger.error(f"Error evaluating answer: {e}")
        return {
            "is_correct": None,
            "feedback": "⚡ Couldn't evaluate right now. Please try again!",
            "score": 0.5
        }


async def help_with_question(question: str, model_answer: str = None, standard: int = 5) -> str:
    """
    Generate helpful, kid-friendly answer when student asks for help.
    Uses Gemini 3 Flash (FREE via Emergent Universal Key).
    Supports math symbols and gives step-by-step explanations.
    """
    try:
        system_msg = f"""You are a patient, friendly tutor helping a Class {standard} student.

RULES:
- Explain in SIMPLE, clear language for kids
- Break down into easy steps
- Use examples they can relate to
- Support ALL math symbols (÷, ×, √, ², ³, π, ∑, ∫, etc.)
- Be encouraging and positive
- Give point-by-point explanations"""

        prompt = f"""Question: {question}

{f"Reference Answer: {model_answer}" if model_answer else ""}

Provide a clear, step-by-step explanation that helps a Class {standard} student understand and solve this.

Format your answer like this:

📚 **Understanding the Question:**
- Explain what we need to find

📝 **Step-by-Step Solution:**
1. First step...
2. Second step...
3. Final answer

💡 **Key Point to Remember:**
- One important thing to remember

Keep it simple, clear, and under 200 words. Use proper math symbols if needed (÷, ×, √, ², etc.)."""

        # Use OpenRouter with free GPT model for help generation
        response = await call_llm(
            prompt=prompt,
            system_message=system_msg,
            timeout=30.0,
            task_type="evaluation"  # Uses openai/gpt-oss-120b:free
        )
        
        if not response:
            return "⚡ I couldn't generate help right now. Please try again or ask your teacher!"
        
        return response.strip()
        
    except Exception as e:
        logger.error(f"Error generating help: {e}")
        return "⚡ I couldn't generate help right now. Please try again or ask your teacher!"



# =============================================================================
# FREQUENTLY ASKED PYQs ANALYSIS
# =============================================================================

async def analyze_frequently_asked_pyqs(pyq_list: list) -> Optional[Dict]:
    """
    Analyze multiple PYQs to find frequently asked questions.
    Uses Gemini 3 Flash Preview to identify:
    - Exact same questions appearing multiple times
    - Similar/conceptually related questions
    
    Args:
        pyq_list: List of dicts with 'id', 'exam_name', 'year', 'questions'
    
    Returns:
        Analysis with exact_repeats, similar_concepts, and analysis_summary
    """
    try:
        # Prepare analysis text from questions
        analysis_text = "Previous Year Papers Analysis:\n\n"
        for idx, pyq in enumerate(pyq_list[:10], 1):  # Limit to 10 PYQs
            analysis_text += f"{idx}. {pyq['exam_name']} {pyq['year']}\n"
            analysis_text += "Questions:\n"
            
            # Extract question text from questions array
            questions = pyq.get('questions', [])[:20]  # Limit to first 20 questions per PYQ
            for q_idx, question in enumerate(questions, 1):
                q_text = question.get('question_text', '') or question.get('question', '')
                if q_text:
                    analysis_text += f"   {q_idx}. {q_text[:150]}\n"  # Limit each question text
            
            analysis_text += "\n"
        
        system_msg = """You are an expert at analyzing exam papers and identifying frequently asked questions.
Analyze the given PYQs and identify:
1. EXACT same questions appearing in multiple papers
2. SIMILAR questions (different wording, same concept)
Focus on questions that appear at least twice."""

        prompt = f"""Analyze these Previous Year Papers and identify frequently asked questions:

{analysis_text}

Identify:
1. **Exact Repeats**: Questions with same or nearly identical wording
2. **Similar Concepts**: Questions testing the same concept but with different wording

Return as JSON:
{{
  "exact_repeats": [
    {{
      "question": "exact question text",
      "count": 3,
      "appearances": [
        {{"exam": "CBSE", "year": 2023}},
        {{"exam": "CBSE", "year": 2022}}
      ]
    }}
  ],
  "similar_concepts": [
    {{
      "concept": "Concept name",
      "count": 5,
      "variations": [
        {{"question": "variation 1", "exam": "CBSE", "year": 2023}},
        {{"question": "variation 2", "exam": "State", "year": 2022}}
      ]
    }}
  ],
  "total_questions": 150,
  "exact_repeat_count": 15,
  "similar_concept_groups": 8
}}"""

        # Use Gemini 2.5 Flash Lite for fast and efficient pattern recognition
        response = await call_llm(
            prompt=prompt,
            system_message=system_msg,
            use_high_quality=False,
            model_override="google/gemini-2.5-flash-lite",  # Fast model for pattern recognition
            expect_json=True,
            timeout=60.0
        )
        
        if not response:
            return None
            
        # Parse JSON response
        json_str = extract_json_from_response(response)
        analysis = json.loads(json_str)
        
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing frequently asked PYQs: {e}")
        return None



async def extract_test_questions(ocr_text: str, model_answers_content: Optional[bytes] = None) -> Optional[List[Dict]]:
    """
    Extract questions from test OCR text and optionally match with model answers.
    Uses GPT OSS 120B Free model.
    
    Args:
        ocr_text: Extracted text from the test paper
        model_answers_content: Raw bytes of model answers PDF (not a path!)
    """
    try:
        # Read model answers if provided (bytes content)
        # Model answers processing removed - Gemini handles PDFs natively
        # No need for local text extraction
        model_answers_text = ""
        if model_answers_content:
            logger.info("Model answers will be processed by Gemini AI")
        
        prompt = f"""Extract all questions from this test paper. For each question:
1. Extract the complete question text (without the options)
2. If it's an MCQ, extract all options separately
3. Assign a question number
4. If model answers are provided, match them to the questions

Test Paper Text:
{ocr_text}

{'Model Answers:' + model_answers_text if model_answers_text else 'No model answers provided.'}

Return a JSON array with this structure:
[
  {{
    "question_number": 1,
    "question_text": "The question text without options",
    "options": ["Option A text", "Option B text", "Option C text", "Option D text"],
    "model_answer": "A or B or C or D (if MCQ) or full answer text if not MCQ",
    "marks": 5,
    "is_mcq": true
  }}
]

IMPORTANT:
- For MCQ questions, extract the options into the "options" array (should have 4 items)
- The "options" array should contain ONLY the option text, not the letter prefix (a, b, c, d)
- For non-MCQ questions, leave "options" as an empty array []
- Set "is_mcq" to true if the question has options, false otherwise

Extract ALL questions. Be thorough."""
        
        response = await call_llm(
            prompt=prompt,
            use_high_quality=False,  # Use free model
            expect_json=True,
            model_override="google/gemini-2.5-flash",
            timeout=90.0
        )
        
        if not response:
            logger.error("No response from LLM for question extraction")
            return None
        
        # Parse JSON
        json_str = extract_json_from_response(response)
        questions = json.loads(json_str)
        
        return questions
        
    except Exception as e:
        logger.error(f"Error extracting test questions: {e}")
        return None


async def evaluate_test_answers(questions: List[Dict], student_answers: Dict[str, str], **kwargs) -> Dict:
    """
    Evaluate student test answers against model answers using GPT OSS 120B Free model.
    Returns ONLY total score (no detailed feedback saved).
    """
    try:
        # Build evaluation prompt
        evaluation_data = []
        
        for question in questions:
            q_num = question.get('question_number')
            q_text = question.get('question_text', '')
            model_answer = question.get('model_answer', '')
            marks = question.get('marks', 5)
            student_answer = student_answers.get(str(q_num), '')
            
            evaluation_data.append({
                "question_number": q_num,
                "question": q_text,
                "model_answer": model_answer,
                "student_answer": student_answer,
                "max_marks": marks
            })
        
        # Check if marking schema is provided
        marking_schema_text = kwargs.get('marking_schema_text', None)
        
        if marking_schema_text:
            # Evaluation with marking schema
            prompt = f"""Evaluate these test answers STRICTLY according to the marking schema provided by the teacher.

MARKING SCHEMA (MUST FOLLOW EXACTLY):
{marking_schema_text}

Questions and Answers:
{json.dumps(evaluation_data, indent=2)}

CRITICAL INSTRUCTIONS:
1. Follow the marking schema EXACTLY as provided
2. Award marks ONLY as specified in the schema
3. Check for keywords, steps, or criteria mentioned in the schema
4. Award partial marks ONLY if schema allows it
5. Be strict and objective - no leniency beyond what schema permits

Return JSON in this format:
{{
  "total_score": 42.5,
  "max_total_score": 50,
  "question_count": 10
}}"""
        else:
            # Standard evaluation without schema
            prompt = f"""Evaluate these test answers. Compare each student answer with the model answer and provide:
1. Score out of max marks for each question
2. Total score

Questions and Answers:
{json.dumps(evaluation_data, indent=2)}

Return JSON in this format (NO detailed feedback, just scores):
{{
  "total_score": 42.5,
  "max_total_score": 50,
  "question_count": 10
}}

Be fair and award partial credit for partially correct answers."""
        
        response = await call_llm(
            prompt=prompt,
            use_high_quality=False,  # Use free model (GPT OSS 120B)
            expect_json=True,
            model_override="google/gemini-2.5-flash",
            timeout=120.0
        )
        
        if not response:
            logger.error("No response from LLM for answer evaluation")
            return {
                "total_score": 0,
                "max_total_score": sum(q.get('marks', 5) for q in questions),
                "question_count": len(questions)
            }
        
        # Parse JSON
        try:
            json_str = extract_json_from_response(response)
            logger.info(f"📝 LLM response extracted: {json_str[:200] if json_str else 'None'}...")
            evaluation = json.loads(json_str)
            logger.info(f"✅ Parsed evaluation: total={evaluation.get('total_score')}, max={evaluation.get('max_total_score')}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON from LLM response: {e}")
            logger.error(f"Raw response: {response[:500]}")
            return {
                "total_score": 0,
                "max_total_score": sum(q.get('marks', 5) for q in questions),
                "question_count": len(questions)
            }
        
        # Ensure we have question count
        if 'question_count' not in evaluation:
            evaluation['question_count'] = len(questions)
        
        return evaluation
        
    except Exception as e:
        logger.error(f"Error evaluating test answers: {e}")
        return {
            "total_score": 0,
            "max_total_score": sum(q.get('marks', 5) for q in questions),
            "question_count": len(questions)
        }

