"""
AI PDF Extraction Service using OpenRouter

Sends PDF directly to Google Gemini 2.5 Flash via OpenRouter for text extraction.
No image conversion needed - Gemini accepts PDF files directly.
"""

import logging
import json
import os
import re
import base64
import httpx
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Model for PDF text extraction (supports file input)
TEXT_EXTRACTION_MODEL = "google/gemini-2.5-flash-lite"
# Model for structured question extraction and other AI tasks
QUESTION_EXTRACTION_MODEL = "google/gemini-2.5-flash-lite"


def extract_json_robust(text: str) -> str:
    """
    Robust JSON extraction that handles common LLM output issues.
    """
    if not text:
        raise ValueError("Empty response received")
    
    # Step 1: Remove control characters
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    original_text = text  # Keep for debugging
    text = text.strip()
    
    # Step 2: Remove markdown code block wrappers
    if '```' in text:
        # Find all ``` positions
        parts = text.split('```')
        if len(parts) >= 3:
            # Content is between first and second ```
            inner = parts[1]
            # Remove 'json' label if present at start
            inner = inner.strip()
            if inner.lower().startswith('json'):
                inner = inner[4:].strip()
            text = inner
    
    # Step 3: Find JSON boundaries
    first_brace = text.find('{')
    first_bracket = text.find('[')
    
    if first_brace == -1 and first_bracket == -1:
        logger.error(f"No JSON found. Response preview: {original_text[:500]}")
        raise ValueError("No JSON structure found in response")
    
    # Determine start position
    if first_brace == -1:
        json_start = first_bracket
    elif first_bracket == -1:
        json_start = first_brace
    else:
        json_start = min(first_brace, first_bracket)
    
    # Find end using bracket counting (handling strings properly)
    depth = 0
    in_string = False
    escape_next = False
    json_end = -1
    
    for i in range(json_start, len(text)):
        char = text[i]
        
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
            depth += 1
        elif char in '}]':
            depth -= 1
            if depth == 0:
                json_end = i + 1
                break
    
    # Fallback: if bracket counting failed, try to find last } or ]
    if json_end == -1 or json_end <= json_start:
        last_brace = text.rfind('}')
        last_bracket = text.rfind(']')
        json_end = max(last_brace, last_bracket) + 1
        logger.warning(f"Bracket counting failed, using fallback. End position: {json_end}")
    
    if json_end <= json_start:
        logger.error(f"Could not find JSON end. Text preview: {text[:500]}")
        raise ValueError("Could not find valid JSON boundaries")
    
    json_str = text[json_start:json_end]
    
    # Step 4: Fix common LLM JSON errors
    json_str = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas before }
    json_str = re.sub(r',\s*]', ']', json_str)  # Remove trailing commas before ]
    json_str = re.sub(r'}\s*{', '},{', json_str)  # Fix missing commas between objects
    
    # Verify it's valid JSON before returning
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error(f"JSON still invalid after cleanup: {e}")
        logger.error(f"Cleaned JSON preview: {json_str[:500]}")
        raise ValueError(f"Invalid JSON after cleanup: {e}")
    
    return json_str


class ExtractionStage:
    """Extraction stage enum for observability"""
    UPLOADED = 'UPLOADED'
    PROCESSING = 'PROCESSING'
    EXTRACTING_TEXT = 'EXTRACTING_TEXT'
    EXTRACTING_QUESTIONS = 'EXTRACTING_QUESTIONS'
    EXTRACTING_SOLUTIONS = 'EXTRACTING_SOLUTIONS'
    SAVING_TO_S3 = 'SAVING_TO_S3'
    VERIFYING_S3 = 'VERIFYING_S3'
    FETCHING_PDF_FROM_S3 = 'FETCHING_PDF_FROM_S3'
    VALIDATING_JSON = 'VALIDATING_JSON'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    TIMEOUT = 'TIMEOUT'


async def extract_text_from_pdf_via_openrouter(pdf_bytes: bytes, test_id: str) -> str:
    """
    Send PDF directly to OpenRouter (Google Gemini 2.5 Flash) for text extraction.
    No image conversion needed - Gemini accepts PDF files directly.
    """
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not configured")
    
    logger.info(f"[EXTRACTION][{test_id}] Sending PDF ({len(pdf_bytes)/1024:.1f}KB) to {TEXT_EXTRACTION_MODEL}...")
    
    # Encode PDF as base64
    pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://test-eval-debug.preview.emergentagent.com",
        "X-Title": "StudyBuddy PDF Extraction"
    }
    
    # User's tested prompt for text extraction
    extraction_prompt = "extract text from this. do not summarize give exact extracted text. where ever images are there, give a text description of the image"
    
    payload = {
        "model": TEXT_EXTRACTION_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": extraction_prompt},
                {"type": "file", "file": {
                    "filename": "document.pdf",
                    "file_data": f"data:application/pdf;base64,{pdf_base64}"
                }}
            ]
        }],
        "max_tokens": 8000,
        "temperature": 0.1
    }
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            
            if response.status_code != 200:
                error_text = response.text
                logger.error(f"[EXTRACTION][{test_id}] OpenRouter error: {response.status_code} - {error_text[:300]}")
                raise Exception(f"OpenRouter API error {response.status_code}: {error_text[:200]}")
            
            data = response.json()
            
            if 'error' in data:
                raise Exception(f"OpenRouter error: {data['error']}")
            
            content = data['choices'][0]['message']['content']
            logger.info(f"[EXTRACTION][{test_id}] Text extracted via {TEXT_EXTRACTION_MODEL}: {len(content)} chars")
            return content
            
    except httpx.TimeoutException:
        logger.error(f"[EXTRACTION][{test_id}] Request timed out")
        raise Exception("PDF extraction timed out. The file may be too large.")
    except Exception as e:
        logger.error(f"[EXTRACTION][{test_id}] Extraction error: {e}")
        raise


async def call_openrouter(prompt: str, system_message: str, max_tokens: int = 4000) -> str:
    """
    Call OpenRouter API with text prompt for structured extraction.
    """
    if not OPENROUTER_API_KEY:
        raise Exception("OPENROUTER_API_KEY not configured")
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://test-eval-debug.preview.emergentagent.com",
        "X-Title": "StudyBuddy AI Tutor"
    }
    
    payload = {
        "model": QUESTION_EXTRACTION_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"[OPENROUTER] API error {response.status_code}: {error_text}")
            raise Exception(f"OpenRouter API error: {response.status_code}")
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        logger.info(f"[OPENROUTER] Response received: {len(content)} chars")
        return content


async def extract_with_gemini(
    test_id: str,
    pdf_bytes: bytes,
    model_answers_pdf_bytes: Optional[bytes] = None
) -> Dict[str, Any]:
    """
    Extract questions from PDF using OpenRouter.
    
    Process:
    1. Send PDF directly to google/gemini-2.5-flash for text extraction
    2. Send extracted text to nvidia/nemotron for structured question extraction
    
    Args:
        test_id: Test ID for logging
        pdf_bytes: PDF file content
        model_answers_pdf_bytes: Optional (ignored)
    
    Returns:
        {"questions": [...], "metadata": {...}}
    """
    logger.info(f"[EXTRACTION][{test_id}] Starting extraction. PDF size: {len(pdf_bytes)/1024:.1f}KB")
    
    # Step 1: Extract text using Gemini 2.5 Flash (direct PDF input)
    try:
        pdf_text = await extract_text_from_pdf_via_openrouter(pdf_bytes, test_id)
        if len(pdf_text) < 50:
            raise Exception("Very little text extracted from PDF")
        logger.info(f"[EXTRACTION][{test_id}] Text extraction complete: {len(pdf_text)} chars")
    except Exception as e:
        logger.error(f"[EXTRACTION][{test_id}] Text extraction failed: {e}")
        raise Exception(f"Could not extract text from PDF: {e}")
    
    # Step 2: Parse extracted text into structured questions with proper types
    system_message = """You are an expert at extracting EVERY SINGLE question from educational question papers.
Your job is to extract ALL questions with COMPLETE text - do not summarize or skip anything.
Return ONLY valid JSON without markdown code blocks or explanations.
NEVER use trailing commas in JSON."""

    # Truncate if too long for context
    max_text_length = 20000
    if len(pdf_text) > max_text_length:
        pdf_text = pdf_text[:max_text_length] + "\n\n[Text truncated due to length...]"
        logger.warning(f"[EXTRACTION][{test_id}] Text truncated to {max_text_length} chars")

    prompt = f"""Extract EVERY question from this question paper. DO NOT skip or summarize any question.

QUESTION PAPER TEXT:
---
{pdf_text}
---

CRITICAL RULES - READ CAREFULLY:

1. EXTRACT EVERY INDIVIDUAL QUESTION - If a section has 8 questions, create 8 separate question objects
2. INCLUDE FULL QUESTION TEXT - Copy the exact question text, don't leave it empty
3. PASSAGES/POEMS - If questions are based on a passage or poem, include the FULL passage/poem text
4. SECTION INSTRUCTIONS - Include instructions like "Read the passage and answer" or "Match the following"
5. SUB-SECTIONS - If a question has parts A), B), C), extract each part's questions separately

QUESTION TYPES:
- "mcq" - Multiple choice with options a, b, c, d
- "short_answer" - 1-2 sentence answers  
- "long_answer" - Paragraph answers
- "fill_blanks" - Has blank spaces to fill (use ___ for blanks)
- "match_following" - Match two columns
- "synonyms" - Find word meanings
- "true_false" - True or False
- "grammar" - Grammar exercises

EXAMPLE - For a comprehension section like:
"QI. Read the passage and answer: [passage text]... 1. Where did it happen? 2. Why?"

Output should be:
{{
  "sections": [
    {{
      "section_id": "QI",
      "section_title": "Read the passage and answer the following questions",
      "section_instruction": "Read the passage and answer the following questions.",
      "passage": "[FULL passage text here - copy everything]",
      "questions": [
        {{
          "question_number": "1",
          "question_type": "short_answer",
          "question_text": "Where did it happen?",
          "marks": 1
        }},
        {{
          "question_number": "2", 
          "question_type": "short_answer",
          "question_text": "Why?",
          "marks": 1
        }}
      ]
    }}
  ]
}}

EXAMPLE - For match the following:
{{
  "section_id": "QII",
  "section_title": "Match the words with their meanings",
  "section_instruction": "Match the words with their meanings",
  "questions": [
    {{
      "question_number": "1",
      "question_type": "match_following",
      "question_text": "Match the words with their meanings",
      "left_column": ["Athletes", "Revive", "Tradition"],
      "right_column": ["People who compete in sports", "To bring back to life", "A custom passed down"],
      "correct_matches": {{"Athletes": "People who compete in sports", "Revive": "To bring back to life", "Tradition": "A custom passed down"}},
      "marks": 5
    }}
  ]
}}

EXAMPLE - For fill in blanks:
{{
  "question_number": "1",
  "question_type": "fill_blanks",
  "question_text": "Olympic Games → ___",
  "instruction": "Use adjectives to describe these nouns",
  "blanks_count": 1,
  "marks": 1
}}

NOW EXTRACT ALL QUESTIONS FROM THE PAPER ABOVE.
Return valid JSON with this structure:
{{
  "sections": [...all sections with their questions...],
  "metadata": {{
    "total_sections": <number>,
    "total_questions": <count all individual questions>,
    "has_comprehension": true/false
  }}
}}"""

    try:
        # Use higher max_tokens for detailed extraction
        response = await call_openrouter(prompt, system_message, max_tokens=8000)
        
        # Use robust JSON extraction (handles trailing commas, control chars, etc.)
        try:
            content = extract_json_robust(response)
            extracted_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"[EXTRACTION][{test_id}] JSON parse error: {e}")
            logger.error(f"[EXTRACTION][{test_id}] Raw content (first 500 chars): {response[:500]}")
            raise Exception(f"AI returned invalid JSON: {e}")
        
        # Validate and normalize structure (supports both old and new formats)
        extracted_data = normalize_extracted_data(extracted_data)
        
        # Count total questions across all sections
        total_questions = 0
        if 'sections' in extracted_data:
            for section in extracted_data['sections']:
                total_questions += len(section.get('questions', []))
        elif 'questions' in extracted_data:
            total_questions = len(extracted_data['questions'])
        
        if 'metadata' not in extracted_data:
            extracted_data['metadata'] = {}
        extracted_data['metadata']['total_questions'] = total_questions
        
        logger.info(f"[EXTRACTION][{test_id}] Success! Extracted {total_questions} questions")
        return extracted_data
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[EXTRACTION][{test_id}] Structured extraction error: {error_msg}")
        raise Exception(f"AI extraction failed: {error_msg}")


async def extract_text_from_pdf_with_gemini(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF for AI content generation.
    Uses google/gemini-2.5-flash via OpenRouter with direct PDF input.
    
    This function is called by the AI content generation endpoint.
    """
    logger.info(f"[TEXT_EXTRACT] Starting PDF text extraction. Size: {len(pdf_bytes)/1024:.1f}KB")
    text = await extract_text_from_pdf_via_openrouter(pdf_bytes, "content-gen")
    return text


def normalize_extracted_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize extracted data to ensure consistent structure.
    Handles both old format (flat questions) and new format (sections with questions).
    """
    if not data:
        return {"sections": [], "questions": [], "metadata": {"total_questions": 0}}
    
    # If already has sections, validate and return
    if 'sections' in data and isinstance(data['sections'], list):
        # Ensure each section has required fields
        for section in data['sections']:
            if 'questions' not in section:
                section['questions'] = []
            if 'section_id' not in section:
                section['section_id'] = 'default'
        
        # Also create flat questions list for backward compatibility
        all_questions = []
        for section in data['sections']:
            for q in section.get('questions', []):
                q['section_id'] = section.get('section_id', 'default')
                q['section_instruction'] = section.get('section_instruction', '')
                q['passage'] = section.get('passage', None)
                all_questions.append(q)
        data['questions'] = all_questions
        return data
    
    # Old format: convert flat questions to section-based
    if 'questions' in data and isinstance(data['questions'], list):
        questions = data['questions']
        # Group into a single default section
        data['sections'] = [{
            'section_id': 'Q1',
            'section_title': 'Questions',
            'section_instruction': None,
            'passage': None,
            'questions': questions
        }]
        return data
    
    # Empty structure
    return {"sections": [], "questions": [], "metadata": {"total_questions": 0}}


def validate_extracted_data(data: Dict[str, Any]) -> bool:
    """
    Validate extracted data structure (supports both old and new formats).
    Raises exception if validation fails.
    """
    if not data:
        raise Exception("Extracted data is empty")
    
    # New format validation
    if 'sections' in data:
        sections = data.get('sections', [])
        if not isinstance(sections, list):
            raise Exception("'sections' must be a list")
        
        total_questions = 0
        for section in sections:
            questions = section.get('questions', [])
            if not isinstance(questions, list):
                raise Exception("Section 'questions' must be a list")
            total_questions += len(questions)
        
        if total_questions == 0:
            raise Exception("No questions found in any section")
        return True
    
    # Old format validation (backward compatibility)
    if 'questions' not in data:
        raise Exception("Missing 'questions' or 'sections' field in extracted data")
    
    questions = data.get('questions', [])
    if not isinstance(questions, list):
        raise Exception("'questions' must be a list")
    
    if len(questions) == 0:
        raise Exception("No questions found")
    
    return True


def convert_to_legacy_format(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Convert extraction format to the format expected by the rest of the system.
    Preserves all new fields (question_type, options, passage, etc.) while maintaining compatibility.
    """
    legacy_questions = []
    
    # Handle section-based format
    if 'sections' in data:
        question_counter = 0
        for section in data['sections']:
            section_info = {
                'section_id': section.get('section_id', ''),
                'section_title': section.get('section_title', ''),
                'section_instruction': section.get('section_instruction', ''),
                'passage': section.get('passage', None)
            }
            
            for q in section.get('questions', []):
                question_counter += 1
                legacy_q = build_question_object(q, question_counter, section_info)
                legacy_questions.append(legacy_q)
        
        return legacy_questions
    
    # Handle flat questions format (backward compatibility)
    questions = data.get('questions', [])
    for i, q in enumerate(questions):
        legacy_q = build_question_object(q, i + 1, {})
        legacy_questions.append(legacy_q)
    
    return legacy_questions


def build_question_object(q: Dict[str, Any], index: int, section_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a standardized question object with all supported fields.
    """
    question_type = q.get('question_type', 'short_answer').lower()
    
    # Normalize question types
    type_mapping = {
        'mcq': 'mcq',
        'multiple_choice': 'mcq',
        'fill_blanks': 'fill_blanks',
        'fill_in_the_blanks': 'fill_blanks',
        'fill in the blanks': 'fill_blanks',
        'match_following': 'match_following',
        'match the following': 'match_following',
        'matching': 'match_following',
        'short_answer': 'short_answer',
        'short': 'short_answer',
        'long_answer': 'long_answer',
        'long': 'long_answer',
        'essay': 'long_answer',
        'comprehension': 'comprehension',
        'reading_comprehension': 'comprehension',
        'true_false': 'true_false',
        'true/false': 'true_false',
        'synonyms': 'synonyms',
        'synonym': 'synonyms',
        'meanings': 'synonyms',
        'grammar': 'grammar',
        'subjective': 'short_answer',
        'numerical': 'short_answer'
    }
    question_type = type_mapping.get(question_type, 'short_answer')
    
    legacy_q = {
        'question_number': q.get('question_number', str(index)),
        'question_text': q.get('question_text', ''),
        'question_type': question_type,
        'marks': q.get('marks', q.get('total_marks', 1)),
        'instruction': q.get('instruction', ''),
        
        # Section context
        'section_id': section_info.get('section_id', q.get('section_id', '')),
        'section_title': section_info.get('section_title', ''),
        'section_instruction': section_info.get('section_instruction', q.get('section_instruction', '')),
        'passage': section_info.get('passage', q.get('passage', None)),
        
        # MCQ specific
        'options': q.get('options', []),
        'correct_answer': q.get('correct_answer', ''),
        
        # Fill in blanks specific
        'blanks_count': q.get('blanks_count', 1),
        
        # Match the following specific
        'left_column': q.get('left_column', []),
        'right_column': q.get('right_column', []),
        'correct_matches': q.get('correct_matches', {}),
        
        # Answer/solution
        'expected_answer': q.get('expected_answer', q.get('model_answer', '')),
        'model_answer': q.get('model_answer', q.get('expected_answer', '')),
        
        # Sub-questions (for compound questions)
        'sub_questions': q.get('sub_questions', [])
    }
    
    return legacy_q


# Alias for backward compatibility
extract_with_gpt4o = extract_with_gemini
